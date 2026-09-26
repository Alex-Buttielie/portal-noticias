"""
Metrica rotulada do resultado da sumarizacao — P1-02 (workstream WS-08,
gate GP-5).

O que existe antes desta intervencao
------------------------------------
Nenhuma. Quando o `SummarizationProvider` falhava, o unico rastro era uma
linha de log com o texto da excecao e um `resumo_proprio` vazio que virava
`status_revisao=pendente` (item invisivel no feed). Nada permitia dizer, em
metrica, "quantas noticias de hoje sairam do provedor e quantas sairam do
fallback, e por que". Era um sistema degradado com aparencia saudavel.

O que este modulo entrega
-------------------------
Um contador com ROTULO duplo, exatamente no formato pedido pelo backlog:

    resultado = sucesso | fallback
    motivo    = sem_credencial | timeout | erro_http | rate_limit
                | conteudo_insuficiente | resposta_invalida
                | erro_do_provider | teto_de_gasto | aplicado

* `registrar()` incrementa e emite uma linha de log estruturado com o rotulo.
* `snapshot()` devolve a leitura corrente do processo.

LIMITACAO CONHECIDA, DECLARADA (nao e falha oculta)
--------------------------------------------------
Este contador e DE PROCESSO. Cada worker Gunicorn/Celery tem o seu: o painel
de observabilidade multi-processo nao pode somar varios processos a partir
dele sem um backend de metricas compartilhado (que este projeto nao tem — ver
`metricas/models.py`, cujas metricas sao todas derivadas do banco por ORM).
Por isso a leitura DURADAVEIRA e separada, em
`metricas/services.py::painel()`, e deriva do marcador persistido em
`NewsItem.tags` (`fallback_local.TAG_ORIGEM_FALLBACK`): essa sobrevive a
reinicio e e a fonte da verdade para o painel. `snapshot()` serve para
correlacionar log e metrica dentro do mesmo processo.

Higiene de log: este modulo NUNCA recebe nem registra credencial, cabecalho de
autorizacao ou corpo de resposta do provedor — apenas rotulos fechados e
contagens. Rotulo fora do conjunto conhecido e normalizado para
`erro_interno` (cardinalidade limitada; um rotulo livre permitiria
cardinalidade ilimitada e, no pior caso, vazar texto sensivel para o nome da
metrica).
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from ..providers.fallback_local import (
    MOTIVO_APLICADO,
    MOTIVOS_CONHECIDOS,
    normalizar_motivo,
)

logger = logging.getLogger(__name__)

RESULTADO_SUCESSO = "sucesso"
RESULTADO_FALLBACK = "fallback"
RESULTADOS_CONHECIDOS = (RESULTADO_SUCESSO, RESULTADO_FALLBACK)

_lock = threading.Lock()
_contadores: dict[tuple[str, str], int] = {}


def _normalizar_resultado(resultado: object) -> str:
    texto = str(resultado or "").strip()
    if texto in RESULTADOS_CONHECIDOS:
        return texto
    # Resultado desconhecido e um bug de chamada: nunca vira rotulo livre.
    logger.warning(
        "telemetria_resumo resultado desconhecido %r — registrado como %s.",
        texto[:40],
        RESULTADO_FALLBACK,
    )
    return RESULTADO_FALLBACK


def registrar(resultado: str, motivo: str, quantidade: int = 1) -> None:
    """
    Incrementa o contador rotulado e emite o log estruturado correspondente.

    `quantidade` permite registrar um LOTE inteiro de uma vez (uma chamada em
    lote do provider = N itens), evitando N linhas de log identicas.
    """
    resultado_normalizado = _normalizar_resultado(resultado)
    motivo_normalizado = normalizar_motivo(motivo)
    try:
        passo = int(quantidade)
    except (TypeError, ValueError):
        passo = 1
    if passo < 1:
        passo = 1

    with _lock:
        chave = (resultado_normalizado, motivo_normalizado)
        _contadores[chave] = _contadores.get(chave, 0) + passo
        total = _contadores[chave]

    # Log estruturado: rotulo + contagem. Sem credencial, sem conteudo, sem
    # corpo de resposta do provedor (nunca).
    logger.info(
        "telemetria_resumo resultado=%s motivo=%s quantidade=%d total_rotulo=%d",
        resultado_normalizado,
        motivo_normalizado,
        passo,
        total,
    )


def registrar_sucesso(quantidade: int = 1) -> None:
    """Atalho do caminho feliz: o provedor respondeu e o resumo foi aplicado."""
    registrar(RESULTADO_SUCESSO, MOTIVO_APLICADO, quantidade)


def registrar_fallback(motivo: str, quantidade: int = 1) -> None:
    """Atalho do caminho degradado, com o motivo ja normalizado."""
    registrar(RESULTADO_FALLBACK, motivo, quantidade)


def snapshot() -> dict:
    """
    Leitura do processo, agrupada por resultado.

    {
      "sucesso": {"aplicado": 3, "total": 3},
      "fallback": {"timeout": 1, "sem_credencial": 2, "total": 3},
    }
    """
    with _lock:
        copia = dict(_contadores)

    por_resultado: dict[str, dict[str, int]] = {
        RESULTADO_SUCESSO: {},
        RESULTADO_FALLBACK: {},
    }
    for (resultado, motivo), total in copia.items():
        por_resultado.setdefault(resultado, {})[motivo] = total

    saida: dict[str, dict[str, int]] = {}
    for resultado, contagem in por_resultado.items():
        linha = dict(contagem)
        linha["total"] = sum(contagem.values())
        saida[resultado] = linha
    return saida


def total(resultado: Optional[str] = None) -> int:
    """Total acumulado; com `resultado`, so aquele rotulo (util em asserts)."""
    dados = snapshot()
    if resultado is None:
        return sum(linha.get("total", 0) for linha in dados.values())
    return dados.get(str(resultado or ""), {}).get("total", 0)


def zerar() -> None:
    """Zera os contadores. Usado por testes (a suite roda em um so processo)."""
    with _lock:
        _contadores.clear()


def motivos_conhecidos() -> frozenset[str]:
    return MOTIVOS_CONHECIDOS
