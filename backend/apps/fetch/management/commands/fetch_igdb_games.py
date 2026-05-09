import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.utils.igdb_api_client import IgdbApiClient
from apps.streams.models import Game, GameGenre

logger = logging.getLogger(__name__)

# IGDB caps `where id = (...)` lists at 500 entries per request.
_IGDB_BATCH_SIZE = 500


class Command(BaseCommand):
    help = (
        "Enriches placeholder Game rows with IGDB metadata. A Game is treated as"
        " unenriched if its `genres` M2M is empty - placeholders are inserted by"
        " the stream-finalization path with no genres until this command runs."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of unenriched games to process this run."
                " Default: drain all unenriched games.",
        )

    def handle(self, *args, **options):
        limit = options.get("limit")

        unenriched_qs = (
            Game.objects.filter(genres__isnull=True).order_by("id")
        )
        if limit:
            unenriched_qs = unenriched_qs[:limit]

        unenriched = list(unenriched_qs)
        if not unenriched:
            self.stdout.write("No unenriched games to process.")
            return

        self.stdout.write(f"Enriching {len(unenriched)} games...")

        # Cache existing genres in process memory so per-game genre lookups
        # during enrichment hit the dict rather than the database.
        genres_by_host_id = {g.host_genre_id: g for g in GameGenre.objects.all()}

        try:
            with IgdbApiClient() as client:
                processed = 0
                for chunk in self._chunked(unenriched, _IGDB_BATCH_SIZE):
                    self._enrich_chunk(client, chunk, genres_by_host_id)
                    processed += len(chunk)
                    self.stdout.write(f"  ...processed {processed}/{len(unenriched)}")
        except Exception as e:
            raise CommandError(f"Enrichment failed: {e}")

        self.stdout.write(self.style.SUCCESS(f"Enrichment finished. Processed: {processed}"))

    @staticmethod
    def _chunked(seq, n):
        for i in range(0, len(seq), n):
            yield seq[i:i + n]

    def _enrich_chunk(self, client, chunk, genres_by_host_id):
        chunk_ids = [g.host_game_id for g in chunk]
        response = client.get_games_by_ids(chunk_ids)
        response_by_id = {item["id"]: item for item in response}

        # If the response references any genre id we haven't stored yet, refresh
        # the genre table once for the whole chunk before linking.
        unknown_genre_ids = {
            gid
            for item in response
            for gid in item.get("genres", [])
            if gid not in genres_by_host_id
        }
        if unknown_genre_ids:
            self._refresh_genres(client, genres_by_host_id)

        games_to_update = []
        through_links = []
        through_model = Game.genres.through

        for game in chunk:
            payload = response_by_id.get(game.host_game_id)
            if not payload:
                # IGDB has no record for this id; row stays unenriched and will be
                # retried on the next run. Acceptable for now.
                continue
            game.host_name = (payload.get("name") or "")[:255]
            game.host_summary = payload.get("summary") or ""
            game.host_url = (payload.get("url") or "")[:1024]
            games_to_update.append(game)

            for gid in payload.get("genres") or []:
                genre = genres_by_host_id.get(gid)
                if genre is not None:
                    through_links.append(through_model(game_id=game.id, gamegenre_id=genre.id))

        with transaction.atomic():
            if games_to_update:
                Game.objects.bulk_update(
                    games_to_update,
                    ["host_name", "host_summary", "host_url"],
                    batch_size=500,
                )
            if through_links:
                through_model.objects.bulk_create(
                    through_links,
                    batch_size=1000,
                    ignore_conflicts=True,
                )

    def _refresh_genres(self, client, genres_by_host_id):
        """Pulls the full genre list from IGDB and inserts any new rows.

        Mutates `genres_by_host_id` in place so the caller picks up the new rows.
        """
        all_genres = client.get_genres(limit=500)
        new_rows = [
            GameGenre(
                host_genre_id=item["id"],
                host_name=(item.get("name") or "")[:64],
                slug=(item.get("slug") or "")[:64],
                host_url=(item.get("url") or "")[:1024],
            )
            for item in all_genres
            if item["id"] not in genres_by_host_id
        ]
        if new_rows:
            GameGenre.objects.bulk_create(new_rows, ignore_conflicts=True)
            inserted_ids = [r.host_genre_id for r in new_rows]
            for genre in GameGenre.objects.filter(host_genre_id__in=inserted_ids):
                genres_by_host_id[genre.host_genre_id] = genre
