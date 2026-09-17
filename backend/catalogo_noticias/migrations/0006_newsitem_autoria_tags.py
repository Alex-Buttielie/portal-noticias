"""FRENTE 3 — autoria/tags para busca por autor/colunista/tags.

Best-effort (blank=True, default vazio): nunca bloqueia a ingestão nem
inventa dado — o pipeline preenche quando o RSS informa.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalogo_noticias", "0005_newsitem_conteudo_completo"),
    ]

    operations = [
        migrations.AddField(
            model_name="newsitem",
            name="autor",
            field=models.CharField(
                blank=True,
                help_text="Autor/colunista creditado na fonte — vazio quando não informado.",
                max_length=200,
            ),
        ),
        migrations.AddField(
            model_name="newsitem",
            name="tags",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Ex.: ['eleições', 'senado']. Lista de strings, minúsculas.",
            ),
        ),
    ]
