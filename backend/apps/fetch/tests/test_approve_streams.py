"""Tests for the approve_streams management command.

After categorize_games has classified known game ids as `isgame`/`isnongame`,
this command sweeps OFFLINE streams: those that observed at least one
`isgame` game id are promoted to APPROVED; those that observed only non-game
categories (or ids never categorized) are deleted.

LIVE and already-APPROVED streams must be untouched.
"""

from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.streams.models import Game, Stream, StreamerProfile


class ApproveStreamsTests(TestCase):
    def setUp(self):
        self.profile = StreamerProfile.objects.create(
            host=StreamerProfile.Host.TWITCH,
            host_user_id=2001,
            host_login="loginx",
            host_display_name="DisplayName",
        )

    def _make_stream(self, host_stream_id, status, host_game_ids):
        return Stream.objects.create(
            streamer_profile=self.profile,
            host_stream_id=host_stream_id,
            status=status,
            language="en",
            started_at=datetime(2025, 1, 1, tzinfo=dt_timezone.utc),
            finished_at=timezone.now() - timedelta(days=1),
            snapshots=[],
            host_game_ids=host_game_ids,
        )

    def _make_isgame(self, host_game_id, igdb_game_id=None):
        return Game.objects.create(
            host_game_id=host_game_id,
            igdb_game_id=igdb_game_id or (host_game_id + 1000),
            category=Game.Category.ISGAME,
        )

    def _make_isnongame(self, host_game_id):
        return Game.objects.create(
            host_game_id=host_game_id,
            category=Game.Category.ISNONGAME,
        )

    def test_offline_stream_with_isgame_is_promoted_to_approved(self):
        self._make_isgame(host_game_id=100)
        stream = self._make_stream(1, Stream.Status.OFFLINE, [100, 200])

        call_command("approve_streams", stdout=mock.Mock())

        stream.refresh_from_db()
        self.assertEqual(stream.status, Stream.Status.APPROVED)

    def test_offline_stream_with_only_non_game_ids_is_deleted(self):
        """A stream whose host_game_ids contains only ids that aren't `isgame`
        (whether `isnongame`, `new`, or absent from Game entirely) is junk
        and must be deleted."""
        self._make_isgame(host_game_id=100)
        self._make_isnongame(host_game_id=509658)
        junk = self._make_stream(1, Stream.Status.OFFLINE, [509658])

        call_command("approve_streams", stdout=mock.Mock())

        self.assertFalse(Stream.objects.filter(pk=junk.pk).exists())

    def test_offline_stream_with_only_new_ids_is_kept_for_second_chance(self):
        """A stream whose host_game_ids contains only `new` (not yet
        categorized) ids must NOT be deleted. The categorize_games run that
        produced the current sweep may have missed those ids transiently;
        they get a second chance on the next run."""
        self._make_isgame(host_game_id=100)
        Game.objects.create(host_game_id=200)  # default category=NEW
        pending = self._make_stream(1, Stream.Status.OFFLINE, [200])

        call_command("approve_streams", stdout=mock.Mock())

        pending.refresh_from_db()
        self.assertEqual(pending.status, Stream.Status.OFFLINE)

    def test_offline_stream_with_mix_of_new_and_isnongame_is_kept(self):
        """Even one `new` id is enough to earn the second chance."""
        self._make_isgame(host_game_id=100)
        Game.objects.create(host_game_id=200)  # default NEW
        self._make_isnongame(host_game_id=509658)
        pending = self._make_stream(1, Stream.Status.OFFLINE, [200, 509658])

        call_command("approve_streams", stdout=mock.Mock())

        pending.refresh_from_db()
        self.assertEqual(pending.status, Stream.Status.OFFLINE)

    def test_offline_stream_with_ids_unknown_to_game_table_is_deleted(self):
        """Ids that aren't represented in the Game table at all (so neither
        isgame nor new nor isnongame) are treated as junk - they have no
        path to ever become approvable."""
        self._make_isgame(host_game_id=100)
        # No Game row exists for host_game_id=200.
        junk = self._make_stream(1, Stream.Status.OFFLINE, [200])

        call_command("approve_streams", stdout=mock.Mock())

        self.assertFalse(Stream.objects.filter(pk=junk.pk).exists())

    def test_mix_of_isgame_and_other_ids_is_approved(self):
        """A stream that observed at least one `isgame` id is approved even
        if it also observed non-game categories alongside."""
        self._make_isgame(host_game_id=100)
        self._make_isnongame(host_game_id=509658)
        mixed = self._make_stream(1, Stream.Status.OFFLINE, [509658, 100])

        call_command("approve_streams", stdout=mock.Mock())

        mixed.refresh_from_db()
        self.assertEqual(mixed.status, Stream.Status.APPROVED)

    def test_live_streams_are_untouched(self):
        """Live streams haven't finalized host_game_ids yet; they must not
        be touched by approve_streams."""
        self._make_isgame(host_game_id=100)
        live = self._make_stream(1, Stream.Status.LIVE, [100])

        call_command("approve_streams", stdout=mock.Mock())

        live.refresh_from_db()
        self.assertEqual(live.status, Stream.Status.LIVE)

    def test_already_approved_streams_are_untouched(self):
        self._make_isgame(host_game_id=100)
        approved = self._make_stream(1, Stream.Status.APPROVED, [100])

        call_command("approve_streams", stdout=mock.Mock())

        # Still exists, status unchanged.
        approved.refresh_from_db()
        self.assertEqual(approved.status, Stream.Status.APPROVED)

    def test_no_isgame_games_short_circuits_without_changes(self):
        """If no Games are categorized as `isgame` yet, nothing should be
        deleted or approved (otherwise we'd nuke every offline stream)."""
        offline = self._make_stream(1, Stream.Status.OFFLINE, [100])

        call_command("approve_streams", stdout=mock.Mock())

        offline.refresh_from_db()
        self.assertEqual(offline.status, Stream.Status.OFFLINE)

    def test_dry_run_does_not_modify_anything(self):
        self._make_isgame(host_game_id=100)
        approved_candidate = self._make_stream(1, Stream.Status.OFFLINE, [100])
        delete_candidate = self._make_stream(2, Stream.Status.OFFLINE, [999])

        call_command("approve_streams", "--dry-run", stdout=mock.Mock())

        approved_candidate.refresh_from_db()
        self.assertEqual(approved_candidate.status, Stream.Status.OFFLINE)
        self.assertTrue(Stream.objects.filter(pk=delete_candidate.pk).exists())

    def test_full_run_handles_mixed_population(self):
        """End-to-end shape: in one run, some streams get deleted, some
        approved, some kept (second chance), some left alone."""
        self._make_isgame(host_game_id=100)
        self._make_isnongame(host_game_id=509658)
        Game.objects.create(host_game_id=200)  # NEW (uncategorized yet)

        approve_me = self._make_stream(1, Stream.Status.OFFLINE, [100, 509658])
        delete_me = self._make_stream(2, Stream.Status.OFFLINE, [509658])
        keep_me = self._make_stream(3, Stream.Status.OFFLINE, [200])
        leave_alone_live = self._make_stream(4, Stream.Status.LIVE, [100])

        call_command("approve_streams", stdout=mock.Mock())

        approve_me.refresh_from_db()
        self.assertEqual(approve_me.status, Stream.Status.APPROVED)
        self.assertFalse(Stream.objects.filter(pk=delete_me.pk).exists())
        keep_me.refresh_from_db()
        self.assertEqual(keep_me.status, Stream.Status.OFFLINE)
        leave_alone_live.refresh_from_db()
        self.assertEqual(leave_alone_live.status, Stream.Status.LIVE)

    def test_batch_size_processes_all_rows_across_multiple_batches(self):
        """`--batch-size 1` must still process every eligible row, just in
        separate statements. Smoke test for the batched update/delete loops."""
        self._make_isgame(host_game_id=100)
        self._make_isnongame(host_game_id=509658)

        approve_streams = [
            self._make_stream(i, Stream.Status.OFFLINE, [100])
            for i in range(1, 4)  # 3 streams to approve
        ]
        delete_streams = [
            self._make_stream(i, Stream.Status.OFFLINE, [509658])
            for i in range(10, 13)  # 3 streams to delete
        ]

        call_command("approve_streams", "--batch-size", "1", stdout=mock.Mock())

        for stream in approve_streams:
            stream.refresh_from_db()
            self.assertEqual(stream.status, Stream.Status.APPROVED)
        for stream in delete_streams:
            self.assertFalse(Stream.objects.filter(pk=stream.pk).exists())
