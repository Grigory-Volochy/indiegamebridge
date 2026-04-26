from django.core.management.base import BaseCommand, CommandError
from core.utils.igdb_api_client import IgdbApiClient


class Command(BaseCommand):
    help = 'Retrieves a list of games'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting to fetch games...")

        # TODO: fetch games and store them

        pass
