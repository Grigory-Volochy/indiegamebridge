from django.db import models


class CachedPage(models.Model):
    key = models.SlugField(
        max_length=64,
        unique=True,
        help_text="Stable identifier for this cached page (e.g. 'home')."
            " Used as the lookup key by the public API."
    )

    content = models.JSONField(
        help_text="Pre-rendered page payload returned to the frontend as-is."
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Time of the latest cache refresh for this page."
    )

    def __str__(self):
        return f"CachedPage: {self.key} (updated {self.updated_at:%Y-%m-%d %H:%M})"
