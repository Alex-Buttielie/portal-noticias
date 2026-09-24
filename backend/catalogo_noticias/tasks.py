"""
Task Celery periodica de ingestao (implementation-contract.md, restricao de
performance: a ingestao deve ser assincrona, nao bloquear requisicoes HTTP).
Agendamento em `settings.CELERY_BEAT_SCHEDULE` (config/settings.py).
"""

import logging

from celery import shared_task

from .services.ingestao import executar_ingestao

logger = logging.getLogger(__name__)


@shared_task(
    name="catalogo_noticias.tasks.ingerir_noticias",
    acks_late=True,
    reject_on_worker_lost=True,
)
def ingerir_noticias():
    """
    Executa uma rodada do pipeline de ingestao (busca -> dedup -> resumo/
    classificacao -> fila de revisao) para todas as fontes configuradas em
    `settings.CATALOGO_NOTICIAS_FONTES_RSS`. Nao recebe argumentos: a task
    de producao sempre usa a configuracao corrente, nunca uma lista
    hardcoded (permite adicionar/remover fontes via config sem alterar
    codigo/deploy do worker).

    ``acks_late`` e ``reject_on_worker_lost`` são explícitos somente nesta
    task: cada grupo é transacional e a constraint/consulta de
    ``url_fonte_original`` torna uma reentrega idempotente. Um worker
    perdido pode repetir o fetch, mas não duplica o item já confirmado pelo
    banco; a reserva de custo antes do LLM mantém esse custo visível.
    """
    registro = executar_ingestao()
    logger.info(
        "Task 'ingerir_noticias' concluida (registro_id=%s, %d itens, %d erro(s) de fonte)",
        registro.id,
        registro.total_itens_ingeridos,
        len(registro.erros_por_fonte),
    )
    return registro.id
