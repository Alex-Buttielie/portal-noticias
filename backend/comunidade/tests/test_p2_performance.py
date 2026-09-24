"""Testes P2-3a: community listings limitadas e sem N+1 de autor."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test.utils import CaptureQueriesContext
from django.db import connection
from rest_framework.test import APIClient

from comunidade.models import Comentario, Publicacao

pytestmark = pytest.mark.django_db
User = get_user_model()


def _autor(suffix: str):
    return User.objects.create_user(
        email=f"p2-comunidade-{suffix}@example.com",
        password="senha123",
        nome=f"Autor {suffix}",
    )


def _publicacoes(quantidade: int, status=Publicacao.STATUS_PUBLICADO):
    autor = _autor("lista")
    return [
        Publicacao.objects.create(
            autor=autor,
            titulo=f"Publicação {indice}",
            conteudo="Corpo",
            tipo=Publicacao.TIPO_ANALISE,
            status=status,
        )
        for indice in range(quantidade)
    ]


def test_listagem_publicacao_default_preserva_lista_completa():
    _publicacoes(25)
    resposta = APIClient().get("/api/comunidade/publicacoes/")

    assert resposta.status_code == 200
    # Opção (a): sem parâmetros, o contrato legado continua lista completa;
    # nenhum cliente atual perde itens silenciosamente.
    assert isinstance(resposta.data, list)
    assert len(resposta.data) == 25


def test_listagem_publicacao_aceita_page_e_page_size_com_teto():
    _publicacoes(120)
    resposta = APIClient().get(
        "/api/comunidade/publicacoes/", {"page": 2, "page_size": 500}
    )

    assert resposta.status_code == 200
    assert resposta.data["count"] == 120
    assert len(resposta.data["results"]) == 20
    assert resposta.data["previous"] is not None


def test_listagem_publicacao_select_related_nao_cresce_com_numero_de_autores():
    # Cada autor distinto tornaria a serialização de autor_nome um N+1 se
    # o related manager fosse acessado sem select_related.
    for indice in range(4):
        autor = _autor(f"n1-{indice}")
        Publicacao.objects.create(
            autor=autor,
            titulo=f"Post {indice}",
            conteudo="Corpo",
            tipo=Publicacao.TIPO_OPINIAO,
            status=Publicacao.STATUS_PUBLICADO,
        )

    with CaptureQueriesContext(connection) as ctx:
        resposta = APIClient().get("/api/comunidade/publicacoes/?page_size=20")
    assert resposta.status_code == 200
    assert len(resposta.data["results"]) == 4
    # COUNT da paginação + uma única consulta da página com JOIN de autor.
    assert len(ctx.captured_queries) <= 3


def test_comentarios_tambem_paginam_e_reusam_autor_carregado():
    autor = _autor("comentario")
    publicacao = Publicacao.objects.create(
        autor=autor,
        titulo="Post com comentários",
        conteudo="Corpo",
        tipo=Publicacao.TIPO_ANALISE,
        status=Publicacao.STATUS_PUBLICADO,
    )
    for indice in range(23):
        Comentario.objects.create(
            autor=autor,
            publicacao=publicacao,
            conteudo=f"Comentário {indice}",
        )

    with CaptureQueriesContext(connection) as ctx:
        resposta_completa = APIClient().get(
            "/api/comunidade/comentarios/", {"publicacao": publicacao.id}
        )
    assert resposta_completa.status_code == 200
    assert isinstance(resposta_completa.data, list)
    assert len(resposta_completa.data) == 23

    with CaptureQueriesContext(connection) as ctx:
        resposta = APIClient().get(
            "/api/comunidade/comentarios/", {"publicacao": publicacao.id, "page_size": 500}
        )
    assert resposta.status_code == 200
    assert resposta.data["count"] == 23
    assert len(resposta.data["results"]) == 23
    assert len(ctx.captured_queries) <= 3
