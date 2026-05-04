"""Tests for the fetch_twitch_streams management command.

The persistence loop in `_poll_streams_by_lang` is the highest-value thing to
test — it has real branching (get_or_create vs update, profile mismatch update,
dedup, snapshot append) and any regression silently corrupts data.
`_finalize_offline_streams` is exercised directly: stale streams must end up
OFFLINE with `max_viewers` and `host_game_ids` derived from `snapshots`, and streams
with too little data must be dropped.
"""

from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.fetch.management.commands.fetch_twitch_streams import Command
from apps.streams.models import Stream, StreamerProfile
from core.utils.twitch_api_client import StreamTuple


def _make_stream_tuple(**overrides):
    """Build a StreamTuple with all fields populated. IDs are numeric (int) post-boundary."""
    defaults = {
        "status": "live",
        "host_stream_id": 1001,
        "host_user_id": 2001,
        "host_login": "loginx",
        "host_display_name": "DisplayName",
        "host_game_id": 3001,
        "viewers": 100,
        "started_at": "2025-01-01T00:00:00Z",
    }
    defaults.update(overrides)
    return StreamTuple(**defaults)


def _build_command():
    cmd = Command()
    cmd.allowed_requests_per_language_poll_round = 1
    cmd.min_time_per_poll_round = 0
    cmd.stdout = mock.Mock()
    cmd.stderr = mock.Mock()
    return cmd


def _patch_iter_streams(*responses):
    """Patch TwitchApiClient so iter_streams returns the given responses in order.

    Each `response` is a tuple `(streams, cursor)`. After the list is exhausted,
    returns `([], None)` so the polling loop terminates cleanly.

    Returns the patcher context manager.
    """
    side_effect = list(responses) + [([], None)]
    patcher = mock.patch(
        "apps.fetch.management.commands.fetch_twitch_streams.TwitchApiClient"
    )
    mock_cls = patcher.start()
    instance = mock_cls.return_value
    instance.__enter__.return_value = instance
    instance.__exit__.return_value = False
    instance.iter_streams.side_effect = side_effect
    return patcher, instance


class PollStreamsByLangPersistenceTests(TestCase):
    def setUp(self):
        self.command = _build_command()

    def _run(self, *responses):
        patcher, _ = _patch_iter_streams(*responses)
        try:
            self.command._poll_streams_by_lang(
                the_language="en", end_time_anchor=10**12
            )
        finally:
            patcher.stop()

    def test_creates_profile_and_stream_with_first_snapshot(self):
        st = _make_stream_tuple()
        self._run(([st], None))

        profile = StreamerProfile.objects.get(host_user_id=2001)
        self.assertEqual(profile.host, StreamerProfile.Host.TWITCH)
        self.assertEqual(profile.host_login, "loginx")
        self.assertEqual(profile.host_display_name, "DisplayName")

        stream = Stream.objects.get(host_stream_id=1001)
        self.assertEqual(stream.streamer_profile_id, profile.id)
        self.assertEqual(stream.status, Stream.Status.LIVE)
        self.assertEqual(stream.language, "en")

        self.assertEqual(len(stream.snapshots), 1)
        snap = stream.snapshots[0]
        self.assertEqual(snap["g"], 3001)
        self.assertEqual(snap["v"], 100)
        # The shared per-round timestamp is an int unix time; just sanity-check it.
        self.assertIsInstance(snap["t"], int)

    def test_existing_profile_with_changed_login_is_updated(self):
        StreamerProfile.objects.create(
            host=StreamerProfile.Host.TWITCH,
            host_user_id=2001,
            host_login="oldlogin",
            host_display_name="OldName",
        )

        st = _make_stream_tuple(host_login="newlogin", host_display_name="NewName")
        self._run(([st], None))

        profile = StreamerProfile.objects.get(host_user_id=2001)
        self.assertEqual(profile.host_login, "newlogin")
        self.assertEqual(profile.host_display_name, "NewName")
        self.assertEqual(StreamerProfile.objects.count(), 1)

    def test_existing_profile_unchanged_is_not_resaved(self):
        """If login/display_name match, no UPDATE should fire (avoids unnecessary writes)."""
        StreamerProfile.objects.create(
            host=StreamerProfile.Host.TWITCH,
            host_user_id=2001,
            host_login="loginx",
            host_display_name="DisplayName",
        )
        before = StreamerProfile.objects.get(host_user_id=2001).updated_at

        st = _make_stream_tuple()
        self._run(([st], None))

        after = StreamerProfile.objects.get(host_user_id=2001).updated_at
        self.assertEqual(before, after)

    def test_dedup_within_poll_creates_one_set_of_rows(self):
        """Same host_stream_id appearing twice within a poll should yield one snapshot."""
        st = _make_stream_tuple()
        self._run(([st, st], None))

        self.assertEqual(StreamerProfile.objects.count(), 1)
        self.assertEqual(Stream.objects.count(), 1)
        self.assertEqual(len(Stream.objects.get().snapshots), 1)

    def test_existing_stream_finished_at_is_refreshed(self):
        profile = StreamerProfile.objects.create(
            host=StreamerProfile.Host.TWITCH,
            host_user_id=2001,
            host_login="loginx",
            host_display_name="DisplayName",
        )
        old_finished_at = timezone.now() - timedelta(hours=1)
        stream = Stream.objects.create(
            streamer_profile=profile,
            host_stream_id=1001,
            status=Stream.Status.LIVE,
            language="en",
            started_at=datetime(2025, 1, 1, tzinfo=dt_timezone.utc),
            finished_at=old_finished_at,
            snapshots=[],
        )

        st = _make_stream_tuple()
        self._run(([st], None))

        stream.refresh_from_db()
        self.assertEqual(stream.status, Stream.Status.LIVE)
        self.assertGreater(stream.finished_at, old_finished_at)
        self.assertEqual(Stream.objects.count(), 1)

    def test_each_poll_appends_a_snapshot_to_existing_stream(self):
        st = _make_stream_tuple()
        self._run(([st], None))
        self._run(([st], None))

        self.assertEqual(Stream.objects.count(), 1)
        self.assertEqual(len(Stream.objects.get().snapshots), 2)


class FinalizeOfflineStreamsTests(TestCase):
    """`_finalize_offline_streams` flips stale LIVE streams to OFFLINE, computing
    `max_viewers` and `host_game_ids` from each stream's `snapshots`. Streams that
    accumulated <= 1 snapshot are dropped entirely."""

    THRESHOLD_MINUTES = 100

    def setUp(self):
        self.command = _build_command()
        self.profile = StreamerProfile.objects.create(
            host=StreamerProfile.Host.TWITCH,
            host_user_id=2001,
            host_login="loginx",
            host_display_name="DisplayName",
        )

    def _make_stream(self, host_stream_id, status, finished_at, snapshots=None):
        return Stream.objects.create(
            streamer_profile=self.profile,
            host_stream_id=host_stream_id,
            status=status,
            language="en",
            started_at=datetime(2025, 1, 1, tzinfo=dt_timezone.utc),
            finished_at=finished_at,
            snapshots=snapshots or [],
        )

    def _run_finalize(self):
        threshold = timezone.now() - timedelta(minutes=self.THRESHOLD_MINUTES)
        return self.command._finalize_offline_streams(threshold)

    def test_stale_live_stream_is_finalized_with_summary_fields(self):
        stale = self._make_stream(
            host_stream_id=1,
            status=Stream.Status.LIVE,
            finished_at=timezone.now() - timedelta(minutes=self.THRESHOLD_MINUTES + 1),
            snapshots=[
                {"g": 100, "v": 80,  "t": 1700000000},
                {"g": 100, "v": 120, "t": 1700000900},
                {"g": 200, "v": 50,  "t": 1700001800},
            ],
        )

        finalized, deleted = self._run_finalize()

        stale.refresh_from_db()
        self.assertEqual((finalized, deleted), (1, 0))
        self.assertEqual(stale.status, Stream.Status.OFFLINE)
        self.assertEqual(stale.max_viewers, 120)
        self.assertEqual(stale.host_game_ids, [100, 200])

    def test_fresh_live_stream_is_left_alone(self):
        fresh = self._make_stream(
            host_stream_id=2,
            status=Stream.Status.LIVE,
            finished_at=timezone.now(),
            snapshots=[
                {"g": 100, "v": 80, "t": 1700000000},
                {"g": 100, "v": 90, "t": 1700000900},
            ],
        )

        finalized, deleted = self._run_finalize()

        fresh.refresh_from_db()
        self.assertEqual((finalized, deleted), (0, 0))
        self.assertEqual(fresh.status, Stream.Status.LIVE)
        self.assertEqual(fresh.max_viewers, 0)
        self.assertEqual(fresh.host_game_ids, [])

    def test_already_offline_stream_is_untouched(self):
        old_offline = self._make_stream(
            host_stream_id=3,
            status=Stream.Status.OFFLINE,
            finished_at=timezone.now() - timedelta(days=7),
            snapshots=[],
        )

        finalized, deleted = self._run_finalize()

        old_offline.refresh_from_db()
        self.assertEqual((finalized, deleted), (0, 0))
        self.assertEqual(old_offline.status, Stream.Status.OFFLINE)

    def test_finished_at_is_preserved(self):
        """finished_at represents the actual end time and must stay frozen at finalize."""
        stale = self._make_stream(
            host_stream_id=4,
            status=Stream.Status.LIVE,
            finished_at=timezone.now() - timedelta(minutes=self.THRESHOLD_MINUTES + 1),
            snapshots=[
                {"g": 100, "v": 50, "t": 1700000000},
                {"g": 100, "v": 60, "t": 1700000900},
            ],
        )
        original_finished_at = stale.finished_at

        self._run_finalize()

        stale.refresh_from_db()
        self.assertEqual(stale.status, Stream.Status.OFFLINE)
        self.assertEqual(stale.finished_at, original_finished_at)

    def test_stream_with_single_snapshot_is_deleted(self):
        single = self._make_stream(
            host_stream_id=5,
            status=Stream.Status.LIVE,
            finished_at=timezone.now() - timedelta(minutes=self.THRESHOLD_MINUTES + 1),
            snapshots=[{"g": 100, "v": 50, "t": 1700000000}],
        )

        finalized, deleted = self._run_finalize()

        self.assertEqual((finalized, deleted), (0, 1))
        self.assertFalse(Stream.objects.filter(pk=single.pk).exists())

    def test_stream_with_zero_snapshots_is_deleted(self):
        empty = self._make_stream(
            host_stream_id=6,
            status=Stream.Status.LIVE,
            finished_at=timezone.now() - timedelta(minutes=self.THRESHOLD_MINUTES + 1),
            snapshots=[],
        )

        finalized, deleted = self._run_finalize()

        self.assertEqual((finalized, deleted), (0, 1))
        self.assertFalse(Stream.objects.filter(pk=empty.pk).exists())

    def test_mixed_batch_finalizes_some_and_deletes_others(self):
        ok = self._make_stream(
            host_stream_id=7,
            status=Stream.Status.LIVE,
            finished_at=timezone.now() - timedelta(minutes=self.THRESHOLD_MINUTES + 1),
            snapshots=[
                {"g": 100, "v": 80, "t": 1700000000},
                {"g": 100, "v": 90, "t": 1700000900},
            ],
        )
        single = self._make_stream(
            host_stream_id=8,
            status=Stream.Status.LIVE,
            finished_at=timezone.now() - timedelta(minutes=self.THRESHOLD_MINUTES + 1),
            snapshots=[{"g": 200, "v": 50, "t": 1700000000}],
        )

        finalized, deleted = self._run_finalize()

        ok.refresh_from_db()
        self.assertEqual((finalized, deleted), (1, 1))
        self.assertEqual(ok.status, Stream.Status.OFFLINE)
        self.assertEqual(ok.max_viewers, 90)
        self.assertEqual(ok.host_game_ids, [100])
        self.assertFalse(Stream.objects.filter(pk=single.pk).exists())
