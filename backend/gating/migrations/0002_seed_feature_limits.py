from django.db import migrations

# Valores de referência, NÃO a decisão final de produto (spec
# gating-free-premium.md, "Fora de escopo" / "Questões em aberto") — ponto
# de partida editável via Django admin (gating.FeatureLimit).
FEATURE_LIMITS_SEED = [
    # (chave, valor_free, valor_premium, descricao)
    ("publicidade", "true", "false", "Exibir publicidade no feed/telas (BRD seção 7)."),
    ("personalizacao_avancada", "false", "true", "Personalização avançada de feed/temas/canais."),
    ("alertas_personalizados_limite", "3", "-1", "Quantidade de alertas personalizados (-1 = ilimitado)."),
    ("resumo_personalizado", "false", "true", "Resumo personalizado entregue no horário escolhido."),
    ("newsletter_personalizada", "false", "true", "Newsletter personalizada por interesse."),
    ("historico_avancado", "false", "true", "Histórico avançado de acontecimentos acompanhados."),
    ("distribuicao_personalizada", "false", "true", "Distribuição/canal de entrega personalizado."),
]


def seed_feature_limits(apps, schema_editor):
    FeatureLimit = apps.get_model("gating", "FeatureLimit")
    for chave, valor_free, valor_premium, descricao in FEATURE_LIMITS_SEED:
        FeatureLimit.objects.get_or_create(
            chave=chave, plano="free", defaults={"valor": valor_free, "descricao": descricao}
        )
        FeatureLimit.objects.get_or_create(
            chave=chave, plano="premium", defaults={"valor": valor_premium, "descricao": descricao}
        )


def remove_feature_limits(apps, schema_editor):
    FeatureLimit = apps.get_model("gating", "FeatureLimit")
    chaves = [item[0] for item in FEATURE_LIMITS_SEED]
    FeatureLimit.objects.filter(chave__in=chaves).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("gating", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_feature_limits, remove_feature_limits),
    ]
