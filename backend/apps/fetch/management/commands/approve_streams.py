import logging

from django.core.management.base import BaseCommand

from apps.streams.models import Game, Stream

logger = logging.getLogger(__name__)


# Default cap on how many OFFLINE streams a single approve/delete pass touches.
# Each batch is its own SQL statement (one transaction); chosen to keep WAL
# size and lock duration bounded on the initial ~1M-row sweep. Steady-state
# runs after that will normally fit in a single batch.
_DEFAULT_BATCH_SIZE = 100_000


class Command(BaseCommand):
    help = (
        "Sweeps OFFLINE streams against the current Game categorization:\n"
        "  - approve: at least one host_game_id is `isgame`\n"
        "  - keep offline (second chance): no `isgame`, but at least one"
        "    host_game_id is still `new` (not yet categorized) - so the"
        "    next run can re-evaluate after categorize_games progresses\n"
        "  - delete: no `isgame` and no `new` - only `isnongame` ids or"
        "    ids unknown to the Game table\n"
        "Run after `categorize_games`. Short-circuits if no Game has been"
        " classified as `isgame` yet (avoids deleting everything before"
        " categorization has produced any positives)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report would-approve / would-delete / would-keep counts without"
                " modifying anything.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=_DEFAULT_BATCH_SIZE,
            help=f"Maximum streams processed per UPDATE/DELETE statement."
                f" Default: {_DEFAULT_BATCH_SIZE}. Lower values reduce lock duration"
                f" and WAL pressure at the cost of more round-trips.",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        batch_size = options.get("batch_size") or _DEFAULT_BATCH_SIZE

        isgame_ids = list(
            Game.objects.filter(category=Game.Category.ISGAME)
            .values_list("host_game_id", flat=True)
        )
        if not isgame_ids:
            self.stdout.write("No `isgame` games. Nothing to approve.")
            return

        new_ids = list(
            Game.objects.filter(category=Game.Category.NEW)
            .values_list("host_game_id", flat=True)
        )

        offline = Stream.objects.filter(status=Stream.Status.OFFLINE)

        to_approve = offline.filter(host_game_ids__overlap=isgame_ids)

        # "Second chance": keep OFFLINE if no isgame overlap but at least one
        # `new` id - re-evaluated on the next run after more categorization.
        to_delete = (
            offline.exclude(host_game_ids__overlap=isgame_ids)
                   .exclude(host_game_ids__overlap=new_ids)
        )

        if dry_run:
            approve_count = to_approve.count()
            delete_count = to_delete.count()
            offline_count = offline.count()
            keep_count = offline_count - approve_count - delete_count
            self.stdout.write(self.style.NOTICE(
                f"DRY RUN over {offline_count} offline streams:\n"
                f"  would approve: {approve_count}\n"
                f"  would delete:  {delete_count}\n"
                f"  would keep:    {keep_count} (only `new` overlap - retried next run)\n"
                f"  ({len(isgame_ids)} games isgame, {len(new_ids)} games new.)"
            ))
            return

        approved_count = self._batched_update(
            to_approve,
            batch_size=batch_size,
            update_fields={"status": Stream.Status.APPROVED},
        )
        deleted_count = self._batched_delete(to_delete, batch_size=batch_size)

        self.stdout.write(self.style.SUCCESS(
            f"Approved {approved_count} streams, deleted {deleted_count} streams."
            f" ({len(isgame_ids)} games isgame, {len(new_ids)} games new.)"
        ))

    @staticmethod
    def _batched_update(qs, batch_size, update_fields):
        """Drains `qs` in batches of `batch_size`, applying `update_fields` to
        each batch in its own statement. Returns the total number of rows
        updated across all batches."""
        total = 0
        while True:
            batch_ids = list(qs.values_list("id", flat=True)[:batch_size])
            if not batch_ids:
                break
            total += Stream.objects.filter(id__in=batch_ids).update(**update_fields)
        return total

    @staticmethod
    def _batched_delete(qs, batch_size):
        """Drains `qs` in batches of `batch_size`, issuing a DELETE per batch.
        Returns the total number of Stream rows deleted across all batches."""
        total = 0
        while True:
            batch_ids = list(qs.values_list("id", flat=True)[:batch_size])
            if not batch_ids:
                break
            deleted, _ = Stream.objects.filter(id__in=batch_ids).delete()
            total += deleted
        return total
