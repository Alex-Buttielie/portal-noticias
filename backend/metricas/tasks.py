"""Rotina periódica de expurgo de analytics de produto (retenção).

Implementa o critério de aceite 24 (implementation-contract.md, run
20260925-1020-observabilidade): "Dado uma retenção de 12 meses, quando o job
de expurgo roda, então eventos brutos e agregados anteriores à janela são
removidos de forma idempotente e o job é auditável".

Três propriedades não negociáveis:

* **Idempotente** — o filtro é sempre "anterior ao corte", então rodar duas
  vezes seguidas (reentrega do beat, retry manual, dois workers) não muda o
  resultado e não duplica efeito.
* **Em lotes** — `DELETE` de tabela inteira numa base de produção segura travar
  tabela e degradar o banco (o app inteiro). O job lê e apaga N primaries por
  vez, em requisições curtas.
* **Auditável e sem dado pessoal** — o log técnico carrega contagens, corte,
  duração e ambiente/release. NUNCA a query buscada, o path acessado, a
  sessão, o usuário ou o e-mail: o job roda justamente para reduzir dado
  pessoal, e não para imprimi-lo no stdout (que é ingerido por Loki).

Sobre "agregados": este projeto não materializa agregados de analytics em
tabela — todo agregado (termos populares, popularidade, engajamento) é
calculado por `Count/Sum` sobre os eventos brutos em tempo de leitura. O que
existe de agregado é o SNAPSHOT em cache (`feed:autocomplete:v2:populares`,
derivado de `EventoBusca`), e é ele que o job invalida: sem isso, a UI
continuaria servindo um agregado computado sobre eventos já expurgados.
"""

from __future__ import annotations

import logging
import time
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import EventoSite

logger = logging.getLogger(__name__)

# Teto de lotes por execução: protege contra laço infinito se um `delete` não
# remover as linhas selecionadas (não deveria acontecer, mas um job de expurgo
# que roda para sempre é pior do que um job que roda amanhã).
MAX_LOTES = 10_000


def _modelos_de_evento() -> list[tuple[str, object]]:
    """Eventos brutos de analytics, na ordem de maior para menor volume.

    Import local: `feed` importa `catalogo_noticias`, e importar no topo do
    módulo criaria dependência circular durante o autodiscover do Celery.
    """

    from feed.models import EventoBusca, InteracaoNoticia

    return [
        ("metricas.EventoSite", EventoSite),
        ("feed.InteracaoNoticia", InteracaoNoticia),
        ("feed.EventoBusca", EventoBusca),
    ]


def _invalida_agregados_cache() -> None:
    """Dropa os snapshots derivados dos eventos expurgados (idempotente)."""

    from feed.busca import invalidar_cache_autocomplete

    invalidar_cache_autocomplete()


@shared_task(
    name="metricas.tasks.expurar_analytics",
    acks_late=True,
    reject_on_worker_lost=True,
    ignore_result=True,
)
def expurar_analytics(dias: int | None = None, lote: int | None = None) -> dict:
    """Expurga eventos de analytics anteriores à janela de retenção.

    ``dias`` e ``lote`` existem para operação manual (teste em ambiente
    controlado com janela reduzida); o agendamento usa os settings.
    """

    from config.metrics import METRICS

    started = time.perf_counter()
    retencao = int(dias if dias is not None else getattr(settings, "ANALYTICS_RETENTION_DAYS", 365))
    tamanho = int(lote if lote is not None else getattr(settings, "ANALYTICS_EXPURGO_LOTE", 1000))
    retencao = max(0, retencao)
    tamanho = max(1, min(50_000, tamanho))
    corte = timezone.now() - timedelta(days=retencao)

    removidos: dict[str, int] = {}
    lotes: dict[str, int] = {}
    for nome, model in _modelos_de_evento():
        total = 0
        executados = 0
        while executados < MAX_LOTES:
            pks = list(
                model.objects.filter(criado_em__lt=corte).values_list("pk", flat=True)[:tamanho]
            )
            if not pks:
                break
            apagados, _ = model.objects.filter(pk__in=pks).delete()
            total += int(apagados or 0)
            executados += 1
            if apagados <= 0:
                # As linhas continuam selecionáveis mas não saem: melhor
                # parar (e deixar visível no log) do que girar até MAX_LOTES.
                logger.error(
                    "expurgo de analytics: %sSelected=%s deleted=0 — interrupting batch "
                    "to avoid a loop",
                    nome,
                    len(pks),
                )
                break
        removidos[nome] = total
        lotes[nome] = executados
        # A contagem é o VALOR do contador, não um rótulo: como `rows=total`,
        # cada contagem distinta criava uma série nova (crescendo com a variação
        # diária) e o alerta por `rows` não agregava nada (achado MINOR-5).
        #
        # Atenção ao chamar `inc`: o segundo parâmetro POSICIONAL é o valor, e
        # `value=` como keyword colidiria com ele (viraria incremento, não
        # rótulo). O rótulo é só `model`, que é o que separa a série.
        METRICS.inc("portal_analytics_purge_deleted_total", total, model=nome)

    _invalida_agregados_cache()

    duracao = time.perf_counter() - started
    total_removido = sum(removidos.values())
    METRICS.observe("portal_analytics_purge_duration_seconds", duracao)
    # Log técnico: contagens e janela, nada de conteúdo de evento.
    logger.info(
        "expurgo de analytics concluido: corte=%s retencao_dias=%s removidos=%s "
        "lotes=%s total_removido=%s duracao_s=%.3f",
        corte.isoformat(),
        retencao,
        removidos,
        lotes,
        total_removido,
        duracao,
    )
    return {
        "corte": corte.isoformat(),
        "retencao_dias": retencao,
        "lote": tamanho,
        "removidos": removidos,
        "lotes": lotes,
        "total_removido": total_removido,
        "duracao_s": round(duracao, 3),
    }


__all__ = ["MAX_LOTES", "expurar_analytics"]
