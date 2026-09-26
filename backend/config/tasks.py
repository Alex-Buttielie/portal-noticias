"""
Tasks Celery do próprio subsistema de filas do portal (P1-03, WS-06).

`config` NÃO é uma app do Django (não está em `INSTALLED_APPS`), então
`app.autodiscover_tasks()` não encontra este módulo sozinho. O registro é
feito explicitamente em `config/celery.py`, que importa este arquivo — o que
também significa que o import acontece cedo, antes de `django.setup()`
terminar. Por isso este módulo NÃO importa models nem toca em settings no
nível do módulo: só `celery` e `config.filas_estado` (que resolve settings
por chamada, em tempo de execução).

NOME ESTÁVEL
------------
`config.tasks.heartbeat_beat` é o contrato entre o beat, o worker e o
monitor. Renomear a task ou a chave do `CELERY_BEAT_SCHEDULE` quebra, em
silêncio, a única prova de que a agenda está rodando — por isso o nome é
fixo e há teste que falha se a chave do beat_schedule e o `name=` divergirem.
"""

from __future__ import annotations

import logging

from celery import shared_task

from . import filas_estado

logger = logging.getLogger(__name__)

#: Nome público da task de heartbeat. Também é a chave usada no
#: `CELERY_BEAT_SCHEDULE` (`portal-heartbeat-beat` -> esta task).
NOME_HEARTBEAT_BEAT = "config.tasks.heartbeat_beat"

#: Intervalo do heartbeat, em segundos (`FILAS_HEARTBEAT_INTERVALO_SEGUNDOS`).
#: O agendamento real fica em `settings.CELERY_BEAT_SCHEDULE`; aqui só fica
#: o valor espelhado para conferência (e para o teste que compara os dois).
INTERVALO_HEARTBEAT_PADRAO = 300


@shared_task(
    name=NOME_HEARTBEAT_BEAT,
    acks_late=False,
    reject_on_worker_lost=False,
    max_retries=0,
)
def heartbeat_beat(enfileirado_em: float | None = None) -> dict:
    """
    Grava em disco a prova de que o beat disparou e um worker consumiu.

    `acks_late=False` e `max_retries=0` são deliberados: o heartbeat não
    tem efeito externo, é idempotente por construção (sobrescreve o próprio
    registro), e reexecutá-lo só fabricaria um sinal mais fresco sem
    qualquer trabalho novo. O valor por baixo (`enfileirado_em`) é o
    epoch do momento em que a mensagem foi publicada; quando ausente (o beat
    envia argumentos fixos, então em produção costuma vir `None`) o registro
    usa o instante da execução — e o relatório trata a idade pela data do
    registro, nunca por mtime de arquivo.

    Devolve o próprio registro gravado, para que um teste/leitor possa
    conferir sem reabrir o arquivo.
    """
    gravou, problema = filas_estado.registrar_beat(
        task=NOME_HEARTBEAT_BEAT,
        enfileirado_em=enfileirado_em,
    )
    if not gravou:
        # Falha de escrita TEM de aparecer: um beat que não consegue gravar o
        # estado não está mais sendo monitorado, e calar aqui devolveria ao
        # relatório um "nunca observado" sem explicação.
        logger.error(
            "Heartbeat do beat NAO pode ser gravado em %s: %s",
            filas_estado.caminho_estado(),
            problema,
        )
    estado = filas_estado.ler_estado()
    registro = estado.get("beat") or {}
    logger.info(
        "Heartbeat do beat registrado (task_id=%s, gravado=%s, arquivo=%s)",
        registro.get("task_id"),
        gravou,
        filas_estado.caminho_estado(),
    )
    return {
        "gravado": gravou,
        "problema": problema,
        "task": NOME_HEARTBEAT_BEAT,
        "registrado_em": registro.get("registrado_em"),
    }
