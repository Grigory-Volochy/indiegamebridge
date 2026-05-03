"""Tests for the fetch_twitch_streams management command.

The persistence loop in `_poll_streams_by_lang` is the highest-value thing to
test — it has real branching (get_or_create vs update_or_create, profile
mismatch update, dedup, snapshot creation) and any regression silently
corrupts data. The stale sweep is tested directly against its query.
"""

from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.fetch.management.commands.fetch_twitch_streams import Command
from apps.streams.models import Stream, StreamerProfile, StreamSnapshot
from core.utils.twitch_api_client import StreamTuple


def _make_stream_tuple(**overrides):
    """Build a StreamTuple with all fields populated."""
    defaults = {
        "status": "live",
        "host_stream_id": "stream-1",
        "host_user_id": "user-1",
        "host_login": "loginx",
        "host_display_name": "DisplayName",
        "host_game_id": "game-1",
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

    def test_creates_profile_stream_and_snapshot(self):
        st = _make_stream_tuple()
        self._run(([st], None))

        profile = StreamerProfile.objects.get(host_user_id="user-1")
        self.assertEqual(profile.host, StreamerProfile.Host.TWITCH)
        self.assertEqual(profile.host_login, "loginx")
        self.assertEqual(profile.host_display_name, "DisplayName")

        stream = Stream.objects.get(host_stream_id="stream-1")
        self.assertEqual(stream.streamer_profile_id, profile.id)
        self.assertEqual(stream.status, Stream.Status.LIVE)
        self.assertEqual(stream.language, "en")

        snapshot = StreamSnapshot.objects.get(stream=stream)
        self.assertEqual(snapshot.viewers, 100)
        self.assertEqual(snapshot.host_game_id, "game-1")

    def test_existing_profile_with_changed_login_is_updated(self):
        StreamerProfile.objects.create(
            host=StreamerProfile.Host.TWITCH,
            host_user_id="user-1",
            host_login="oldlogin",
            host_display_name="OldName",
        )

        st = _make_stream_tuple(host_login="newlogin", host_display_name="NewName")
        self._run(([st], None))

        profile = StreamerProfile.objects.get(host_user_id="user-1")
        self.assertEqual(profile.host_login, "newlogin")
        self.assertEqual(profile.host_display_name, "NewName")
        self.assertEqual(StreamerProfile.objects.count(), 1)

    def test_existing_profile_unchanged_is_not_resaved(self):
        """If login/display_name match, no UPDATE should fire (avoids unnecessary writes)."""
        StreamerProfile.objects.create(
            host=StreamerProfile.Host.TWITCH,
            host_user_id="user-1",
            host_login="loginx",
            host_display_name="DisplayName",
        )
        before = StreamerProfile.objects.get(host_user_id="user-1").updated_at

        st = _make_stream_tuple()
        self._run(([st], None))

        after = StreamerProfile.objects.get(host_user_id="user-1").updated_at
        self.assertEqual(before, after)

    def test_dedup_within_poll_creates_one_set_of_rows(self):
        """Same host_stream_id appearing twice within a poll should yield one snapshot."""
        st = _make_stream_tuple()
        self._run(([st, st], None))

        self.assertEqual(StreamerProfile.objects.count(), 1)
        self.assertEqual(Stream.objects.count(), 1)
        self.assertEqual(StreamSnapshot.objects.count(), 1)

    def test_existing_stream_finished_at_is_refreshed(self):
        profile = StreamerProfile.objects.create(
            host=StreamerProfile.Host.TWITCH,
            host_user_id="user-1",
            host_login="loginx",
            host_display_name="DisplayName",
        )
        old_finished_at = timezone.now() - timedelta(hours=1)
        stream = Stream.objects.create(
            streamer_profile=profile,
            host_stream_id="stream-1",
            status=Stream.Status.LIVE,
            language="en",
            started_at=datetime(2025, 1, 1, tzinfo=dt_timezone.utc),
            finished_at=old_finished_at,
        )

        st = _make_stream_tuple()
        self._run(([st], None))

        stream.refresh_from_db()
        self.assertEqual(stream.status, Stream.Status.LIVE)
        self.assertGreater(stream.finished_at, old_finished_at)
        # No duplicate row should be created
        self.assertEqual(Stream.objects.count(), 1)

    def test_each_poll_creates_new_snapshot_for_existing_stream(self):
        st = _make_stream_tuple()
        self._run(([st], None))
        self._run(([st], None))

        self.assertEqual(Stream.objects.count(), 1)
        self.assertEqual(StreamSnapshot.objects.count(), 2)


class StaleSweepTests(TestCase):
    """The stale sweep flips long-unseen LIVE streams to OFFLINE without touching finished_at."""

    THRESHOLD_MINUTES = 100

    def setUp(self):
        self.profile = StreamerProfile.objects.create(
            host=StreamerProfile.Host.TWITCH,
            host_user_id="user-1",
            host_login="loginx",
            host_display_name="DisplayName",
        )

    def _make_stream(self, host_stream_id, status, finished_at):
        return Stream.objects.create(
            streamer_profile=self.profile,
            host_stream_id=host_stream_id,
            status=status,
            language="en",
            started_at=datetime(2025, 1, 1, tzinfo=dt_timezone.utc),
            finished_at=finished_at,
        )

    def _run_sweep(self):
        threshold = timezone.now() - timedelta(minutes=self.THRESHOLD_MINUTES)
        return Stream.objects.filter(
            status=Stream.Status.LIVE,
            finished_at__lt=threshold,
        ).update(status=Stream.Status.OFFLINE)

    def test_stale_live_stream_is_marked_offline(self):
        stale = self._make_stream(
            "stream-stale",
            Stream.Status.LIVE,
            timezone.now() - timedelta(minutes=self.THRESHOLD_MINUTES + 1),
        )
        fresh = self._make_stream(
            "stream-fresh", Stream.Status.LIVE, timezone.now()
        )

        flipped = self._run_sweep()

        stale.refresh_from_db()
        fresh.refresh_from_db()
        self.assertEqual(flipped, 1)
        self.assertEqual(stale.status, Stream.Status.OFFLINE)
        self.assertEqual(fresh.status, Stream.Status.LIVE)

    def test_already_offline_streams_are_untouched(self):
        old_offline = self._make_stream(
            "stream-old",
            Stream.Status.OFFLINE,
            timezone.now() - timedelta(days=7),
        )

        flipped = self._run_sweep()

        old_offline.refresh_from_db()
        self.assertEqual(flipped, 0)
        self.assertEqual(old_offline.status, Stream.Status.OFFLINE)

    def test_sweep_does_not_modify_finished_at(self):
        """finished_at must stay frozen — it represents the actual end time."""
        stale = self._make_stream(
            "stream-stale",
            Stream.Status.LIVE,
            timezone.now() - timedelta(minutes=self.THRESHOLD_MINUTES + 1),
        )
        original_finished_at = stale.finished_at

        self._run_sweep()

        stale.refresh_from_db()
        self.assertEqual(stale.status, Stream.Status.OFFLINE)
        self.assertEqual(stale.finished_at, original_finished_at)
