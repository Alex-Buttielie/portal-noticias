"""Deduplicacao/agrupamento lexical — Frente B.

Replica a heuristica do portal (backend ``catalogo_noticias``):
titulos que cobrem o MESMO acontecimento sao agrupados por similaridade
ponderada de tokens, nao por igualdade de string.

- Tokens genericos do lote (df >= 4 em lotes >= 6 itens) + conectores
  jornalisticos curados recebem peso 0.15; demais tokens peso 1.0.
- Pareamento de tokens e fuzzy (SequenceMatcher por token >= 0.82),
  cobrindo variacao de genero/numero sem stopwords.
- ``similaridade(a, b)``: Jaccard fuzzy SEM ponderacao de lote (mesmo que
  o portal em uso isolado). ``a``/``b`` aceitam str (titulo) ou dict
  com chave ``titulo``.
- ``agrupar(itens, limiar=0.55)``: single-linkage sobre o lote; devolve
  lista de grupos (cada grupo = lista dos itens originais). A filtragem
  por janela temporal fica em ``execucao`` (aqui so similaridade).
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

_STOPWORDS_PT = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "um",
    "uma", "para", "com", "por", "que", "no", "na", "nos", "nas", "ao",
    "aos", "se", "sobre",
}

_LIMIAR_FUZZY_TOKEN = 0.82
_PESO_TOKEN_GENERICO = 0.15
_DF_MINIMO_GENERICO = 4
_TAMANHO_MINIMO_LOTE_PARA_PESO = 6

_PESO_TOKEN_CONECTOR_CURADO = 0.15
_CONECTORES_JORNALISTICOS_COMUNS_PT = {
    "anuncia", "anuncio", "anuncios", "anunciam", "anunciou", "anunciando",
    "anunciado", "anunciada", "anunciados", "anunciadas",
    "lanca", "lança", "lancam", "lançam", "lancou", "lançou", "lancamento",
    "lançamento",
    "divulga", "divulgam", "divulgou", "divulgacao", "divulgação",
    "apresenta", "apresentam", "apresentou", "apresentacao", "apresentação",
    "plano", "planos", "pacote", "pacotes", "medida", "medidas",
    "programa", "programas", "projeto", "projetos", "proposta", "propostas",
    "governo", "governamental", "prefeitura",
    "policia", "polícia", "policial", "policiais",
    "investiga", "investigam", "investigou", "investigacao", "investigação",
    "novo", "nova", "novos", "novas",
}


def _titulo_de(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("titulo") or item.get("title") or "")
    return str(getattr(item, "titulo", "") or "")


def _tokens_titulo(titulo: str) -> set[str]:
    titulo = titulo.lower()
    titulo = re.sub(r"[^\w\s]", " ", titulo)
    return {p for p in titulo.split() if p not in _STOPWORDS_PT}


def _pesos_por_frequencia_no_lote(lista_de_tokens: list[set[str]]) -> dict[str, float]:
    pesos: dict[str, float] = {}
    n = len(lista_de_tokens)
    if n > 0:
        frequencia: dict[str, int] = {}
        for tokens in lista_de_tokens:
            for token in tokens:
                frequencia[token] = frequencia.get(token, 0) + 1
        limiar = _DF_MINIMO_GENERICO if n >= _TAMANHO_MINIMO_LOTE_PARA_PESO else n + 1
        pesos = {tok: (_PESO_TOKEN_GENERICO if freq >= limiar else 1.0) for tok, freq in frequencia.items()}
    for tokens in lista_de_tokens:
        for token in tokens:
            if token in _CONECTORES_JORNALISTICOS_COMUNS_PT:
                pesos[token] = min(pesos.get(token, 1.0), _PESO_TOKEN_CONECTOR_CURADO)
    return pesos


def _tokens_fuzzy_pareados(tokens_a: set[str], tokens_b: set[str]) -> list[tuple[str, str]]:
    comuns = tokens_a & tokens_b
    pares = [(t, t) for t in comuns]
    restantes_a = tokens_a - comuns
    restantes_b = set(tokens_b - comuns)
    for token_a in restantes_a:
        melhor, melhor_score = None, 0.0
        for token_b in restantes_b:
            score = SequenceMatcher(None, token_a, token_b).ratio()
            if score > melhor_score:
                melhor, melhor_score = token_b, score
        if melhor is not None and melhor_score >= _LIMIAR_FUZZY_TOKEN:
            pares.append((token_a, melhor))
            restantes_b.discard(melhor)
    return pares


def _similaridade_ponderada(tokens_a: set[str], tokens_b: set[str], pesos: dict[str, float]) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    pares = _tokens_fuzzy_pareados(tokens_a, tokens_b)
    peso_inter = sum(max(pesos.get(a, 1.0), pesos.get(b, 1.0)) for a, b in pares)
    peso_uniao = sum(pesos.get(t, 1.0) for t in (tokens_a | tokens_b))
    return peso_inter / peso_uniao if peso_uniao > 0 else 0.0


def similaridade(a: Any, b: Any) -> float:
    """Similaridade [0,1] entre dois titulos (ou itens com titulo)."""
    return _similaridade_ponderada(_tokens_titulo(_titulo_de(a)), _tokens_titulo(_titulo_de(b)), {})


def agrupar(itens: list[Any], limiar: float = 0.55) -> list[list[Any]]:
    """Agrupa itens do mesmo acontecimento (single-linkage, >= limiar).

    Grupos de 1 item = sem cobertura duplicada neste lote (nao geram
    cluster — ver ``execucao``).
    """
    tokens_por_item = [_tokens_titulo(_titulo_de(item)) for item in itens]
    pesos = _pesos_por_frequencia_no_lote(tokens_por_item)
    grupos_idx: list[list[int]] = []
    for i, tokens in enumerate(tokens_por_item):
        melhor_grupo, melhor_score = None, 0.0
        for gi, idxs in enumerate(grupos_idx):
            score = max(
                _similaridade_ponderada(tokens, tokens_por_item[j], pesos) for j in idxs
            )
            if score > melhor_score:
                melhor_grupo, melhor_score = gi, score
        if melhor_grupo is not None and melhor_score >= limiar:
            grupos_idx[melhor_grupo].append(i)
        else:
            grupos_idx.append([i])
    return [[itens[i] for i in idxs] for idxs in grupos_idx]
