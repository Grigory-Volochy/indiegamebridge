import time
import concurrent.futures

from django.core.management.base import BaseCommand
from core.utils.twitch_api_client import TwitchApiClient


class Command(BaseCommand):
    help = 'Retrieves a list of streams'

    # Combined Helix request budget across all languages per poll round.
    # Together with min_time_per_poll_round this keeps the steady-state
    # request rate comfortably below the Helix 800/min limit.
    total_max_requests_per_poll_round = 0
    min_time_per_poll_round = 0

    # Actual limit of requests allowed per poll round for each language in the queue.
    # Recalculated every time when a poll is completed for a language in the queue.
    allowed_requests_per_language_poll_round = 0

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting to fetch streams...")

        # TODO: later use values from admin settings
        languages = ["en", "de", "fr"]

        # Used to calculate limit of allowed requests per language
        # Initially all the languages are in the queue
        nof_current_languages = len(languages)

        # Per-language cap on Helix requests within a single poll round.
        # Bounds the in-memory batch each language thread accumulates before the DataBase write.
        # TODO: later use value from admin settings
        max_requests_per_language_poll_round = 100

        # TODO: later use value from admin settings
        self.total_max_requests_per_poll_round = 200

        # TODO: later use value from admin settings
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
        # TODO: later use value from admin settings
        total_max_poll_time = 100

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
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"{label} failed: {e}"))
                self.stdout.write(self.style.SUCCESS(f"Completed - {label}"))

                # When poll for certain language is finished, then the max value of available requests for each language should be recalculated,
                # because the limits allocated to the language are now released and available for remaining languages in the queue
                nof_current_languages -= 1
                if nof_current_languages > 0:
                    self.allowed_requests_per_language_poll_round = min(round(self.total_max_requests_per_poll_round / nof_current_languages), max_requests_per_language_poll_round)

        self.stdout.write(self.style.SUCCESS(f"Total streams collected: {total_collected}"))

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

        collected = 0
        with TwitchApiClient() as client:
            cursor = None
            while True:
                round_started_at = time.time()

                response_streams, cursor = client.iter_streams(
                    language=the_language,
                    end_time_anchor=end_time_anchor,
                    max_requests=self.allowed_requests_per_language_poll_round,
                    cursor=cursor
                )

                collected += len(response_streams)
                self.stdout.write(self.style.SUCCESS(f"Streams fetched per poll round: {len(response_streams)}"))

                for one_stream in response_streams:
                    # TODO: handle insert/update for each stream
                    pass

                if response_streams:
                    # TODO: write streams to DataBase
                    pass

                # Normal end of the language polling
                if not response_streams or not cursor:
                    break

                # Hit the global deadline. Either this language has more streams than the
                # current configuration can drain in one cron interval, or Helix is responding
                # slowly. If this fires regularly, raise the cron interval and total_max_poll_time in step.
                if time.time() >= end_time_anchor:
                    self.stdout.write(self.style.WARNING(f"Stream polling terminated as time limit exceeded. Language: {the_language}"))
                    # TODO: make entry for admin dashboard analytics with details about the issue
                    break

                # Respect Helix rate limits
                time_to_sleep = round(self.min_time_per_poll_round - (time.time() - round_started_at))
                if time_to_sleep > 0:
                    time.sleep(time_to_sleep)
                else:
                    # TODO: make entry for admin dashboard analytics that round takes more time than the current time limit for single round
                    self.stdout.write(self.style.WARNING(f"Stream poll round exceeded current time limit for single round. Language: {the_language}"))

        return collected
