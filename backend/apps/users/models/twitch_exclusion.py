from django.db import models


class TwitchExclusion(models.Model):
    """If a user wants to opt out, the user's Twitch ID is added to the table.
    During the streams poll, the ID will be used to exclude the related streams.
    """
    twitch_id = models.BigIntegerField(
        unique=True,
        help_text="User's Twitch ID"
    )

    optout_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Time when the user requested the opt out."
    )
