"""
Task Celery periodica de ingestao (implementation-contract.md, restricao de
performance: a ingestao deve ser assincrona, nao bloquear requisicoes HTTP).
Agendamento em `settings.CELERY_BEAT_SCHEDULE` (config/settings.py).
"""

import logging

from celery import shared_task

from .services.ingestao import executar_ingestao

logger = logging.getLogger(__name__)


@shared_task(name="catalogo_noticias.tasks.ingerir_noticias")
def ingerir_noticias():
    """
    Executa uma rodada do pipeline de ingestao (busca -> dedup -> resumo/
    classificacao -> fila de revisao) para todas as fontes configuradas em
    `settings.CATALOGO_NOTICIAS_FONTES_RSS`. Nao recebe argumentos: a task
    de producao sempre usa a configuracao corrente, nunca uma lista
    hardcoded (permite adicionar/remover fontes via config sem alterar
    codigo/deploy do worker).
    """
    registro = executar_ingestao()
    logger.info(
        "Task 'ingerir_noticias' concluida (registro_id=%s, %d itens, %d erro(s) de fonte)",
        registro.id,
        registro.total_itens_ingeridos,
        len(registro.erros_por_fonte),
    )
    return registro.id
