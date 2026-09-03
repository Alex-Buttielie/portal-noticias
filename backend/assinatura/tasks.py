"""
Task Celery periódica de vencimento/grace period (implementation-contract.md
run 20260902-1426-assinatura-premium, critérios de aceite 5, 6, 8).
Agendamento em `settings.CELERY_BEAT_SCHEDULE`.
"""

import logging

from celery import shared_task

from .services import processar_vencimentos_e_grace_periods

logger = logging.getLogger(__name__)


@shared_task(name="assinatura.tasks.processar_vencimentos")
def processar_vencimentos():
    resultado = processar_vencimentos_e_grace_periods()
    logger.info("Task 'processar_vencimentos' concluída: %s", resultado)
    return resultado
