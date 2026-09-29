"""
Tasks Celery periódicas de assinatura (implementation-contract.md run
20260902-1426-assinatura-premium, critérios de aceite 5, 6, 8) e de
conciliação com o provedor. Agendamento em `settings.CELERY_BEAT_SCHEDULE`.
"""

import logging

from celery import shared_task

from .services import processar_vencimentos_e_grace_periods, reconciliar_com_provedor

logger = logging.getLogger(__name__)


# Cobrança/renovação pode produzir efeitos externos; ack imediato é
# deliberado porque a task não possui idempotência durável por execução.
@shared_task(
    name="assinatura.tasks.processar_vencimentos",
    acks_late=False,
    reject_on_worker_lost=False,
)
def processar_vencimentos():
    resultado = processar_vencimentos_e_grace_periods()
    logger.info("Task 'processar_vencimentos' concluída: %s", resultado)
    return resultado


# Idempotente por construção (toda correção passa por
# `services.aplicar_resultado_provedor`, cujas transições são guardadas
# pelo status e pela cobrança em aberto): reexecutar não muda nada, o que
# torna o ack tardio seguro aqui — e é o que se quer numa task cujo
# propósito é justamente pegar de volta o que a notificação do provedor
# não conseguiu entregar.
@shared_task(
    name="assinatura.tasks.reconciliar_com_provedor",
    acks_late=True,
    reject_on_worker_lost=False,
)
def reconciliar_com_provedor_task():
    resultado = reconciliar_com_provedor()
    logger.info("Task 'reconciliar_com_provedor' concluída: %s", resultado)
    return resultado
