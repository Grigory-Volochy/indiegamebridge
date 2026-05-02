from django.contrib.postgres.fields import ArrayField
from django.db import models


class Stream(models.Model):
    class Status(models.TextChoices):
        LIVE = 'live', 'Live'
        OFFLINE = 'offline', 'Offline'

    class Host(models.TextChoices):
        TWITCH = 'twitch', 'Twitch'

    status = models.CharField(
        max_length=16,
        default=Status.LIVE,
        choices=Status.choices,
        help_text="Whether the stream is currently live or offline - defined by host"
    )

    host_stream_id = models.CharField(
        max_length=64,
        help_text="An ID that identifies the stream - defined by host"
    )

    host_user_id = models.CharField(
        max_length=64,
        help_text="The ID of the user that is broadcasting the stream - defined by host"
    )

    host = models.CharField(
        max_length=16,
        choices=Host.choices,
        help_text="Host name"
    )

    language = models.CharField(
        max_length=2,
        help_text="ISO 639-1 two-letter language code"
    )

    host_game_ids = ArrayField(
        models.CharField(max_length=64),
        blank=True,
        default=list,
        help_text="The game IDs detected by snapshots"
    )

    max_viewers = models.PositiveIntegerField(
        help_text="Max viewers number detected by snapshots"
    )

    avg_viewers = models.PositiveIntegerField(
        help_text="Average viewers number calculated via snapshots"
    )

    started_at = models.DateTimeField(
        help_text="Time when stream started - defined by host"
    )

    finished_at = models.DateTimeField(
        help_text="Time when stream finished. While the stream is live, this is updated on every poll"
            " to act as 'last seen alive'. Once the stream goes offline, the value is finalized and stops updating."
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['host', 'host_stream_id'], name='unique_host_stream'),
        ]

    def __str__(self):
        return f'Stream ID: {self.host_stream_id} | Streamer ID: {self.host_user_id} | Status: {self.status}'
