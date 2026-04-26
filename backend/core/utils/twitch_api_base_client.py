"""Shared Twitch OAuth and retrying HTTP client.

Both the Twitch Helix and IGDB API clients use this as a base, since IGDB
authenticates with the same Twitch app credentials.
"""

import logging
import time

import httpx
from django.conf import settings


logger = logging.getLogger(__name__)

_TWITCH_API_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
_TOKEN_REFRESH_MARGIN_SECONDS = 60
_MAX_REQUEST_ATTEMPTS = 3
_BACKOFF_BASE_SECONDS = 1.0
_RETRY_AFTER_CAP_SECONDS = 60.0
_RETRYABLE_STATUSES = {500, 502, 503, 504}


class TwitchApiBaseClient:
    """Owns the OAuth token lifecycle and a retrying HTTP client."""

    def __init__(self):
        self._token = None
        self._token_expires_at = 0
        self._client = httpx.Client(timeout=20)

    def _ensure_token(self):
        if self._token and time.time() < self._token_expires_at - _TOKEN_REFRESH_MARGIN_SECONDS:
            return
        logger.debug("Refreshing Twitch app token")
        resp = self._client.post(_TWITCH_API_TOKEN_URL, params={
            "client_id": settings.TWITCH_API_CLIENT_ID,
            "client_secret": settings.TWITCH_API_CLIENT_SECRET,
            "grant_type": "client_credentials",
        })
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expires_at = time.time() + data["expires_in"]
        logger.debug("Twitch token refreshed; expires in %ss", data["expires_in"])

    def _headers(self):
        self._ensure_token()
        return {
            "Client-ID": settings.TWITCH_API_CLIENT_ID,
            "Authorization": f"Bearer {self._token}",
        }

    def _request(self, method, url, **kwargs):
        for attempt in range(_MAX_REQUEST_ATTEMPTS):
            is_last_attempt = attempt == _MAX_REQUEST_ATTEMPTS - 1
            try:
                resp = self._client.request(method, url, headers=self._headers(), **kwargs)
            except httpx.TransportError as e:
                if is_last_attempt:
                    raise
                backoff = _BACKOFF_BASE_SECONDS * (2 ** attempt)
                logger.warning("Twitch request failed (%s); backing off %.1fs before retry", type(e).__name__, backoff)
                time.sleep(backoff)
                continue

            # 401 only triggers a token refresh on the first attempt; a second 401
            # after a fresh token means a deeper auth problem, so stop retrying.
            if resp.status_code == 401 and attempt == 0:
                logger.warning("Twitch returned 401; refreshing token and retrying")
                self._token = None
                continue

            if resp.status_code == 429 and not is_last_attempt:
                try:
                    retry_after = float(resp.headers.get("Retry-After", "1"))
                except ValueError:
                    retry_after = 1.0
                retry_after = min(retry_after, _RETRY_AFTER_CAP_SECONDS)
                logger.warning("Twitch rate limited; sleeping %.1fs before retry", retry_after)
                time.sleep(retry_after)
                continue

            if resp.status_code in _RETRYABLE_STATUSES and not is_last_attempt:
                backoff = _BACKOFF_BASE_SECONDS * (2 ** attempt)
                logger.warning("Twitch returned %d; backing off %.1fs before retry", resp.status_code, backoff)
                time.sleep(backoff)
                continue

            resp.raise_for_status()
            return resp

        resp.raise_for_status()
        return resp

    def close(self):
        if self._client and not self._client.is_closed:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
