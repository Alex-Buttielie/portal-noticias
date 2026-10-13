from decimal import Decimal

from django.db import migrations


def seed(apps, schema_editor):
    """
    M-07 (run 20261012-1806-monetizacao-sprint1) — BRD §6 prevê semestral
    (R$20) e anual (R$30). Hoje só existem `free` e `premium` (anual)
    ativos no banco; esta migration cadastra o semestral que falta, sem
    tocar nos planos já existentes. `get_or_create` por nome: idempotente,
    não duplica se já tiver sido criado manualmente pelo admin.

    Premissa (Finding 2, minor, do code-review-contract.md desta run):
    `Plan.nome` NÃO tem `unique=True` (`assinatura/models.py`), então este
    `get_or_create` só é idempotente para correspondência EXATA do nome
    "Premium Semestral" — não detecta um plano semestral pré-existente
    cadastrado manualmente com nome diferente (ex.: "Semestral Premium",
    "Premium semestral" em outra caixa). Não há evidência, no código ou
    nas migrations deste repositório, de que qualquer plano com
    "semestral" no nome tenha sido cadastrado antes desta migration — esta
    migration é o primeiro ponto do histórico de código que introduz esse
    nome. Ainda assim, esta checagem NÃO confirma o estado real dos bancos
    de dev/homolog/prod (fora do alcance desta migration/código-fonte); se
    o time tiver o hábito de cadastrar planos manualmente pelo admin antes
    de aplicar migrations de seed, confirme com
    `Plan.objects.filter(nome__icontains="semestral")` antes do deploy, ou
    adicione essa checagem aqui.
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
