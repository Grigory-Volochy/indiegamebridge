from django.core.management.base import BaseCommand, CommandError
from core.utils.twitch_api_client import TwitchApiClient


class Command(BaseCommand):
    help = 'Retrieves a list of streams'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting to fetch streams...")

        try:
            # TODO: retrieve game IDs from games table (should be populated by fetch_igdb_games)
            game_ids = []

            if not game_ids:
                self.stdout.write(self.style.WARNING("No game IDs available; skipping stream fetch."))
                return

            # Fetch streams
            with TwitchApiClient() as client:
                response_streams = list(client.iter_streams(game_ids=game_ids))

            # TODO: insert/update into streams table

            self.stdout.write(self.style.SUCCESS(f"Streams fetched: {len(response_streams)}"))

        except Exception as e:
            raise CommandError(f"Failed to fetch streams: {e}")
