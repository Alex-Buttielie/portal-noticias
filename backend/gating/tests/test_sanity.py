"""
Testes mínimos de sanidade do executor (não substituem a suíte formal do
tester) — implementation-contract.md run 20260902-1420-gating-free-premium.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIClient

from gating.models import FeatureLimit, FeatureLimitAlteracaoLog
from gating.services import (
    RecursoGatedException,
    exigir_feature,
    has_feature,
    obter_limite_numerico,
    plano_do_usuario,
)

pytestmark = pytest.mark.django_db

User = get_user_model()


def _usuario(papel="free", email=None):
    return User.objects.create_user(
        email=email or f"{papel}@example.com", password="senha123", papel=papel
    )


def test_has_feature_true_para_premium_com_registro_verdadeiro():
    FeatureLimit.objects.update_or_create(
        chave="personalizacao_avancada", plano="premium", defaults={"valor": "true"}
    )
    usuario = _usuario("premium")

    assert has_feature(usuario, "personalizacao_avancada") is True


def test_has_feature_false_para_free_sem_registro_correspondente():
    FeatureLimit.objects.update_or_create(
        chave="personalizacao_avancada", plano="premium", defaults={"valor": "true"}
    )
    usuario = _usuario("free")

    assert has_feature(usuario, "personalizacao_avancada") is False


def test_has_feature_fail_safe_para_chave_desconhecida():
    usuario_premium = _usuario("premium")

    assert has_feature(usuario_premium, "chave_que_nao_existe") is False


def test_has_feature_usuario_anonimo_tratado_como_free():
    FeatureLimit.objects.update_or_create(chave="publicidade", plano="free", defaults={"valor": "true"})

    assert has_feature(AnonymousUser(), "publicidade") is True
    assert plano_do_usuario(AnonymousUser()) == "free"


def test_admin_equivalente_a_premium():
    FeatureLimit.objects.update_or_create(
        chave="personalizacao_avancada", plano="premium", defaults={"valor": "true"}
    )
    usuario_admin = _usuario("admin")

    assert plano_do_usuario(usuario_admin) == "premium"
    assert has_feature(usuario_admin, "personalizacao_avancada") is True


def test_obter_limite_numerico_convencao_ilimitado():
    FeatureLimit.objects.update_or_create(
        chave="alertas_personalizados_limite", plano="premium", defaults={"valor": "-1"}
    )
    FeatureLimit.objects.update_or_create(
        chave="alertas_personalizados_limite", plano="free", defaults={"valor": "3"}
    )

    assert obter_limite_numerico(_usuario("premium"), "alertas_personalizados_limite") == -1
    assert obter_limite_numerico(_usuario("free"), "alertas_personalizados_limite") == 3


def test_obter_limite_numerico_valor_malformado_cai_no_default():
    FeatureLimit.objects.create(chave="chave_malformada", plano="free", valor="nao-e-um-numero")

    assert obter_limite_numerico(_usuario("free"), "chave_malformada", default=7) == 7


def test_exigir_feature_levanta_excecao_quando_nao_disponivel():
    usuario_free = _usuario("free")

    with pytest.raises(RecursoGatedException):
        exigir_feature(usuario_free, "resumo_personalizado")


def test_exigir_feature_nao_levanta_quando_disponivel():
    FeatureLimit.objects.update_or_create(
        chave="resumo_personalizado", plano="premium", defaults={"valor": "true"}
    )
    usuario_premium = _usuario("premium")

    exigir_feature(usuario_premium, "resumo_personalizado")  # não deve lançar


def test_alteracao_via_admin_gera_log_de_auditoria():
    """
    Simula o que `FeatureLimitAdmin.save_model` faz (sem passar pelo cliente
    HTTP do admin, que exigiria uma sessão autenticada de staff) — confirma
    o comportamento central: capturar o valor anterior antes de salvar o
    novo, e criar o log.
    """
    from gating.admin import FeatureLimitAdmin
    from django.contrib import admin as django_admin

    registro, _ = FeatureLimit.objects.update_or_create(
        chave="publicidade", plano="free", defaults={"valor": "true"}
    )
    admin_instance = FeatureLimitAdmin(FeatureLimit, django_admin.site)
    admin_user = _usuario("admin", email="admin-audit@example.com")

    class RequestFake:
        user = admin_user

    registro.valor = "false"
    admin_instance.save_model(RequestFake(), registro, form=None, change=True)

    log = FeatureLimitAlteracaoLog.objects.get(feature_limit_chave="publicidade", plano="free")
    assert log.valor_anterior == "true"
    assert log.valor_novo == "false"
    assert log.alterado_por_id == admin_user.id

    registro.refresh_from_db()
    assert registro.valor == "false"
    assert has_feature(_usuario("free", email="leitor@example.com"), "publicidade") is False


def test_endpoint_meus_recursos_funciona_sem_autenticacao():
    FeatureLimit.objects.update_or_create(chave="publicidade", plano="free", defaults={"valor": "true"})
    FeatureLimit.objects.update_or_create(chave="publicidade", plano="premium", defaults={"valor": "false"})
    client = APIClient()

    resposta = client.get("/api/gating/meus-recursos/")

    assert resposta.status_code == 200
    assert resposta.data["plano"] == "free"
    chaves = {recurso["chave"]: recurso for recurso in resposta.data["recursos"]}
    assert chaves["publicidade"]["disponivel"] is True


def test_endpoint_meus_recursos_para_usuario_premium():
    FeatureLimit.objects.update_or_create(chave="publicidade", plano="free", defaults={"valor": "true"})
    FeatureLimit.objects.update_or_create(chave="publicidade", plano="premium", defaults={"valor": "false"})
    usuario_premium = _usuario("premium", email="premium-recursos@example.com")
    client = APIClient()
    client.force_authenticate(user=usuario_premium)

    resposta = client.get("/api/gating/meus-recursos/")

    assert resposta.data["plano"] == "premium"
    chaves = {recurso["chave"]: recurso for recurso in resposta.data["recursos"]}
    assert chaves["publicidade"]["disponivel"] is False
