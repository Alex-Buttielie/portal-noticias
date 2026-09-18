"""Resumo/classificacao via LLM (Chat Completions) — Frente B.

- ``resumir_em_lote(itens, cfg) -> list[dict]``: um dict por item de
  entrada, posicionalmente correspondente, com chaves
  {resumo, categoria, urgente} + {tokens, custo_usd} (observabilidade).
  Cada chamada HTTP cobre ate ``llm_lote`` itens; ``max_tokens`` do
  payload = ``llm_max_tokens`` (por item) x tamanho do lote.
- Sem chave (``llm_api_key`` vazia/ausente) levanta ``SemLLMError`` ANTES
  de qualquer HTTP — o chamador (``execucao``) marca tudo pendente.
- Falha de rede/resposta invalida levanta ``LLMError`` (o chamador trata
  o lote com fallback pendente, sem derrubar a execucao).
- Custo estimado = tokens/1000 x ``llm_preco_1k``. Quando o provedor nao
  devolve ``usage.total_tokens``, tokens/custo ficam ``None``/``0.0``
  (nunca inventados).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import requests

logger = logging.getLogger("ingestao.pipeline.summarizer")


class SemLLMError(Exception):
    """Sem chave de LLM configurada — resumo automatico indisponivel."""


class LLMError(Exception):
    """Provedor de LLM falhou (rede, HTTP nao-2xx, resposta invalida)."""


def _cfg(cfg: dict | Any, nome: str, default: Any) -> Any:
    if isinstance(cfg, dict):
        return cfg.get(nome, default)
    return getattr(cfg, nome, default)


def _api_key(cfg: dict | Any) -> str:
    for nome in ("llm_api_key", "api_key", "LLM_API_KEY"):
        v = _cfg(cfg, nome, "")
        if v:
            return str(v).strip()
    return (os.environ.get("LLM_API_KEY") or os.environ.get("CATALOGO_NOTICIAS_LLM_API_KEY") or "").strip()


def _montar_prompt_lote(itens: list[dict]) -> str:
    blocos = "\n\n".join(
        f"Noticia {i}:\nFonte: {it.get('nome_fonte', '')}\n"
        f"Titulo: {it.get('titulo', '')}\nConteudo: {it.get('summary', '') or it.get('content_html', '')}"
        for i, it in enumerate(itens, start=1)
    )
    return (
        "Voce e um assistente de curadoria jornalistica. Abaixo ha "
        f"{len(itens)} noticias NUMERADAS e INDEPENDENTES entre si "
        "(podem ou nao ser sobre o mesmo assunto — trate cada uma "
        "separadamente). Para CADA noticia, escreva um resumo PROPRIO "
        "(nunca copie frases literais do texto original, e nunca misture "
        "informacao de uma noticia com outra) e classifique categoria "
        "(uma palavra, ex.: politica, economia, esportes, tecnologia) e "
        f"se e urgente (true/false).\n\n{blocos}\n\n"
        f"Responda em JSON: uma lista com exatamente {len(itens)} objetos, "
        "um por noticia, na mesma ordem, cada um no formato "
        '\'{"id": <numero da noticia>, "resumo": ..., "categoria": ..., '
        '"urgente": ...}\'. Responda SOMENTE a lista JSON, sem texto '
        "adicional antes ou depois."
    )


def _chamar_api(prompt: str, cfg: dict | Any, max_tokens: int) -> dict:
    base = str(_cfg(cfg, "llm_base_url", "") or _cfg(cfg, "llm_api_base", "") or "").rstrip("/")
    if not base:
        raise LLMError("llm_base_url nao configurada.")
    modelo = str(_cfg(cfg, "llm_model", "gpt-4o-mini") or "gpt-4o-mini")
    timeout = int(_cfg(cfg, "llm_timeout", 30) or 30)
    try:
        resposta = requests.post(
            f"{base}/chat/completions",
            headers={
                "Authorization": f"Bearer {_api_key(cfg)}",
                "Content-Type": "application/json",
            },
            json={
                "model": modelo,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": max_tokens,
            },
            timeout=timeout,
        )
        resposta.raise_for_status()
        return resposta.json()
    except requests.RequestException as exc:
        raise LLMError(f"Falha ao chamar o provedor de LLM ({base}): {exc}") from exc


def _interpretar_resposta_lote(resposta: dict, n: int, preco_1k: float) -> list[dict]:
    try:
        conteudo = resposta["choices"][0]["message"]["content"]
        dados = json.loads(conteudo)
        if not isinstance(dados, list):
            raise ValueError("resposta em lote esperada como lista JSON")
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise LLMError(f"Resposta do provedor de LLM em formato inesperado: {exc}") from exc

    uso = resposta.get("usage", {}) or {}
    total = uso.get("total_tokens")
    por_item = (total // n) if total else None

    por_id: dict[int, dict] = {}
    for entrada in dados:
        if isinstance(entrada, dict) and isinstance(entrada.get("id"), int):
            por_id[entrada["id"]] = entrada

    resultados: list[dict] = []
    for i in range(1, n + 1):
        entrada = por_id.get(i)
        if not entrada or not str(entrada.get("resumo") or "").strip():
            # id ausente/invalido: NUNCA reaproveita resumo de outro id —
            # este item cai em revisao humana (resumo vazio).
            logger.warning("Item %d/%d sem resumo valido na resposta em lote — resumo vazio.", i, n)
            resultados.append({"resumo": "", "categoria": "", "urgente": False, "tokens": None, "custo_usd": 0.0})
            continue
        resultados.append(
            {
                "resumo": str(entrada["resumo"]),
                "categoria": str(entrada.get("categoria") or "").strip().lower(),
                "urgente": bool(entrada.get("urgente", False)),
                "tokens": por_item,
                "custo_usd": (por_item / 1000) * preco_1k if por_item else 0.0,
            }
        )
    return resultados


def resumir_em_lote(itens: list[dict], cfg: dict | Any) -> list[dict]:
    """Resume/classifica ``itens`` via LLM. Levanta ``SemLLMError`` sem chave."""
    if not itens:
        return []
    if not _api_key(cfg):
        raise SemLLMError(
            "LLM sem chave configurada (llm_api_key/LLM_API_KEY) — resumo automatico indisponivel."
        )
    tamanho_lote = max(1, int(_cfg(cfg, "llm_lote", 10) or 10))
    max_tokens_item = max(1, int(_cfg(cfg, "llm_max_tokens", 220) or 220))
    preco_1k = float(_cfg(cfg, "llm_preco_1k", 0.15) or 0.0)

    resultados: list[dict] = []
    for inicio in range(0, len(itens), tamanho_lote):
        lote = itens[inicio : inicio + tamanho_lote]
        prompt = _montar_prompt_lote(lote)
        resposta = _chamar_api(prompt, cfg, max_tokens_item * len(lote))
        resultados.extend(_interpretar_resposta_lote(resposta, len(lote), preco_1k))
    if len(resultados) != len(itens):
        raise LLMError("Numero de resultados diverge do numero de itens — lote descartado.")
    return resultados
