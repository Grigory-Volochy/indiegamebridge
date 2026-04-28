"""Twitch Helix API client."""

from collections import namedtuple

from core.utils.twitch_api_base_client import TwitchApiBaseClient


_TWITCH_API_URL = "https://api.twitch.tv/helix"
_DEFAULT_PAGE_SIZE = 5 # 100
_DEFAULT_MAX_REQUESTS_PER_RUN = 3 # 750

# Collect only necessary fields to reduce memory usage
StreamTuple = namedtuple("StreamTuple", ["id", "user_id","viewer_count", "game_id", "type"])


class TwitchApiClient(TwitchApiBaseClient):
    """Client for the Twitch Helix API."""

    def get_streams(self, language, first=_DEFAULT_PAGE_SIZE, after=None):
        """Retrieves single page - up to 100 entries

        Args:
            language (str): The streams language tag using an ISO 639-1 two-letter language code
            first (int, optional): The maximum number of items to return per page. Defaults to _DEFAULT_PAGE_SIZE.
            after (str, optional): The cursor used to get the next page of results. Defaults to None.

        Returns:
            dict: streams
        """

        params = {
            "type": "live",
            "language": language,
            "first": first
        }
        if after:
            params["after"] = after

        resp = self._request("GET", f"{_TWITCH_API_URL}/streams", params=params)
        return resp.json()

    def iter_streams(self, language, max_requests=_DEFAULT_MAX_REQUESTS_PER_RUN, cursor=None):
        """Retrieves specified amount of pages

        Args:
            language (str): The streams language tag using an ISO 639-1 two-letter language code
            max_requests (int, optional): Requests limit for the one run. Defaults to _DEFAULT_MAX_REQUESTS_PER_RUN.
            cursor (str, optional): The cursor used to get the next page of results. Defaults to None.

        Returns:
            list, str: streams, cursor
        """

        streams = []
        for _ in range(max_requests):
            raw_streams = self.get_streams(language, after=cursor)
            for one_raw_stream in raw_streams.get("data", []):
                streams.append(StreamTuple(
                    id=one_raw_stream.get("id"),
                    user_id=one_raw_stream.get("user_id"),
                    viewer_count=one_raw_stream.get("viewer_count"),
                    game_id=one_raw_stream.get("game_id"),
                    type=one_raw_stream.get("type"),
                ))
                    
            cursor = raw_streams.get("pagination", {}).get("cursor")
            if not cursor:
                break
        return streams, cursor
