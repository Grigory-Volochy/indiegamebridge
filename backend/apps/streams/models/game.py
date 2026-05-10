from django.db import models


class Game(models.Model):
    class Category(models.TextChoices):
        # For newly detected game ID we insert 'placeholder' with the category 'new' - at this point we do not know if the
        # game ID has a valid IGDB game ID. We need the 'placeholder' to be assigned for the stream that introduced it during poll.
        NEW = "new", "New"

        # To get 'isgame' category the game must to have non-empty 'igdb_id' during data enrichment via Helix API.
        ISGAME = "isgame", "Is Game"

        # If game does not have 'igdb_id' during data enrichment via Helix API, then it is non-game Helix API category.
        # We still keep the game entry for future usage (other streams also may use this Helix API category).
        ISNONGAME = "isnongame", "Is non-Game"

    genres = models.ManyToManyField(
        "streams.GameGenre",
        related_name="games",
        blank=True,
    )

    host_game_id = models.BigIntegerField(
        unique=True,
        help_text="An unique identifier for mapping data from Helix API response - defined by Helix API response."
            " Set once at time of creation (the 'get streams' endpoint)."
    )

    igdb_game_id = models.BigIntegerField(
        blank=True,
        default=0,
        help_text="An unique identifier for mapping data from IGDB API response - defined by Helix API response."
            " Empty until updated during game data enrichment from Helix API (the 'get games' endpoint) - empty if not exists."
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

    category = models.CharField(
        max_length=16,
        default=Category.NEW,
        choices=Category.choices,
        help_text="Current status of the game entry. 'New' on insertion, and either 'Is Game' or 'Is non-Game' on data enrichment."
    )
