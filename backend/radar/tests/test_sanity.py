from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from catalogo_noticias.models import NewsItem
from gating.models import FeatureLimit
from radar import services

pytestmark = pytest.mark.django_db

User = get_user_model()


def _item(titulo, categoria, cidade="", estado="", pais="", url=None):
    return NewsItem.objects.create(
        titulo=titulo,
        resumo_proprio="Resumo",
        conteudo_bruto="Bruto",
        url_fonte_original=url or f"https://g1/{titulo}",
        nome_fonte="G1",
        categoria=categoria,
        pais=pais,
        estado=estado,
        cidade=cidade,
        status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
    )


def test_tendencias_sem_filtro_agrega_por_categoria():
    _item("A", "esportes")
    _item("B", "esportes")
    _item("C", "politica")

    resultado = services.tendencias()

    assuntos = {a["categoria"]: a["numero_noticias"] for a in resultado["assuntos_em_alta"]}
    assert assuntos["esportes"] == 2
    assert assuntos["politica"] == 1
    assert "COBERTURA jornalística" in resultado["aviso_metodologia"]


def test_tendencias_filtra_por_cidade():
    _item("A", "esportes", cidade="São Paulo")
    _item("B", "esportes", cidade="Rio de Janeiro")

    resultado = services.tendencias(cidade="São Paulo")

    total = sum(a["numero_noticias"] for a in resultado["assuntos_em_alta"])
    assert total == 1


def test_item_pendente_nao_conta_no_radar():
    NewsItem.objects.create(
        titulo="Pendente",
        resumo_proprio="R",
        conteudo_bruto="B",
        url_fonte_original="https://g1/pendente-radar",
        nome_fonte="G1",
        categoria="esportes",
        status_revisao=NewsItem.STATUS_PENDENTE,
    )
    resultado = services.tendencias()
    assert resultado["assuntos_em_alta"] == []


def test_salvar_localidade_e_idempotente():
    usuario = User.objects.create_user(email="radar@example.com", password="senha123", papel="free")
    services.salvar_localidade(usuario, cidade="São Paulo")
    services.salvar_localidade(usuario, cidade="São Paulo")
    assert services.localidades_salvas(usuario).count() == 1


def test_radar_avancado_gated_para_free():
    from gating.services import has_feature

    usuario_free = User.objects.create_user(email="free-radar@example.com", password="senha123", papel="free")
    usuario_premium = User.objects.create_user(
        email="premium-radar@example.com", password="senha123", papel="premium"
    )
    FeatureLimit.objects.update_or_create(chave="radar_avancado", plano="free", defaults={"valor": "false"})
    FeatureLimit.objects.update_or_create(chave="radar_avancado", plano="premium", defaults={"valor": "true"})

    assert has_feature(usuario_free, "radar_avancado") is False
    assert has_feature(usuario_premium, "radar_avancado") is True
