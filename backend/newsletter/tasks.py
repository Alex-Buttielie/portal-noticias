import logging

from celery import shared_task

from .models import InscricaoNewsletter
from .services import enviar_newsletters

logger = logging.getLogger(__name__)


def _executar_e_logar(periodo):
    envio = enviar_newsletters(periodo=periodo)
    logger.info(
        "Task 'enviar_newsletters' (periodo=%s) concluída: %d enviados, %d falhas, %d processadas.",
        periodo,
        envio.total_enviados,
        envio.total_falhas,
        envio.total_inscricoes_processadas,
    )
    return envio.id


# Envios de newsletter têm efeito externo e não são idempotentes por
# execução; ack imediato é explícito para não reentregar um e-mail.
@shared_task(
    name="newsletter.tasks.enviar_newsletters",
    acks_late=False,
    reject_on_worker_lost=False,
)
def enviar_newsletters_task():
    """
    Mantida sem argumento (envia para TODAS as inscrições ativas,
    independente de período) para compatibilidade com quem já agenda/chama
    esta task pelo nome antigo. As execuções periódicas reais de produção
    usam as duas tasks abaixo (BRD seção 27 — resumo da manhã/noite como
    envios de fato distintos, não só um rótulo).
    """
    return _executar_e_logar(periodo=None)


@shared_task(
    name="newsletter.tasks.enviar_newsletters_manha",
    acks_late=False,
    reject_on_worker_lost=False,
)
def enviar_newsletters_manha_task():
    return _executar_e_logar(periodo=InscricaoNewsletter.PERIODO_MANHA)


@shared_task(
    name="newsletter.tasks.enviar_newsletters_noite",
    acks_late=False,
    reject_on_worker_lost=False,
)
def enviar_newsletters_noite_task():
    return _executar_e_logar(periodo=InscricaoNewsletter.PERIODO_NOITE)
