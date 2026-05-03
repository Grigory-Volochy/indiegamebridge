import logging
import time
from datetime import timedelta
import concurrent.futures

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.utils.twitch_api_client import TwitchApiClient
from apps.streams.models import StreamerProfile, Stream, StreamSnapshot

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Retrieves a list of streams"

    # Combined Helix request budget across all languages per poll round.
    # Together with min_time_per_poll_round this keeps the steady-state
    # request rate comfortably below the Helix 800/min limit.
    total_max_requests_per_poll_round = 0
    min_time_per_poll_round = 0

    # Actual limit of requests allowed per poll round for each language in the queue.
    # Recalculated every time when a poll is completed for a language in the queue.
    allowed_requests_per_language_poll_round = 0

    def handle(self, *args, **kwargs):
        logger.info("Starting to fetch streams...")

        # TODO LATER: use values from admin settings
        languages = ["en", "de", "fr"]

        # Used to calculate limit of allowed requests per language
        # Initially all the languages are in the queue
        nof_current_languages = len(languages)

        # Per-language cap on Helix requests within a single poll round.
        # Bounds the in-memory batch each language thread accumulates before the DataBase write.
        # TODO LATER: use value from admin settings
        max_requests_per_language_poll_round = 100

        # Cron tick interval in minutes.
        # TODO LATER: use value from admin settings
        cron_interval_minutes = 15

        # TODO LATER: use value from admin settings
        self.total_max_requests_per_poll_round = 200

        # TODO LATER: use value from admin settings
        self.min_time_per_poll_round = 20

        # Per-language request budget for this poll round, taking the lower of:
        # - the global Helix budget split evenly across languages (rate-limit safety)
        # - the per-language cap (memory safety: streams accumulate in RAM until the DataBase write)
        if nof_current_languages > 0:
            self.allowed_requests_per_language_poll_round = min(round(self.total_max_requests_per_poll_round / nof_current_languages), max_requests_per_language_poll_round)

        # Safety cap on total polling time for the whole command.
        # Polling normally finishes on its own once each language's cursor is exhausted;
        # this fuse forces the command to stop before the next cron tick fires,
        # preventing two invocations from overlapping if a round is unusually slow.
        # TODO LATER: use value from admin settings
        total_max_poll_time = 900

        end_time_anchor = time.time() + total_max_poll_time

        total_collected = 0

        # Poll each language in a separate thread
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(languages)) as executor:
            # Schedule poll for each language and store the future objects
            future_to_poll = {
                executor.submit(
                    self._poll_streams_by_lang,
                    the_language=one_language,
                    end_time_anchor=end_time_anchor,
                ): f"Fetch streams for language: {one_language}"
                for one_language in languages
            }

            for future in concurrent.futures.as_completed(future_to_poll):
                label = future_to_poll[future]
                try:
                    total_collected += future.result()
                except Exception:
                    logger.exception("%s failed", label)
                logger.info("Completed - %s", label)

                # When poll for certain language is finished, then the max value of available requests for each language should be recalculated,
                # because the limits allocated to the language are now released and available for remaining languages in the queue
                nof_current_languages -= 1
                if nof_current_languages > 0:
                    self.allowed_requests_per_language_poll_round = min(round(self.total_max_requests_per_poll_round / nof_current_languages), max_requests_per_language_poll_round)

            # For every storing stream with live status and finished_at older than 10 cron time span for the polling, update status to offline
            stale_stream_threshold = timezone.now() - timedelta(minutes=4 * cron_interval_minutes)
            stale_stream_count = Stream.objects.filter(
                status=Stream.Status.LIVE,
                finished_at__lt=stale_stream_threshold,
            ).update(status=Stream.Status.OFFLINE)

        logger.info("Total streams collected: %s", total_collected)
        logger.info("Marked %s stale streams as offline", stale_stream_count)

    def _poll_streams_by_lang(self, the_language, end_time_anchor):
        """Polls Twitch streams for one language until the cursor is exhausted or the deadline is hit.

        Runs sequential poll rounds, each issuing up to
        `self.allowed_requests_per_language_poll_round` paginated requests via
        `TwitchApiClient.iter_streams`. Sleeps the remainder of
        `self.min_time_per_poll_round` between rounds to keep the request rate
        under the Helix rate limit.

        Args:
            the_language (str): Streams language tag using an ISO 639-1 two-letter code.
            end_time_anchor (float): Soft global deadline as a `time.time()` value.
                Checked after each poll round; if exceeded, polling stops and
                whatever was collected so far is returned.

        Returns:
            int: Total number of streams collected for this language across all rounds.
        """

        with TwitchApiClient() as client:
            dedup_ids = set()
            cursor = None
            while True:
                round_started_at = time.time()

                response_streams, cursor = client.iter_streams(
                    language=the_language,
                    end_time_anchor=end_time_anchor,
                    max_requests=self.allowed_requests_per_language_poll_round,
                    cursor=cursor
                )

                logger.info("Unfiltered streams fetched per poll round: %s | Language: %s", len(response_streams), the_language)

                # Insert/update data
                with transaction.atomic():
                    for one_stream in response_streams:

                        # Avoid duplicated streams due to possible page shifts during the poll
                        if one_stream.host_stream_id in dedup_ids:
                            continue
                        dedup_ids.add(one_stream.host_stream_id)

                        profile, _ = StreamerProfile.objects.get_or_create(
                            host=StreamerProfile.Host.TWITCH,
                            host_user_id=one_stream.host_user_id,
                            defaults={
                                "host_login": one_stream.host_login,
                                "host_display_name": one_stream.host_display_name,
                            }
                        )

                        # Update rarely changed fields on mismatch
                        if (profile.host_login, profile.host_display_name) != (one_stream.host_login, one_stream.host_display_name):
                            profile.host_login = one_stream.host_login
                            profile.host_display_name = one_stream.host_display_name
                            profile.save(update_fields=["host_login", "host_display_name"])

                        stream, _ = Stream.objects.update_or_create(
                            streamer_profile=profile,
                            host_stream_id=one_stream.host_stream_id,
                            defaults={
                                "status": Stream.Status.LIVE,
                                "language": the_language,
                                "started_at": one_stream.started_at,
                                "finished_at": timezone.now(),
                            }
                        )

                        StreamSnapshot.objects.create(
                            stream=stream,
                            viewers=one_stream.viewers,
                            host_game_id=one_stream.host_game_id,
                        )

                # Normal end of the language polling
                if not response_streams or not cursor:
                    break

                # Hit the global deadline. Either this language has more streams than the
                # current configuration can drain in one cron interval, or Helix is responding
                # slowly. If this fires regularly, raise the cron interval and total_max_poll_time in step.
                if time.time() >= end_time_anchor:
                    logger.warning("Stream polling terminated as time limit exceeded. Language: %s", the_language)
                    # TODO LATER: make entry for admin dashboard analytics with details about the issue
                    break

                # Respect Helix rate limits
                execution_time = round(time.time() - round_started_at)
                time_to_sleep = self.min_time_per_poll_round - execution_time
                logger.info("Execution time: %ss | Safe execution time is >= %ss | Language: %s", execution_time, self.min_time_per_poll_round, the_language)
                if time_to_sleep > 0:
                    time.sleep(time_to_sleep)

        return len(dedup_ids)
