from django.db import models

from apps.streams.models.stream import Stream


class StreamSnapshot(models.Model):
    stream = models.ForeignKey(
        Stream,
        on_delete=models.CASCADE,
        related_name='snapshots'
    )

    viewers = models.PositiveIntegerField(
        help_text="Current number of viewers",
    )

    shot_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Time at which the snapshot was made"
    )

    host_game_id = models.CharField(
        max_length=64,
        help_text="The game ID currently being streamed - defined by host"
    )

    def __str__(self):
        return f'Stream ID: {self.stream_id} | Time: {self.shot_at} | Viewers: {self.viewers}'
