"""
Frente D — cliente do microserviço de ingestão (`feed/microservice_client.py`).

`requests` sempre mockado (nenhuma chamada de rede real); um teste de
integração valida o fallback silencioso para o serviço local nas views.
"""

from __future__ import annotations

import pytest
import requests
from django.test import override_settings
from rest_framework.test import APIClient
from unittest.mock import patch

from catalogo_noticias.models import NewsItem
from feed import microservice_client
from feed.microservice_client import (
    MicroserviceIndisponivelError,
    obter_detalhe_cluster,
    obter_detalhe_item,
    obter_feed,
    obter_urgentes,
    servico_ativo,
    sincronizar_fontes,
)

pytestmark = pytest.mark.django_db

BASE_TESTE = "http://ingestao-teste:8001"


class RespostaFake:
    def __init__(self, payload=None, status_code=200, json_erro=False):
        self._payload = payload
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._json_erro = json_erro

    def json(self):
        if self._json_erro:
            raise ValueError("corpo não-JSON")
        return self._payload


def _news_item(**kwargs):
    defaults = dict(
        titulo="Noticia local de fallback",
        resumo_proprio="Resumo autoral local.",
        conteudo_bruto="Conteudo bruto local.",
        url_fonte_original="https://g1/fallback-local",
        nome_fonte="G1",
        categoria="geral",
        status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
    )
    defaults.update(kwargs)
    return NewsItem.objects.create(**defaults)


# --- servico_ativo -----------------------------------------------------------

def test_servico_inativo_quando_url_vazia():
    with override_settings(MICROSERVICO_INGESTAO_URL=""):
        assert servico_ativo() is False


def test_servico_ativo_quando_url_configurada():
    with override_settings(MICROSERVICO_INGESTAO_URL=BASE_TESTE):
        assert servico_ativo() is True


# --- obter_feed --------------------------------------------------------------

def test_obter_feed_ok_envia_params_e_token():
    payload = {"count": 1, "next": None, "previous": None, "results": [{"id": 7, "titulo": "X"}]}
    with override_settings(MICROSERVICO_INGESTAO_URL=BASE_TESTE, INGESTAO_API_TOKEN="segredo"):
        with patch.object(microservice_client.requests, "get", return_value=RespostaFake(payload)) as mock_get:
            resultado = obter_feed(categoria="esportes", busca="gol", page=2)

    assert resultado["count"] == 1
    _, kwargs = mock_get.call_args
    assert kwargs["params"] == {"categoria": "esportes", "busca": "gol", "page": 2}
    assert kwargs["headers"] == {"X-API-Token": "segredo"}
    assert kwargs["timeout"] == 10


def test_obter_feed_converte_id_string_para_int():
    payload = {"count": 1, "next": None, "previous": None, "results": [{"id": "42", "titulo": "Y"}]}
    with override_settings(MICROSERVICO_INGESTAO_URL=BASE_TESTE):
        with patch.object(microservice_client.requests, "get", return_value=RespostaFake(payload)):
            resultado = obter_feed()

    assert resultado["results"][0]["id"] == 42


def test_obter_feed_descarta_next_previous_do_host_remoto():
    payload = {
        "count": 3, "next": "http://servico:9000/api/v1/feed?page=2",
        "previous": "http://servico:9000/api/v1/feed?page=0",
        "results": [{"id": 7, "titulo": "X"}],
    }
    with override_settings(MICROSERVICO_INGESTAO_URL=BASE_TESTE):
        with patch.object(microservice_client.requests, "get", return_value=RespostaFake(payload)):
            resultado = obter_feed()

    assert resultado["next"] is None
    assert resultado["previous"] is None
    assert resultado["results"][0]["id"] == 7


def test_obter_feed_erro_http_levanta_excecao():
    with override_settings(MICROSERVICO_INGESTAO_URL=BASE_TESTE):
        with patch.object(microservice_client.requests, "get", return_value=RespostaFake({}, status_code=500)):
            with pytest.raises(MicroserviceIndisponivelError):
                obter_feed()


# --- obter_urgentes ----------------------------------------------------------

def test_obter_urgentes_ok():
    with override_settings(MICROSERVICO_INGESTAO_URL=BASE_TESTE):
        with patch.object(
            microservice_client.requests, "get", return_value=RespostaFake([{"id": "3", "titulo": "U"}])
        ):
            resultado = obter_urgentes(limite=4)

    assert resultado == [{"id": 3, "titulo": "U"}]


# --- detalhes ----------------------------------------------------------------

def test_obter_detalhe_cluster_404_retorna_none():
    with override_settings(MICROSERVICO_INGESTAO_URL=BASE_TESTE):
        with patch.object(
            microservice_client.requests, "get", return_value=RespostaFake(None, status_code=404)
        ):
            assert obter_detalhe_cluster(999) is None


def test_obter_detalhe_item_ok():
    payload = {"id": "9", "tipo": "item", "titulo": "Z"}
    with override_settings(MICROSERVICO_INGESTAO_URL=BASE_TESTE):
        with patch.object(microservice_client.requests, "get", return_value=RespostaFake(payload)):
            resultado = obter_detalhe_item(9)

    assert resultado["id"] == 9
    assert resultado["titulo"] == "Z"


# --- sincronizar -------------------------------------------------------------

def test_sincronizar_fontes_ok():
    fontes = [{"nome": "G1", "url": "https://g1.globo.com/rss/g1/", "ativo": True}]
    with override_settings(MICROSERVICO_INGESTAO_URL=BASE_TESTE, INGESTAO_API_TOKEN="tok"):
        with patch.object(
            microservice_client.requests, "post", return_value=RespostaFake({"ok": True})
        ) as mock_post:
            resultado = sincronizar_fontes(fontes)

    assert resultado == {"ok": True}
    args, kwargs = mock_post.call_args
    assert args[0] == BASE_TESTE + "/api/v1/fontes/sincronizar"
    assert kwargs["json"] == {"fontes": fontes}
    assert kwargs["headers"] == {"X-API-Token": "tok"}


# --- falhas de rede ----------------------------------------------------------

def test_timeout_levanta_microservice_indisponivel():
    with override_settings(MICROSERVICO_INGESTAO_URL=BASE_TESTE):
        with patch.object(
            microservice_client.requests, "get", side_effect=requests.Timeout("travou")
        ):
            with pytest.raises(MicroserviceIndisponivelError):
                obter_feed()
        with patch.object(
            microservice_client.requests, "post", side_effect=requests.ConnectionError("caiu")
        ):
            with pytest.raises(MicroserviceIndisponivelError):
                sincronizar_fontes([])


# --- fallback local nas views ------------------------------------------------

def test_view_feed_usa_servico_local_quando_microservico_falha():
    _news_item()
    with override_settings(MICROSERVICO_INGESTAO_URL=BASE_TESTE):
        with patch.object(
            microservice_client.requests, "get", side_effect=requests.Timeout("travou")
        ):
            resposta = APIClient().get("/api/feed/")

    assert resposta.status_code == 200
    assert resposta.data["count"] == 1
    assert resposta.data["results"][0]["titulo"] == "Noticia local de fallback"


def test_view_urgentes_usa_servico_local_quando_microservico_falha():
    _news_item(urgente=True, url_fonte_original="https://g1/urgente-fallback")
    with override_settings(MICROSERVICO_INGESTAO_URL=BASE_TESTE):
        with patch.object(
            microservice_client.requests, "get", side_effect=requests.ConnectionError("caiu")
        ):
            resposta = APIClient().get("/api/feed/urgentes/")

    assert resposta.status_code == 200
    assert len(resposta.data) == 1
