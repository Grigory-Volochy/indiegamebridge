from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    # AddIndexConcurrently must run outside a transaction.
    # AddField with a constant default is metadata-only on PostgreSQL >= 11,
    # so it stays fast regardless and is safe to run in this mode.
    atomic = False

    dependencies = [
        ("streams", "0005_stream_duration"),
    ]

    operations = [
        migrations.AddField(
            model_name="stream",
            name="genre_ids",
            field=ArrayField(
                models.BigIntegerField(),
                blank=True,
                default=list,
                help_text="Distinct GameGenre.host_genre_id values across this stream's games."
                    " Denormalized from host_game_ids -> Game.genres so genre-filtered search"
                    " can hit a small RHS array instead of resolving genres -> games -> overlap."
                    " Refreshed when IGDB enrichment adds genre links (see enrich_igdb_games).",
            ),
        ),
        AddIndexConcurrently(
            model_name="stream",
            index=GinIndex(fields=["genre_ids"], name="stream_genre_ids_gin"),
        ),
    ]
