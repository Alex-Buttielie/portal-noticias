"""Adiciona marcador de reconciliação periódica dos validators RSS.

O marcador é um ``DateTimeField`` padrão, sem SQL específico de vendor; a
migração funciona tanto em SQLite quanto em PostgreSQL. Fontes existentes
começam com ``NULL`` e, portanto, fazem uma leitura incondicional na primeira
execução depois do deploy.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogo_noticias", "0012_fonterobo_http_validators"),
    ]

    operations = [
        migrations.AddField(
            model_name="fonterobo",
            name="ultima_revalidacao_completa",
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    "Última execução em que o feed foi validado sem depender de um "
                    "304; após o TTL de segurança a próxima leitura é incondicional."
                ),
                null=True,
            ),
        ),
    ]
