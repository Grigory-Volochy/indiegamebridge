"""Unit tests for the shared Twitch/IGDB HTTP client and the Helix client."""

from unittest import mock

import httpx
from django.test import SimpleTestCase, override_settings

from core.utils.twitch_api_base_client import TwitchApiBaseClient


def _mock_response(status_code=200, json_data=None, headers=None):
    resp = mock.Mock(spec=httpx.Response)
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.json.return_value = json_data or {}
    if 400 <= status_code < 600:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=mock.Mock(), response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


@override_settings(
    TWITCH_API_CLIENT_ID="test-client-id",
    TWITCH_API_CLIENT_SECRET="test-client-secret",
)
class TwitchApiBaseClientTests(SimpleTestCase):
    def setUp(self):
        client_patcher = mock.patch("core.utils.twitch_api_base_client.httpx.Client")
        self.mock_client_cls = client_patcher.start()
        self.mock_http = self.mock_client_cls.return_value
        self.addCleanup(client_patcher.stop)

        sleep_patcher = mock.patch("core.utils.twitch_api_base_client.time.sleep")
        self.mock_sleep = sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

        time_patcher = mock.patch("core.utils.twitch_api_base_client.time.time")
        self.mock_time = time_patcher.start()
        self.mock_time.return_value = 1_000_000.0
        self.addCleanup(time_patcher.stop)

    @staticmethod
    def _token_response(access_token="tok", expires_in=3600):
        return _mock_response(
            status_code=200,
            json_data={"access_token": access_token, "expires_in": expires_in},
        )

    def test_ensure_token_fetches_on_first_call(self):
        self.mock_http.post.return_value = self._token_response("tok-1", 3600)

        client = TwitchApiBaseClient()
        client._ensure_token()

        self.mock_http.post.assert_called_once()
        args, kwargs = self.mock_http.post.call_args
        self.assertEqual(args[0], "https://id.twitch.tv/oauth2/token")
        self.assertEqual(
            kwargs["params"],
            {
                "client_id": "test-client-id",
                "client_secret": "test-client-secret",
                "grant_type": "client_credentials",
            },
        )
        self.assertEqual(client._token, "tok-1")
        self.assertEqual(client._token_expires_at, 1_000_000.0 + 3600)

    def test_ensure_token_skipped_when_valid(self):
        self.mock_http.post.return_value = self._token_response("tok-1", 3600)
        client = TwitchApiBaseClient()
        client._ensure_token()
        self.mock_http.post.reset_mock()

        client._ensure_token()

        self.mock_http.post.assert_not_called()

    def test_ensure_token_refreshes_within_expiry_margin(self):
        self.mock_http.post.return_value = self._token_response("tok-1", 3600)
        client = TwitchApiBaseClient()
        client._ensure_token()

        # Move into the 60-second pre-expiry window.
        self.mock_time.return_value = 1_000_000.0 + 3600 - 30
        self.mock_http.post.return_value = self._token_response("tok-2", 3600)
        client._ensure_token()

        self.assertEqual(client._token, "tok-2")

    def test_request_happy_path_returns_response(self):
        self.mock_http.post.return_value = self._token_response()
        ok = _mock_response(200, json_data={"data": []})
        self.mock_http.request.return_value = ok

        client = TwitchApiBaseClient()
        resp = client._request("GET", "https://api.twitch.tv/helix/streams")

        self.assertIs(resp, ok)
        self.mock_http.request.assert_called_once()
        _, kwargs = self.mock_http.request.call_args
        self.assertEqual(kwargs["headers"]["Client-ID"], "test-client-id")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer tok")

    def test_request_401_first_attempt_refreshes_token_and_retries(self):
        self.mock_http.post.side_effect = [
            self._token_response("tok-1"),
            self._token_response("tok-2"),
        ]
        self.mock_http.request.side_effect = [
            _mock_response(401),
            _mock_response(200, json_data={"data": []}),
        ]

        client = TwitchApiBaseClient()
        resp = client._request("GET", "https://api.twitch.tv/helix/streams")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.mock_http.request.call_count, 2)
        self.assertEqual(self.mock_http.post.call_count, 2)
        self.assertEqual(client._token, "tok-2")

    def test_request_401_on_second_attempt_is_not_retried(self):
        self.mock_http.post.side_effect = [
            self._token_response("tok-1"),
            self._token_response("tok-2"),
        ]
        self.mock_http.request.side_effect = [
            _mock_response(401),
            _mock_response(401),
        ]

        client = TwitchApiBaseClient()
        with self.assertRaises(httpx.HTTPStatusError):
            client._request("GET", "https://api.twitch.tv/helix/streams")

        self.assertEqual(self.mock_http.request.call_count, 2)

    def test_request_429_sleeps_retry_after_then_retries(self):
        self.mock_http.post.return_value = self._token_response()
        self.mock_http.request.side_effect = [
            _mock_response(429, headers={"Retry-After": "5"}),
            _mock_response(200),
        ]

        client = TwitchApiBaseClient()
        client._request("GET", "https://api.twitch.tv/helix/streams")

        self.mock_sleep.assert_called_once_with(5.0)

    def test_request_429_retry_after_capped(self):
        self.mock_http.post.return_value = self._token_response()
        self.mock_http.request.side_effect = [
            _mock_response(429, headers={"Retry-After": "9999"}),
            _mock_response(200),
        ]

        client = TwitchApiBaseClient()
        client._request("GET", "https://api.twitch.tv/helix/streams")

        self.mock_sleep.assert_called_once_with(60.0)

    def test_request_429_invalid_retry_after_falls_back_to_one_second(self):
        self.mock_http.post.return_value = self._token_response()
        self.mock_http.request.side_effect = [
            _mock_response(429, headers={"Retry-After": "not-a-number"}),
            _mock_response(200),
        ]

        client = TwitchApiBaseClient()
        client._request("GET", "https://api.twitch.tv/helix/streams")

        self.mock_sleep.assert_called_once_with(1.0)

    def test_request_5xx_retries_with_exponential_backoff(self):
        self.mock_http.post.return_value = self._token_response()
        self.mock_http.request.side_effect = [
            _mock_response(503),
            _mock_response(503),
            _mock_response(200),
        ]

        client = TwitchApiBaseClient()
        resp = client._request("GET", "https://api.twitch.tv/helix/streams")

        self.assertEqual(resp.status_code, 200)
        # _BACKOFF_BASE_SECONDS * (2 ** attempt) for attempts 0 and 1.
        self.assertEqual(
            [c.args[0] for c in self.mock_sleep.call_args_list],
            [1.0, 2.0],
        )

    def test_request_transport_error_retries_and_eventually_succeeds(self):
        self.mock_http.post.return_value = self._token_response()
        self.mock_http.request.side_effect = [
            httpx.ConnectError("boom"),
            _mock_response(200),
        ]

        client = TwitchApiBaseClient()
        resp = client._request("GET", "https://api.twitch.tv/helix/streams")

        self.assertEqual(resp.status_code, 200)
        self.mock_sleep.assert_called_once_with(1.0)

    def test_request_transport_error_on_last_attempt_raises(self):
        self.mock_http.post.return_value = self._token_response()
        self.mock_http.request.side_effect = [
            httpx.ConnectError("boom"),
            httpx.ConnectError("boom"),
            httpx.ConnectError("boom"),
        ]

        client = TwitchApiBaseClient()
        with self.assertRaises(httpx.ConnectError):
            client._request("GET", "https://api.twitch.tv/helix/streams")

        self.assertEqual(self.mock_http.request.call_count, 3)

    def test_request_5xx_exhausts_retries_then_raises(self):
        self.mock_http.post.return_value = self._token_response()
        self.mock_http.request.side_effect = [
            _mock_response(503),
            _mock_response(503),
            _mock_response(503),
        ]

        client = TwitchApiBaseClient()
        with self.assertRaises(httpx.HTTPStatusError):
            client._request("GET", "https://api.twitch.tv/helix/streams")

        self.assertEqual(self.mock_http.request.call_count, 3)
