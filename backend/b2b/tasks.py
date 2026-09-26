import logging

from celery import shared_task

from .services import verificar_e_enviar_alertas

logger = logging.getLogger(__name__)


# Alertas podem disparar efeitos externos; não herdam reentrega tardia.
@shared_task(
    name="b2b.tasks.verificar_alertas",
    acks_late=False,
    reject_on_worker_lost=False,
)
def verificar_alertas_task():
    resultado = verificar_e_enviar_alertas()
    logger.info(
        "Task 'verificar_alertas' concluída: %d critério(s) verificado(s), %d alerta(s) enviado(s), "
        "%d falha(s), %d suprimido(s) por limite de execução, %d por limite de organização, "
        "%d por cooldown.",
        resultado["total_criterios_verificados"],
        resultado["total_alertas_enviados"],
        resultado["total_falhas"],
        resultado["total_suprimidos_por_limite_execucao"],
        resultado["total_suprimidos_por_limite_organizacao"],
        resultado["total_suprimidos_por_cooldown"],
    )
    # As anomalias de tenant já foram logadas em WARNING por
    # `services._registrar_anomalia`, uma linha por anomalia e com a ação
    # sugerida — aqui só sai o placar para o beat.
    if resultado["anomalias"]:
        logger.warning(
            "Task 'verificar_alertas': %d anomalia(s) de tenant detectada(s): %s",
            len(resultado["anomalias"]),
            ", ".join(sorted({a["tipo"] for a in resultado["anomalias"]})),
        )
    return resultado
