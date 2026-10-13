from decimal import Decimal

from django.db import migrations


def seed(apps, schema_editor):
    """
    M-07 (run 20261012-1806-monetizacao-sprint1) — BRD §6 prevê semestral
    (R$20) e anual (R$30). Hoje só existem `free` e `premium` (anual)
    ativos no banco; esta migration cadastra o semestral que falta, sem
    tocar nos planos já existentes. `get_or_create` por nome: idempotente,
    não duplica se já tiver sido criado manualmente pelo admin.
    """
    Plan = apps.get_model("assinatura", "Plan")
    Plan.objects.get_or_create(
        nome="Premium Semestral",
        defaults={
            "preco": Decimal("20.00"),
            "duracao_dias": 180,
            "ativo": True,
        },
    )


def remover(apps, schema_editor):
    Plan = apps.get_model("assinatura", "Plan")
    Plan.objects.filter(nome="Premium Semestral").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("assinatura", "0002_subscription_assinatura_uma_em_andamento_por_usuario"),
    ]

    operations = [
        migrations.RunPython(seed, remover),
    ]
