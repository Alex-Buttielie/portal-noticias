"""
H-07 (run 20261013-1048-home-radar-central-ux, Bloco H): `resumo_e_fallback`
em `FeedEntrySerializer`/`SecaoHomeSerializer`/`FonteDetalheSerializer` —
calculado em `feed/services.py` a partir de
`catalogo_noticias.providers.fallback_local.origem_fallback_local` sobre as
`tags` do `NewsItem`, NUNCA por comparação de string com o texto fixo
(`_FRASE_SEM_RESUMO_EDITORIAL`, que esta run não altera).
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from catalogo_noticias.models import NewsCluster, NewsItem
from catalogo_noticias.providers.fallback_local import marcadores_tags

pytestmark = pytest.mark.django_db


def _news_item(**kwargs):
    defaults = dict(
        titulo="Noticia de teste",
        resumo_proprio="Resumo autoral de teste, escrito por um humano.",
        conteudo_bruto="Conteudo bruto de teste.",
        url_fonte_original="https://g1/teste-fallback",
        nome_fonte="G1",
        categoria="geral",
        status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
    )
    defaults.update(kwargs)
    return NewsItem.objects.create(**defaults)


def test_feed_lista_marca_resumo_e_fallback_true_quando_item_tem_tag_de_fallback():
    _news_item(
        url_fonte_original="https://g1/fallback-1",
        resumo_proprio="Noticia de teste Resumo editorial nao gerado pelo portal...",
        tags=marcadores_tags("sem_credencial"),
    )
    client = APIClient()

    resposta = client.get("/api/feed/")

    assert resposta.status_code == 200
    assert resposta.data["results"][0]["resumo_e_fallback"] is True


def test_feed_lista_marca_resumo_e_fallback_false_quando_item_nao_tem_a_tag():
    _news_item(url_fonte_original="https://g1/sem-fallback-1")
    client = APIClient()

    resposta = client.get("/api/feed/")

    assert resposta.status_code == 200
    assert resposta.data["results"][0]["resumo_e_fallback"] is False


def test_detalhe_item_marca_resumo_e_fallback_por_fonte():
    item = _news_item(
        url_fonte_original="https://g1/fallback-detalhe",
        resumo_proprio="Noticia de teste Resumo editorial nao gerado pelo portal...",
        tags=marcadores_tags("timeout"),
    )
    client = APIClient()

    resposta = client.get(f"/api/feed/item/{item.id}/")

    assert resposta.status_code == 200
    assert resposta.data["fontes"][0]["resumo_e_fallback"] is True


def test_detalhe_cluster_distingue_fallback_por_fonte_dentro_do_mesmo_cluster():
    cluster = NewsCluster.objects.create(
        titulo_acontecimento="Evento coberto por 2 fontes", numero_fontes_distintas=2
    )
    _news_item(
        url_fonte_original="https://g1/cluster-fallback",
        nome_fonte="G1",
        resumo_proprio="Noticia de teste Resumo editorial nao gerado pelo portal...",
        tags=marcadores_tags("erro_http"),
        cluster=cluster,
    )
    _news_item(
        url_fonte_original="https://uol/cluster-sem-fallback",
        nome_fonte="UOL",
        resumo_proprio="Resumo autoral real escrito por um jornalista da UOL.",
        cluster=cluster,
    )
    client = APIClient()

    resposta = client.get(f"/api/feed/cluster/{cluster.id}/")

    assert resposta.status_code == 200
    por_fonte = {f["nome_fonte"]: f["resumo_e_fallback"] for f in resposta.data["fontes"]}
    assert por_fonte == {"G1": True, "UOL": False}


def test_home_secoes_propaga_resumo_e_fallback():
    _news_item(
        url_fonte_original="https://g1/home-fallback",
        resumo_proprio="Noticia de teste Resumo editorial nao gerado pelo portal...",
        tags=marcadores_tags("conteudo_insuficiente"),
    )
    client = APIClient()

    resposta = client.get("/api/feed/home/")

    assert resposta.status_code == 200
    todas = [item for lista in resposta.data.values() for item in lista]
    assert todas, "esperava pelo menos uma seção não vazia na Home"
    assert any(item.get("resumo_e_fallback") is True for item in todas)
