"""Testes P2-3b/P2-3c/P2-4 do feed e da configuração Celery."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from catalogo_noticias.models import NewsItem
from feed import busca as busca_engine
from feed.models import EventoBusca
from feed.tasks import registrar_evento_busca

pytestmark = pytest.mark.django_db
User = get_user_model()


def test_busca_publica_enfileira_evento_sem_insert_sincrono():
    client = APIClient()
    with patch.object(busca_engine.registrar_evento_busca, "delay") as enfileirar:
        resposta = client.get(
            "/api/feed/busca/",
            {"q": "termo-novo"},
            HTTP_X_REQUEST_ID="p2-busca-request",
        )

    assert resposta.status_code == 200
    assert EventoBusca.objects.count() == 0
    enfileirar.assert_called_once()
    argumentos = enfileirar.call_args.kwargs
    assert argumentos["query"] == "termo-novo"
    assert argumentos["request_id"] == "p2-busca-request"


def test_registrar_busca_fora_de_request_gera_uuid_em_vez_do_sentinel():
    with patch("config.middleware.get_current_request_id", return_value="-"):
        with patch.object(busca_engine.registrar_evento_busca, "delay") as enfileirar:
            busca_engine.registrar_busca("primeira", 0)
            busca_engine.registrar_busca("segunda", 0)

    ids = [call.kwargs["request_id"] for call in enfileirar.call_args_list]
    assert len(ids) == 2
    assert ids[0] != ids[1]
    assert all(uuid.UUID(valor) for valor in ids)
    assert all(valor != "-" for valor in ids)


def test_task_evento_resolve_usuario_e_e_idempotente_por_request_id():
    usuario = User.objects.create_user(
        email="p2-busca-user@example.com", password="senha123", papel="free"
    )
    payload = {
        "query": "  Evento assíncrono  ",
        "resultados": 4,
        "user_id": usuario.pk,
        "session_key": "sessao-p2",
        "filtros": {"categoria": "cidades"},
        "request_id": "p2-event-idempotente",
    }

    primeiro_id = registrar_evento_busca.run(**payload)
    segundo_id = registrar_evento_busca.run(**payload)

    assert primeiro_id == segundo_id
    evento = EventoBusca.objects.get()
    assert evento.user_id == usuario.pk
    assert evento.query_normalizada == "evento assíncrono"
    assert evento.resultados == 4
    assert evento.filtros == {"categoria": "cidades"}


def test_autocomplete_reaproveita_vocabulario_sem_query_no_segundo_prefixo():
    cache_locmem = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "p2-autocomplete",
        }
    }
    with override_settings(CACHES=cache_locmem, FEED_AUTOCOMPLETE_CACHE_TTL_SEGUNDOS=60):
        cache.clear()
        NewsItem.objects.create(
            titulo="Prefeitura anuncia novo plano",
            url_fonte_original="https://p2.test/autocomplete-1",
            nome_fonte="Fonte P2",
            categoria="cidades",
            status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
        )
        NewsItem.objects.create(
            titulo="Prefeitura explica o cronograma",
            url_fonte_original="https://p2.test/autocomplete-2",
            nome_fonte="Fonte P2",
            categoria="cidades",
            status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
        )

        with CaptureQueriesContext(connection) as primeira:
            primeira_resposta = busca_engine.autocomplete("pre")
        with CaptureQueriesContext(connection) as segunda:
            segunda_resposta = busca_engine.autocomplete("pre")

        assert primeira_resposta
        assert segunda_resposta == primeira_resposta
        assert primeira.captured_queries
        assert segunda.captured_queries == []
        cache.clear()


def test_configuracao_celery_limita_reentrega_as_tasks_idempotentes():
    assert settings.CELERY_WORKER_PREFETCH_MULTIPLIER == 1
    assert settings.CELERY_WORKER_MAX_TASKS_PER_CHILD == 100

    from config.celery import app
    from catalogo_noticias.tasks import ingerir_noticias
    from newsletter.tasks import (
        enviar_newsletters_manha_task,
        enviar_newsletters_noite_task,
        enviar_newsletters_task,
    )
    from b2b.tasks import verificar_alertas_task
    from assinatura.tasks import processar_vencimentos

    assert app.conf.task_acks_late is False
    assert app.conf.task_reject_on_worker_lost is None
    assert app.conf.worker_prefetch_multiplier == 1

    for task in (ingerir_noticias, registrar_evento_busca):
        assert task.acks_late is True
        assert task.reject_on_worker_lost is True

    for task in (
        enviar_newsletters_task,
        enviar_newsletters_manha_task,
        enviar_newsletters_noite_task,
        verificar_alertas_task,
        processar_vencimentos,
    ):
        assert task.acks_late is False
        assert task.reject_on_worker_lost is False
