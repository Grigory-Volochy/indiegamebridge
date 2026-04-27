"""IGDB API client. Uses the same Twitch OAuth flow as Helix."""

from core.utils.twitch_api_base_client import TwitchApiBaseClient


_IGDB_API_URL = "https://api.igdb.com/v4"
# IGDB caps `limit` at 500 per request; using a small temporary value while
# the response shape is being explored. Bump back toward 500 once that's done.
_DEFAULT_PAGE_SIZE = 3
_APICALYPSE_HEADERS = {"Content-Type": "text/plain"}


class IgdbApiClient(TwitchApiBaseClient):
    """Client for the IGDB API.

    Note: IGDB uses Apicalypse (POST with a text body) rather than REST query
    params. Implementations of methods below should use ``self._request`` with
    ``content=<query>`` and ``headers={"Content-Type": "text/plain"}``.
    """

    def get_games(self, limit=_DEFAULT_PAGE_SIZE, offset=0):
        query = f"fields *; limit {limit}; offset {offset}; where genres = 32;" # TODO: use selected genres instead of hard-coded value (32 = indie games)
        resp = self._request(
            "POST",
            f"{_IGDB_API_URL}/games/",
            content=query,
            headers=_APICALYPSE_HEADERS,
        )
        return resp.json()

    def iter_games(self, page_size=_DEFAULT_PAGE_SIZE):
        offset = 0
        while True:
            data = self.get_games(limit=page_size, offset=offset)
            if not data:
                break
            yield from data
            if len(data) < page_size:
                break
            offset += page_size
            break   # !!! LIMIT FOR TEST ONLY !!!

    def get_genres(self, limit=_DEFAULT_PAGE_SIZE, offset=0):
        query = f"fields *; limit {limit}; offset {offset};"
        resp = self._request(
            "POST",
            f"{_IGDB_API_URL}/genres/",
            content=query,
            headers=_APICALYPSE_HEADERS,
        )
        return resp.json()