from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from apps.streams.models.streamer_profile import StreamerProfile


class Stream(models.Model):
    class Status(models.TextChoices):
        LIVE = "live", "Live"
        OFFLINE = "offline", "Offline"

    streamer_profile = models.ForeignKey(
        StreamerProfile,
        on_delete=models.CASCADE,
        related_name="streams"
    )

    status = models.CharField(
        max_length=16,
        default=Status.LIVE,
        choices=Status.choices,
        help_text="Whether the stream is currently live or offline - defined by host"
    )

    host_stream_id = models.BigIntegerField(
        help_text="An ID that identifies the stream - defined by host"
    )

    language = models.CharField(
        max_length=2,
        help_text="ISO 639-1 two-letter language code"
    )

    max_viewers = models.PositiveIntegerField(
        default=0,
        db_index=True,
        help_text="Max viewers observed across all snapshots."
            " Populated when the stream goes offline; live streams stay at 0."
    )

    started_at = models.DateTimeField(
        help_text="Time when stream started - defined by host"
    )

    finished_at = models.DateTimeField(
        help_text="Time when stream finished. While the stream is live, this is updated on every poll"
            " to act as last seen alive. Once the stream goes offline, the value is finalized and stops updating."
    )

    snapshots = models.JSONField(
        blank=True,
        default=list,
        help_text="Rolling list of per-poll observations appended while the stream is live."
            " Each entry is a dict with short keys: g=host_game_id, v=viewers, t=poll_timestamp_unix."
    )

    host_game_ids = ArrayField(
        models.BigIntegerField(),
        blank=True,
        default=list,
        help_text="Distinct game IDs observed across snapshots."
            " Populated when the stream goes offline; supports fast lookup by game."
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["streamer_profile", "host_stream_id"], name="unique_host_stream"),
        ]
        indexes = [
            GinIndex(fields=["host_game_ids"], name="stream_host_game_ids_gin"),
        ]

    def __str__(self):
        return f"Stream ID: {self.host_stream_id} | Streamer ID: {self.streamer_profile_id} | Status: {self.status}"
