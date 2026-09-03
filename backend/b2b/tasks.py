import logging

from celery import shared_task

from .services import verificar_e_enviar_alertas

logger = logging.getLogger(__name__)


@shared_task(name="b2b.tasks.verificar_alertas")
def verificar_alertas_task():
    resultado = verificar_e_enviar_alertas()
    logger.info(
        "Task 'verificar_alertas' concluída: %d critério(s) verificado(s), %d alerta(s) enviado(s), %d falha(s).",
        resultado["total_criterios_verificados"],
        resultado["total_alertas_enviados"],
        resultado["total_falhas"],
    )
    return resultado
