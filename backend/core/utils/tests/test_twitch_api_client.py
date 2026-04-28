"""Unit tests for the Helix client."""

from unittest import mock

from django.test import SimpleTestCase

from core.utils.twitch_api_client import TwitchApiClient


class TwitchApiClientIterStreamsTests(SimpleTestCase):
    """
    `__init__` opens a real ``httpx.Client``, which we don't need here — the
    pagination loop only touches ``self.get_streams``. Constructing via
    ``__new__`` skips that and keeps the test focused on the loop.
    """

    def test_iter_streams_paginates_until_no_cursor(self):
        client = TwitchApiClient.__new__(TwitchApiClient)
        pages = [
            {"data": [{"id": "1"}, {"id": "2"}], "pagination": {"cursor": "abc"}},
            {"data": [{"id": "3"}], "pagination": {"cursor": "def"}},
            {"data": [{"id": "4"}], "pagination": {}},
        ]
        with mock.patch.object(client, "get_streams", side_effect=pages) as gs:
            result = list(client.iter_streams(languages=["nolang"]))

        self.assertEqual([s["id"] for s in result], ["1", "2", "3", "4"])
        self.assertEqual(
            [c.kwargs.get("after") for c in gs.call_args_list],
            [None, "abc", "def"],
        )

    def test_iter_streams_stops_when_pagination_key_missing(self):
        client = TwitchApiClient.__new__(TwitchApiClient)
        with mock.patch.object(
            client, "get_streams", return_value={"data": [{"id": "1"}]}
        ) as gs:
            result = list(client.iter_streams(languages=["nolang"]))

        self.assertEqual(result, [{"id": "1"}])
        gs.assert_called_once()

    def test_iter_streams_stops_when_cursor_is_empty_string(self):
        client = TwitchApiClient.__new__(TwitchApiClient)
        with mock.patch.object(
            client,
            "get_streams",
            return_value={"data": [], "pagination": {"cursor": ""}},
        ) as gs:
            result = list(client.iter_streams(languages=["nolang"]))

        self.assertEqual(result, [])
        gs.assert_called_once()
