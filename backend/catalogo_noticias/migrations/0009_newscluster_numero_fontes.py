"""
Run 20260923-1216-p1-feed-cache-indices (P1-1): denormaliza
`NewsCluster.numero_fontes_distintas` como coluna.

- `AddField` com default 1 (clusters sempre têm >= 1 item por construção).
- `backfill_numero_fontes`: COUNT DISTINCT de `nome_fonte` por cluster para
  as linhas pré-existentes. Idempotente (recomputa e só grava quando
  diverge — rodar N vezes dá o mesmo resultado). Reverso sem efeito.
"""

from django.db import migrations, models


def backfill_numero_fontes(apps, schema_editor):
    NewsCluster = apps.get_model("catalogo_noticias", "NewsCluster")
    NewsItem = apps.get_model("catalogo_noticias", "NewsItem")
    for cluster in NewsCluster.objects.all().iterator(chunk_size=500):
        total = (
            NewsItem.objects.filter(cluster_id=cluster.pk)
            .values("nome_fonte")
            .distinct()
            .count()
        )
        if total != cluster.numero_fontes_distintas:
            NewsCluster.objects.filter(pk=cluster.pk).update(
                numero_fontes_distintas=total
            )


def reverso_sem_efeito(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalogo_noticias", "0008_seed_fontes_padrao"),
    ]

    operations = [
        migrations.AddField(
            model_name="newscluster",
            name="numero_fontes_distintas",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.RunPython(backfill_numero_fontes, reverso_sem_efeito),
    ]
