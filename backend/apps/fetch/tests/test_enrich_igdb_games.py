"""Tests for the enrich_igdb_games management command (IGDB enrichment).

The command pulls Game rows that are categorized as `isgame` AND have no
genres linked yet, queries IGDB by `igdb_game_id`, and fills in name/summary/
url plus M2M genres. Games with other categories (`new`, `isnongame`) must
not be touched by this command.

Covers:
- Filter is "category=isgame AND genres empty" — other categories skipped.
- Game returned by IGDB gets fields filled and genre links created.
- Game NOT returned by IGDB stays unenriched and remains a candidate next run.
- Unknown genre id in the IGDB response triggers a single genre-table refresh,
  and the new genre is then linked to the game.
- --limit caps how many games are processed in a run.
"""

from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from apps.streams.models import Game, GameGenre


def _patch_igdb_client(get_games_by_ids_response=None, get_genres_response=None):
    """Patches IgdbApiClient so the command sees a mock context manager.

    Returns (patcher, instance). Caller is responsible for `patcher.stop()`.
    """
    patcher = mock.patch(
        "apps.fetch.management.commands.enrich_igdb_games.IgdbApiClient"
    )
    mock_cls = patcher.start()
    instance = mock_cls.return_value
    instance.__enter__.return_value = instance
    instance.__exit__.return_value = False
    instance.get_games_by_ids.return_value = get_games_by_ids_response or []
    instance.get_genres.return_value = get_genres_response or []
    return patcher, instance


def _make_genre(host_genre_id=32, name="Indie", slug="indie", url="https://igdb/genre/indie"):
    return GameGenre.objects.create(
        host_genre_id=host_genre_id, host_name=name, slug=slug, host_url=url,
    )


def _make_isgame(host_game_id, igdb_game_id):
    """Helper: a game that's been categorized as isgame and is ready for IGDB enrichment."""
    return Game.objects.create(
        host_game_id=host_game_id,
        igdb_game_id=igdb_game_id,
        category=Game.Category.ISGAME,
    )


class EnrichIgdbGamesTests(TestCase):
    def test_already_enriched_isgame_skips_igdb_call(self):
        """An `isgame` Game with at least one linked genre is treated as
        enriched and must not trigger an IGDB request."""
        genre = _make_genre()
        game = _make_isgame(host_game_id=100, igdb_game_id=12345)
        game.genres.add(genre)

        patcher, instance = _patch_igdb_client()
        try:
            call_command("enrich_igdb_games", stdout=mock.Mock())
        finally:
            patcher.stop()

        instance.get_games_by_ids.assert_not_called()
        instance.get_genres.assert_not_called()

    def test_new_category_games_are_not_enriched(self):
        """`category='new'` games haven't been categorized yet and must not
        be sent to IGDB."""
        _make_genre()
        Game.objects.create(host_game_id=100)  # default category=NEW

        patcher, instance = _patch_igdb_client()
        try:
            call_command("enrich_igdb_games", stdout=mock.Mock())
        finally:
            patcher.stop()

        instance.get_games_by_ids.assert_not_called()

    def test_isnongame_category_is_not_enriched(self):
        """`isnongame` rows represent non-game Helix categories and must be
        excluded from IGDB enrichment entirely."""
        _make_genre()
        Game.objects.create(
            host_game_id=509658,
            host_name="Just Chatting",
            category=Game.Category.ISNONGAME,
        )

        patcher, instance = _patch_igdb_client()
        try:
            call_command("enrich_igdb_games", stdout=mock.Mock())
        finally:
            patcher.stop()

        instance.get_games_by_ids.assert_not_called()

    def test_unenriched_isgame_is_filled_and_linked_to_known_genre(self):
        _make_genre(host_genre_id=32)
        game = _make_isgame(host_game_id=100, igdb_game_id=12345)

        # IGDB response is keyed on igdb_game_id, not host_game_id.
        response = [{
            "id": 12345,
            "name": "Some Indie Game",
            "summary": "A short summary.",
            "url": "https://igdb/game/some-indie-game",
            "genres": [32],
        }]
        patcher, _ = _patch_igdb_client(get_games_by_ids_response=response)
        try:
            call_command("enrich_igdb_games", stdout=mock.Mock())
        finally:
            patcher.stop()

        game.refresh_from_db()
        self.assertEqual(game.host_name, "Some Indie Game")
        self.assertEqual(game.host_summary, "A short summary.")
        self.assertEqual(game.host_url, "https://igdb/game/some-indie-game")
        self.assertEqual(
            list(game.genres.values_list("host_genre_id", flat=True)),
            [32],
        )

    def test_igdb_lookup_uses_igdb_game_id_not_host_game_id(self):
        """Regression guard: the chunk ids sent to IGDB must be the
        `igdb_game_id` values, never the Twitch `host_game_id`."""
        _make_genre(host_genre_id=32)
        _make_isgame(host_game_id=100, igdb_game_id=12345)
        _make_isgame(host_game_id=200, igdb_game_id=67890)

        patcher, instance = _patch_igdb_client(get_games_by_ids_response=[])
        try:
            call_command("enrich_igdb_games", stdout=mock.Mock())
        finally:
            patcher.stop()

        called_ids = instance.get_games_by_ids.call_args.args[0]
        self.assertEqual(sorted(called_ids), [12345, 67890])

    def test_game_with_multiple_genres_links_all_of_them(self):
        _make_genre(host_genre_id=32, name="Indie", slug="indie")
        _make_genre(host_genre_id=31, name="Adventure", slug="adventure", url="u")
        game = _make_isgame(host_game_id=100, igdb_game_id=12345)

        response = [{
            "id": 12345,
            "name": "G",
            "summary": "",
            "url": "",
            "genres": [32, 31],
        }]
        patcher, _ = _patch_igdb_client(get_games_by_ids_response=response)
        try:
            call_command("enrich_igdb_games", stdout=mock.Mock())
        finally:
            patcher.stop()

        linked = sorted(game.genres.values_list("host_genre_id", flat=True))
        self.assertEqual(linked, [31, 32])

    def test_game_missing_from_response_stays_unenriched(self):
        """If IGDB returns no row for an igdb id, that Game stays untouched
        so it gets retried next run."""
        _make_genre(host_genre_id=32)
        present = _make_isgame(host_game_id=100, igdb_game_id=12345)
        absent = _make_isgame(host_game_id=200, igdb_game_id=99999)

        response = [{
            "id": 12345,
            "name": "Present",
            "summary": "ok",
            "url": "u",
            "genres": [32],
        }]
        patcher, _ = _patch_igdb_client(get_games_by_ids_response=response)
        try:
            call_command("enrich_igdb_games", stdout=mock.Mock())
        finally:
            patcher.stop()

        present.refresh_from_db()
        self.assertEqual(present.host_name, "Present")

        absent.refresh_from_db()
        # host_name from categorize stays empty here since we never set it
        self.assertEqual(absent.host_summary, "")
        self.assertEqual(absent.host_url, "")
        self.assertEqual(absent.genres.count(), 0)

    def test_unknown_genre_in_response_triggers_one_refresh(self):
        """An IGDB response referencing a genre id we don't have should pull
        the full genre list once and link the new row afterwards."""
        self.assertEqual(GameGenre.objects.count(), 0)
        game = _make_isgame(host_game_id=100, igdb_game_id=12345)

        games_response = [{
            "id": 12345,
            "name": "G",
            "summary": "",
            "url": "",
            "genres": [32],
        }]
        genres_response = [{
            "id": 32,
            "name": "Indie",
            "slug": "indie",
            "url": "https://igdb/genre/indie",
        }]
        patcher, instance = _patch_igdb_client(
            get_games_by_ids_response=games_response,
            get_genres_response=genres_response,
        )
        try:
            call_command("enrich_igdb_games", stdout=mock.Mock())
        finally:
            patcher.stop()

        instance.get_genres.assert_called_once()
        self.assertEqual(GameGenre.objects.count(), 1)

        game.refresh_from_db()
        self.assertEqual(
            list(game.genres.values_list("host_genre_id", flat=True)),
            [32],
        )

    def test_limit_caps_work_per_run(self):
        """--limit 3 over 10 unenriched isgame games processes exactly 3."""
        _make_genre(host_genre_id=32)
        Game.objects.bulk_create([
            Game(
                host_game_id=i,
                igdb_game_id=10000 + i,
                category=Game.Category.ISGAME,
            )
            for i in range(1, 11)
        ])

        def fake_response(ids):
            return [{
                "id": gid,
                "name": f"G{gid}",
                "summary": "",
                "url": "",
                "genres": [32],
            } for gid in ids]

        patcher = mock.patch(
            "apps.fetch.management.commands.enrich_igdb_games.IgdbApiClient"
        )
        mock_cls = patcher.start()
        instance = mock_cls.return_value
        instance.__enter__.return_value = instance
        instance.__exit__.return_value = False
        instance.get_games_by_ids.side_effect = fake_response
        try:
            call_command("enrich_igdb_games", "--limit", "3", stdout=mock.Mock())
        finally:
            patcher.stop()

        called_ids = instance.get_games_by_ids.call_args.args[0]
        self.assertEqual(len(called_ids), 3)
        self.assertEqual(Game.objects.exclude(host_name="").count(), 3)

    def test_field_truncation_protects_against_oversized_igdb_strings(self):
        """name/url get clipped to model max_lengths to avoid raising on the
        rare oversized IGDB value."""
        _make_genre(host_genre_id=32)
        game = _make_isgame(host_game_id=100, igdb_game_id=12345)

        response = [{
            "id": 12345,
            "name": "X" * 1000,
            "summary": "fine",
            "url": "https://igdb/" + ("y" * 2000),
            "genres": [32],
        }]
        patcher, _ = _patch_igdb_client(get_games_by_ids_response=response)
        try:
            call_command("enrich_igdb_games", stdout=mock.Mock())
        finally:
            patcher.stop()

        game.refresh_from_db()
        self.assertEqual(len(game.host_name), 255)
        self.assertEqual(len(game.host_url), 1024)
