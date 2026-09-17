from django.db import migrations, models


def seed(apps, schema_editor):
    ConfiguracaoSistema = apps.get_model("gating", "ConfiguracaoSistema")
    # Flag nasce DESMARCADA: premium liberado a todos, assinaturas pausadas.
    ConfiguracaoSistema.objects.get_or_create(pk=1, defaults={"premium_ativo": False})


def remover(apps, schema_editor):
    ConfiguracaoSistema = apps.get_model("gating", "ConfiguracaoSistema")
    ConfiguracaoSistema.objects.filter(pk=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("gating", "0003_seed_radar_avancado"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfiguracaoSistema",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("premium_ativo", models.BooleanField(default=False, help_text="Quando marcado, os planos Premium passam a valer e as funcionalidades voltam a ser limitadas por plano. Quando desmarcado, tudo fica liberado e assinar é pausado.")),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "configuração do sistema",
                "verbose_name_plural": "configuração do sistema",
            },
        ),
        migrations.RunPython(seed, remover),
    ]
