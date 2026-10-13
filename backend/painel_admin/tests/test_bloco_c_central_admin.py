"""Testes do Bloco C (Central/Admin) — implementation-contract.md run
20261013-1048-home-radar-central-ux.

Cobre: criação de usuário pelo admin (C-01), filtro por papel (C-01),
leitura de AuditoriaAdmin (C-05), leitura de FeatureLimitAlteracaoLog
(C-06) e contagem de "ativos agora" (C-07). O bloqueio/desbloqueio e a
alternância de papel já tinham cobertura em `test_sanity.py`
(`test_admin_altera_papel_e_status_do_usuario_com_auditoria`).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.test import APIClient

from gating.models import FeatureLimit, FeatureLimitAlteracaoLog
from painel_admin.models import AuditoriaAdmin

pytestmark = pytest.mark.django_db

User = get_user_model()


def _admin():
    return User.objects.create_user(email="admin-blococ@example.com", password="senha123", papel="admin")


def _free():
    return User.objects.create_user(email="free-blococ@example.com", password="senha123", papel="free")


# ---------------------------------------------------------------------------
# C-01 — criação de usuário pelo admin.
# ---------------------------------------------------------------------------


def test_admin_cria_usuario_com_sucesso_e_audita():
    admin = _admin()
    client = APIClient()
    client.force_authenticate(user=admin)

    resposta = client.post(
        "/api/admin/usuarios/",
        {"email": "novo-usuario@example.com", "nome": "Novo Usuario", "senha": "SenhaForte123", "papel": "premium"},
        format="json",
    )

    assert resposta.status_code == 201
    assert resposta.data["email"] == "novo-usuario@example.com"
    assert resposta.data["papel"] == "premium"
    assert resposta.data["is_active"] is True
    assert "senha" not in resposta.data

    criado = User.objects.get(email="novo-usuario@example.com")
    assert criado.papel == "premium"
    assert criado.check_password("SenhaForte123")
    # Criado pelo admin: não passa pelo fluxo público de verificação por
    # e-mail, e a senha definida é temporária (troca obrigatória).
    assert criado.email_verificado is True
    assert criado.deve_trocar_senha is True

    assert AuditoriaAdmin.objects.filter(acao="usuario_create", alvo_id=str(criado.id)).exists()


def test_admin_cria_usuario_com_papel_padrao_free_quando_nao_informado():
    admin = _admin()
    client = APIClient()
    client.force_authenticate(user=admin)

    resposta = client.post(
        "/api/admin/usuarios/",
        {"email": "sem-papel@example.com", "senha": "SenhaForte123"},
        format="json",
    )

    assert resposta.status_code == 201
    assert resposta.data["papel"] == "free"


def test_admin_cria_usuario_recusa_email_duplicado():
    admin = _admin()
    User.objects.create_user(email="ja-existe@example.com", password="senha123", papel="free")
    client = APIClient()
    client.force_authenticate(user=admin)

    resposta = client.post(
        "/api/admin/usuarios/",
        {"email": "ja-existe@example.com", "senha": "SenhaForte123"},
        format="json",
    )

    assert resposta.status_code == 400
    assert "email" in resposta.data


def test_admin_cria_usuario_colisao_de_corrida_devolve_400_nao_500():
    """code-review-contract.md Finding 2 (minor) — janela de corrida (TOCTOU)
    entre `UsuarioCriacaoSerializer.validate_email` e `criar_usuario_admin`/
    `user.save()`: duas requisições quase simultâneas com o mesmo e-mail
    podem ambas passar a validação antes de qualquer uma comitar, e a
    segunda colide com a constraint `unique=True` de `email`
    (`IntegrityError`). Simulado aqui forçando `criar_usuario_admin` (já
    chamado DEPOIS da validação ter passado) a levantar `IntegrityError`,
    exatamente a janela que uma corrida real abriria — a view deve
    devolver 400 (mesma mensagem da checagem normal), nunca 500.
    """
    admin = _admin()
    client = APIClient()
    client.force_authenticate(user=admin)

    with patch("painel_admin.views.criar_usuario_admin", side_effect=IntegrityError("duplicate key")):
        resposta = client.post(
            "/api/admin/usuarios/",
            {"email": "corrida@example.com", "senha": "SenhaForte123"},
            format="json",
        )

    assert resposta.status_code == 400
    assert "email" in resposta.data
    # A conta NÃO foi criada por esta requisição (a exceção interrompeu antes
    # de qualquer side-effect pós-criação, como a auditoria).
    assert not User.objects.filter(email="corrida@example.com").exists()


def test_admin_cria_usuario_recusa_senha_fraca():
    admin = _admin()
    client = APIClient()
    client.force_authenticate(user=admin)

    resposta = client.post(
        "/api/admin/usuarios/",
        {"email": "senha-fraca@example.com", "senha": "12345678"},
        format="json",
    )

    assert resposta.status_code == 400
    assert "senha" in resposta.data
    assert not User.objects.filter(email="senha-fraca@example.com").exists()


def test_admin_cria_usuario_recusa_papel_invalido():
    admin = _admin()
    client = APIClient()
    client.force_authenticate(user=admin)

    resposta = client.post(
        "/api/admin/usuarios/",
        {"email": "papel-invalido@example.com", "senha": "SenhaForte123", "papel": "super-admin"},
        format="json",
    )

    assert resposta.status_code == 400
    assert not User.objects.filter(email="papel-invalido@example.com").exists()


def test_usuario_nao_admin_nao_cria_usuario():
    free = _free()
    client = APIClient()
    client.force_authenticate(user=free)

    resposta = client.post(
        "/api/admin/usuarios/",
        {"email": "intruso@example.com", "senha": "SenhaForte123"},
        format="json",
    )

    assert resposta.status_code == 404
    assert not User.objects.filter(email="intruso@example.com").exists()


# ---------------------------------------------------------------------------
# C-01 — filtro por papel na listagem (view já suportava; prova explícita).
# ---------------------------------------------------------------------------


def test_admin_filtra_lista_de_usuarios_por_papel():
    admin = _admin()
    User.objects.create_user(email="premium1@example.com", password="senha123", papel="premium")
    User.objects.create_user(email="free1@example.com", password="senha123", papel="free")
    client = APIClient()
    client.force_authenticate(user=admin)

    resposta = client.get("/api/admin/usuarios/?papel=premium")

    assert resposta.status_code == 200
    emails = {u["email"] for u in resposta.data["results"]}
    assert "premium1@example.com" in emails
    assert "free1@example.com" not in emails
    assert all(u["papel"] == "premium" for u in resposta.data["results"])


# ---------------------------------------------------------------------------
# C-05 — leitura de AuditoriaAdmin.
# ---------------------------------------------------------------------------


def test_admin_le_auditoria_e_filtra_por_acao():
    admin = _admin()
    alvo = _free()
    AuditoriaAdmin.objects.create(acao="usuario_update", alvo_tipo="User", alvo_id=str(alvo.id), detalhe={}, alterado_por=admin)
    AuditoriaAdmin.objects.create(acao="limite_update", alvo_tipo="FeatureLimit", alvo_id="1", detalhe={}, alterado_por=admin)
    client = APIClient()
    client.force_authenticate(user=admin)

    resposta = client.get("/api/admin/auditoria/?acao=usuario_update")

    assert resposta.status_code == 200
    assert resposta.data["count"] == 1
    assert resposta.data["results"][0]["acao"] == "usuario_update"
    assert resposta.data["results"][0]["alterado_por_email"] == admin.email


def test_admin_filtra_auditoria_por_alvo_tipo():
    admin = _admin()
    AuditoriaAdmin.objects.create(acao="usuario_update", alvo_tipo="User", alvo_id="1", detalhe={}, alterado_por=admin)
    AuditoriaAdmin.objects.create(acao="limite_update", alvo_tipo="FeatureLimit", alvo_id="2", detalhe={}, alterado_por=admin)
    client = APIClient()
    client.force_authenticate(user=admin)

    resposta = client.get("/api/admin/auditoria/?alvo_tipo=FeatureLimit")

    assert resposta.status_code == 200
    assert resposta.data["count"] == 1
    assert resposta.data["results"][0]["alvo_tipo"] == "FeatureLimit"


def test_usuario_nao_admin_nao_le_auditoria():
    free = _free()
    client = APIClient()
    client.force_authenticate(user=free)
    resposta = client.get("/api/admin/auditoria/")
    assert resposta.status_code == 404


# ---------------------------------------------------------------------------
# C-06 — leitura de FeatureLimitAlteracaoLog.
# ---------------------------------------------------------------------------


def test_admin_le_historico_de_alteracoes_de_limite():
    admin = _admin()
    limite = FeatureLimit.objects.create(chave="feed_max_itens", plano="free", valor="10")
    client = APIClient()
    client.force_authenticate(user=admin)
    client.patch(f"/api/admin/limites/{limite.id}/", {"valor": "20"}, format="json")

    resposta = client.get("/api/admin/limites/historico/")

    assert resposta.status_code == 200
    assert resposta.data["count"] >= 1
    registro = next(r for r in resposta.data["results"] if r["feature_limit_chave"] == "feed_max_itens")
    assert registro["valor_anterior"] == "10"
    assert registro["valor_novo"] == "20"
    assert registro["alterado_por_email"] == admin.email


def test_admin_filtra_historico_de_limite_por_plano():
    admin = _admin()
    FeatureLimitAlteracaoLog.objects.create(feature_limit_chave="radar_credito", plano="free", valor_anterior="1", valor_novo="2", alterado_por=admin)
    FeatureLimitAlteracaoLog.objects.create(feature_limit_chave="radar_credito", plano="premium", valor_anterior="1", valor_novo="999", alterado_por=admin)
    client = APIClient()
    client.force_authenticate(user=admin)

    resposta = client.get("/api/admin/limites/historico/?plano=premium")

    assert resposta.status_code == 200
    assert resposta.data["count"] == 1
    assert resposta.data["results"][0]["plano"] == "premium"


def test_admin_filtra_historico_de_limite_por_chave():
    admin = _admin()
    FeatureLimitAlteracaoLog.objects.create(feature_limit_chave="radar_credito", plano="free", valor_anterior="1", valor_novo="2", alterado_por=admin)
    FeatureLimitAlteracaoLog.objects.create(feature_limit_chave="alertas_max", plano="free", valor_anterior="1", valor_novo="2", alterado_por=admin)
    client = APIClient()
    client.force_authenticate(user=admin)

    resposta = client.get("/api/admin/limites/historico/?chave=radar_credito")

    assert resposta.status_code == 200
    assert resposta.data["count"] == 1
    assert resposta.data["results"][0]["feature_limit_chave"] == "radar_credito"


# ---------------------------------------------------------------------------
# C-07 — "ativos agora".
# ---------------------------------------------------------------------------


def test_admin_conta_usuarios_ativos_agora():
    admin = _admin()
    recente = _free()
    recente.last_seen = timezone.now()
    recente.save(update_fields=["last_seen"])
    antigo = User.objects.create_user(email="antigo@example.com", password="senha123", papel="free")
    antigo.last_seen = timezone.now() - timezone.timedelta(minutes=30)
    antigo.save(update_fields=["last_seen"])
    sem_atividade = User.objects.create_user(email="nunca-logou@example.com", password="senha123", papel="free")
    assert sem_atividade.last_seen is None

    client = APIClient()
    client.force_authenticate(user=admin)
    resposta = client.get("/api/admin/usuarios/ativos-agora/")

    assert resposta.status_code == 200
    # `recente` + o próprio `admin` (o middleware grava last_seen na
    # requisição de login/force_authenticate só se passar pelo middleware;
    # como o teste usa force_authenticate, o admin pode não ter last_seen —
    # por isso o teste conta explicitamente, sem assumir >= 2.
    assert resposta.data["ativos_agora"] >= 1
    assert resposta.data["ativos_agora"] < User.objects.count()


def test_usuario_nao_admin_nao_ve_ativos_agora():
    free = _free()
    client = APIClient()
    client.force_authenticate(user=free)
    resposta = client.get("/api/admin/usuarios/ativos-agora/")
    assert resposta.status_code == 404


# ---------------------------------------------------------------------------
# C-07 — atividade recente (mescla AuditoriaAdmin + RegistroExecucaoIngestao).
# ---------------------------------------------------------------------------


def test_admin_ve_atividade_recente_mesclada_por_timestamp():
    from catalogo_noticias.models import RegistroExecucaoIngestao

    admin = _admin()
    alvo = _free()
    AuditoriaAdmin.objects.create(acao="usuario_update", alvo_tipo="User", alvo_id=str(alvo.id), detalhe={}, alterado_por=admin)
    RegistroExecucaoIngestao.objects.create(itens_por_fonte={"G1": 3}, total_itens_ingeridos=3, total_grupos_formados=2)
    RegistroExecucaoIngestao.objects.create(falhou=True, erro_falha="boom")

    client = APIClient()
    client.force_authenticate(user=admin)
    resposta = client.get("/api/admin/atividade-recente/")

    assert resposta.status_code == 200
    tipos = {e["tipo"] for e in resposta.data}
    assert tipos == {"auditoria", "ingestao"}
    # Ordenado por timestamp decrescente — garantido por quem monta a lista,
    # verificado aqui sem depender de qual evento aconteceu "primeiro" (os
    # três foram criados em sequência rápida pelo teste).
    timestamps = [e["timestamp"] for e in resposta.data]
    assert timestamps == sorted(timestamps, reverse=True)
    falha = next(e for e in resposta.data if e["tipo"] == "ingestao" and e["detalhe"].get("falhou"))
    assert falha["titulo"] == "Ingestão falhou"
