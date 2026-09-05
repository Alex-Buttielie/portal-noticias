"""
Fábrica de gateway plugável (`obter_gateway_pagamento`, setting
`ASSINATURA_PAYMENT_GATEWAY_PROVIDER`) — ideia incorporada do protótipo
`testes-ia` (troca de gateway por env, sem mudar código cliente).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.test import override_settings

from assinatura.providers.payment import (
    GATEWAY_MANUAL,
    ManualPaymentGatewayProvider,
    obter_gateway_pagamento,
)


def test_default_usa_manual():
    gateway = obter_gateway_pagamento("manual")

    assert isinstance(gateway, ManualPaymentGatewayProvider)


def test_none_le_do_settings():
    with override_settings(ASSINATURA_PAYMENT_GATEWAY_PROVIDER="manual"):
        assert isinstance(obter_gateway_pagamento(None), ManualPaymentGatewayProvider)


def test_nome_e_case_insensitive_e_tolera_espacos():
    assert isinstance(obter_gateway_pagamento("  MANUAL  "), ManualPaymentGatewayProvider)


def test_nome_desconhecido_falha_alto():
    with pytest.raises(ValueError, match="desconhecido"):
        obter_gateway_pagamento("mercadopago-ainda-nao-implementado")


def test_manual_aprova_cobranca_sem_rede(db):
    from django.contrib.auth import get_user_model

    from assinatura import services
    from assinatura.models import Plan, Subscription

    User = get_user_model()
    user = User.objects.create_user(email="factory@example.com", password="senha123", papel="free")
    plan = Plan.objects.create(nome="Semestral", preco=Decimal("20.00"), duracao_dias=180, ativo=True)

    # Sem injetar gateway: usa a fábrica (settings de teste = "manual").
    subscription = services.assinar_plano(user, plan)

    assert subscription.status == Subscription.STATUS_ATIVA
    assert GATEWAY_MANUAL == "manual"
