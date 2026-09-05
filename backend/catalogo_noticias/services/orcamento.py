"""
Orcamento diario do `SummarizationProvider` (implementation-contract.md, run
20260903-1211-teto-gasto-diario-llm) — mitigacao direta do risco "Custo de
IA/infraestrutura" (BRD secao 30, impacto Alto).

`services/ingestao.py::executar_ingestao` consulta `gasto_llm_hoje_usd()` e
`teto_excedido()` antes de cada lote de chamadas ao provedor; `metricas`
reaproveita as mesmas funcoes para expor o gasto do dia no painel de
observabilidade (nao ha modelo/tabela novo — tudo deriva de
`RegistroExecucaoIngestao`, ja existente).
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from ..models import RegistroExecucaoIngestao

logger = logging.getLogger(__name__)


def gasto_llm_hoje_usd() -> float:
    """
    Soma `RegistroExecucaoIngestao.custo_estimado_summarization_usd`
    (ignorando `None` — `Sum` do ORM ja faz isso) de execucoes cujo
    `executado_em` cai no dia corrente NO FUSO LOCAL do projeto
    (`TIME_ZONE = "America/Sao_Paulo"`, mesmo fuso ja usado pelo resto do
    projeto — ver `_itens_recentes_persistidos` em `services/ingestao.py`
    e `CELERY_TIMEZONE`). `timezone.now()` sempre devolve UTC (projeto usa
    `USE_TZ=True`) — por isso convertemos com `timezone.localtime()` ANTES
    de truncar a hora, senao a janela do "dia corrente" fica deslocada em
    3h (vira [21h de ontem, 21h de hoje) em horario de Sao Paulo).

    Agregacao via `Sum` (uma unica query), nunca iteracao em Python —
    mesmo cuidado de performance ja aplicado em
    `metricas/services.py::painel` (implementation-contract.md, restricao
    de performance).

    Fail-open (task-plan.md, risco "Falha ao persistir/consultar gasto do
    dia"): qualquer excecao ao calcular o gasto (ex.: problema de banco) e
    capturada AQUI, logada como warning, e a funcao devolve `0.0` — uma
    falha de LEITURA de metricas nunca pode interromper a ingestao (que
    depende deste valor antes de cada lote, ver
    `services/ingestao.py::executar_ingestao`).
    """
    try:
        agora_local = timezone.localtime(timezone.now())
        inicio_do_dia = agora_local.replace(hour=0, minute=0, second=0, microsecond=0)
        fim_do_dia = inicio_do_dia + timedelta(days=1)
        total = RegistroExecucaoIngestao.objects.filter(
            executado_em__gte=inicio_do_dia, executado_em__lt=fim_do_dia
        ).aggregate(total=Sum("custo_estimado_summarization_usd"))["total"]
        return float(total) if total is not None else 0.0
    except Exception:  # noqa: BLE001 — fail-open deliberado, ver docstring acima
        logger.warning(
            "Falha ao calcular gasto_llm_hoje_usd() — assumindo 0.0 (fail-open) "
            "para nao interromper a ingestao.",
            exc_info=True,
        )
        return 0.0


def teto_diario_usd() -> float:
    try:
        from catalogo_noticias.services.config_robo import cfg_valor

        return float(cfg_valor("CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD", "llm_teto_gasto_diario_usd", float))
    except Exception:
        return settings.CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD


def teto_excedido(gasto_acumulado_usd: float) -> bool:
    """`gasto_acumulado_usd >= teto_diario_usd()` — >= (nao >), o gasto que IGUALA o teto ja conta como excedido."""
    return gasto_acumulado_usd >= teto_diario_usd()
