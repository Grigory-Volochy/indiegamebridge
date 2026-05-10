import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.utils.twitch_api_client import TwitchApiClient
from apps.streams.models import Game

logger = logging.getLogger(__name__)

# Helix `/helix/games` accepts up to 100 ids per request.
_HELIX_BATCH_SIZE = 100


class Command(BaseCommand):
    help = (
        "Categorizes placeholder Game rows by calling Helix `/games`."
        " Sets each row's `category` to either ISGAME (when Helix returns a"
        " non-empty igdb_id) or ISNONGAME (when igdb_id is empty - e.g."
        " 'Just Chatting'), and stores Helix's `name` into `host_name`."
        " Rows where Helix returns nothing stay `category='new'` and are"
        " retried on the next run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of `new` games to process this run."
                " Default: drain everything categorized as `new`.",
        )

    def handle(self, *args, **options):
        limit = options.get("limit")

        new_qs = Game.objects.filter(category=Game.Category.NEW).order_by("id")
        if limit:
            new_qs = new_qs[:limit]

        new_games = list(new_qs)
        if not new_games:
            self.stdout.write("No `new` games to categorize.")
            return

        self.stdout.write(f"Categorizing {len(new_games)} games via Helix...")

        try:
            with TwitchApiClient() as client:
                processed = 0
                for chunk in self._chunked(new_games, _HELIX_BATCH_SIZE):
                    self._categorize_chunk(client, chunk)
                    processed += len(chunk)
                    self.stdout.write(f"  ...processed {processed}/{len(new_games)}")
        except Exception as e:
            raise CommandError(f"Categorization failed: {e}")

        self.stdout.write(self.style.SUCCESS(f"Categorization finished. Processed: {processed}"))

    @staticmethod
    def _chunked(seq, n):
        for i in range(0, len(seq), n):
            yield seq[i:i + n]

    def _categorize_chunk(self, client, chunk):
        chunk_ids = [g.host_game_id for g in chunk]
        response = client.get_games_by_ids(chunk_ids)
        # Helix returns ids as strings; convert for dict lookup against our BIGINTs.
        response_by_id = {}
        for item in response:
            try:
                response_by_id[int(item["id"])] = item
            except (TypeError, ValueError, KeyError):
                continue

        to_update = []
        for game in chunk:
            payload = response_by_id.get(game.host_game_id)
            if not payload:
                # Helix has no row for this id; stays `new` and gets retried.
                continue

            game.host_name = (payload.get("name") or "")[:255]

            igdb_id_raw = payload.get("igdb_id") or ""
            if igdb_id_raw:
                try:
                    game.igdb_game_id = int(igdb_id_raw)
                except (TypeError, ValueError):
                    # Unexpected igdb_id shape - leave as `new` for retry.
                    continue
                game.category = Game.Category.ISGAME
            else:
                game.category = Game.Category.ISNONGAME

            to_update.append(game)

        if to_update:
            with transaction.atomic():
                Game.objects.bulk_update(
                    to_update,
                    ["category", "igdb_game_id", "host_name"],
                    batch_size=500,
                )
