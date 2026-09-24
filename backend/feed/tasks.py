"""Tarefas assíncronas de métricas do feed.

O registro de busca não pode fazer parte do caminho de leitura: a view
apenas enfileira dados primitivos e o worker resolve o usuário novamente.
"""

from __future__ import annotations

import logging
import re

from celery import shared_task
from django.contrib.auth import get_user_model

from .models import EventoBusca

logger = logging.getLogger(__name__)


@shared_task(
    name="feed.tasks.registrar_evento_busca",
    acks_late=True,
    reject_on_worker_lost=True,
    ignore_result=True,
)
def registrar_evento_busca(
    query: str,
    resultados: int,
    user_id: int | None = None,
    session_key: str = "",
    filtros: dict | None = None,
    request_id: str | None = None,
) -> int:
    """Persiste um ``EventoBusca`` recebido como payload JSON do Celery.

    ``user_id`` e ``request_id`` são deliberadamente primitivos: objeto
    Django não é serializável entre processos. O request id, quando presente,
    funciona como chave idempotente para uma reentrega da task. Eventos sem
    request id continuam sendo criados individualmente.
    """

    filtros = filtros if isinstance(filtros, dict) else {}
    request_id = str(request_id or "").strip()
    if not request_id or request_id == "-":
        request_id = None
    else:
        request_id = request_id[:64]
    try:
        resultado = max(0, int(resultados or 0))
    except (TypeError, ValueError):
        resultado = 0

    user = None
    if user_id:
        try:
            user = get_user_model().objects.filter(pk=user_id).first()
        except Exception:
            # O usuário pode ter sido removido entre o request e o worker; a
            # métrica anônima ainda é válida.
            user = None

    query_texto = (query or "")[:300]
    query_normalizada = re.sub(r"\s+", " ", query_texto.strip().lower())[:300]
    defaults = {
        "query": query_texto,
        "query_normalizada": query_normalizada,
        "user": user,
        "session_key": (session_key or "")[:64],
        "resultados": resultado,
        "filtros": filtros,
    }
    if request_id:
        evento, created = EventoBusca.objects.get_or_create(
            request_id=request_id,
            defaults=defaults,
        )
        if not created:
            logger.debug("EventoBusca já registrado para request_id=%s", request_id)
        return evento.id
    return EventoBusca.objects.create(**defaults).id
