"""Canal durável de telemetria de job: worker -> processo que serve `/metrics`.

Por que isto existe (achado MAJOR-4 da revisão do backend, run
20260925-1020-observabilidade): `config/metrics.py` é um registro **por
processo**, e o `/metrics` é servido pelo processo **web**. O `record_celery`
roda no **worker** e o expurgo de analytics é disparado pelo **beat** — nenhum
dos dois serve `/metrics`. Logo `portal_celery_tasks_total`,
`portal_celery_task_duration_seconds` e `portal_analytics_purge_*` não
apareciam em **nenhum** scrape: o painel de jobs que o contrato promete (critério
14) não tinha dado, e não existia métrica de **atraso** nenhum.

O que este módulo entrega, e o que ele NÃO entrega, está escrito aqui porque a
distinção é o ponto:

* **Entrega (nesta arquitetura, single-node)**: um arquivo de estado em disco
  que o worker/atualiza a cada task e o processo web lê. É o mesmo padrão do
  heartbeat do beat (`OBSERVABILITY_BEAT_HEARTBEAT_FILE` +
  `infra/systemd/celery-beat-heartbeat@.service`), escolhido em vez de uma
  tabela de domínio porque não exige migration e não guarda dado pessoal — o
  conteúdo é nome de task (código), estado final e contagens. A partir dele o
  processo web publica `portal_job_task_idle_seconds` (o **atraso** que o
  contrato pedia), contagem por resultado, retries e soma/count de duração.
* **Não entrega, e é cross-process por natureza**: o histograma por task
  (`portal_celery_task_duration_seconds`) continua no processo worker. Expor
  histogramas de outro processo exige um exporter no worker (Pushgateway ou
  porta própria) — isso é do bloco de infra, e está registrado em vez de
  fingido aqui. O que o canal durável entrega é o agregável (`_sum`/`_count`) e
  a frescor, que é 90% do alerta de "job travado".

Semântica das métricas publicadas: são **gauges com valor absoluto** lidos do
arquivo, não contadores incrementados. O produtor é outro processo, então somar
por `instance` (o padrão do projeto para counters) multiplicaria o mesmo número.
Use `max()`/`last()`; nunca `rate()` sobre elas.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger("config.job_state")

SETTING_ARQUIVO = "OBSERVABILITY_JOB_STATE_FILE"
SETTING_IDADE_MAXIMA = "OBSERVABILITY_JOB_STATE_MAX_AGE_SECONDS"
# Teto de nomes de task mantidos no arquivo. O vocabulário real é o registro de
# tasks do Celery (dezenas); o teto existe para que um chamador com nome
# dinâmico não vire crescimento de arquivo em disco.
MAX_TASKS = 200
VERSAO = 1

# RLock, não Lock: `_mutar` segura o lock e chama `ler()`, que também o pega.
_lock = threading.RLock()


def _setting(nome: str, padrao: str = "") -> str:
    try:
        from django.conf import settings
    except Exception:  # noqa: BLE001 - importável sem Django pronto
        return padrao
    try:
        return str(getattr(settings, nome, padrao) or "").strip()
    except Exception:  # noqa: BLE001
        return padrao


def caminho() -> Path | None:
    """Caminho configurado, ou `None` quando o canal não está ligado."""

    bruto = _setting(SETTING_ARQUIVO)
    return Path(bruto) if bruto else None


def idade_maxima() -> float:
    try:
        return max(1.0, float(_setting(SETTING_IDADE_MAXIMA, "900")))
    except (TypeError, ValueError):
        return 900.0


def _estado_vazio() -> dict:
    return {"versao": VERSAO, "atualizado_em": 0.0, "tasks": {}}


def _carregar(caminho_arquivo: Path) -> dict:
    dados = json.loads(caminho_arquivo.read_text(encoding="utf-8"))
    if not isinstance(dados, dict) or not isinstance(dados.get("tasks"), dict):
        raise ValueError("formato")
    return dados


def ler() -> dict | None:
    """Estado gravado pelo worker, ou `None` se não há canal legível."""

    alvo = caminho()
    if alvo is None:
        return None
    try:
        with _lock:
            return _carregar(alvo)
    except FileNotFoundError:
        return None
    except Exception as exc:  # noqa: BLE001 - leitura nunca derruba o processo
        logger.warning("estado de job ilegível (%s): %s", type(exc).__name__, alvo)
        return None


def _gravar(estado: dict) -> None:
    """Escrita atômica: arquivo temporário + `os.replace`.

    Um `write` direto deixaria o leitor do processo web vendo JSON pela metade
    (e o reader o trataria como ilegível, apagando a telemetria por um instante).
    """

    alvo = caminho()
    if alvo is None:
        return
    alvo.parent.mkdir(parents=True, exist_ok=True)
    temporario = alvo.with_name(f"{alvo.name}.tmp-{os.getpid()}")
    temporario.write_text(json.dumps(estado, sort_keys=True), encoding="utf-8")
    os.replace(temporario, alvo)


def _recortar(estado: dict) -> dict:
    tasks = estado.get("tasks") or {}
    if len(tasks) <= MAX_TASKS:
        return estado
    # `item[1]` pode não ser um dict se o arquivo foi editado à mão: um registro
    # corrompido não pode impedir a gravação dos demais.
    ordenadas = sorted(
        tasks.items(),
        key=lambda item: float((item[1] or {}).get("ultimo_fim") or 0)
        if isinstance(item[1], dict)
        else 0.0,
        reverse=True,
    )
    estado["tasks"] = dict(ordenadas[:MAX_TASKS])
    return estado


def _registro_novo() -> dict:
    return {
        "resultados": {},
        "retries": 0,
        "duracao_soma": 0.0,
        "duracao_contagem": 0,
        "ultimo_fim": 0.0,
        "ultimo_sucesso": 0.0,
    }


def _mutar(mutacao) -> None:
    if caminho() is None:
        return
    with _lock:
        try:
            estado = ler() or _estado_vazio()
            mutacao(estado)
            estado["versao"] = VERSAO
            estado["atualizado_em"] = time.time()
            _gravar(_recortar(estado))
        except Exception as exc:  # noqa: BLE001 - telemetria nunca derruba o worker
            logger.warning("estado de job não gravado (%s)", type(exc).__name__)


def registrar_task(nome: str, resultado: str, duracao: float) -> None:
    """Fim de execução de task: contagem por resultado, duração e frescor."""

    task = str(nome or "desconhecida")[:160]
    estado_final = str(resultado or "unknown")[:32]
    agora = time.time()

    def _aplica(estado: dict) -> None:
        tasks = estado.setdefault("tasks", {})
        registro = tasks.get(task)
        if not isinstance(registro, dict):
            registro = tasks[task] = _registro_novo()
        resultados = registro.setdefault("resultados", {})
        resultados[estado_final] = int(resultados.get(estado_final, 0)) + 1
        try:
            registro["duracao_soma"] = float(registro.get("duracao_soma") or 0.0) + max(0.0, float(duracao))
        except (TypeError, ValueError):
            pass
        registro["duracao_contagem"] = int(registro.get("duracao_contagem") or 0) + 1
        registro["ultimo_fim"] = agora
        if estado_final == "SUCCESS":
            registro["ultimo_sucesso"] = agora

    _mutar(_aplica)


def registrar_retry(nome: str) -> None:
    """Retry pedido pelo Celery (critério 14: retry precisa ser consultável)."""

    task = str(nome or "desconhecida")[:160]

    def _aplica(estado: dict) -> None:
        tasks = estado.setdefault("tasks", {})
        registro = tasks.get(task)
        if not isinstance(registro, dict):
            registro = tasks[task] = _registro_novo()
        registro["retries"] = int(registro.get("retries") or 0) + 1

    _mutar(_aplica)


def publicar_metricas(estado: dict | None = None) -> dict | None:
    """Publica o estado durável no registry do processo web.

    Devolve um resumo para o health check (`{"tasks": n, "age_seconds": x}`)
    ou `None` quando não há canal legível — o check transforma "não há como
    saber" em degradação, nunca em `ok`.
    """

    from .metrics import METRICS

    if estado is None:
        estado = ler()
    if not estado:
        return None
    agora = time.time()
    atualizado = float(estado.get("atualizado_em") or 0.0)
    # Clock entre o worker e o web pode estar adiantado: idade negativa é 0, não
    # um freshness "infinitamente bom".
    idade = max(0.0, agora - atualizado) if atualizado else 0.0
    METRICS.gauge("portal_job_state_age_seconds", idade)
    tasks = estado.get("tasks") or {}
    for task, registro in tasks.items():
        if not isinstance(registro, dict):
            continue
        rotulo = str(task)[:160]
        for resultado, contagem in (registro.get("resultados") or {}).items():
            METRICS.gauge(
                "portal_job_tasks_recorded", float(contagem), task=rotulo, result=str(resultado)[:32]
            )
        METRICS.gauge(
            "portal_job_task_retries_recorded", float(registro.get("retries") or 0), task=rotulo
        )
        METRICS.gauge(
            "portal_job_task_duration_seconds_sum",
            float(registro.get("duracao_soma") or 0.0),
            task=rotulo,
        )
        METRICS.gauge(
            "portal_job_task_duration_seconds_count",
            float(registro.get("duracao_contagem") or 0),
            task=rotulo,
        )
        sucesso = float(registro.get("ultimo_sucesso") or 0.0)
        METRICS.gauge(
            "portal_job_task_idle_seconds",
            max(0.0, agora - sucesso) if sucesso else -1.0,
            task=rotulo,
        )
    return {"tasks": len(tasks), "age_seconds": round(idade, 1)}


__all__ = [
    "MAX_TASKS",
    "SETTING_ARQUIVO",
    "SETTING_IDADE_MAXIMA",
    "caminho",
    "idade_maxima",
    "ler",
    "publicar_metricas",
    "registrar_retry",
    "registrar_task",
]
