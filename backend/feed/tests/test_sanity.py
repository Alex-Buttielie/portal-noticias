"""
Testes mínimos de sanidade do executor (não substituem a suíte formal do
tester) — implementation-contract.md run 20260902-1409-feed-consumo.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from catalogo_noticias.models import NewsCluster, NewsItem

pytestmark = pytest.mark.django_db

User = get_user_model()


def _news_item(**kwargs):
    defaults = dict(
        titulo="Noticia de teste",
        resumo_proprio="Resumo autoral de teste.",
        conteudo_bruto="Conteudo bruto de teste.",
        url_fonte_original="https://g1/teste",
        nome_fonte="G1",
        categoria="geral",
        status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
    )
    defaults.update(kwargs)
    return NewsItem.objects.create(**defaults)


def test_feed_publico_sem_autenticacao_retorna_200():
    _news_item()
    client = APIClient()

    resposta = client.get("/api/feed/")

    assert resposta.status_code == 200
    assert resposta.data["count"] == 1


def test_item_pendente_nunca_aparece_no_feed():
    _news_item(status_revisao=NewsItem.STATUS_PENDENTE, url_fonte_original="https://g1/pendente")
    client = APIClient()

    resposta = client.get("/api/feed/")

    assert resposta.data["count"] == 0


def test_item_pendente_no_detalhe_retorna_404():
    item = _news_item(status_revisao=NewsItem.STATUS_PENDENTE, url_fonte_original="https://g1/pendente-detalhe")
    client = APIClient()

    resposta = client.get(f"/api/feed/item/{item.id}/")

    assert resposta.status_code == 404


def test_filtro_por_categoria():
    _news_item(categoria="esportes", url_fonte_original="https://g1/esportes")
    _news_item(categoria="politica", url_fonte_original="https://g1/politica")
    client = APIClient()

    resposta = client.get("/api/feed/?categoria=esportes")

    assert resposta.data["count"] == 1
    assert resposta.data["results"][0]["categoria"] == "esportes"


def test_busca_por_palavra_chave():
    _news_item(titulo="Selecao vence amistoso", url_fonte_original="https://g1/selecao")
    _news_item(titulo="Banco Central mantem juros", url_fonte_original="https://g1/juros")
    client = APIClient()

    resposta = client.get("/api/feed/?busca=selecao")

    assert resposta.data["count"] == 1
    assert "Selecao" in resposta.data["results"][0]["titulo"]


def test_detalhe_de_cluster_lista_todas_as_fontes():
    cluster = NewsCluster.objects.create(titulo_acontecimento="Fato coberto por 2 fontes", categoria_dominante="cidades")
    _news_item(
        titulo="Fato coberto por 2 fontes (G1)",
        nome_fonte="G1",
        url_fonte_original="https://g1/fato-cluster",
        cluster=cluster,
        categoria="cidades",
    )
    _news_item(
        titulo="Fato coberto por 2 fontes (UOL)",
        nome_fonte="UOL",
        url_fonte_original="https://uol/fato-cluster",
        cluster=cluster,
        categoria="cidades",
    )
    client = APIClient()

    resposta = client.get(f"/api/feed/cluster/{cluster.id}/")

    assert resposta.status_code == 200
    assert len(resposta.data["fontes"]) == 2
    nomes = {fonte["nome_fonte"] for fonte in resposta.data["fontes"]}
    assert nomes == {"G1", "UOL"}


def test_detalhe_de_item_standalone_funciona():
    item = _news_item(titulo="Noticia sem par", url_fonte_original="https://g1/standalone")
    client = APIClient()

    resposta = client.get(f"/api/feed/item/{item.id}/")

    assert resposta.status_code == 200
    assert resposta.data["tipo"] == "item"
    assert len(resposta.data["fontes"]) == 1
    assert resposta.data["fontes"][0]["nome_fonte"] == "G1"


def test_id_inexistente_retorna_404_nos_dois_endpoints_de_detalhe():
    client = APIClient()

    resposta_item = client.get("/api/feed/item/999999/")
    resposta_cluster = client.get("/api/feed/cluster/999999/")

    assert resposta_item.status_code == 404
    assert resposta_cluster.status_code == 404


def test_usuario_premium_nao_ve_publicidade():
    _news_item()
    usuario_premium = User.objects.create_user(email="premium@example.com", password="senha123", papel="premium")
    client = APIClient()
    client.force_authenticate(user=usuario_premium)

    resposta = client.get("/api/feed/")

    assert resposta.data["exibir_publicidade"] is False


def test_visitante_ve_publicidade():
    _news_item()
    client = APIClient()

    resposta = client.get("/api/feed/")

    assert resposta.data["exibir_publicidade"] is True


# ---------------------------------------------------------------------------
# BRD seção 10 — "Manter equilíbrio entre categorias para evitar
# concentração excessiva em um único assunto." Gap real encontrado na
# análise do BRD: o feed geral nunca controlava concentração por categoria.
# ---------------------------------------------------------------------------


def test_feed_geral_intercala_categorias_nao_deixa_uma_dominar_o_topo():
    from feed import services

    # 5 itens de "esportes" (mais recentes) + 1 de "politica" + 1 de
    # "economia" — sem equilíbrio, os 2 últimos ficariam nas posições 6 e 7;
    # com equilíbrio, cada um deve aparecer entre as 3 primeiras posições.
    for i in range(5):
        _news_item(
            titulo=f"Esporte {i}", categoria="esportes", url_fonte_original=f"https://g1/esporte-{i}"
        )
    _news_item(titulo="Politica 1", categoria="politica", url_fonte_original="https://g1/politica-1")
    _news_item(titulo="Economia 1", categoria="economia", url_fonte_original="https://g1/economia-1")

    itens = list(services.itens_publicaveis())
    entradas = services.construir_feed_entries(itens)
    equilibradas = services.equilibrar_por_categoria(entradas)

    assert len(equilibradas) == 7
    categorias_top3 = {entrada["categoria"] for entrada in equilibradas[:3]}
    assert categorias_top3 == {"esportes", "politica", "economia"}


def test_feed_filtrado_por_categoria_nao_e_reequilibrado():
    for i in range(5):
        _news_item(
            titulo=f"Esporte {i}", categoria="esportes", url_fonte_original=f"https://g1/filtro-esporte-{i}"
        )
    _news_item(titulo="Politica 1", categoria="politica", url_fonte_original="https://g1/filtro-politica-1")
    client = APIClient()

    resposta = client.get("/api/feed/?categoria=esportes")

    assert resposta.data["count"] == 5
    assert all(r["categoria"] == "esportes" for r in resposta.data["results"])
