"""
Task Celery periodica de ingestao (implementation-contract.md, restricao de
performance: a ingestao deve ser assincrona, nao bloquear requisicoes HTTP).
Agendamento em `settings.CELERY_BEAT_SCHEDULE` (config/settings.py).

RETRY E IDEMPOTÊNCIA (P1-03, WS-06)
-----------------------------------
Antes desta alteração a task não tinha retry nenhum: uma falha de banco ou
de broker matava a execução do ciclo e o próximo disparo só voltaria 15
minutos depois. Agora:

* `autoretry_for` é uma lista ESTREITA de falhas transitórias de
  infraestrutura (banco indisponível, Redis indisponível). Erro de conteúdo
  de uma fonte não entra aqui: ele já é capturado por fonte dentro de
  `executar_ingestao` e vira `RegistroExecucaoIngestao.erros_por_fonte` — um
  RSS fora do ar não deve reprocessar a ingestão inteira.
* `max_retries`/`retry_backoff`/`retry_jitter` dão espera exponencial com
  dispersão, para que N workers que caíram juntos não voltem juntos.
* O número de tentativas é OBSERVÁVEL: vai para o log e para o estado
  durável (`config/filas_estado.py`), de onde `manage.py saude_filas` o lê.
  Um retry que ninguém pode ver é indistinguível de "não houve retry".
* Reexecutar não duplica: `NewsItem.url_fonte_original` é `UNIQUE` e a
  persistência em lote (`_persistir_news_items_em_lote`) filtra o que já
  existe antes de escrever. O teste
  `test_ingestao_retry_nao_duplica_conteudo` prova isso com uma falha
  depois da escrita.
"""

import logging

from celery import shared_task
from django.db import OperationalError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from config import filas_estado

from .services.ingestao import executar_ingestao

logger = logging.getLogger(__name__)

#: Falhas que justificam reprocessar o ciclo. Estreito de propósito: é
#: preferível um ciclo perdido (o beat dispara de novo em 15 min) a um
#: reprocessamento de uma falha que nunca vai passar.
EXCECOES_RETRY = (OperationalError, RedisConnectionError, RedisTimeoutError)

#: Tentativas extras além da primeira. 3 extras = 4 execuções no máximo,
#: com backoff 1s/2s/4s (+jitter) — dentro da janela de 15 min do beat.
MAX_TENTATIVAS = 3

TASK_INGESTAO = "catalogo_noticias.tasks.ingerir_noticias"


@shared_task(
    name=TASK_INGESTAO,
    acks_late=True,
    reject_on_worker_lost=True,
    bind=True,
    autoretry_for=EXCECOES_RETRY,
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=MAX_TENTATIVAS,
)
def ingerir_noticias(self):
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

    ``bind=True`` é o que dá acesso a ``self.request.retries``: sem ele a
    task não sabe em que tentativa está e o contador de tentativas do
    relatório seria sempre 1.
    """
    tentativa = int(getattr(self.request, "retries", 0) or 0) + 1
    total = int(self.max_retries) + 1
    try:
        registro = executar_ingestao()
    except BaseException as exc:
        # Registra a falha ANTES de propagar: é o `autoretry_for` que decide
        # se há retry, e o registro precisa existir em todas as tentativas,
        # não só na última.
        gravou, problema = filas_estado.registrar_ciclo(
            task=TASK_INGESTAO,
            estado=filas_estado.ESTADO_FALHA,
            tentativa=tentativa,
            max_tentativas=total,
            erro=exc,
        )
        logger.error(
            "Task 'ingerir_noticias' falhou (tentativa=%d/%d, gravou_estado=%s, "
            "problema_estado=%s, tipo=%s): %s",
            tentativa,
            total,
            gravou,
            problema,
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        raise

    gravou, problema = filas_estado.registrar_ciclo(
        task=TASK_INGESTAO,
        estado=filas_estado.ESTADO_SUCESSO,
        tentativa=tentativa,
        max_tentativas=total,
        detalhe={
            "registro_id": registro.id,
            "itens_ingeridos": registro.total_itens_ingeridos,
            "grupos_formados": registro.total_grupos_formados,
            "erros_por_fonte": len(registro.erros_por_fonte),
        },
    )
    logger.info(
        "Task 'ingerir_noticias' concluida (registro_id=%s, %d itens, %d erro(s) "
        "de fonte, tentativa=%d/%d, gravou_estado=%s, problema_estado=%s)",
        registro.id,
        registro.total_itens_ingeridos,
        len(registro.erros_por_fonte),
        tentativa,
        total,
        gravou,
        problema,
    )
    return registro.id
