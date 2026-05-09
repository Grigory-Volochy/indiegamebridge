from django.db import models


class GameGenre(models.Model):
    host_genre_id = models.BigIntegerField(
        unique=True,
        help_text="An ID that identifies the game genre - defined by host; set once at time of creation;"
            " used as unique identifier for mapping data from IGDB API response."
    )

    host_name = models.CharField(
        max_length=64,
        help_text="Genre readable name - defined by host; updated on every pull if mismatched."
    )

    host_url = models.CharField(
        max_length=1024,
        help_text="Source URL to the dedicated page of the genre - defined by host."
    )

    slug = models.CharField(
        max_length=64,
        unique=True,
        help_text="Genre slug - defined by host; set once at time of creation; later use for internal URLs."
    )
