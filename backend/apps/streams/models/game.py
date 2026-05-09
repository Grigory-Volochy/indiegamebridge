from django.db import models


class Game(models.Model):
    genres = models.ManyToManyField(
        "streams.GameGenre",
        related_name="games",
        blank=True,
    )

    host_game_id = models.BigIntegerField(
        unique=True,
        help_text="An ID that identifies the game - defined by host; set once at time of creation;"
            " used as unique identifier for mapping data from IGDB API response."
    )

    host_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Game readable name - defined by host. Empty until enriched from IGDB."
    )

    host_summary = models.TextField(
        blank=True,
        default="",
        help_text="Game description - defined by host. Empty until enriched from IGDB."
    )

    host_url = models.CharField(
        max_length=1024,
        blank=True,
        default="",
        help_text="Source URL to the dedicated page of the game - defined by host. Empty until enriched from IGDB."
    )
