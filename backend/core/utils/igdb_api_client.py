"""IGDB API client. Uses the same Twitch OAuth flow as Helix."""

from core.utils.twitch_api_base_client import TwitchApiBaseClient


_IGDB_API_URL = "https://api.igdb.com/v4"


class IgdbApiClient(TwitchApiBaseClient):
    """Client for the IGDB API.

    Note: IGDB uses Apicalypse (POST with a text body) rather than REST query
    params. Implementations of methods below should use ``self._request`` with
    ``content=<query>`` and ``headers={"Content-Type": "text/plain"}``.
    """

    def get_games(self):
        # TODO: use IGDB API to retrieve games from https://api.igdb.com/v4/games/ also see https://api-docs.igdb.com/ for documentation
        pass
