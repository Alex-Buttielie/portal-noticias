"""
Testes de `ObjetivoAssinaturaView` (GET/PUT `/api/assinatura/objetivo/`):
só usuário Premium (via `gating.personalizacao_avancada`) pode ler/gravar
o objetivo da assinatura; usuário free recebe 403.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from gating.models import ConfiguracaoSistema, FeatureLimit

pytestmark = pytest.mark.django_db

User = get_user_model()


def _garante_feature_personalizacao():
    # `premium_ativo=True` é o que faz o gating valer de verdade — sem
    # isso, `premium_liberado_geral()` libera tudo pra todo mundo (ver
    # `gating/tests/test_sanity.py`, fixture `_premium_ativo_para_gating`,
    # que só se aplica dentro daquele módulo).
    ConfiguracaoSistema.objects.update_or_create(pk=1, defaults={"premium_ativo": True})
    FeatureLimit.objects.update_or_create(
        chave="personalizacao_avancada", plano="free", defaults={"valor": "false"}
    )
    FeatureLimit.objects.update_or_create(
        chave="personalizacao_avancada", plano="premium", defaults={"valor": "true"}
    )


def test_usuario_free_recebe_403(fabrica_usuario_premium):
    _garante_feature_personalizacao()
    usuario_free = User.objects.create_user(email="free-objetivo@example.com", password="senha123")

    client = APIClient()
    client.force_authenticate(user=usuario_free)
    resposta = client.get("/api/assinatura/objetivo/")

    assert resposta.status_code == 403


def test_usuario_premium_grava_e_le_o_objetivo(fabrica_usuario_premium):
    _garante_feature_personalizacao()
    usuario_premium = fabrica_usuario_premium()

    client = APIClient()
    client.force_authenticate(user=usuario_premium)

    resposta = client.put(
        "/api/assinatura/objetivo/", {"objetivo": "acompanhar economia pra decidir um investimento"}, format="json"
    )
    assert resposta.status_code == 200
    assert resposta.data["objetivo"] == "acompanhar economia pra decidir um investimento"
    assert resposta.data["atualizado_em"] is not None

    usuario_premium.refresh_from_db()
    assert usuario_premium.objetivo_assinatura == "acompanhar economia pra decidir um investimento"

    resposta_get = client.get("/api/assinatura/objetivo/")
    assert resposta_get.status_code == 200
    assert resposta_get.data["objetivo"] == "acompanhar economia pra decidir um investimento"


def test_objetivo_e_truncado_em_500_caracteres(fabrica_usuario_premium):
    _garante_feature_personalizacao()
    usuario_premium = fabrica_usuario_premium()

    client = APIClient()
    client.force_authenticate(user=usuario_premium)

    texto_longo = "a" * 600
    resposta = client.put("/api/assinatura/objetivo/", {"objetivo": texto_longo}, format="json")

    # O serializer já rejeita (400) antes de chegar no service, que também trunca.
    assert resposta.status_code == 400
