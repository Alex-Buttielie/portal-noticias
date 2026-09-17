"""FRENTE 3 — busca como mecanismo principal de descoberta.

- Multi-campo com pesos: título > tags/autor > resumo > categoria/fonte/local.
- Filtros: categoria, autor, local (país/estado/cidade), período.
- Autocomplete, sugestões, termos populares, histórico e correção ("você
  quis dizer") — tudo derivado de dado real (EventoBusca + NewsItem), nada
  inventado.
- Cada busca e cada clique em resultado são registrados (EventoBusca /
  InteracaoNoticia tipo search_click) para métricas e recomendação.
"""

from __future__ import annotations

import difflib
import re
from datetime import datetime

from django.db.models import Count, Q
from django.utils import timezone

from catalogo_noticias.models import NewsItem

from .models import EventoBusca

MAX_CANDIDATOS = 300

_PESO_TITULO = 10.0
_PESO_TITULO_PREFIXO = 4.0
_PESO_TAGS = 6.0
_PESO_AUTOR = 6.0
_PESO_RESUMO = 4.0
_PESO_CATEGORIA_EXATA = 8.0
_PESO_CATEGORIA_PARCIAL = 4.0
_PESO_FONTE = 3.0
_PESO_LOCAL = 5.0


def normalizar_query(q: str) -> str:
    q = (q or "").strip().lower()
    return re.sub(r"\s+", " ", q)


def _tokens(q_norm: str) -> list[str]:
    return [t for t in re.split(r"[^\wà-ú]+", q_norm, flags=re.UNICODE) if len(t) >= 2]


def buscar(
    q: str,
    categoria: str | None = None,
    autor: str | None = None,
    pais: str | None = None,
    estado: str | None = None,
    cidade: str | None = None,
    data_de=None,
    data_ate=None,
    limite: int = 20,
) -> tuple[list[dict], int]:
    """Retorna (resultados_ranqueados, total_candidatos). Cada resultado é
    um dict de entrada de feed + `relevancia` + `trecho` (motivo do match)."""
    from . import services as feed_services
    from .recomendacao import aplicar_bloqueios, overrides_vigentes

    q_norm = normalizar_query(q)
    toks = _tokens(q_norm)
    if not toks and not any([categoria, autor, pais, estado, cidade, data_de, data_ate]):
        return [], 0

    qs = NewsItem.objects.filter(status_revisao__in=feed_services.STATUS_PUBLICAVEIS)
    if categoria:
        qs = qs.filter(categoria__iexact=categoria.strip())
    if autor:
        qs = qs.filter(autor__icontains=autor.strip())
    if pais:
        qs = qs.filter(pais__iexact=pais.strip())
    if estado:
        qs = qs.filter(estado__iexact=estado.strip())
    if cidade:
        qs = qs.filter(cidade__iexact=cidade.strip())
    if data_de:
        qs = qs.filter(timestamp_ingestao__date__gte=data_de)
    if data_ate:
        qs = qs.filter(timestamp_ingestao__date__lte=data_ate)

    if toks:
        cond = Q()
        for t in toks:
            cond |= (
                Q(titulo__icontains=t)
                | Q(resumo_proprio__icontains=t)
                | Q(conteudo_completo__icontains=t)
                | Q(categoria__icontains=t)
                | Q(autor__icontains=t)
                | Q(nome_fonte__icontains=t)
                | Q(cidade__icontains=t)
                | Q(estado__icontains=t)
                | Q(pais__icontains=t)
            )
        qs = qs.filter(cond)

    candidatos = list(qs.select_related("cluster").order_by("-timestamp_ingestao")[:MAX_CANDIDATOS])
    total = len(candidatos)

    pontuados = []
    for item in candidatos:
        relevancia, trechos = _relevancia(item, q_norm, toks)
        # Filtro puro (sem query): mantém tudo, ordena por recência.
        if not toks:
            relevancia = 1.0
        if relevancia <= 0:
            continue
        pontuados.append((relevancia, _ts(item), item, trechos))
    pontuados.sort(key=lambda r: (r[0], r[1]), reverse=True)

    entradas = feed_services.construir_feed_entries([p[2] for p in pontuados])
    # Reanexa relevância/trecho (construir_feed_entries agrupa por cluster —
    # usa o melhor score do grupo, evitando duplicação na listagem).
    score_por_item = {p[2].id: (p[0], p[3]) for p in pontuados}
    for e in entradas:
        melhor, trechos = 0.0, []
        if e["tipo"] == "item":
            melhor, trechos = score_por_item.get(e["id"], (0.0, []))
        else:
            for p in pontuados:
                if p[2].cluster_id == e["id"]:
                    if p[0] > melhor:
                        melhor, trechos = p[0], p[3]
        e["relevancia"] = round(melhor, 2)
        e["trecho"] = "; ".join(trechos[:2])
    entradas.sort(key=lambda e: (e.get("relevancia", 0), e.get("timestamp")), reverse=True)

    _, bloqueios, _ = overrides_vigentes()
    if bloqueios:
        from .recomendacao import chave_entrada

        entradas = [e for e in entradas if chave_entrada(e) not in bloqueios]
    return entradas[:limite], total


def _ts(item: NewsItem):
    return item.timestamp_publicacao_fonte or item.timestamp_ingestao


def _relevancia(item: NewsItem, q_norm: str, toks: list[str]) -> tuple[float, list[str]]:
    titulo = (item.titulo or "").lower()
    resumo = (item.resumo_proprio or "").lower()
    tags = [str(t).lower() for t in (item.tags or []) if str(t).strip()]
    autor = (item.autor or "").lower()
    categoria = (item.categoria or "").lower()
    fonte = (item.nome_fonte or "").lower()
    local = " ".join([item.cidade or "", item.estado or "", item.pais or ""]).lower()

    score, trechos = 0.0, []
    if q_norm and q_norm in titulo:
        score += _PESO_TITULO
        trechos.append("título")
    elif q_norm and titulo.startswith(q_norm):
        score += _PESO_TITULO + _PESO_TITULO_PREFIXO
        trechos.append("título")
    for t in toks:
        if t in titulo:
            score += 3.0
        if any(t in tag or tag in t for tag in tags):
            score += 2.0
        if t in autor:
            score += 2.0
        if t in resumo:
            score += 1.0
        if t in categoria:
            score += 1.5
        if t in fonte:
            score += 1.0
        if t in local:
            score += 1.5
    if tags and any(t in tags for t in toks):
        score += _PESO_TAGS - 2.0
        if "tags" not in trechos:
            trechos.append("tags")
    if autor and q_norm and q_norm in autor:
        score += _PESO_AUTOR
        trechos.append("autor")
    if q_norm and q_norm in resumo and "resumo" not in trechos:
        score += _PESO_RESUMO
        trechos.append("conteúdo")
    if categoria and q_norm == categoria:
        score += _PESO_CATEGORIA_EXATA
        trechos.append("categoria")
    elif categoria and q_norm and q_norm in categoria:
        score += _PESO_CATEGORIA_PARCIAL
        trechos.append("categoria")
    if q_norm and q_norm in fonte:
        score += _PESO_FONTE
        trechos.append("fonte")
    if q_norm and q_norm in local:
        score += _PESO_LOCAL
        trechos.append("local")
    return score, trechos or (["conteúdo"] if score > 0 else [])


# ---------------------------------------------------------------------------
# Autocomplete / sugestões / populares / histórico / correção
# ---------------------------------------------------------------------------

def autocomplete(prefixo: str, limite: int = 8) -> list[str]:
    """Sugestões a partir de buscas reais + categorias/tags/autores do
    catálogo. Ordena: termo popular primeiro, depois alfabético."""
    pref = normalizar_query(prefixo)
    if len(pref) < 2:
        return []
    sugestoes: dict[str, int] = {}

    populares = (
        EventoBusca.objects.filter(query_normalizada__startswith=pref)
        .values("query_normalizada")
        .annotate(total=Count("id"))
        .order_by("-total")[:limite]
    )
    for r in populares:
        sugestoes[r["query_normalizada"]] = sugestoes.get(r["query_normalizada"], 0) + r["total"] * 10

    for cat in NewsItem.objects.exclude(categoria="").values_list("categoria", flat=True).distinct()[:200]:
        c = (cat or "").strip().lower()
        if c.startswith(pref):
            sugestoes[c] = sugestoes.get(c, 0) + 5
    for titulo in NewsItem.objects.filter(
        titulo__istartswith=pref,
        status_revisao__in=[NewsItem.STATUS_NAO_APLICAVEL, NewsItem.STATUS_APROVADO],
    ).values_list("titulo", flat=True)[:limite]:
        t = (titulo or "").strip()
        if t:
            sugestoes[t.lower()] = sugestoes.get(t.lower(), 0) + 3

    ordenadas = sorted(sugestoes.items(), key=lambda kv: (-kv[1], kv[0]))
    return [termo for termo, _ in ordenadas[:limite]]


def termos_populares(dias: int = 7, limite: int = 10) -> list[dict]:
    from .recomendacao import termos_em_alta

    return termos_em_alta(dias=dias, limite=limite)


def historico(user=None, session_key: str = "", limite: int = 10) -> list[str]:
    qs = EventoBusca.objects.exclude(query_normalizada="")
    if user is not None and getattr(user, "is_authenticated", False):
        qs = qs.filter(user=user)
    elif session_key:
        qs = qs.filter(session_key=session_key, user__isnull=True)
    else:
        return []
    vistos, out = set(), []
    for q in qs.order_by("-criado_em").values_list("query", "query_normalizada")[: limite * 3]:
        if q[1] not in vistos:
            vistos.add(q[1])
            out.append(q[0])
        if len(out) >= limite:
            break
    return out


def sugestao_correcao(q: str) -> str | None:
    """'Você quis dizer' — só sugere quando a busca atual tem pouco ou
    nenhum resultado; vocabulário = termos populares + categorias."""
    q_norm = normalizar_query(q)
    if not q_norm:
        return None
    vocab = [t["termo"] for t in termos_populares()]
    vocab += [(c or "").strip().lower() for c in
              NewsItem.objects.exclude(categoria="").values_list("categoria", flat=True).distinct()[:100]]
    vocab = [v for v in dict.fromkeys(vocab) if v and v != q_norm]
    matches = difflib.get_close_matches(q_norm, vocab, n=1, cutoff=0.75)
    return matches[0] if matches else None


# ---------------------------------------------------------------------------
# Registro de eventos (métricas + recomendação)
# ---------------------------------------------------------------------------

def registrar_busca(q: str, resultados: int, user=None, session_key: str = "", filtros: dict | None = None) -> None:
    try:
        EventoBusca.objects.create(
            query=(q or "")[:300],
            query_normalizada=normalizar_query(q)[:300],
            user=user if getattr(user, "is_authenticated", False) else None,
            session_key=(session_key or "")[:64],
            resultados=resultados,
            filtros=filtros or {},
        )
    except Exception:
        pass


def registrar_clique_resultado(
    entry_tipo: str, entry_id: int, query: str = "",
    user=None, session_key: str = "", tempo_leitura_seg: int = 0,
) -> None:
    from .models import InteracaoNoticia

    try:
        from catalogo_noticias.models import NewsCluster

        kwargs: dict = {
            "tipo": InteracaoNoticia.TIPO_SEARCH_CLICK,
            "entry_tipo": entry_tipo,
            "query": (query or "")[:300],
            "user": user if getattr(user, "is_authenticated", False) else None,
            "session_key": (session_key or "")[:64],
            "tempo_leitura_seg": max(0, int(tempo_leitura_seg or 0)),
        }
        if entry_tipo == "cluster":
            obj = NewsCluster.objects.filter(pk=entry_id).first()
            if obj is None:
                return
            kwargs["cluster"] = obj
            primeiro = obj.itens.order_by("-timestamp_ingestao").first()
            kwargs["categoria"] = (obj.categoria_dominante or (primeiro.categoria if primeiro else ""))[:100]
        else:
            obj = NewsItem.objects.filter(pk=entry_id).first()
            if obj is None:
                return
            kwargs["item"] = obj
            kwargs["categoria"] = (obj.categoria or "")[:100]
        InteracaoNoticia.objects.create(**kwargs)
    except Exception:
        pass
