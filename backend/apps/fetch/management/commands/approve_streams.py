import logging

from django.core.management.base import BaseCommand
from django.db.models import BigIntegerField, Exists, Lookup, OuterRef

from apps.streams.models import Game, Stream

logger = logging.getLogger(__name__)


@BigIntegerField.register_lookup
class _MemberOf(Lookup):
    # Postgres `lhs = ANY(rhs_array)`. Lets the planner use the unique index
    # on Game.host_game_id when joining against Stream.host_game_ids, instead
    # of materializing a multi-MB ARRAY[...] literal of every categorized id.
    # Emitted directly (no outer parens) because `= ANY(...)` is a quantified
    # comparison, not a value expression.
    lookup_name = "memberof"

    def as_sql(self, compiler, connection):
        lhs_sql, lhs_params = self.process_lhs(compiler, connection)
        rhs_sql, rhs_params = self.process_rhs(compiler, connection)
        return f"{lhs_sql} = ANY({rhs_sql})", (*lhs_params, *rhs_params)


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

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)

        if not Game.objects.filter(category=Game.Category.ISGAME).exists():
            self.stdout.write("No `isgame` games. Nothing to approve.")
            return

        offline = Stream.objects.filter(status=Stream.Status.OFFLINE)

        # EXISTS against Game by host_game_id (its unique index) avoids
        # materializing every isgame/new id as an ARRAY[...] literal -
        # which previously made the DELETE seq-scan offline streams while
        # comparing each row's array against a million-element array on
        # every batch.
        has_isgame = Exists(
            Game.objects.filter(
                category=Game.Category.ISGAME,
                host_game_id__memberof=OuterRef("host_game_ids"),
            )
        )
        has_isgame_or_new = Exists(
            Game.objects.filter(
                category__in=[Game.Category.ISGAME, Game.Category.NEW],
                host_game_id__memberof=OuterRef("host_game_ids"),
            )
        )

        to_approve = offline.filter(has_isgame)
        to_delete = offline.filter(~has_isgame_or_new)

        if dry_run:
            approve_count = to_approve.count()
            delete_count = to_delete.count()
            offline_count = offline.count()
            keep_count = offline_count - approve_count - delete_count
            self.stdout.write(self.style.NOTICE(
                f"DRY RUN over {offline_count} offline streams:\n"
                f"  would approve: {approve_count}\n"
                f"  would delete:  {delete_count}\n"
                f"  would keep:    {keep_count} (only `new` overlap - retried next run)"
            ))
            return

        approved_count = to_approve.update(status=Stream.Status.APPROVED)
        deleted_count, _ = to_delete.delete()

        self.stdout.write(self.style.SUCCESS(
            f"Approved {approved_count} streams, deleted {deleted_count} streams."
        ))
