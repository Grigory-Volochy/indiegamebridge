"""Tests for the backfill_games_from_streams one-shot command.

Scans OFFLINE streams, dedupes their `host_game_ids` arrays, and inserts a
placeholder Game for each id not already present. Live streams must be ignored
(their host_game_ids isn't finalized yet); existing Games must not be touched.
"""

from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.streams.models import Game, Stream, StreamerProfile


class BackfillGamesFromStreamsTests(TestCase):
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

    def _run(self):
        call_command("backfill_games_from_streams", stdout=mock.Mock())

    def test_inserts_placeholder_for_each_unique_offline_stream_game_id(self):
        self._make_stream(1, Stream.Status.OFFLINE, [100, 200])
        self._make_stream(2, Stream.Status.OFFLINE, [200, 300])

        self._run()

        game_ids = sorted(Game.objects.values_list("host_game_id", flat=True))
        self.assertEqual(game_ids, [100, 200, 300])
        # Placeholders carry no metadata.
        for game in Game.objects.all():
            self.assertEqual(game.host_name, "")
            self.assertEqual(game.genres.count(), 0)

    def test_live_streams_are_ignored(self):
        """Live streams haven't had host_game_ids finalized yet, so their values
        must not leak into the Game table."""
        self._make_stream(1, Stream.Status.LIVE, [100, 200])

        self._run()

        self.assertEqual(Game.objects.count(), 0)

    def test_already_present_games_are_not_disturbed(self):
        """Pre-existing rows (possibly already enriched) must survive untouched."""
        Game.objects.create(host_game_id=100, host_name="Already Enriched")
        self._make_stream(1, Stream.Status.OFFLINE, [100, 200])

        self._run()

        self.assertEqual(Game.objects.count(), 2)
        existing = Game.objects.get(host_game_id=100)
        self.assertEqual(existing.host_name, "Already Enriched")
        self.assertTrue(Game.objects.filter(host_game_id=200).exists())

    def test_no_offline_streams_inserts_nothing(self):
        self._run()
        self.assertEqual(Game.objects.count(), 0)

    def test_offline_stream_with_empty_host_game_ids_is_no_op(self):
        self._make_stream(1, Stream.Status.OFFLINE, [])

        self._run()

        self.assertEqual(Game.objects.count(), 0)

    def test_idempotent_across_repeated_runs(self):
        """Running the backfill twice must not double-insert."""
        self._make_stream(1, Stream.Status.OFFLINE, [100, 200])

        self._run()
        self._run()

        self.assertEqual(Game.objects.count(), 2)
