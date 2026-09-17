"""
Mercado Pago em sandbox (`MercadoPagoGatewayProvider` + webhook): tudo com
`requests` mockado — nenhum teste bate na rede de verdade.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient

from assinatura.models import HistoricoPagamento, Plan, Subscription
from assinatura.providers.payment import (
    GATEWAY_MERCADOPAGO,
    MercadoPagoGatewayProvider,
    ProvedorPagamentoError,
    obter_gateway_pagamento,
)

pytestmark = pytest.mark.django_db

User = get_user_model()


def _usuario(email="mp@example.com"):
    return User.objects.create_user(email=email, password="senha123", papel="free")


def _plano():
    return Plan.objects.create(nome="Premium Mensal", preco=Decimal("29.90"), duracao_dias=30, ativo=True)


def _resposta(status_code=201, corpo=None):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = corpo or {}
    mock.text = str(corpo)
    return mock


@override_settings(ASSINATURA_MP_ACCESS_TOKEN="TEST-dummy", ASSINATURA_MP_SANDBOX=True)
def test_factory_registra_mercadopago():
    gateway = obter_gateway_pagamento("mercadopago")

    assert isinstance(gateway, MercadoPagoGatewayProvider)
    assert GATEWAY_MERCADOPAGO == "mercadopago"


@override_settings(ASSINATURA_MP_ACCESS_TOKEN="")
def test_sem_token_falha_alto():
    with pytest.raises(ProvedorPagamentoError, match="ACCESS_TOKEN"):
        MercadoPagoGatewayProvider()


@override_settings(ASSINATURA_MP_ACCESS_TOKEN="TEST-dummy", ASSINATURA_MP_SANDBOX=True)
def test_criar_cobranca_devolve_pendente_e_checkout_sandbox():
    usuario = _usuario()
    plano = _plano()
    subscription = Subscription.objects.create(
        user=usuario, plan=plano, status=Subscription.STATUS_PAGAMENTO_PENDENTE,
        preco_cobrado=plano.preco, duracao_dias_no_momento=plano.duracao_dias,
    )
    payload = {"id": "pre-123", "sandbox_init_point": "https://sandbox.mercadopago.com/checkout/pre-123"}

    with patch("requests.post", return_value=_resposta(201, payload)) as post:
        resultado = MercadoPagoGatewayProvider().criar_cobranca(subscription, plano.preco)

    assert resultado.referencia_gateway == "pre-123"
    assert resultado.status == "pendente"
    assert resultado.url_checkout == "https://sandbox.mercadopago.com/checkout/pre-123"
    corpo_enviado = post.call_args.kwargs["json"]
    assert corpo_enviado["payer_email"] == "mp@example.com"
    assert corpo_enviado["auto_recurring"]["currency_id"] == "BRL"


@override_settings(ASSINATURA_MP_ACCESS_TOKEN="TEST-dummy")
def test_assinar_plano_mp_fica_pendente_com_checkout():
    from assinatura import services

    usuario = _usuario(email="mp-assinar@example.com")
    plano = _plano()
    payload = {"id": "pre-456", "sandbox_init_point": "https://sandbox.mercadopago.com/checkout/pre-456"}

    with patch("requests.post", return_value=_resposta(201, payload)):
        subscription = services.assinar_plano(usuario, plano, MercadoPagoGatewayProvider())

    assert subscription.status == Subscription.STATUS_PAGAMENTO_PENDENTE
    assert subscription.gateway_referencia == "pre-456"
    assert subscription.checkout_url == "https://sandbox.mercadopago.com/checkout/pre-456"


@override_settings(ASSINATURA_MP_ACCESS_TOKEN="TEST-dummy")
def test_consultar_status_mapeia_estados():
    gateway = MercadoPagoGatewayProvider()

    with patch("requests.get", return_value=_resposta(200, {"status": "authorized"})):
        assert gateway.consultar_status("pre-1") == "aprovado"
    with patch("requests.get", return_value=_resposta(200, {"status": "pending"})):
        assert gateway.consultar_status("pre-1") == "pendente"
    with patch("requests.get", return_value=_resposta(200, {"status": "cancelled"})):
        assert gateway.consultar_status("pre-1") == "recusado"


@override_settings(ASSINATURA_MP_ACCESS_TOKEN="TEST-dummy")
def test_webhook_confirma_assinatura_pendente():
    usuario = _usuario(email="mp-webhook@example.com")
    plano = _plano()
    subscription = Subscription.objects.create(
        user=usuario, plan=plano, status=Subscription.STATUS_PAGAMENTO_PENDENTE,
        preco_cobrado=plano.preco, duracao_dias_no_momento=plano.duracao_dias,
        gateway_referencia="pre-789",
    )
    HistoricoPagamento.objects.create(
        subscription=subscription, valor=plano.preco,
        status=HistoricoPagamento.STATUS_PENDENTE, referencia_gateway="pre-789",
    )

    with patch("requests.get", return_value=_resposta(200, {"status": "authorized"})):
        resposta = APIClient().post("/api/assinatura/webhook/mercadopago/?topic=preapproval&id=pre-789")

    assert resposta.status_code == 200
    subscription.refresh_from_db()
    assert subscription.status == Subscription.STATUS_ATIVA


@override_settings(ASSINATURA_MP_ACCESS_TOKEN="TEST-dummy")
def test_webhook_desconhecido_responde_200_sem_efeito():
    with patch("requests.get", return_value=_resposta(200, {"status": "authorized"})):
        resposta = APIClient().post("/api/assinatura/webhook/mercadopago/?topic=preapproval&id=pre-inexistente")

    assert resposta.status_code == 200
