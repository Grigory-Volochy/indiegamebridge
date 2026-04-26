"""Twitch Helix API client."""

from backend.core.utils.twitch_api_base_client import TwitchApiAuth


_TWITCH_API_URL = "https://api.twitch.tv/helix"
_DEFAULT_PAGE_SIZE = 100


class TwitchApiClient(TwitchApiAuth):
    """Client for the Twitch Helix API."""

    def get_streams(self, game_ids, first=_DEFAULT_PAGE_SIZE, after=None):
        params = {"game_id": game_ids, "first": first}
        if after:
            params["after"] = after
        resp = self._request("GET", f"{_TWITCH_API_URL}/streams", params=params)
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
