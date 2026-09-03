from django.db import migrations


def seed(apps, schema_editor):
    FeatureLimit = apps.get_model("gating", "FeatureLimit")
    FeatureLimit.objects.get_or_create(
        chave="radar_avancado",
        plano="free",
        defaults={"valor": "false", "descricao": "Evolução temporal de tendências do Radar."},
    )
    FeatureLimit.objects.get_or_create(
        chave="radar_avancado",
        plano="premium",
        defaults={"valor": "true", "descricao": "Evolução temporal de tendências do Radar."},
    )


def remover(apps, schema_editor):
    FeatureLimit = apps.get_model("gating", "FeatureLimit")
    FeatureLimit.objects.filter(chave="radar_avancado").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("gating", "0002_seed_feature_limits"),
    ]

    operations = [
        migrations.RunPython(seed, remover),
    ]
