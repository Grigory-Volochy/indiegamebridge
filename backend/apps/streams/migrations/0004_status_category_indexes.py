from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    # CONCURRENTLY index builds cannot run inside a transaction.
    atomic = False

    dependencies = [
        ("streams", "0003_game_category_game_igdb_game_id_and_more"),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="stream",
            index=models.Index(
                fields=["finished_at"],
                name="stream_live_finished_at_idx",
                condition=models.Q(status="live"),
            ),
        ),
        AddIndexConcurrently(
            model_name="game",
            index=models.Index(
                fields=["category"],
                name="game_category_idx",
            ),
        ),
    ]
