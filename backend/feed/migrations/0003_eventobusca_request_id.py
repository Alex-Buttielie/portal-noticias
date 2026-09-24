"""Adiciona request_id idempotente ao evento de busca (P2-3b/P2-4)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feed", "0002_rename_feed_evento_query_n_8f7c1a_idx_feed_evento_query_n_a300f3_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="eventobusca",
            name="request_id",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
    ]
