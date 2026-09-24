"""Persiste validators HTTP por fonte RSS (P2-2).

Os campos são strings porque ``Last-Modified`` é um header HTTP e deve ser
reenviado exatamente como recebido. A migration é DDL padrão do Django,
portanto aplica igualmente em SQLite e PostgreSQL; não há SQL específico de
vendor.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogo_noticias", "0011_newsitem_busca_trgm"),
    ]

    operations = [
        migrations.AddField(
            model_name="fonterobo",
            name="etag",
            field=models.CharField(blank=True, default="", max_length=512),
        ),
        migrations.AddField(
            model_name="fonterobo",
            name="last_modified",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
    ]
