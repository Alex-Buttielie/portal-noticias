"""
Testes mínimos de sanidade do executor (não substituem a suíte formal do
tester) — implementation-contract.md run 20260902-1426-assinatura-premium.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from assinatura import services
from assinatura.models import (
    AssinaturaMudancaEstadoLog,
    ConfiguracaoAssinatura,
    HistoricoPagamento,
    Plan,
    Subscription,
)
from assinatura.providers.payment import PaymentGatewayProvider, ResultadoCobranca

pytestmark = pytest.mark.django_db

User = get_user_model()


def _usuario(papel="free", email=None):
    return User.objects.create_user(email=email or f"{papel}@example.com", password="senha123", papel=papel)


def _plano(nome="Premium Semestral", preco="20.00", duracao_dias=180, ativo=True):
    return Plan.objects.create(nome=nome, preco=Decimal(preco), duracao_dias=duracao_dias, ativo=ativo)


class ProviderSempreAprova(PaymentGatewayProvider):
    def criar_cobranca(self, subscription, valor):
        return ResultadoCobranca(referencia_gateway="teste-aprovado", status="aprovado")

    def consultar_status(self, referencia_gateway):
        return "aprovado"

    def cancelar(self, referencia_gateway):
        return None


class ProviderSempreRecusa(PaymentGatewayProvider):
    def criar_cobranca(self, subscription, valor):
        return ResultadoCobranca(referencia_gateway="teste-recusado", status="recusado")

    def consultar_status(self, referencia_gateway):
        return "recusado"

    def cancelar(self, referencia_gateway):
        return None


def test_plano_ativo_aparece_na_listagem_publica():
    _plano(nome="Ativo", ativo=True)
    _plano(nome="Inativo", ativo=False)
    client = APIClient()

    resposta = client.get("/api/assinatura/planos/")

    nomes = {plano["nome"] for plano in resposta.data}
    assert nomes == {"Ativo"}


def test_assinar_com_gateway_aprovando_ativa_na_hora_e_promove_usuario():
    plano = _plano()
    usuario = _usuario("free")

    subscription = services.assinar_plano(usuario, plano, payment_gateway=ProviderSempreAprova())

    usuario.refresh_from_db()
    assert subscription.status == Subscription.STATUS_ATIVA
    assert subscription.inicio is not None
    assert subscription.vencimento is not None
    assert usuario.papel == "premium"
    assert HistoricoPagamento.objects.filter(subscription=subscription, status="aprovado").exists()


def test_assinar_com_gateway_recusando_nao_promove_usuario_mas_inicia_grace_period():
    plano = _plano()
    usuario = _usuario("free")

    subscription = services.assinar_plano(usuario, plano, payment_gateway=ProviderSempreRecusa())

    usuario.refresh_from_db()
    assert subscription.status == Subscription.STATUS_INADIMPLENTE
    assert subscription.grace_period_termina_em is not None
    assert usuario.papel == "free"


def test_pagamento_recusado_nao_derruba_acesso_premium_ja_ativo():
    plano = _plano()
    usuario = _usuario("free")
    subscription = services.assinar_plano(usuario, plano, payment_gateway=ProviderSempreAprova())

    subscription = services.processar_pagamento_recusado(subscription)
    usuario.refresh_from_db()

    assert subscription.status == Subscription.STATUS_INADIMPLENTE
    assert usuario.papel == "premium"  # grace period — não derruba na hora


def test_grace_period_expirado_derruba_para_free():
    plano = _plano()
    usuario = _usuario("free")
    subscription = services.assinar_plano(usuario, plano, payment_gateway=ProviderSempreAprova())
    subscription = services.processar_pagamento_recusado(subscription)

    # empurra o grace period para o passado, simulando tempo decorrido
    subscription.grace_period_termina_em = timezone.now() - timedelta(days=1)
    subscription.save(update_fields=["grace_period_termina_em"])

    resultado = services.processar_vencimentos_e_grace_periods(payment_gateway=ProviderSempreAprova())

    subscription.refresh_from_db()
    usuario.refresh_from_db()
    assert resultado["expiradas"] == 1
    assert subscription.status == Subscription.STATUS_EXPIRADA
    assert usuario.papel == "free"


def test_grace_period_ainda_nao_vencido_nao_muda_nada():
    plano = _plano()
    usuario = _usuario("free")
    subscription = services.assinar_plano(usuario, plano, payment_gateway=ProviderSempreAprova())
    subscription = services.processar_pagamento_recusado(subscription)  # grace period no futuro

    resultado = services.processar_vencimentos_e_grace_periods(payment_gateway=ProviderSempreAprova())

    subscription.refresh_from_db()
    assert resultado["expiradas"] == 0
    assert subscription.status == Subscription.STATUS_INADIMPLENTE


def test_cancelar_mantem_acesso_premium_ate_vencimento():
    plano = _plano()
    usuario = _usuario("free")
    subscription = services.assinar_plano(usuario, plano, payment_gateway=ProviderSempreAprova())

    subscription = services.cancelar_assinatura(subscription)
    usuario.refresh_from_db()

    assert subscription.status == Subscription.STATUS_CANCELADA
    assert subscription.renovacao_automatica is False
    assert usuario.papel == "premium"  # ainda dentro do período já pago


def test_cancelada_com_vencimento_passado_e_encerrada_e_derruba_para_free():
    plano = _plano()
    usuario = _usuario("free")
    subscription = services.assinar_plano(usuario, plano, payment_gateway=ProviderSempreAprova())
    subscription = services.cancelar_assinatura(subscription)

    subscription.vencimento = timezone.now() - timedelta(days=1)
    subscription.save(update_fields=["vencimento"])

    resultado = services.processar_vencimentos_e_grace_periods(payment_gateway=ProviderSempreAprova())

    subscription.refresh_from_db()
    usuario.refresh_from_db()
    assert resultado["encerradas"] == 1
    assert subscription.status == Subscription.STATUS_ENCERRADA
    assert usuario.papel == "free"


def test_toda_transicao_gera_log_de_auditoria():
    plano = _plano()
    usuario = _usuario("free")
    subscription = services.assinar_plano(usuario, plano, payment_gateway=ProviderSempreAprova())

    logs = list(AssinaturaMudancaEstadoLog.objects.filter(subscription=subscription).order_by("criado_em"))
    estados = [log.estado_novo for log in logs]

    assert Subscription.STATUS_PAGAMENTO_PENDENTE in estados
    assert Subscription.STATUS_ATIVA in estados


def test_nao_permite_segunda_assinatura_concorrente():
    plano = _plano()
    usuario = _usuario("free")
    services.assinar_plano(usuario, plano, payment_gateway=ProviderSempreAprova())

    with pytest.raises(services.AssinaturaJaExisteError):
        services.assinar_plano(usuario, plano, payment_gateway=ProviderSempreAprova())


def test_cancelar_ou_expirar_nunca_apaga_o_usuario():
    plano = _plano()
    usuario = _usuario("free")
    subscription = services.assinar_plano(usuario, plano, payment_gateway=ProviderSempreAprova())
    services.cancelar_assinatura(subscription)

    assert User.objects.filter(pk=usuario.pk).exists()


def test_endpoint_assinar_via_api():
    plano = _plano()
    usuario = _usuario("free", email="api-assinar@example.com")
    client = APIClient()
    client.force_authenticate(user=usuario)

    resposta = client.post("/api/assinatura/assinar/", {"plan_id": plano.id}, format="json")

    assert resposta.status_code == 201
    assert resposta.data["status"] in (Subscription.STATUS_ATIVA, Subscription.STATUS_PAGAMENTO_PENDENTE)


def test_endpoint_cancelar_requer_autenticacao():
    client = APIClient()

    resposta = client.post("/api/assinatura/cancelar/")

    assert resposta.status_code in (401, 403)


def test_endpoint_historico_pagamentos_isola_por_usuario():
    plano = _plano()
    usuario_a = _usuario("free", email="hist-a@example.com")
    usuario_b = _usuario("free", email="hist-b@example.com")
    services.assinar_plano(usuario_a, plano, payment_gateway=ProviderSempreAprova())

    client = APIClient()
    client.force_authenticate(user=usuario_b)
    resposta = client.get("/api/assinatura/historico-pagamentos/")

    assert resposta.data == []


def test_configuracao_assinatura_e_singleton():
    config1 = services.obter_configuracao()
    config2 = services.obter_configuracao()

    assert config1.pk == config2.pk == 1
    assert ConfiguracaoAssinatura.objects.count() == 1
