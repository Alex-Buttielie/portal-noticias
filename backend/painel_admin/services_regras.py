"""FRENTE 6 — aplicação dos overrides no feed geral.

Opera sobre a lista de entradas (dicts) JÁ construída por
`feed.services.construir_feed_entries`, mais a lista opcional de `NewsItem`
para casar `colunista_destaque` com `NewsItem.autor` (defensivo: se o campo
não existir, a regra é ignorada sem quebrar o feed).

Tudo é best-effort e nunca levanta exceção para o caller (feed público não
pode cair por causa de regra editorial mal configurada).
"""

from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def _norm(valor) -> str:
    return (valor or "").strip().lower()


def regras_vigentes():
    """Devolve a lista de `RegraCuradoria` vigentes agora (ordenadas)."""
    from painel_admin.models import RegraCuradoria

    agora = timezone.now()
    qs = RegraCuradoria.objects.filter(ativo=True).order_by("ordem", "-criado_em")
    return [r for r in qs if r.vigente(agora)]


def aplicar_regras_curadoria(entradas: list[dict], itens=None) -> list[dict]:
    """Aplica bloqueios, boosts, ordem de categorias e selos forçados.

    `itens`: lista opcional de `NewsItem` (para `colunista_destaque` via
    `NewsItem.autor`). Retorna uma NOVA lista; nunca muta a original.
    """
    try:
        regras = regras_vigentes()
    except Exception as exc:
        logger.warning("regras_curadoria: ignorando (tabela ausente?) %s", exc)
        return entradas
    if not regras:
        return entradas
    try:
        return _aplicar(entradas, itens, regras)
    except Exception as exc:  # pragma: no cover — rede de segurança
        logger.warning("regras_curadoria: falha ao aplicar: %s", exc)
        return entradas


def _chave(e: dict):
    try:
        return (e.get("tipo") or "item", int(e.get("id")))
    except (TypeError, ValueError):
        return ("item", -1)


def _aplicar(entradas, itens, regras):
    from painel_admin.models import RegraCuradoria

    resultado = [dict(e) for e in entradas]

    # Mapa (tipo,id) -> autor, quando os itens trazem o campo.
    autor_por_chave: dict[tuple, str] = {}
    if itens:
        for it in itens:
            autor = getattr(it, "autor", "") or ""
            cluster_id = getattr(it, "cluster_id", None)
            if cluster_id:
                autor_por_chave.setdefault(("cluster", cluster_id), autor)
            pk = getattr(it, "id", None)
            if pk is not None:
                autor_por_chave.setdefault(("item", pk), autor)

    bloqueios_entrada = set()
    bloqueios_categoria = set()
    for r in regras:
        if r.tipo == RegraCuradoria.TIPO_BLOQUEIO_ENTRADA and r.entry_tipo and r.entry_id:
            bloqueios_entrada.add((r.entry_tipo, r.entry_id))
        elif r.tipo == RegraCuradoria.TIPO_BLOQUEIO_CATEGORIA and r.alvo.strip():
            bloqueios_categoria.add(_norm(r.alvo))
    if bloqueios_entrada or bloqueios_categoria:
        resultado = [
            e for e in resultado
            if _chave(e) not in bloqueios_entrada
            and _norm(e.get("categoria")) not in bloqueios_categoria
        ]

    # Selos/urgente/exclusivo forçados (por entrada).
    for r in regras:
        if r.tipo not in (RegraCuradoria.TIPO_SELO_FORCADO,
                          RegraCuradoria.TIPO_URGENTE_FORCADO,
                          RegraCuradoria.TIPO_EXCLUSIVO_FORCADO):
            continue
        if not (r.entry_tipo and r.entry_id):
            continue
        for e in resultado:
            if _chave(e) != (r.entry_tipo, r.entry_id):
                continue
            if r.tipo == RegraCuradoria.TIPO_URGENTE_FORCADO:
                e["urgente"] = True
            elif r.tipo == RegraCuradoria.TIPO_EXCLUSIVO_FORCADO:
                e["selo_editorial"] = "Exclusivo"
            elif r.alvo.strip():
                e["selo_editorial"] = r.alvo.strip()[:60]

    # Boosts: entradas/categorias/colunistas para o topo (estável, por ordem).
    boosts = [r for r in regras if r.tipo in (
        RegraCuradoria.TIPO_BOOST_ENTRADA, RegraCuradoria.TIPO_BOOST_CATEGORIA,
        RegraCuradoria.TIPO_COLUNISTA_DESTAQUE, RegraCuradoria.TIPO_EXCLUSIVO_FORCADO,
    )]
    for r in sorted(boosts, key=lambda x: -x.ordem):
        if r.tipo == RegraCuradoria.TIPO_BOOST_ENTRADA and r.entry_tipo and r.entry_id:
            alvo = (r.entry_tipo, r.entry_id)
            topo = [e for e in resultado if _chave(e) == alvo]
            resto = [e for e in resultado if _chave(e) != alvo]
            resultado = topo + resto
        elif r.tipo == RegraCuradoria.TIPO_BOOST_CATEGORIA and r.alvo.strip():
            cat = _norm(r.alvo)
            topo = [e for e in resultado if _norm(e.get("categoria")) == cat]
            resto = [e for e in resultado if _norm(e.get("categoria")) != cat]
            resultado = topo + resto
        elif r.tipo == RegraCuradoria.TIPO_COLUNISTA_DESTAQUE and r.alvo.strip():
            nome = _norm(r.alvo)
            topo = [e for e in resultado if _norm(autor_por_chave.get(_chave(e), "")) == nome]
            resto = [e for e in resultado if _norm(autor_por_chave.get(_chave(e), "")) != nome]
            resultado = topo + resto
        elif r.tipo == RegraCuradoria.TIPO_EXCLUSIVO_FORCADO and r.entry_tipo and r.entry_id:
            alvo = (r.entry_tipo, r.entry_id)
            topo = [e for e in resultado if _chave(e) == alvo]
            resto = [e for e in resultado if _chave(e) != alvo]
            resultado = topo + resto

    # Ordem fixa de categorias (última regra ativa do tipo vence).
    ordens = [r for r in regras if r.tipo == RegraCuradoria.TIPO_ORDEM_CATEGORIAS and r.alvo.strip()]
    if ordens:
        seq = [_norm(c) for c in ordens[-1].alvo.split(",") if c.strip()]
        pos = {c: i for i, c in enumerate(seq)}
        com_idx = [(pos.get(_norm(e.get("categoria")), len(seq)), i, e) for i, e in enumerate(resultado)]
        com_idx.sort(key=lambda t: (t[0], t[1]))
        resultado = [t[2] for t in com_idx]

    return resultado
