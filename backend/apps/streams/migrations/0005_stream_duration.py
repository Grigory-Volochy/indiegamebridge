from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    # AddIndexConcurrently must run outside a transaction.
    # AddField with a constant default is metadata-only on PostgreSQL >= 11,
    # so it stays fast regardless and is safe to run in this mode.
    atomic = False

    dependencies = [
        ("streams", "0004_status_category_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="stream",
            name="duration",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Stream length in seconds, derived from finished_at - started_at."
                    " Populated when the stream goes offline; live streams stay at 0.",
            ),
        ),
        AddIndexConcurrently(
            model_name="stream",
            index=models.Index(fields=["duration"], name="stream_duration_idx"),
        ),
    ]
