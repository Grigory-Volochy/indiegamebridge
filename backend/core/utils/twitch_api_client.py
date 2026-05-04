"""Twitch Helix API client."""

import logging
import time
from collections import namedtuple

from core.utils.twitch_api_base_client import TwitchApiBaseClient

logger = logging.getLogger(__name__)


_TWITCH_API_URL = "https://api.twitch.tv/helix"
_DEFAULT_PAGE_SIZE = 100
_DEFAULT_MAX_REQUESTS_PER_LANGUAGE_POLL_ROUND = 750

# Collect only necessary fields to reduce memory usage
StreamTuple = namedtuple(
    "StreamTuple",
    [
        "status",
        "host_stream_id",
        "host_user_id",
        "host_login",
        "host_display_name",
        "host_game_id",
        "viewers",
        "started_at",
    ]
)

# Mirrors the corresponding model CharField max_lengths. Streams whose API values
# exceed any of these bounds are skipped to keep DB inserts safe.
# (host_stream_id, host_user_id, host_game_id are stored as BigInteger in the DB,
# so they're validated by int() conversion below rather than a length check.)
_STR_FIELD_MAX_LENGTHS = {
    "status": 16,
    "host_login": 64,
    "host_display_name": 255,
}


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

    def iter_streams(self, language, end_time_anchor, max_requests=_DEFAULT_MAX_REQUESTS_PER_LANGUAGE_POLL_ROUND, cursor=None) -> tuple[list[StreamTuple], str]:
        """Paginates through live streams for one language, up to max_requests pages.

        Args:
            language (str): The streams language tag using an ISO 639-1 two-letter language code.
            end_time_anchor (int): Soft deadline as a `time.time()` value. Checked after each
                page; if exceeded, pagination stops and the partial result is returned. Requests
                already in flight are not aborted.
            max_requests (int, optional): Maximum number of paginated requests to issue in this
                call. Defaults to _DEFAULT_MAX_REQUESTS_PER_LANGUAGE_POLL_ROUND.
            cursor (str, optional): Pagination cursor to resume from. Defaults to None.

        Returns:
            tuple[list[StreamTuple], str | None]: Collected streams and the next cursor
            (None if pagination is exhausted).
        """

        streams = []
        non_numeric_id_type_detected = False
        for _ in range(max_requests):
            raw_streams = self.get_streams(language, after=cursor)
            for one_raw_stream in raw_streams.get("data", []):
                raw_stream_id = one_raw_stream.get("id")
                raw_user_id = one_raw_stream.get("user_id")
                raw_game_id = one_raw_stream.get("game_id")

                # Silently skip streams with any empty ID
                if not all([raw_stream_id, raw_user_id, raw_game_id]):
                    continue

                # Helix returns these as strings; we store them as BIGINT for size/speed.
                # Skip the stream if any value is unexpectedly non-numeric rather than crashing the round.
                try:
                    host_stream_id = int(raw_stream_id)
                    host_user_id = int(raw_user_id)
                    host_game_id = int(raw_game_id)
                except (TypeError, ValueError):
                    non_numeric_id_type_detected = True
                    continue

                current_stream = StreamTuple(
                    status=one_raw_stream.get("type", None),
                    host_stream_id=host_stream_id,
                    host_user_id=host_user_id,
                    host_login=one_raw_stream.get("user_login", None),
                    host_display_name=one_raw_stream.get("user_name", None),
                    host_game_id=host_game_id,
                    viewers=one_raw_stream.get("viewer_count", None),
                    started_at=one_raw_stream.get("started_at", None),
                )

                # All fields are required, and string fields must fit their DB column
                if all(current_stream) and all(
                    len(getattr(current_stream, field)) <= max_len
                    for field, max_len in _STR_FIELD_MAX_LENGTHS.items()
                ):
                    streams.append(current_stream)

            cursor = raw_streams.get("pagination", {}).get("cursor")

            if not cursor or time.time() >= end_time_anchor:
                break

        # Normally, this will never happen, but it allows us to be notified if it happens.
        if non_numeric_id_type_detected:
            logger.warning("IMPORTANT: non-numeric ID field was detected in Helix API response while polling streams!")

        return streams, cursor
