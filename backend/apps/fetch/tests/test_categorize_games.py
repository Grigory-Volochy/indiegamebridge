"""Tests for the categorize_games management command (Helix categorization).

The command pulls Game rows with `category='new'`, calls Helix /games to look
each one up, and sets `category` to either `isgame` (non-empty igdb_id) or
`isnongame` (empty igdb_id). Helix's `name` is captured into `host_name`.
Rows where Helix returns nothing stay `new` and get retried next run.
"""

from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from apps.streams.models import Game


def _patch_twitch_client(get_games_by_ids_response=None):
    """Patches TwitchApiClient so the command sees a mock context manager.

    Returns (patcher, instance). Caller is responsible for `patcher.stop()`.
    """
    patcher = mock.patch(
        "apps.fetch.management.commands.categorize_games.TwitchApiClient"
    )
    mock_cls = patcher.start()
    instance = mock_cls.return_value
    instance.__enter__.return_value = instance
    instance.__exit__.return_value = False
    instance.get_games_by_ids.return_value = get_games_by_ids_response or []
    return patcher, instance


class CategorizeGamesTests(TestCase):
    def test_no_new_games_skips_helix_call(self):
        Game.objects.create(
            host_game_id=100,
            host_name="Already known",
            category=Game.Category.ISGAME,
            igdb_game_id=12345,
        )

        patcher, instance = _patch_twitch_client()
        try:
            call_command("categorize_games", stdout=mock.Mock())
        finally:
            patcher.stop()

        instance.get_games_by_ids.assert_not_called()

    def test_non_empty_igdb_id_marks_isgame_and_stores_igdb_game_id(self):
        game = Game.objects.create(host_game_id=32982)

        # Helix returns ids as strings.
        response = [{
            "id": "32982",
            "name": "Grand Theft Auto V",
            "box_art_url": "https://...",
            "igdb_id": "1020",
        }]
        patcher, _ = _patch_twitch_client(get_games_by_ids_response=response)
        try:
            call_command("categorize_games", stdout=mock.Mock())
        finally:
            patcher.stop()

        game.refresh_from_db()
        self.assertEqual(game.category, Game.Category.ISGAME)
        self.assertEqual(game.igdb_game_id, 1020)
        self.assertEqual(game.host_name, "Grand Theft Auto V")

    def test_empty_igdb_id_marks_isnongame(self):
        """Categories like 'Just Chatting' come back with igdb_id=='' from
        Helix and must be stored as `isnongame` for caching."""
        game = Game.objects.create(host_game_id=509658)

        response = [{
            "id": "509658",
            "name": "Just Chatting",
            "box_art_url": "https://...",
            "igdb_id": "",
        }]
        patcher, _ = _patch_twitch_client(get_games_by_ids_response=response)
        try:
            call_command("categorize_games", stdout=mock.Mock())
        finally:
            patcher.stop()

        game.refresh_from_db()
        self.assertEqual(game.category, Game.Category.ISNONGAME)
        self.assertEqual(game.host_name, "Just Chatting")
        self.assertEqual(game.igdb_game_id, 0)

    def test_game_missing_from_helix_response_stays_new(self):
        """If Helix returns nothing for an id, the row must stay `new` so it
        can be retried on the next run rather than being silently lost."""
        game = Game.objects.create(host_game_id=99999)

        patcher, _ = _patch_twitch_client(get_games_by_ids_response=[])
        try:
            call_command("categorize_games", stdout=mock.Mock())
        finally:
            patcher.stop()

        game.refresh_from_db()
        self.assertEqual(game.category, Game.Category.NEW)
        self.assertEqual(game.host_name, "")
        self.assertEqual(game.igdb_game_id, 0)

    def test_mixed_response_classifies_each_row_independently(self):
        """One Helix response can contain both isgame and isnongame entries;
        each Game must be categorized correctly based on its own payload."""
        gta = Game.objects.create(host_game_id=32982)
        chatting = Game.objects.create(host_game_id=509658)

        response = [
            {"id": "32982", "name": "GTA V", "igdb_id": "1020"},
            {"id": "509658", "name": "Just Chatting", "igdb_id": ""},
        ]
        patcher, _ = _patch_twitch_client(get_games_by_ids_response=response)
        try:
            call_command("categorize_games", stdout=mock.Mock())
        finally:
            patcher.stop()

        gta.refresh_from_db()
        chatting.refresh_from_db()
        self.assertEqual(gta.category, Game.Category.ISGAME)
        self.assertEqual(gta.igdb_game_id, 1020)
        self.assertEqual(chatting.category, Game.Category.ISNONGAME)
        self.assertEqual(chatting.igdb_game_id, 0)

    def test_already_categorized_games_are_left_alone(self):
        """Only `new` games are processed; isgame/isnongame must be untouched
        even if they appear in the Helix response somehow."""
        existing = Game.objects.create(
            host_game_id=32982,
            host_name="Pre-set",
            category=Game.Category.ISGAME,
            igdb_game_id=1020,
        )

        response = [{"id": "32982", "name": "Different Name", "igdb_id": "9999"}]
        patcher, instance = _patch_twitch_client(get_games_by_ids_response=response)
        try:
            call_command("categorize_games", stdout=mock.Mock())
        finally:
            patcher.stop()

        # Helix should not even be called since there are no `new` games.
        instance.get_games_by_ids.assert_not_called()

        existing.refresh_from_db()
        self.assertEqual(existing.host_name, "Pre-set")
        self.assertEqual(existing.igdb_game_id, 1020)

    def test_limit_caps_work_per_run(self):
        Game.objects.bulk_create([Game(host_game_id=i) for i in range(1, 11)])

        def fake_response(ids):
            return [
                {"id": str(gid), "name": f"G{gid}", "igdb_id": str(10000 + gid)}
                for gid in ids
            ]

        patcher = mock.patch(
            "apps.fetch.management.commands.categorize_games.TwitchApiClient"
        )
        mock_cls = patcher.start()
        instance = mock_cls.return_value
        instance.__enter__.return_value = instance
        instance.__exit__.return_value = False
        instance.get_games_by_ids.side_effect = fake_response
        try:
            call_command("categorize_games", "--limit", "3", stdout=mock.Mock())
        finally:
            patcher.stop()

        called_ids = instance.get_games_by_ids.call_args.args[0]
        self.assertEqual(len(called_ids), 3)
        self.assertEqual(Game.objects.filter(category=Game.Category.ISGAME).count(), 3)
        self.assertEqual(Game.objects.filter(category=Game.Category.NEW).count(), 7)

    def test_malformed_igdb_id_keeps_row_as_new_for_retry(self):
        """If Helix sends a non-integer igdb_id (shouldn't happen but is
        defensible), the row must stay `new` rather than corrupting state."""
        game = Game.objects.create(host_game_id=100)

        response = [{"id": "100", "name": "Weird", "igdb_id": "not-a-number"}]
        patcher, _ = _patch_twitch_client(get_games_by_ids_response=response)
        try:
            call_command("categorize_games", stdout=mock.Mock())
        finally:
            patcher.stop()

        game.refresh_from_db()
        self.assertEqual(game.category, Game.Category.NEW)
