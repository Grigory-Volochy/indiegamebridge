import logging
import time

from django.core.management.base import BaseCommand
from django.db import connection, transaction

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "One-shot backfill: recomputes Stream.genre_ids for every approved stream"
        " from the current Game.genres M2M state. Intended to run once after the"
        " 0006_stream_genre_ids migration; subsequent updates are handled per-chunk"
        " by enrich_igdb_games. Safe to re-run (idempotent)."
        "\n\n"
        "Processes streams in id-range batches, each in its own transaction. This"
        " keeps memory bounded and lock duration short on resource-constrained"
        " hosts (e.g. 1 vCPU VPS over a 1M+ row table). Use --start-id to resume"
        " from a specific id if a previous run was interrupted."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many approved streams would change without writing."
                " Same batched scan as the real run.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="Stream id range per batch. Default 5000. Smaller values reduce"
                " memory and lock pressure but add per-statement overhead.",
        )
        parser.add_argument(
            "--start-id",
            type=int,
            default=None,
            help="Skip ids below this value. Use to resume after a partial run."
                " Default: start from MIN(id) of approved streams.",
        )
        parser.add_argument(
            "--stop-id",
            type=int,
            default=None,
            help="Stop processing at this id (inclusive). Default: MAX(id) of"
                " approved streams.",
        )

    # The per-batch SQL. `%s` placeholders are (lo, hi, lo, hi) - lo/hi reused for
    # the COUNT/UPDATE driver and the inner subquery's predicate. The inner WHERE
    # has its own `s.id BETWEEN ...` so the join + group-by only touches one slice
    # of the table; without it Postgres would aggregate the full table per batch.
    _SUBQUERY_SQL = """
        SELECT s.id AS stream_id,
               array_agg(DISTINCT gg.host_genre_id ORDER BY gg.host_genre_id) AS ids
        FROM streams_stream s
        JOIN streams_game g ON g.host_game_id = ANY(s.host_game_ids)
        JOIN streams_game_genres link ON link.game_id = g.id
        JOIN streams_gamegenre gg ON gg.id = link.gamegenre_id
        WHERE s.status = 'approved'
          AND s.id BETWEEN %s AND %s
        GROUP BY s.id
    """

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        batch_size = options["batch_size"]
        start_id_arg = options.get("start_id")
        stop_id_arg = options.get("stop_id")

        if batch_size <= 0:
            self.stderr.write("--batch-size must be > 0.")
            return

        bounds = self._approved_id_bounds()
        if bounds is None:
            self.stdout.write("No approved streams to process.")
            return
        min_id, max_id = bounds

        lo = start_id_arg if start_id_arg is not None else min_id
        hi_limit = stop_id_arg if stop_id_arg is not None else max_id

        if lo > hi_limit:
            self.stdout.write(
                f"start-id ({lo}) > stop-id ({hi_limit}); nothing to do."
            )
            return

        self.stdout.write(
            f"{'DRY RUN ' if dry_run else ''}Backfilling Stream.genre_ids over"
            f" id range [{lo}, {hi_limit}] in batches of {batch_size}..."
        )

        total_changed = 0
        batches = 0
        started_at = time.monotonic()

        while lo <= hi_limit:
            hi = min(lo + batch_size - 1, hi_limit)
            changed = self._process_batch(lo, hi, dry_run=dry_run)
            total_changed += changed
            batches += 1

            elapsed = time.monotonic() - started_at
            self.stdout.write(
                f"  batch {batches:>4d} [{lo}..{hi}]:"
                f" {changed} {'would change' if dry_run else 'updated'}"
                f"  (total: {total_changed}; elapsed: {elapsed:.1f}s)"
            )
            lo = hi + 1

        msg = (
            f"DRY RUN: would update {total_changed} approved streams"
            f" across {batches} batches."
            if dry_run else
            f"Backfilled genre_ids for {total_changed} approved streams"
            f" across {batches} batches."
        )
        self.stdout.write(self.style.SUCCESS(msg))

    @staticmethod
    def _approved_id_bounds():
        with connection.cursor() as cur:
            cur.execute(
                "SELECT MIN(id), MAX(id) FROM streams_stream WHERE status = 'approved';"
            )
            min_id, max_id = cur.fetchone()
        if min_id is None:
            return None
        return min_id, max_id

    def _process_batch(self, lo, hi, dry_run):
        """One id-range batch, in its own transaction. Returns row count."""
        with transaction.atomic():
            with connection.cursor() as cur:
                if dry_run:
                    cur.execute(
                        f"""
                        SELECT COUNT(*)
                        FROM ({self._SUBQUERY_SQL}) sub
                        JOIN streams_stream s ON s.id = sub.stream_id
                        WHERE s.genre_ids IS DISTINCT FROM sub.ids;
                        """,
                        [lo, hi],
                    )
                    (count,) = cur.fetchone()
                    return count

                cur.execute(
                    f"""
                    UPDATE streams_stream s
                    SET genre_ids = sub.ids
                    FROM ({self._SUBQUERY_SQL}) sub
                    WHERE s.id = sub.stream_id
                      AND s.genre_ids IS DISTINCT FROM sub.ids;
                    """,
                    [lo, hi],
                )
                return cur.rowcount
