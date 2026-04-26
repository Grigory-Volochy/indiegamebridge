"""Twitch Client."""

import httpx
import time
from django.conf import settings


class TwitchClient:

    def __init__(self):
        self._token = None
        self._token_expires_at = 0
        self._client = httpx.Client(timeout=20)

    def _ensure_token(self):
        if self._token and time.time() < self._token_expires_at - 60:
            return
        resp = self._client.post(settings.TWITCH_API_TOKEN_URL, params={
            "client_id": settings.TWITCH_API_CLIENT_ID,
            "client_secret": settings.TWITCH_API_CLIENT_SECRET,
            "grant_type": "client_credentials",
        })
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expires_at = time.time() + data["expires_in"]

    def _headers(self):
        self._ensure_token()
        return {
            "Client-ID": settings.TWITCH_API_CLIENT_ID,
            "Authorization": f"Bearer {self._token}",
        }

    def get_streams(self, game_ids, first=100, after=None):
        params = {"game_id": game_ids, "first": first}
        if after:
            params["after"] = after
        resp = self._client.get(f"{settings.TWITCH_API_URL}/streams", params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def iter_streams(self, game_ids):
        cursor = None
        while True:
            # TODO: handle case when there are more than 100 game IDs - Helix only allows up to 100 game IDs per request
            data = self.get_streams(game_ids, after=cursor)
            yield from data["data"]
            cursor = data.get("pagination", {}).get("cursor")
            if not cursor:
                break

    def close(self):
        if self._client and not self._client.is_closed:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
