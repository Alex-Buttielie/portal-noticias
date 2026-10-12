"""
Testes de `AfinidadeView` (GET `/api/feed/afinidade/`): agrega
`InteracaoNoticia` tipo "read" do usuário por categoria, ponderada por
recência (meia-vida de `AfinidadeView.MEIA_VIDA_DIAS` dias); 403 para
usuário sem a feature `personalizacao_avancada`.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from gating.models import ConfiguracaoSistema, FeatureLimit

from .. import views as feed_views
from ..models import InteracaoNoticia

pytestmark = pytest.mark.django_db

User = get_user_model()


def _garante_feature_personalizacao():
    # Ver comentário equivalente em assinatura/tests/test_objetivo_assinatura.py.
    ConfiguracaoSistema.objects.update_or_create(pk=1, defaults={"premium_ativo": True})
    FeatureLimit.objects.update_or_create(
        chave="personalizacao_avancada", plano="free", defaults={"valor": "false"}
    )
    FeatureLimit.objects.update_or_create(
        chave="personalizacao_avancada", plano="premium", defaults={"valor": "true"}
    )


def _cria_interacao(user, categoria, dias_atras, tipo=InteracaoNoticia.TIPO_READ):
    interacao = InteracaoNoticia.objects.create(
        user=user, tipo=tipo, entry_tipo="item", categoria=categoria,
    )
    if dias_atras:
        InteracaoNoticia.objects.filter(pk=interacao.pk).update(
            criado_em=timezone.now() - timedelta(days=dias_atras)
        )
    return interacao


def test_usuario_free_recebe_403(fabrica_usuario_premium):
    _garante_feature_personalizacao()
    usuario_free = User.objects.create_user(email="free-afinidade@example.com", password="senha123")

    client = APIClient()
    client.force_authenticate(user=usuario_free)
    resposta = client.get("/api/feed/afinidade/")

    assert resposta.status_code == 403


def test_premium_sem_leituras_devolve_vazio(fabrica_usuario_premium):
    _garante_feature_personalizacao()
    usuario_premium = fabrica_usuario_premium()

    client = APIClient()
    client.force_authenticate(user=usuario_premium)
    resposta = client.get("/api/feed/afinidade/")

    assert resposta.status_code == 200
    assert resposta.data["categorias"] == {}
    assert resposta.data["objetivo_assinatura"] == ""


def test_leituras_recentes_pesam_mais_que_leituras_antigas(fabrica_usuario_premium):
    _garante_feature_personalizacao()
    usuario_premium = fabrica_usuario_premium()

    _cria_interacao(usuario_premium, "tecnologia", dias_atras=0)
    _cria_interacao(usuario_premium, "esportes", dias_atras=feed_views.AfinidadeView.MEIA_VIDA_DIAS * 3)

    client = APIClient()
    client.force_authenticate(user=usuario_premium)
    resposta = client.get("/api/feed/afinidade/")

    categorias = resposta.data["categorias"]
    assert categorias["tecnologia"] > categorias["esportes"]
    assert categorias["tecnologia"] == pytest.approx(1.0, abs=0.01)


def test_leituras_fora_da_tipo_read_nao_contam(fabrica_usuario_premium):
    _garante_feature_personalizacao()
    usuario_premium = fabrica_usuario_premium()

    _cria_interacao(usuario_premium, "cultura", dias_atras=0, tipo=InteracaoNoticia.TIPO_VIEW)

    client = APIClient()
    client.force_authenticate(user=usuario_premium)
    resposta = client.get("/api/feed/afinidade/")

    assert resposta.data["categorias"] == {}


def test_objetivo_assinatura_aparece_na_resposta(fabrica_usuario_premium):
    _garante_feature_personalizacao()
    usuario_premium = fabrica_usuario_premium()
    usuario_premium.objetivo_assinatura = "entender tecnologia pro trabalho"
    usuario_premium.save(update_fields=["objetivo_assinatura"])

    client = APIClient()
    client.force_authenticate(user=usuario_premium)
    resposta = client.get("/api/feed/afinidade/")

    assert resposta.data["objetivo_assinatura"] == "entender tecnologia pro trabalho"
