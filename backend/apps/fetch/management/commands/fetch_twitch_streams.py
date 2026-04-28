import time
import concurrent.futures

from django.core.management.base import BaseCommand, CommandError
from core.utils.twitch_api_client import TwitchApiClient


class Command(BaseCommand):
    help = 'Retrieves a list of streams'

    TOTAL_MAX_REQUESTS_PER_RUN = 10 # 100 (Helix limit is 800/min)
    TIME_SPAN_BETWEEN_RUNS = 20.0 # 60
    MAX_RUNS = 3 # 10

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting to fetch streams...")

        # TODO: later use values from admin settings
        languages = ["en", "de"]
        
        # Limit total number of requests per run for each language - the bottle neck is not only Helix rate limits but memory usage too to keep all the entries before write them to DataBase
        max_requests_per_run = round(self.TOTAL_MAX_REQUESTS_PER_RUN / len(languages))

        # Poll each language in a separate thread
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(languages)) as executor:
            # Schedule poll for each language and store the future objects
            future_to_poll = {
                executor.submit(
                    self._poll_streams_by_lang,
                    the_language=one_language,
                    max_requests_per_run=max_requests_per_run,
                ): f"Fetch streams for language: {one_language}"
                for one_language in languages
            }

            for future in concurrent.futures.as_completed(future_to_poll):
                label = future_to_poll[future]
                try:
                    future.result()
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"{label} failed: {e}"))
                self.stdout.write(self.style.SUCCESS(f"Completed - {label}"))

    def _poll_streams_by_lang(self, the_language, max_requests_per_run):
        with TwitchApiClient() as client:
            cursor = None
            for _ in range(self.MAX_RUNS):
                response_streams, cursor = client.iter_streams(
                    language=the_language,
                    max_requests=max_requests_per_run,
                    cursor=cursor,
                )
                self.stdout.write(self.style.SUCCESS(f"Streams fetched per run: {len(response_streams)}"))
                for one_stream in response_streams:
                    # TODO: handle insert/update for each stream
                    self.stdout.write(f"user_id: {one_stream.user_id}")

                if response_streams:
                    # TODO: write streams to DataBase
                    pass

                if not response_streams or not cursor:
                    break
                time.sleep(self.TIME_SPAN_BETWEEN_RUNS)
