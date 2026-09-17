"""FRENTE 3 — camada de recomendação da Home (e base do Radar).

Tudo aqui é LEITURA + cálculo em memória sobre dados já existentes:
- `NewsItem`/`NewsCluster` (publicáveis, via `feed.services`);
- sinais em `feed.models.InteracaoNoticia` / `EventoBusca`;
- overrides em `feed.models.DestaqueEditorial`.

Pesos de score (somam no máximo ~100, só para ORDENAR — nunca exibidos
como "nota" ao leitor; o frontend recebe `motivo` textual):
- recência (decaimento exponencial, meia-vida 24h) ......... até 30
- editorial (urgente + nº de fontes) ...................... até 15
- popularidade (views/cliques 7d, escala log) ............. até 20
- crescimento (fração 24h dentro de 7d) ................... até 15
- engajamento (tempo leitura, salvos, shares) ............. até 15
- personalização (match com interesses, com teto) ......... até 12
- tendência (overlap com buscas recentes) ................. até 10
- região (só quando região explícita/autorizada) .......... +8 fixo

Anti-bolha: `montar_home` limita a participação de uma mesma categoria
por seção (teto de 50%, arredondado p/ cima) e intercala o restante.
Conteúdo velho no topo: o top-3 da curadoria exige frescor (<72h), salvo
override manual — item velho cai para "recentes".
Sem repetição: cada entrada aparece em UMA seção (ordem de prioridade).
Bloqueios editoriais: excluídos em TODAS as seções.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from catalogo_noticias.models import NewsItem

from .models import DestaqueEditorial, EventoBusca, InteracaoNoticia

JANELA_POPULARIDADE_DIAS = 7
JANELA_CRESCIMENTO_HORAS = 24
FRESCOR_TOPO_HORAS = 72
TETO_CATEGORIA_POR_SECAO = 0.5

_PESOS = {
    "recencia": 30.0,
    "editorial": 15.0,
    "popularidade": 20.0,
    "crescimento": 15.0,
    "engajamento": 15.0,
    "personalizacao": 12.0,
    "tendencia": 10.0,
    "regiao": 8.0,
}


def chave_entrada(entrada: dict) -> tuple[str, int]:
    return (entrada.get("tipo") or "item", int(entrada.get("id")))


# ---------------------------------------------------------------------------
# Overrides editoriais
# ---------------------------------------------------------------------------

def overrides_vigentes() -> tuple[dict[tuple[str, int], DestaqueEditorial], set[tuple[str, int]], list[DestaqueEditorial]]:
    """Retorna (por_chave, bloqueios, manchetes_ordenadas) vigentes agora."""
    agora = timezone.now()
    qs = DestaqueEditorial.objects.filter(ativo=True).select_related("cluster", "item")
    por_chave: dict[tuple[str, int], DestaqueEditorial] = {}
    bloqueios: set[tuple[str, int]] = set()
    manchetes: list[DestaqueEditorial] = []
    for ov in qs:
        if ov.inicio and agora < ov.inicio:
            continue
        if ov.fim and agora > ov.fim:
            continue
        alvo_id = ov.cluster_id if ov.entry_tipo == "cluster" else ov.item_id
        if not alvo_id:
            continue
        chave = (ov.entry_tipo, alvo_id)
        if ov.tipo == DestaqueEditorial.TIPO_BLOQUEIO:
            bloqueios.add(chave)
        else:
            por_chave[chave] = ov
            if ov.tipo == DestaqueEditorial.TIPO_MANCHETE:
                manchetes.append(ov)
    manchetes.sort(key=lambda o: (o.posicao, -o.criado_em.timestamp()))
    return por_chave, bloqueios, manchetes


def aplicar_bloqueios(entradas: list[dict], bloqueios: set[tuple[str, int]]) -> list[dict]:
    if not bloqueios:
        return entradas
    return [e for e in entradas if chave_entrada(e) not in bloqueios]


# ---------------------------------------------------------------------------
# Sinais agregados (nunca duplicar contadores em NewsItem/NewsCluster)
# ---------------------------------------------------------------------------

def agregar_sinais() -> dict[tuple[str, int], dict]:
    """Agrega InteracaoNoticia (7d + recorte 24h) por entrada. Retorna
    {(tipo,id): {views, cliques, leituras, tempo_leitura_seg, salvos,
    shares, cliques_busca, recentes_24h}} — tudo zerado quando sem sinal."""
    agora = timezone.now()
    corte_7d = agora - timedelta(days=JANELA_POPULARIDADE_DIAS)
    corte_24h = agora - timedelta(hours=JANELA_CRESCIMENTO_HORAS)
    sinais: dict[tuple[str, int], dict] = defaultdict(
        lambda: {"views": 0, "cliques": 0, "leituras": 0, "tempo_leitura_seg": 0,
                 "salvos": 0, "shares": 0, "cliques_busca": 0, "recentes_24h": 0,
                 "total_7d": 0}
    )
    qs = InteracaoNoticia.objects.filter(criado_em__gte=corte_7d).values(
        "tipo", "entry_tipo", "cluster_id", "item_id", "tempo_leitura_seg", "criado_em"
    )
    for row in qs.iterator(chunk_size=2000):
        alvo = row["cluster_id"] if row["entry_tipo"] == "cluster" else row["item_id"]
        if not alvo:
            continue
        chave = (row["entry_tipo"], alvo)
        s = sinais[chave]
        tipo = row["tipo"]
        if tipo == InteracaoNoticia.TIPO_VIEW:
            s["views"] += 1
        elif tipo == InteracaoNoticia.TIPO_CLICK:
            s["cliques"] += 1
        elif tipo == InteracaoNoticia.TIPO_READ:
            s["leituras"] += 1
            s["tempo_leitura_seg"] += row["tempo_leitura_seg"] or 0
        elif tipo == InteracaoNoticia.TIPO_SAVE:
            s["salvos"] += 1
        elif tipo == InteracaoNoticia.TIPO_UNSAVE:
            s["salvos"] -= 1
        elif tipo == InteracaoNoticia.TIPO_SHARE:
            s["shares"] += 1
        elif tipo == InteracaoNoticia.TIPO_SEARCH_CLICK:
            s["cliques_busca"] += 1
        s["total_7d"] += 1
        if row["criado_em"] >= corte_24h:
            s["recentes_24h"] += 1
    return dict(sinais)


def termos_em_alta(dias: int = 7, limite: int = 20) -> list[dict]:
    """Termos mais buscados no período — sinal de tendência + base do
    autocomplete/termos populares."""
    corte = timezone.now() - timedelta(days=dias)
    linhas = (
        EventoBusca.objects.filter(criado_em__gte=corte)
        .exclude(query_normalizada="")
        .values("query_normalizada")
        .annotate(total=Count("id"))
        .order_by("-total")[:limite]
    )
    return [{"termo": r["query_normalizada"], "total": r["total"]} for r in linhas]


# ---------------------------------------------------------------------------
# Pontuação
# ---------------------------------------------------------------------------

def _horas_desde(timestamp) -> float:
    try:
        delta = timezone.now() - timestamp
        return max(0.0, delta.total_seconds() / 3600.0)
    except Exception:
        return 0.0


def pontuar_entrada(
    entrada: dict,
    sinais: dict | None = None,
    interesses: list[str] | None = None,
    termos_tendencia: list[str] | None = None,
    regiao: dict | None = None,
) -> dict:
    """Calcula score + breakdown + motivo textual. Não filtra nada (filtros
    de bloqueio/frescor ficam no assembly das seções)."""
    interesses_norm = {(i or "").strip().lower() for i in (interesses or []) if (i or "").strip()}
    termos = [t.lower() for t in (termos_tendencia or [])]
    s = (sinais or {}).get(chave_entrada(entrada), {})

    horas = _horas_desde(entrada.get("timestamp"))
    recencia = _PESOS["recencia"] * math.exp(-horas / 24.0 * math.log(2))

    editorial = 0.0
    if entrada.get("urgente"):
        editorial += 8.0
    if (entrada.get("numero_fontes") or 1) >= 3:
        editorial += 7.0
    editorial = min(editorial, _PESOS["editorial"])

    volume_7d = (s.get("views", 0) + 2 * s.get("cliques", 0) + s.get("cliques_busca", 0))
    popularidade = min(_PESOS["popularidade"], _PESOS["popularidade"] * math.log1p(volume_7d) / math.log1p(50))

    total_7d = s.get("total_7d", 0) or 0
    fracao_24h = (s.get("recentes_24h", 0) / total_7d) if total_7d >= 5 else 0.0
    crescimento = _PESOS["crescimento"] * fracao_24h

    eng_raw = (s.get("tempo_leitura_seg", 0) / 60.0) + 3 * max(0, s.get("salvos", 0)) + 2 * s.get("shares", 0)
    engajamento = min(_PESOS["engajamento"], _PESOS["engajamento"] * math.log1p(eng_raw) / math.log1p(30))

    personalizacao = 0.0
    categoria = (entrada.get("categoria") or "").lower()
    if categoria and categoria in interesses_norm:
        personalizacao = 8.0
    personalizacao = min(personalizacao, _PESOS["personalizacao"])

    tendencia = 0.0
    if termos:
        texto = f"{entrada.get('titulo', '')} {entrada.get('resumo', '')} {categoria}".lower()
        hits = sum(1 for t in termos if t and t in texto)
        tendencia = min(_PESOS["tendencia"], 3.0 * hits)

    regiao_pts = 0.0
    if regiao and any(regiao.values()):
        for campo in ("pais", "estado", "cidade"):
            esperado = (regiao.get(campo) or "").strip().lower()
            obtido = (entrada.get(campo) or "").strip().lower()
            if esperado and obtido and esperado == obtido:
                regiao_pts = _PESOS["regiao"]
                break

    score = recencia + editorial + popularidade + crescimento + engajamento + personalizacao + tendencia + regiao_pts

    if regiao_pts:
        motivo = "Perto de você"
    elif personalizacao:
        motivo = "Pelos seus interesses"
    elif crescimento >= 8:
        motivo = "Em crescimento"
    elif popularidade >= 10:
        motivo = "Popular agora"
    elif tendencia >= 3:
        motivo = "Tendência nas buscas"
    elif editorial >= 8:
        motivo = "Cobertura urgente" if entrada.get("urgente") else "Múltiplas fontes"
    elif recencia >= 20:
        motivo = "Publicado agora"
    else:
        motivo = "Recente"

    return {
        "score": round(score, 2),
        "motivo": motivo,
        "detalhe": {
            "recencia": round(recencia, 2),
            "editorial": round(editorial, 2),
            "popularidade": round(popularidade, 2),
            "crescimento": round(crescimento, 2),
            "engajamento": round(engajamento, 2),
            "personalizacao": round(personalizacao, 2),
            "tendencia": round(tendencia, 2),
            "regiao": round(regiao_pts, 2),
        },
    }


# ---------------------------------------------------------------------------
# Assembly — Home em seções (sem repetição, anti-bolha, frescor no topo)
# ---------------------------------------------------------------------------

def _com_score(entradas, sinais, interesses, termos, regiao, overrides):
    saida = []
    for e in entradas:
        copia = dict(e)
        pts = pontuar_entrada(e, sinais, interesses, termos, regiao)
        copia["score"] = pts["score"]
        copia["motivo"] = pts["motivo"]
        ov = overrides.get(chave_entrada(e))
        copia["override"] = ov.tipo if ov else None
        saida.append(copia)
    saida.sort(key=lambda x: x["score"], reverse=True)
    return saida


def _limitar_categoria(entradas: list[dict], teto: float = TETO_CATEGORIA_POR_SECAO) -> list[dict]:
    """Anti-bolha: nenhuma categoria ocupa mais que `teto` da seção; o
    excedente vai para o fim (não é descartado)."""
    if len(entradas) <= 2:
        return entradas
    max_por_categoria = max(1, math.ceil(len(entradas) * teto))
    contagem: Counter = Counter()
    dentro, excedente = [], []
    for e in entradas:
        cat = (e.get("categoria") or "").lower()
        if contagem[cat] < max_por_categoria:
            dentro.append(e)
            contagem[cat] += 1
        else:
            excedente.append(e)
    # Reintercala o excedente para não empilhar a mesma categoria no fim.
    resultado, fila = [], list(excedente)
    for e in dentro:
        resultado.append(e)
        if fila and len(resultado) % 3 == 0:
            resultado.append(fila.pop(0))
    resultado.extend(fila)
    return resultado


def montar_home(
    entradas: list[dict],
    interesses: list[str] | None = None,
    regiao: dict | None = None,
    limite_secao: int = 6,
) -> dict:
    """Monta as seções da Home a partir de entradas JÁ publicáveis e
    agrupadas (`feed.services.construir_feed_entries`)."""
    overrides, bloqueios, manchetes = overrides_vigentes()
    base = aplicar_bloqueios(entradas, bloqueios)
    sinais = agregar_sinais()
    termos = [t["termo"] for t in termos_em_alta()]

    por_chave = {chave_entrada(e): e for e in base}
    usadas: set[tuple[str, int]] = set()

    def reservar(lista, n):
        out = []
        for e in lista:
            if chave_entrada(e) not in usadas:
                usadas.add(chave_entrada(e))
                out.append(e)
                if len(out) >= n:
                    break
        return out

    # 1) Manchetes: overrides manuais primeiro, na ordem de posição.
    secao_manchetes = []
    for ov in manchetes:
        alvo_id = ov.cluster_id if ov.entry_tipo == "cluster" else ov.item_id
        e = por_chave.get((ov.entry_tipo, alvo_id))
        if e and chave_entrada(e) not in usadas:
            copia = dict(e)
            copia["score"], copia["motivo"], copia["override"] = 100.0, "Escolha editorial", ov.tipo
            secao_manchetes.append(copia)
            usadas.add(chave_entrada(e))

    ranqueadas = _com_score(base, sinais, interesses, termos, regiao, overrides)
    frescas = [e for e in ranqueadas if _horas_desde(e.get("timestamp")) <= FRESCOR_TOPO_HORAS]

    # 2) Curadoria: top por score com frescor exigido no top-3 (salvo override).
    curadoria_pool = [e for e in frescas if chave_entrada(e) not in usadas]
    for e in ranqueadas:  # completa com as melhores restantes se faltar frescor
        if len(curadoria_pool) >= limite_secao:
            break
        if chave_entrada(e) not in usadas and e not in curadoria_pool:
            curadoria_pool.append(e)
    secao_curadoria = reservar(_limitar_categoria(curadoria_pool), limite_secao)

    # 3) Para você: só com interesses; sem sinal, seção vazia (sem bolha de um item só).
    secao_para_voce: list[dict] = []
    interesses_norm = {(i or "").strip().lower() for i in (interesses or []) if (i or "").strip()}
    if interesses_norm:
        pool_voce = [e for e in ranqueadas
                     if (e.get("categoria") or "").lower() in interesses_norm
                     and chave_entrada(e) not in usadas]
        secao_para_voce = reservar(_limitar_categoria(pool_voce), limite_secao)

    # 4) Populares: ordena por popularidade+crescimento+engajamento.
    def apelo(e):
        d = pontuar_entrada(e, sinais, interesses, termos, None)["detalhe"]
        return d["popularidade"] + d["crescimento"] + d["engajamento"]

    pool_pop = sorted((e for e in ranqueadas if chave_entrada(e) not in usadas),
                      key=apelo, reverse=True)
    secao_populares = reservar(_limitar_categoria(pool_pop), limite_secao)

    # 5) Tendência: quem conversa com as buscas recentes.
    pool_tend = sorted((e for e in ranqueadas if chave_entrada(e) not in usadas),
                       key=lambda e: pontuar_entrada(e, sinais, interesses, termos, None)["detalhe"]["tendencia"]
                       + pontuar_entrada(e, sinais, interesses, termos, None)["detalhe"]["crescimento"],
                       reverse=True)
    pool_tend = [e for e in pool_tend
                 if pontuar_entrada(e, sinais, interesses, termos, None)["detalhe"]["tendencia"] > 0
                 or pontuar_entrada(e, sinais, interesses, termos, None)["detalhe"]["crescimento"] >= 5]
    secao_tendencia = reservar(_limitar_categoria(pool_tend), limite_secao)

    # 6) Recentes: cronológico puro com o que sobrou (conteúdo velho mora aqui, nunca no topo).
    restantes = [e for e in base if chave_entrada(e) not in usadas]
    restantes.sort(key=lambda e: e.get("timestamp"), reverse=True)
    secao_recentes = []
    for e in restantes[:limite_secao]:
        copia = dict(e)
        pts = pontuar_entrada(e, sinais, interesses, termos, regiao)
        copia["score"], copia["motivo"] = pts["score"], "Recente"
        copia.setdefault("override", None)
        usadas.add(chave_entrada(e))
        secao_recentes.append(copia)

    return {
        "manchetes": secao_manchetes,
        "curadoria": secao_curadoria,
        "para_voce": secao_para_voce,
        "populares": secao_populares,
        "tendencia": secao_tendencia,
        "recentes": secao_recentes,
    }


# ---------------------------------------------------------------------------
# Destaques do Dia (dinâmicos + override manual)
# ---------------------------------------------------------------------------

def destaques_do_dia(
    entradas: list[dict],
    regiao: dict | None = None,
    limite: int = 5,
) -> list[dict]:
    """Relevância editorial + acessos + crescimento + pesquisas +
    engajamento + região. Overrides tipo=destaque sempre primeiro."""
    overrides, bloqueios, _ = overrides_vigentes()
    base = aplicar_bloqueios(entradas, bloqueios)
    sinais = agregar_sinais()
    termos = [t["termo"] for t in termos_em_alta()]

    manuais = []
    for chave, ov in overrides.items():
        if ov.tipo != DestaqueEditorial.TIPO_DESTAQUE:
            continue
        e = next((x for x in base if chave_entrada(x) == chave), None)
        if e:
            copia = dict(e)
            copia["score"], copia["motivo"], copia["override"] = 100.0, "Escolha editorial", ov.tipo
            manuais.append(copia)
    manuais.sort(key=lambda e: e["score"], reverse=True)

    usados = {chave_entrada(e) for e in manuais}

    def apelo_destaque(e):
        d = pontuar_entrada(e, sinais, None, termos, regiao)["detalhe"]
        return d["editorial"] + d["popularidade"] + d["crescimento"] + d["tendencia"] + d["engajamento"] + d["regiao"]

    dinamicos = []
    for e in sorted((x for x in base if chave_entrada(x) not in usados), key=apelo_destaque, reverse=True):
        if len(manuais) + len(dinamicos) >= limite:
            break
        copia = dict(e)
        pts = pontuar_entrada(e, sinais, None, termos, regiao)
        copia["score"], copia["motivo"] = round(apelo_destaque(e), 2), pts["motivo"]
        copia["override"] = None
        dinamicos.append(copia)
    return (manuais + dinamicos)[:limite]


# ---------------------------------------------------------------------------
# Cobertura completa (agrupamento do mesmo evento)
# ---------------------------------------------------------------------------

def cobertura_completa(tipo: str, entrada_id: int, limite_relacionadas: int = 5) -> dict | None:
    """Fontes + horários + atualizações + relacionadas, com origem clara.
    Retorna None quando a entrada não existe ou não é publicável."""
    from . import services as feed_services

    if tipo == "cluster":
        detalhe = feed_services.detalhe_cluster(entrada_id)
    elif tipo == "item":
        detalhe = feed_services.detalhe_item(entrada_id)
    else:
        return None
    if detalhe is None:
        return None

    # Linha do tempo das atualizações: itens publicáveis do cluster/item com
    # horário de publicação na fonte (fallback ingestão). Só dado real.
    if tipo == "cluster":
        from catalogo_noticias.models import NewsCluster

        try:
            cluster = NewsCluster.objects.get(pk=entrada_id)
        except NewsCluster.DoesNotExist:
            return None
        itens = list(cluster.itens.filter(
            status_revisao__in=feed_services.STATUS_PUBLICAVEIS
        ).order_by("timestamp_ingestao"))
    else:
        itens = list(NewsItem.objects.filter(
            pk=entrada_id, status_revisao__in=feed_services.STATUS_PUBLICAVEIS
        ))

    atualizacoes = [{
        "nome_fonte": i.nome_fonte,
        "url_fonte_original": i.url_fonte_original,
        "titulo": i.titulo,
        "timestamp": feed_services._timestamp_ordenacao(i),
    } for i in itens]

    # Relacionadas: mesma categoria, outra entrada, ranqueadas por score —
    # evita duplicar a própria cobertura na Home.
    chave_atual = (tipo, entrada_id)
    candidatas = [i for i in NewsItem.objects.filter(
        status_revisao__in=feed_services.STATUS_PUBLICAVEIS,
        categoria__iexact=(detalhe.get("categoria") or ""),
    ).exclude(categoria="").select_related("cluster")[:200]]
    entradas_rel = feed_services.construir_feed_entries(candidatas)
    _, bloqueios, _ = overrides_vigentes()
    entradas_rel = [e for e in aplicar_bloqueios(entradas_rel, bloqueios)
                    if chave_entrada(e) != chave_atual]
    sinais = agregar_sinais()
    termos = [t["termo"] for t in termos_em_alta()]
    ranqueadas = _com_score(entradas_rel, sinais, None, termos, None, {})
    relacionadas = [{k: r[k] for k in ("tipo", "id", "titulo", "resumo", "categoria",
                                       "urgente", "numero_fontes", "timestamp", "score", "motivo")
                     if k in r} for r in ranqueadas[:limite_relacionadas]]

    return {
        **detalhe,
        "total_atualizacoes": len(atualizacoes),
        "numero_fontes": len({a["nome_fonte"] for a in atualizacoes}),
        "atualizacoes": sorted(atualizacoes, key=lambda a: a["timestamp"]),
        "relacionadas": relacionadas,
    }


def relacionadas_para(tipo: str, entrada_id: int, categoria: str, limite: int = 5) -> list[dict]:
    cob = cobertura_completa(tipo, entrada_id, limite_relacionadas=limite)
    return (cob or {}).get("relacionadas", [])
