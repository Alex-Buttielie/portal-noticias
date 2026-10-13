"""
C-07 (`last_seen` / "ativos agora") e C-01 (criação de usuário pelo admin,
delegada a `identidade.services.criar_usuario_admin`) —
implementation-contract.md run 20261013-1048-home-radar-central-ux, Bloco C.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from identidade.services import (
    LAST_SEEN_THROTTLE_SEGUNDOS,
    atualizar_last_seen,
    contar_usuarios_ativos_agora,
    criar_usuario_admin,
)

pytestmark = pytest.mark.django_db

User = get_user_model()


def _usuario(**kwargs):
    defaults = {"email": "usuario-last-seen@example.com", "password": "senha123", "papel": "free"}
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


# ---------------------------------------------------------------------------
# `atualizar_last_seen` — serviço puro (sem HTTP), throttle.
# ---------------------------------------------------------------------------


def test_atualizar_last_seen_grava_quando_nunca_visto():
    user = _usuario()
    assert user.last_seen is None

    atualizar_last_seen(user)

    user.refresh_from_db()
    assert user.last_seen is not None


def test_atualizar_last_seen_nao_grava_update_antes_do_throttle():
    user = _usuario()
    primeiro = timezone.now() - timezone.timedelta(seconds=5)
    user.last_seen = primeiro
    user.save(update_fields=["last_seen"])

    atualizar_last_seen(user)

    user.refresh_from_db()
    # Menos de LAST_SEEN_THROTTLE_SEGUNDOS desde `primeiro` — não deve ter
    # mudado (restrição de performance: nunca um UPDATE por requisição).
    assert user.last_seen == primeiro


def test_atualizar_last_seen_grava_apos_passar_o_throttle():
    user = _usuario()
    antigo = timezone.now() - timezone.timedelta(seconds=LAST_SEEN_THROTTLE_SEGUNDOS + 5)
    user.last_seen = antigo
    user.save(update_fields=["last_seen"])

    atualizar_last_seen(user)

    user.refresh_from_db()
    assert user.last_seen > antigo


# ---------------------------------------------------------------------------
# Middleware — integração via requisição HTTP real (APIClient roda a stack
# completa de middleware, incluindo `AtualizarUltimoAcessoMiddleware`).
# ---------------------------------------------------------------------------


def test_middleware_atualiza_last_seen_em_requisicao_autenticada():
    user = _usuario(email="autenticado-middleware@example.com")
    assert user.last_seen is None
    client = APIClient()
    client.force_authenticate(user=user)

    resposta = client.get("/api/preferencias-cookies/")

    assert resposta.status_code == 200
    user.refresh_from_db()
    assert user.last_seen is not None


def test_middleware_nao_atualiza_last_seen_para_requisicao_anonima():
    client = APIClient()
    resposta = client.get("/api/preferencias-cookies/")
    assert resposta.status_code == 401
    # Nenhum usuário para atualizar — só garante que não quebra/erra.


def test_middleware_respeita_throttle_entre_duas_requisicoes_seguidas():
    user = _usuario(email="duas-requisicoes@example.com")
    client = APIClient()
    client.force_authenticate(user=user)

    client.get("/api/preferencias-cookies/")
    user.refresh_from_db()
    primeiro_valor = user.last_seen
    assert primeiro_valor is not None

    client.get("/api/preferencias-cookies/")
    user.refresh_from_db()
    # Duas requisições na mesma fração de segundo — bem dentro do throttle
    # de 60s, não deve ter gerado um segundo UPDATE com timestamp diferente.
    assert user.last_seen == primeiro_valor


# ---------------------------------------------------------------------------
# `contar_usuarios_ativos_agora`.
# ---------------------------------------------------------------------------


def test_contar_usuarios_ativos_agora_considera_so_a_janela():
    dentro = _usuario(email="dentro-da-janela@example.com")
    dentro.last_seen = timezone.now()
    dentro.save(update_fields=["last_seen"])

    fora = _usuario(email="fora-da-janela@example.com")
    fora.last_seen = timezone.now() - timezone.timedelta(minutes=10)
    fora.save(update_fields=["last_seen"])

    nunca = _usuario(email="nunca-ativo@example.com")
    assert nunca.last_seen is None

    assert contar_usuarios_ativos_agora(janela_minutos=5) == 1


def test_contar_usuarios_ativos_agora_janela_configuravel():
    usuario = _usuario(email="janela-configuravel@example.com")
    usuario.last_seen = timezone.now() - timezone.timedelta(minutes=8)
    usuario.save(update_fields=["last_seen"])

    assert contar_usuarios_ativos_agora(janela_minutos=5) == 0
    assert contar_usuarios_ativos_agora(janela_minutos=10) == 1


# ---------------------------------------------------------------------------
# `criar_usuario_admin` — serviço puro chamado por
# `painel_admin.views.UsuarioListView.post` (a validação de e-mail/senha é
# testada no nível de integração HTTP em
# `painel_admin/tests/test_bloco_c_central_admin.py`; aqui testamos o
# serviço isoladamente).
# ---------------------------------------------------------------------------


def test_criar_usuario_admin_define_flags_corretas():
    user = criar_usuario_admin(email="criado-pelo-admin@example.com", senha="SenhaForte123", nome="Fulano", papel="premium")

    assert user.pk is not None
    assert user.email == "criado-pelo-admin@example.com"
    assert user.nome == "Fulano"
    assert user.papel == "premium"
    assert user.is_active is True
    assert user.email_verificado is True
    assert user.deve_trocar_senha is True
    assert user.check_password("SenhaForte123")
    assert user.consentimento_aceito_em is None


def test_criar_usuario_admin_pode_criar_ja_bloqueado():
    user = criar_usuario_admin(email="criado-bloqueado@example.com", senha="SenhaForte123", is_active=False)
    assert user.is_active is False


def test_criar_usuario_admin_papel_padrao_free():
    user = criar_usuario_admin(email="criado-sem-papel@example.com", senha="SenhaForte123")
    assert user.papel == User.PAPEL_FREE
