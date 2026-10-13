"""
M-01 (implementation-contract.md run 20261012-1806-monetizacao-sprint1) —
`conteudo` (texto raspado até 6.000 caracteres) não pode mais aparecer no
JSON público de `detalhe_cluster`/`detalhe_item`. Risco de direito autoral
(BRD §18): o texto completo continua no banco (`conteudo_completo`), só não
é mais servido pela API pública.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from catalogo_noticias.models import NewsCluster, NewsItem

pytestmark = pytest.mark.django_db


def _news_item(**kwargs):
    defaults = dict(
        titulo="Noticia de teste M-01",
        resumo_proprio="Resumo autoral de teste.",
        conteudo_bruto="Conteudo bruto de teste.",
        conteudo_completo="Texto integral raspado da fonte — não pode ir ao público.",
        url_fonte_original="https://g1/teste-m01",
        nome_fonte="G1",
        categoria="geral",
        status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
    )
    defaults.update(kwargs)
    return NewsItem.objects.create(**defaults)


def test_detalhe_de_item_nao_expoe_conteudo():
    item = _news_item(url_fonte_original="https://g1/item-m01")
    client = APIClient()

    resposta = client.get(f"/api/feed/item/{item.id}/")

    assert resposta.status_code == 200
    for fonte in resposta.data["fontes"]:
        assert "conteudo" not in fonte


def test_detalhe_de_cluster_nao_expoe_conteudo_em_nenhuma_fonte():
    cluster = NewsCluster.objects.create(titulo_acontecimento="Fato M-01", categoria_dominante="geral")
    _news_item(nome_fonte="G1", url_fonte_original="https://g1/fato-m01", cluster=cluster)
    _news_item(nome_fonte="UOL", url_fonte_original="https://uol/fato-m01", cluster=cluster)
    client = APIClient()

    resposta = client.get(f"/api/feed/cluster/{cluster.id}/")

    assert resposta.status_code == 200
    assert len(resposta.data["fontes"]) == 2
    for fonte in resposta.data["fontes"]:
        assert "conteudo" not in fonte


def test_servico_de_detalhe_tambem_nao_devolve_conteudo_no_dict_bruto():
    """Prova no nível do serviço (não só do serializer) — mesmo que alguém
    troque o serializer por um genérico, o dict já sai sem a chave."""
    from feed import services

    item = _news_item(url_fonte_original="https://g1/servico-m01")
    detalhe = services.detalhe_item(item.id)

    assert detalhe is not None
    for fonte in detalhe["fontes"]:
        assert "conteudo" not in fonte
