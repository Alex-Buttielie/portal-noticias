"""Curadoria: decide publicacao direta vs. revisao humana — Frente B.

``decidir_status(item, resumo, n_fontes, cfg) -> "pendente" | "aprovado"``

- ``item``: dict bruto (chaves de ``rss.buscar_itens``).
- ``resumo``: dict de ``summarizer.resumir_em_lote`` ({resumo, categoria,
  urgente}) OU str (resumo puro — categoria cai para a do item).
- ``n_fontes``: tamanho do grupo/dedup a que o item pertence (n. de itens
  que cobrem o mesmo acontecimento neste ciclo, incluindo janela recente).
- ``cfg``: dict com resumo_sim_max (0.6), resumo_trecho_max (0.6),
  categorias_sensiveis (str csv ou lista), limiar_fontes_alta_relevancia
  (3), cluster_sempre_revisao (True).

Regras do portal (TODAS aplicadas, nesta ordem):
 1. sem resumo confiavel -> pendente (nunca publicar sem resumo proprio).
 2. resumo copia/quase-copia do bruto (ratio >= resumo_sim_max OU trecho
    continuo copiado >= resumo_trecho_max) -> pendente (BRD §18).
 3. categoria sensivel OU n_fontes >= limiar -> pendente (alta relevancia).
 4. grupo com 2+ itens e cluster_sempre_revisao=True -> pendente.
 5. senao -> aprovado.

Regras NOVAS desta frente (documentadas):
 N1. titulo muito curto (< 15 chars uteis) -> pendente (manchete
     truncada/ilegivel nao deve publicar sozinha).
 N2. URL ausente/invalida (nao comeca com http) -> pendente
     (rastreabilidade BRD §18 — defesa em profundidade alem do rss.py).
 N3. titulo TODO EM MAIUSCULAS (shouting/clickbait, >= 15 letras e
     >= 80% maiusculas) -> pendente.
 N4. resumo muito curto (< 30 chars) mas nao vazio -> pendente (resumo
     degenerado do provedor).
"""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

PENDENTE = "pendente"
APROVADO = "aprovado"

_TAMANHO_MINIMO_TRECHO_COPIADO = 20
_TITULO_MINIMO_CHARS = 15
_RESUMO_MINIMO_CHARS = 30


def _cfg(cfg: Any, nome: str, default: Any) -> Any:
    if isinstance(cfg, dict):
        return cfg.get(nome, default)
    return getattr(cfg, nome, default)


def _texto_bruto(item: dict) -> str:
    if not isinstance(item, dict):
        return str(item or "")
    return str(
        item.get("content_html") or item.get("summary") or item.get("conteudo") or ""
    )


def _resumo_e_categoria(resumo: Any, item: dict) -> tuple[str, str]:
    if isinstance(resumo, dict):
        texto = str(resumo.get("resumo") or "")
        categoria = str(resumo.get("categoria") or item.get("categoria") or "")
    else:
        texto, categoria = str(resumo or ""), str(item.get("categoria") or "")
    return texto, categoria.strip().lower()


def _proporcao_copiada(resumo: str, bruto: str) -> float:
    """Fracao dos chars do resumo em blocos continuos identicos do bruto.

    Blocos < 20 chars sao ignorados (vocabulario compartilhado normal nao
    conta como copia de TRECHO). Normalizada pelo tamanho do PROPRIO
    resumo — pega copia verbatim de trecho curto em materia longa, caso
    que ``SequenceMatcher.ratio()`` sobre o texto inteiro nao captura.
    """
    if not resumo:
        return 0.0
    matcher = SequenceMatcher(None, resumo, bruto, autojunk=False)
    copiado = sum(b.size for b in matcher.get_matching_blocks() if b.size >= _TAMANHO_MINIMO_TRECHO_COPIADO)
    return copiado / len(resumo)


def _eh_categoria_sensivel(categoria: str, cfg: Any) -> bool:
    raw = _cfg(cfg, "categorias_sensiveis", "")
    if isinstance(raw, str):
        sensiveis = {c.strip().lower() for c in raw.split(",") if c.strip()}
    else:
        sensiveis = {str(c).strip().lower() for c in (raw or [])}
    return (categoria or "").strip().lower() in sensiveis


def _titulo_todo_maiusculas(titulo: str) -> bool:
    letras = [c for c in titulo if c.isalpha()]
    if len(letras) < 15:
        return False
    return sum(1 for c in letras if c.isupper()) / len(letras) >= 0.8


def decidir_status(item: dict, resumo: Any, n_fontes: int, cfg: Any) -> str:
    """Aplica as regras do portal (+ N1..N4) e devolve pendente/aprovado."""
    item = item or {}
    texto_resumo, categoria = _resumo_e_categoria(resumo, item)
    bruto = _texto_bruto(item)
    n = max(1, int(n_fontes or 1))

    sim_max = float(_cfg(cfg, "resumo_sim_max", 0.6))
    trecho_max = float(_cfg(cfg, "resumo_trecho_max", 0.6))
    limiar_fontes = int(_cfg(cfg, "limiar_fontes_alta_relevancia", 3))
    cluster_revisao = bool(_cfg(cfg, "cluster_sempre_revisao", True))

    # N2 — rastreabilidade antes de tudo.
    url = str(item.get("url") or item.get("url_fonte_original") or "")
    if not url.startswith("http"):
        return PENDENTE
    # N1 — manchete truncada/ilegivel.
    if len((item.get("titulo") or "").strip()) < _TITULO_MINIMO_CHARS:
        return PENDENTE
    # 1 — sem resumo confiavel, nunca publica.
    if not texto_resumo.strip():
        return PENDENTE
    # N4 — resumo degenerado.
    if len(texto_resumo.strip()) < _RESUMO_MINIMO_CHARS:
        return PENDENTE
    # 2 — copia/quase-copia do bruto (BRD §18, direitos autorais).
    if bruto.strip():
        if SequenceMatcher(None, texto_resumo.strip(), bruto.strip()).ratio() >= sim_max:
            return PENDENTE
        if _proporcao_copiada(texto_resumo.strip(), bruto.strip()) >= trecho_max:
            return PENDENTE
    # 3 — alta relevancia.
    if _eh_categoria_sensivel(categoria, cfg) or n >= limiar_fontes:
        return PENDENTE
    # 4 — cluster exige revisao.
    if cluster_revisao and n >= 2:
        return PENDENTE
    # N3 — shouting/clickbait.
    if _titulo_todo_maiusculas(str(item.get("titulo") or "")):
        return PENDENTE
    return APROVADO
