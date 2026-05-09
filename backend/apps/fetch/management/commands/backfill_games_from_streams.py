import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.streams.models import Stream, Game

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "One-shot backfill: ensures a placeholder Game row exists for every game id"
        " observed across already-stored OFFLINE streams. Intended to run once after"
        " introducing the Game model; subsequent inserts are handled by the stream"
        " finalization path."
    )

    def handle(self, *args, **options):
        offline_qs = (
            Stream.objects.filter(status=Stream.Status.OFFLINE)
            .only("host_game_ids")
        )

        observed_ids = set()
        scanned = 0
        for stream in offline_qs.iterator(chunk_size=2000):
            scanned += 1
            observed_ids.update(stream.host_game_ids or [])

        self.stdout.write(f"Scanned {scanned} offline streams; {len(observed_ids)} unique game ids observed.")

        if not observed_ids:
            return

        existing_ids = set(
            Game.objects.filter(host_game_id__in=observed_ids).values_list("host_game_id", flat=True)
        )
        missing_ids = observed_ids - existing_ids

        if not missing_ids:
            self.stdout.write("All observed game ids already have rows. Nothing to insert.")
            return

        with transaction.atomic():
            Game.objects.bulk_create(
                [Game(host_game_id=gid) for gid in sorted(missing_ids)],
                batch_size=500,
                ignore_conflicts=True,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Inserted {len(missing_ids)} placeholder Game rows."
                f" {len(existing_ids)} were already present."
            )
        )
