from datetime import datetime
from pathlib import Path
import json

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from core.utils.igdb_api_client import IgdbApiClient


class Command(BaseCommand):
    help = 'Retrieves a list of games'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting to fetch games...")

        try:
            # TODO: fetch games and store them
            with IgdbApiClient() as client:
                response_games = list(client.iter_games(10))
                # response_genres = list(client.get_genres(100))

            # TODO: insert/update into games table

            self.stdout.write(self.style.SUCCESS(f"Games fetched: {len(response_games)}"))

            # DEVELOPMENT ONLY: dump response into JSON file to use it for game model mapping
            # Path(f"{settings.BASE_DIR.parent}/data/igdb_games_raw_response.json").write_text(json.dumps(response_games, indent=2))
            # Path(f"{settings.BASE_DIR.parent}/data/igdb_genres_raw_response.json").write_text(json.dumps(response_genres, indent=2))

        except Exception as e:
            raise CommandError(f"Failed to fetch games: {e}")
