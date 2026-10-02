import logging

from celery import shared_task

from .models import InscricaoNewsletter
from .services import enviar_newsletters, expirar_pendencias

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


# ---------------------------------------------------------------------------
# DOUBLE OPT-IN — a varredura de pendências
# ---------------------------------------------------------------------------
#
# Esta task NÃO impede que uma pendência vencida confirme: isso é o prazo do
# `TimestampSigner` (`NEWSLETTER_TOKEN_CONFIRMACAO_MAX_AGE_SECONDS`), que vale
# desde o momento em que o link foi assinado. O que ela faz é carimbar
# `pendencia_expirada_em`, para que o banco responda "por que esta inscrição não
# confirmou?" — que é a pergunta que fica sem resposta quando o único fato é um
# `confirmado_em IS NULL`.
#
# É idempotente e sem efeito externo: não envia e-mail nenhum, e uma segunda
# execução encontra zero linhas (o filtro exige `pendencia_expirada_em IS
# NULL`). Por isso `acks_late=False` e `max_retries=0` são o certo — reexecutar
# não faria mal, e reexecutar gastaria um worker.
#
# NÃO está no `CELERY_BEAT_SCHEDULE`: a varredura é idempotente e barata
# (índice), e o prazo do token já é o que garante a correção mesmo sem ela. O
# que falta sem agendamento é a VISIBILIDADE, não a segurança. Registrar o nome
# da task no beat é decisão de quem opera o ambiente, e esta migration de
# estado pendente ainda depende de autorização.
@shared_task(
    name="newsletter.tasks.expirar_pendencias_task",
    acks_late=False,
    reject_on_worker_lost=False,
    max_retries=0,
)
def expirar_pendencias_task():
    expiradas = expirar_pendencias()
    logger.info(
        "Task 'expirar_pendencias' concluída: %d pendência(s) vencida(s).",
        expiradas,
    )
    return expiradas
