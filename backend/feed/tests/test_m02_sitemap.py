"""
M-02 (implementation-contract.md run 20261012-1806-monetizacao-sprint1) —
endpoint leve e paginado em `backend/feed/` que lista só as entradas
publicáveis E indexáveis (com resumo próprio — mesma regra de M-03 no
frontend), para `frontend/app/sitemap.ts` montar `/sitemap.xml` sem incluir
notícia marcada `noindex`.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from catalogo_noticias.models import NewsCluster, NewsItem

pytestmark = pytest.mark.django_db


def _news_item(**kwargs):
    defaults = dict(
        titulo="Noticia de teste M-02",
        resumo_proprio="Resumo autoral de teste.",
        url_fonte_original="https://g1/teste-m02",
        nome_fonte="G1",
        categoria="geral",
        status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
    )
    defaults.update(kwargs)
    return NewsItem.objects.create(**defaults)


def test_servico_inclui_apenas_entradas_com_resumo():
    from feed import services

    com_resumo = _news_item(url_fonte_original="https://g1/com-resumo-m02", resumo_proprio="Tem resumo.")
    sem_resumo = _news_item(url_fonte_original="https://g1/sem-resumo-m02", resumo_proprio="")

    entradas = services.entradas_sitemap()
    ids = {e["id"] for e in entradas}

    assert com_resumo.id in ids
    assert sem_resumo.id not in ids


def test_servico_nao_inclui_item_nao_publicavel():
    from feed import services

    pendente = _news_item(
        url_fonte_original="https://g1/pendente-m02",
        status_revisao=NewsItem.STATUS_PENDENTE,
    )

    entradas = services.entradas_sitemap()
    ids = {e["id"] for e in entradas}

    assert pendente.id not in ids


def test_servico_agrupa_cluster_em_uma_entrada():
    from feed import services

    cluster = NewsCluster.objects.create(titulo_acontecimento="Fato M-02", categoria_dominante="geral")
    _news_item(nome_fonte="G1", url_fonte_original="https://g1/fato-m02", cluster=cluster)
    _news_item(nome_fonte="UOL", url_fonte_original="https://uol/fato-m02", cluster=cluster)

    entradas = services.entradas_sitemap()
    entradas_cluster = [e for e in entradas if e["tipo"] == "cluster" and e["id"] == cluster.id]

    assert len(entradas_cluster) == 1


def test_endpoint_responde_paginado_com_entradas_indexaveis():
    item = _news_item(url_fonte_original="https://g1/endpoint-m02")
    client = APIClient()

    resposta = client.get("/api/feed/sitemap/")

    assert resposta.status_code == 200
    assert "results" in resposta.data
    assert "count" in resposta.data
    ids = {e["id"] for e in resposta.data["results"]}
    assert item.id in ids
    for entrada in resposta.data["results"]:
        assert set(entrada.keys()) == {"tipo", "id", "categoria", "timestamp"}


def test_endpoint_nao_lista_noticia_sem_resumo():
    sem_resumo = _news_item(url_fonte_original="https://g1/endpoint-sem-resumo-m02", resumo_proprio="")
    client = APIClient()

    resposta = client.get("/api/feed/sitemap/")

    assert resposta.status_code == 200
    ids = {e["id"] for e in resposta.data["results"]}
    assert sem_resumo.id not in ids


def test_servico_inclui_noticia_mais_antiga_que_a_janela_do_feed():
    """
    Remediação do Finding 1 (major) do code-review-contract.md desta run:
    `entradas_sitemap()` reaproveitava `itens_publicaveis()`, que corta por
    `timestamp_ingestao__gte = agora - FEED_JANELA_HORAS` (72h em
    produção) — uma notícia publicável e indexável com mais de 3 dias
    nunca aparecia no sitemap, contradizendo o próprio objetivo do M-02
    (dar alcance orgânico ao acervo). Este teste cobre exatamente o
    cenário de falha descrito no finding.
    """
    from feed import services

    antiga = _news_item(
        url_fonte_original="https://g1/antiga-m02",
        resumo_proprio="Resumo autoral de notícia antiga, mas publicável.",
    )
    # `timestamp_ingestao` é `auto_now_add=True` — só pode ser retroagido
    # via `.update()` depois da criação (o `save()` ignoraria o valor
    # passado no `create()`).
    NewsItem.objects.filter(pk=antiga.id).update(
        timestamp_ingestao=timezone.now() - timedelta(hours=96)
    )

    entradas = services.entradas_sitemap()
    ids = {e["id"] for e in entradas}

    assert antiga.id in ids


def test_endpoint_lista_noticia_mais_antiga_que_a_janela_do_feed():
    """Mesmo cenário acima, mas batendo no endpoint HTTP real (não só no
    service) — o que o critério de aceite 3/M-02 do
    implementation-contract.md exige ("dado um conjunto de notícias
    publicáveis... /sitemap.xml é gerado... só as publicáveis e
    indexáveis aparecem")."""
    antiga = _news_item(
        url_fonte_original="https://g1/antiga-endpoint-m02",
        resumo_proprio="Resumo autoral de notícia antiga, mas publicável.",
    )
    NewsItem.objects.filter(pk=antiga.id).update(
        timestamp_ingestao=timezone.now() - timedelta(hours=96)
    )
    client = APIClient()

    resposta = client.get("/api/feed/sitemap/")

    assert resposta.status_code == 200
    ids = {e["id"] for e in resposta.data["results"]}
    assert antiga.id in ids


def test_endpoint_respeita_page_size(settings):
    for i in range(3):
        _news_item(
            url_fonte_original=f"https://g1/paginacao-m02-{i}",
            resumo_proprio=f"Resumo {i}",
        )
    client = APIClient()

    resposta = client.get("/api/feed/sitemap/", {"page_size": 2})

    assert resposta.status_code == 200
    assert len(resposta.data["results"]) == 2
    assert resposta.data["count"] >= 3
