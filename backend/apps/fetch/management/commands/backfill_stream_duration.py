import logging
import time

from django.core.management.base import BaseCommand
from django.db.models.expressions import RawSQL

from apps.streams.models import Stream

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "One-shot backfill: populates `duration` for already-finalized streams"
        " (OFFLINE and APPROVED) created before the field existed. Computes"
        " duration as EXTRACT(EPOCH FROM (finished_at - started_at)), clamped"
        " to >= 0 to absorb any data rows where finished_at slipped behind"
        " started_at. Runs in batches with a short pause between, so it does"
        " not block live writes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size", type=int, default=10_000,
            help="Rows updated per batch (default: 10000).",
        )
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Cap on total rows processed this run (default: drain everything).",
        )
        parser.add_argument(
            "--sleep", type=float, default=0.5,
            help="Seconds to pause between batches (default: 0.5).",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        limit = options.get("limit")
        sleep_seconds = options["sleep"]

        qs = Stream.objects.filter(
            status__in=[Stream.Status.OFFLINE, Stream.Status.APPROVED],
            duration=0,
        )

        remaining = qs.count()
        target = min(remaining, limit) if limit else remaining
        if target == 0:
            self.stdout.write("Nothing to backfill.")
            return

        self.stdout.write(
            f"Backfilling duration for {target} streams"
            f" (batch={batch_size}, sleep={sleep_seconds}s)..."
        )

        processed = 0
        while processed < target:
            chunk_cap = min(batch_size, target - processed)
            # Each iteration re-queries duration=0, so the previous batch's
            # rows fall out of the result set automatically.
            ids = list(qs.values_list("id", flat=True)[:chunk_cap])
            if not ids:
                break

            updated = Stream.objects.filter(id__in=ids).update(
                duration=RawSQL(
                    "GREATEST(EXTRACT(EPOCH FROM (finished_at - started_at))::INT, 0)",
                    [],
                )
            )
            processed += updated
            self.stdout.write(f"  ...processed {processed}/{target}")

            if sleep_seconds > 0 and processed < target:
                time.sleep(sleep_seconds)

        self.stdout.write(self.style.SUCCESS(f"Backfill complete. Processed {processed}."))
