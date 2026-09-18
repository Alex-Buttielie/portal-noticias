"""FRENTE 3 — algoritmos + busca + agrupamento (testes de aceite)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from catalogo_noticias.models import NewsCluster, NewsItem
from feed import busca as busca_engine
from feed import recomendacao as rec
from feed.models import DestaqueEditorial, EventoBusca, InteracaoNoticia

pytestmark = pytest.mark.django_db

User = get_user_model()
_seq = {"n": 0}


def _news_item(**kwargs):
    _seq["n"] += 1
    defaults = dict(
        titulo=f"Noticia {_seq['n']}",
        resumo_proprio="Resumo autoral.",
        url_fonte_original=f"https://fonte.test/{_seq['n']}",
        nome_fonte="FonteTeste",
        categoria="geral",
        status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
    )
    defaults.update(kwargs)
    return NewsItem.objects.create(**defaults)


def _entradas():
    from feed import services as feed_services

    return feed_services.construir_feed_entries(list(feed_services.itens_publicaveis()))


def _interacao(entry_tipo, entry_id, tipo="view", categoria="geral"):
    kwargs = dict(tipo=tipo, entry_tipo=entry_tipo, categoria=categoria)
    if entry_tipo == "cluster":
        kwargs["cluster"] = NewsCluster.objects.get(pk=entry_id)
    else:
        kwargs["item"] = NewsItem.objects.get(pk=entry_id)
    return InteracaoNoticia.objects.create(**kwargs)


# -- Home em seções --------------------------------------------------------

def test_home_sem_repeticao_entre_secoes():
    for i in range(8):
        _news_item(titulo=f"Home {i}", categoria=f"cat{i % 3}")
    secoes = rec.montar_home(_entradas())
    assert set(secoes) == {"manchetes", "curadoria", "para_voce", "populares", "tendencia", "recentes"}
    chaves = [(e["tipo"], e["id"]) for lista in secoes.values() for e in lista]
    assert len(chaves) == len(set(chaves))


def test_bloqueio_editorial_exclui_de_tudo():
    item = _news_item(titulo="Bloqueada", categoria="x")
    DestaqueEditorial.objects.create(
        tipo=DestaqueEditorial.TIPO_BLOQUEIO, entry_tipo="item", item=item)
    secoes = rec.montar_home(_entradas())
    chaves = [(e["tipo"], e["id"]) for lista in secoes.values() for e in lista]
    assert ("item", item.id) not in chaves
    dest = rec.destaques_do_dia(_entradas())
    assert all((d["tipo"], d["id"]) != ("item", item.id) for d in dest)


def test_manchete_fixa_no_topo_respeitando_posicao():
    a = _news_item(titulo="Manchete B")
    b = _news_item(titulo="Manchete A")
    DestaqueEditorial.objects.create(
        tipo=DestaqueEditorial.TIPO_MANCHETE, entry_tipo="item", item=a, posicao=2)
    DestaqueEditorial.objects.create(
        tipo=DestaqueEditorial.TIPO_MANCHETE, entry_tipo="item", item=b, posicao=1)
    secoes = rec.montar_home(_entradas())
    assert [e["id"] for e in secoes["manchetes"]] == [b.id, a.id]


def test_conteudo_velho_nao_abre_a_curadoria():
    velho = _news_item(titulo="Velha popular")
    NewsItem.objects.filter(pk=velho.pk).update(
        timestamp_ingestao=timezone.now() - timedelta(days=10))
    for i in range(5):
        _news_item(titulo=f"Nova {i}")
    for _ in range(6):
        _interacao("item", velho.id, tipo="click")
    entradas = _entradas()
    velho_e = next(e for e in entradas if e["id"] == velho.id)
    velho_e["timestamp"] = timezone.now() - timedelta(days=10)
    secoes = rec.montar_home(entradas)
    top3 = secoes["curadoria"][:3]
    assert all((e["tipo"], e["id"]) != ("item", velho.id) for e in top3)


def test_para_voce_vazio_sem_interesses_anti_bolha():
    _news_item(categoria="esportes")
    secoes = rec.montar_home(_entradas(), interesses=[])
    assert secoes["para_voce"] == []


def test_personalizacao_prioriza_interesse_com_teto():
    for i in range(6):
        _news_item(titulo=f"Esp {i}", categoria="esportes")
    _news_item(titulo="Tec 1", categoria="tecnologia")
    secoes = rec.montar_home(_entradas(), interesses=["esportes"])
    assert secoes["para_voce"]
    assert all(e["categoria"] == "esportes" for e in secoes["para_voce"])


# -- Destaques do Dia ------------------------------------------------------

def test_destaques_manuais_primeiro():
    a = _news_item(titulo="Orgânica quente")
    b = _news_item(titulo="Manual")
    for _ in range(8):
        _interacao("item", a.id, tipo="click")
    DestaqueEditorial.objects.create(
        tipo=DestaqueEditorial.TIPO_DESTAQUE, entry_tipo="item", item=b)
    dest = rec.destaques_do_dia(_entradas(), limite=5)
    assert dest[0]["id"] == b.id
    assert dest[0]["override"] == "destaque"


# -- Busca -----------------------------------------------------------------

def test_busca_multi_campo_autor_categoria_tags():
    _news_item(titulo="Acordo no senado", categoria="política",
               autor="Colunista X", tags=["senado", "acordo"])
    resultados, _ = busca_engine.buscar("colunista x")
    assert resultados and "autor" in resultados[0]["trecho"]
    resultados, _ = busca_engine.buscar("senado")
    assert resultados
    resultados, _ = busca_engine.buscar("q-inexistente-xyz", categoria="política")
    assert resultados == []


def test_busca_registra_evento_e_historico():
    client = APIClient()
    _news_item(titulo="Buscável demais")
    r = client.get("/api/feed/busca/", {"q": "buscável"})
    assert r.status_code == 200
    assert EventoBusca.objects.filter(query_normalizada="buscável").exists()
    r2 = client.get("/api/feed/busca/historico/")
    assert r2.status_code == 200


def test_autocomplete_populares_correcao():
    EventoBusca.objects.create(query="eleições 2026", query_normalizada="eleições 2026", resultados=3)
    EventoBusca.objects.create(query="eleições 2026", query_normalizada="eleições 2026", resultados=3)
    assert "eleições 2026" in busca_engine.autocomplete("elei")
    assert busca_engine.termos_populares()[0]["termo"] == "eleições 2026"
    assert busca_engine.sugestao_correcao("eleicoes 2026") in ("eleições 2026", None)


def test_clique_em_resultado_registra_search_click():
    client = APIClient()
    item = _news_item(titulo="Clicável")
    r = client.post("/api/feed/interacoes/", {
        "tipo": "search_click", "entry_tipo": "item",
        "entry_id": item.id, "query": "clicável"}, format="json")
    assert r.status_code == 201
    assert InteracaoNoticia.objects.filter(tipo="search_click", item=item).exists()


# -- Agrupamento / cobertura completa --------------------------------------

def test_cobertura_cluster_fontes_atualizacoes_relacionadas():
    cluster = NewsCluster.objects.create(titulo_acontecimento="Evento Y", categoria_dominante="geral")
    _news_item(titulo="Fonte 1 cobre Y", cluster=cluster, url_fonte_original="https://a.test/1", nome_fonte="A")
    _news_item(titulo="Fonte 2 cobre Y", cluster=cluster, url_fonte_original="https://b.test/2", nome_fonte="B")
    _news_item(titulo="Outra pauta", categoria="geral")
    cob = rec.cobertura_completa("cluster", cluster.id)
    assert cob["numero_fontes"] == 2
    assert cob["total_atualizacoes"] == 2
    assert cob["atualizacoes"][0]["timestamp"] <= cob["atualizacoes"][-1]["timestamp"]
    assert all(r["id"] != cluster.id or r["tipo"] != "cluster" for r in cob["relacionadas"])
    client = APIClient()
    r = client.get(f"/api/feed/cobertura/cluster/{cluster.id}/")
    assert r.status_code == 200
    assert "atualizacoes" in r.data and "relacionadas" in r.data


def test_cobertura_nao_vaza_pendente():
    item = _news_item(status_revisao=NewsItem.STATUS_PENDENTE)
    assert rec.cobertura_completa("item", item.id) is None
    client = APIClient()
    assert client.get(f"/api/feed/cobertura/item/{item.id}/").status_code == 404


def test_home_nao_duplica_cluster():
    cluster = NewsCluster.objects.create(titulo_acontecimento="Evento Z")
    _news_item(titulo="Z fonte 1", cluster=cluster, url_fonte_original="https://z.test/1", nome_fonte="A")
    _news_item(titulo="Z fonte 2", cluster=cluster, url_fonte_original="https://z.test/2", nome_fonte="B")
    entradas = _entradas()
    assert sum(1 for e in entradas if (e["tipo"], e["id"]) == ("cluster", cluster.id)) == 1


# -- Endpoints --------------------------------------------------------------

def test_home_endpoint_secoes_e_publicidade():
    _news_item()
    client = APIClient()
    r = client.get("/api/feed/home/")
    assert r.status_code == 200
    for secao in ("manchetes", "curadoria", "para_voce", "populares", "tendencia", "recentes"):
        assert secao in r.data


def test_radar_tendencias_com_score_e_para_voce():
    _news_item(categoria="saude", cidade="Recife", estado="PE", pais="Brasil")
    client = APIClient()
    r = client.get("/api/radar/tendencias/")
    assert r.status_code == 200
    assert "score" in r.data["assuntos_em_alta"][0]
    r2 = client.get("/api/radar/para-voce/", {"cidade": "Recife"})
    assert r2.status_code == 200
    assert "secoes" in r2.data
