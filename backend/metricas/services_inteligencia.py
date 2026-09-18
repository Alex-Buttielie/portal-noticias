"""FRENTE 6 — Central de Inteligência: agregações e insights editoriais.

Regra de ouro: TUDO aqui é agregação ORM sobre dados reais (`EventoSite`,
`feed.InteracaoNoticia`, `feed.EventoBusca`, `User`, `NewsItem`,
`NewsCluster`, `Publicacao`, `LocalidadeSalva`). Quando não há dados
suficientes, o bloco correspondente volta com `sem_dados: True` + mensagem —
NUNCA com números inventados.

Não duplica sinais: views/cliques/compartilhamentos por notícia vêm de
`InteracaoNoticia`; buscas de `EventoBusca`; o resto de `EventoSite`.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import EventoSite

User = get_user_model()


def _feed_models():
    """Import tardio de `feed` (FRENTE 3): devolve (EventoBusca,
    InteracaoNoticia) ou (None, None) quando o app ainda não tem os
    modelos — a Central funciona só com `EventoSite` nesse caso."""
    try:
        from feed.models import EventoBusca, InteracaoNoticia

        return EventoBusca, InteracaoNoticia
    except Exception:
        return None, None


class _QueryVazia:
    """Substituto de queryset quando os modelos do `feed` ainda não existem:
    cadeia filter/exclude/values/annotate/order_by e itera vazio."""

    def filter(self, *a, **k):
        return self

    def exclude(self, *a, **k):
        return self

    def values(self, *a, **k):
        return self

    def values_list(self, *a, **k):
        return []

    def annotate(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def count(self):
        return 0

    def __iter__(self):
        return iter([])

    def __getitem__(self, fatia):
        return []

PERIODOS_VALIDOS = ("hoje", "ontem", "7d", "30d", "90d", "custom")


def _tem_campo(model, nome: str) -> bool:
    try:
        model._meta.get_field(nome)
        return True
    except Exception:
        return False


def resolver_periodo(periodo: str = "30d", inicio: str | None = None, fim: str | None = None):
    """Devolve (inicio_dt, fim_dt, dias, rotulo). `fim` = agora."""
    agora = timezone.now()
    periodo = (periodo or "30d").strip().lower()
    if periodo not in PERIODOS_VALIDOS:
        periodo = "30d"
    if periodo == "hoje":
        ini = agora.replace(hour=0, minute=0, second=0, microsecond=0)
        return ini, agora, 1, "hoje"
    if periodo == "ontem":
        hoje0 = agora.replace(hour=0, minute=0, second=0, microsecond=0)
        return hoje0 - timedelta(days=1), hoje0, 1, "ontem"
    if periodo in ("7d", "30d", "90d"):
        dias = int(periodo[:-1])
        return agora - timedelta(days=dias), agora, dias, periodo
    # custom: YYYY-MM-DD..YYYY-MM-DD
    try:
        ini_d = datetime.strptime((inicio or ""), "%Y-%m-%d").date()
        fim_d = datetime.strptime((fim or ""), "%Y-%m-%d").date()
        if fim_d < ini_d:
            ini_d, fim_d = fim_d, ini_d
        ini_dt = timezone.make_aware(datetime.combine(ini_d, datetime.min.time()))
        fim_dt = timezone.make_aware(datetime.combine(fim_d, datetime.max.time()))
        dias = max(1, (fim_d - ini_d).days + 1)
        return ini_dt, min(fim_dt, agora), dias, f"{ini_d.isoformat()}..{fim_d.isoformat()}"
    except Exception:
        return agora - timedelta(days=30), agora, 30, "30d"


def _pct(atual: float, anterior: float):
    if anterior is None or anterior == 0:
        return None
    try:
        return round((atual - anterior) / abs(anterior) * 100.0, 1)
    except Exception:
        return None


def _serie_diaria(qs, campo_data: str, dias: int, ini, fim):
    dados = (
        qs.filter(**{f"{campo_data}__gte": ini, f"{campo_data}__lte": fim})
        .annotate(dia=TruncDate(campo_data))
        .values("dia")
        .annotate(total=Count("id"))
        .order_by("dia")
    )
    mapa = {r["dia"]: r["total"] for r in dados if r["dia"] is not None}
    base = (fim - timedelta(days=dias - 1)).date() if dias > 1 else ini.date()
    serie = []
    for i in range(max(1, dias)):
        dia = base + timedelta(days=i)
        if dias == 1:
            dia = ini.date()
            if i > 0:
                break
        serie.append({"dia": dia.isoformat(), "total": mapa.get(dia, 0)})
    return serie


def _top(qs, campo: str, limite: int = 10):
    linhas = list(
        qs.exclude(**{campo: ""}).values(campo).annotate(total=Count("id")).order_by("-total")[:limite]
    )
    return [{"label": r[campo], "total": r["total"]} for r in linhas]


def _chave_entrada(tipo: str, cluster_id, item_id):
    alvo = cluster_id if tipo == "cluster" else item_id
    return (tipo or "item", alvo)


def _titulos_entradas(chaves):
    """Resolve títulos reais para entradas (cluster/item). Sem dado → '—'."""
    from catalogo_noticias.models import NewsCluster, NewsItem

    titulos: dict[tuple, dict] = {}
    cluster_ids = [c[1] for c in chaves if c[0] == "cluster" and c[1]]
    item_ids = [c[1] for c in chaves if c[0] == "item" and c[1]]
    try:
        for cl in NewsCluster.objects.filter(pk__in=cluster_ids):
            titulos[("cluster", cl.id)] = {
                "titulo": cl.titulo_acontecimento,
                "categoria": cl.categoria_dominante or "",
            }
    except Exception:
        pass
    try:
        for it in NewsItem.objects.filter(pk__in=item_ids):
            titulos[("item", it.id)] = {"titulo": it.titulo, "categoria": it.categoria or ""}
    except Exception:
        pass
    return titulos


def _agregar_interacoes(ini, fim):
    """Agrega InteracaoNoticia no período por entrada (vazio sem FRENTE 3)."""
    vazio = {
        "por_entrada": {},
        "total_views": 0,
        "total_cliques": 0,
        "total_shares": 0,
        "total_salvos": 0,
        "tempo_medio_leitura_seg": 0.0,
        "leituras_com_tempo": 0,
    }
    _, InteracaoNoticia = _feed_models()
    if InteracaoNoticia is None:
        return vazio
    qs = InteracaoNoticia.objects.filter(criado_em__gte=ini, criado_em__lte=fim).values(
        "tipo", "entry_tipo", "cluster_id", "item_id", "categoria", "tempo_leitura_seg", "criado_em"
    )
    por_entrada: dict[tuple, dict] = defaultdict(
        lambda: {"views": 0, "cliques": 0, "leituras": 0, "tempo_total": 0,
                 "salvos": 0, "shares": 0, "categoria": ""}
    )
    total_views = total_cliques = total_shares = total_salvos = 0
    tempos = []
    for r in qs.iterator(chunk_size=2000):
        alvo = r["cluster_id"] if r["entry_tipo"] == "cluster" else r["item_id"]
        if not alvo:
            continue
        chave = (r["entry_tipo"] or "item", alvo)
        agg = por_entrada[chave]
        if r["categoria"]:
            agg["categoria"] = agg["categoria"] or r["categoria"]
        t = r["tipo"]
        if t in (InteracaoNoticia.TIPO_VIEW, InteracaoNoticia.TIPO_CLICK,
                 InteracaoNoticia.TIPO_READ, InteracaoNoticia.TIPO_SEARCH_CLICK):
            agg["views"] += 1
            total_views += 1
        if t in (InteracaoNoticia.TIPO_CLICK, InteracaoNoticia.TIPO_SEARCH_CLICK):
            agg["cliques"] += 1
            total_cliques += 1
        if t == InteracaoNoticia.TIPO_READ:
            agg["leituras"] += 1
            agg["tempo_total"] += int(r["tempo_leitura_seg"] or 0)
            tempos.append(int(r["tempo_leitura_seg"] or 0))
        if t == InteracaoNoticia.TIPO_SAVE:
            agg["salvos"] += 1
            total_salvos += 1
        if t == InteracaoNoticia.TIPO_SHARE:
            agg["shares"] += 1
            total_shares += 1
    tempo_medio = round(sum(tempos) / len(tempos), 1) if tempos else 0.0
    return {
        "por_entrada": dict(por_entrada),
        "total_views": total_views,
        "total_cliques": total_cliques,
        "total_shares": total_shares,
        "total_salvos": total_salvos,
        "tempo_medio_leitura_seg": tempo_medio,
        "leituras_com_tempo": len(tempos),
    }


def central_inteligencia(periodo: str = "30d", inicio: str | None = None, fim: str | None = None) -> dict:
    ini, fim_dt, dias, rotulo = resolver_periodo(periodo, inicio, fim)
    delta = fim_dt - ini
    ini_ant, fim_ant = ini - delta, ini

    ev = EventoSite.objects.filter(criado_em__gte=ini, criado_em__lte=fim_dt)
    ev_ant = EventoSite.objects.filter(criado_em__gte=ini_ant, criado_em__lt=fim_ant)

    page = ev.filter(tipo=EventoSite.TIPO_PAGE_VIEW)
    page_ant = ev_ant.filter(tipo=EventoSite.TIPO_PAGE_VIEW)
    visitas, visitas_ant = page.count(), page_ant.count()
    sessoes = page.exclude(sessao="").values("sessao").distinct().count()
    sessoes_ant = page_ant.exclude(sessao="").values("sessao").distinct().count()

    # Sessões recorrentes: mesma sessão (ou usuário) em 2+ dias distintos.
    def _recorrentes(qs):
        dias_por_sessao: dict[str, set] = defaultdict(set)
        for r in qs.exclude(sessao="").values("sessao", "criado_em").iterator(chunk_size=2000):
            dias_por_sessao[r["sessao"]].add(r["criado_em"].date())
        rec = sum(1 for v in dias_por_sessao.values() if len(v) >= 2)
        # autenticados em 2+ dias
        dias_por_user: dict[int, set] = defaultdict(set)
        for r in qs.exclude(user__isnull=True).values("user_id", "criado_em").iterator(chunk_size=2000):
            dias_por_user[r["user_id"]].add(r["criado_em"].date())
        rec_user = sum(1 for v in dias_por_user.values() if len(v) >= 2)
        return rec, rec_user

    sess_rec, users_rec = _recorrentes(ev)
    taxa_retorno = round(sess_rec / sessoes * 100, 1) if sessoes else 0.0

    usuarios_novos = User.objects.filter(date_joined__gte=ini, date_joined__lte=fim_dt).count()
    usuarios_novos_ant = User.objects.filter(date_joined__gte=ini_ant, date_joined__lt=fim_ant).count()

    tempo_medio_pagina = ev.filter(tempo_permanencia_seg__gt=0).aggregate(m=Avg("tempo_permanencia_seg"))["m"] or 0.0
    tempo_medio_pagina = round(float(tempo_medio_pagina), 1)
    scroll_medio = ev.filter(scroll_max_pct__gt=0).aggregate(m=Avg("scroll_max_pct"))["m"] or 0.0
    scroll_medio = round(float(scroll_medio), 1)

    # Entradas/saídas: primeira/última page_view por sessão (paths reais).
    entradas_c, saidas_c = Counter(), Counter()
    por_sessao: dict[str, list] = defaultdict(list)
    for r in page.exclude(sessao="").exclude(path="").values("sessao", "path", "criado_em").order_by("criado_em").iterator(chunk_size=2000):
        por_sessao[r["sessao"]].append(r["path"])
    for paths in por_sessao.values():
        if paths:
            entradas_c[paths[0]] += 1
            saidas_c[paths[-1]] += 1

    inter = _agregar_interacoes(ini, fim_dt)
    inter_ant = _agregar_interacoes(ini_ant, fim_ant)
    por_entrada = inter["por_entrada"]
    distintos_com_view = len([k for k, v in por_entrada.items() if v["views"] > 0])
    views_por_noticia = round(inter["total_views"] / distintos_com_view, 2) if distintos_com_view else 0.0

    EventoBusca, _ = _feed_models()
    if EventoBusca is None:
        buscas = buscas_ant = _QueryVazia()
        total_buscas = total_buscas_ant = 0
        buscas_sem_resultado = 0
        termos_top: list = []
    else:
        buscas = EventoBusca.objects.filter(criado_em__gte=ini, criado_em__lte=fim_dt)
        buscas_ant = EventoBusca.objects.filter(criado_em__gte=ini_ant, criado_em__lt=fim_ant)
        total_buscas, total_buscas_ant = buscas.count(), buscas_ant.count()
        buscas_sem_resultado = buscas.filter(resultados=0).count()
        termos_top = [
            {"termo": r["query_normalizada"], "total": r["total"]}
            for r in buscas.exclude(query_normalizada="").values("query_normalizada")
            .annotate(total=Count("id")).order_by("-total")[:10]
        ]
    buscas_sem_resultado = buscas.filter(resultados=0).count()
    termos_top = [
        {"termo": r["query_normalizada"], "total": r["total"]}
        for r in buscas.exclude(query_normalizada="").values("query_normalizada")
        .annotate(total=Count("id")).order_by("-total")[:10]
    ]

    titulos = _titulos_entradas(list(por_entrada.keys()))

    def _rank(chave_metrica, limite=10):
        ordenadas = sorted(por_entrada.items(), key=lambda kv: kv[1][chave_metrica], reverse=True)
        out = []
        for chave, agg in ordenadas[:limite]:
            if agg[chave_metrica] <= 0:
                continue
            meta = titulos.get(chave, {})
            out.append({
                "tipo": chave[0], "id": chave[1],
                "titulo": meta.get("titulo") or "—",
                "categoria": agg.get("categoria") or meta.get("categoria") or "",
                "total": agg[chave_metrica],
            })
        return out

    # Maior tempo médio (só entradas com 3+ leituras — dado real mínimo).
    com_tempo = [
        (chave, agg["tempo_total"] / agg["leituras"])
        for chave, agg in por_entrada.items() if agg["leituras"] >= 3
    ]
    com_tempo.sort(key=lambda kv: kv[1], reverse=True)
    maior_tempo = [
        {"tipo": c[0], "id": c[1], "titulo": titulos.get(c, {}).get("titulo") or "—",
         "categoria": por_entrada[c].get("categoria") or "",
         "media_seg": round(media, 1), "leituras": por_entrada[c]["leituras"]}
        for c, media in com_tempo[:10]
    ]

    # Categorias/autores em views reais (InteracaoNoticia).
    cat_views = Counter()
    for chave, agg in por_entrada.items():
        if agg["views"] and agg.get("categoria"):
            cat_views[agg["categoria"]] += agg["views"]
    categorias_top = [{"label": k, "total": v} for k, v in cat_views.most_common(10)]

    autores_top: list[dict] = []
    autores_sem_dados = True
    try:
        from catalogo_noticias.models import NewsItem

        if _tem_campo(NewsItem, "autor"):
            item_ids = [c[1] for c in por_entrada if c[0] == "item" and c[1]]
            mapa_autor = dict(
                NewsItem.objects.filter(pk__in=item_ids).exclude(autor="").values_list("id", "autor")
            )
            cont = Counter()
            for chave, agg in por_entrada.items():
                if chave[0] == "item" and chave[1] in mapa_autor and agg["views"]:
                    cont[mapa_autor[chave[1]]] += agg["views"]
            autores_top = [{"label": k, "total": v} for k, v in cont.most_common(10)]
            autores_sem_dados = not bool(
                NewsItem.objects.exclude(autor="").exists()
            )
    except Exception:
        autores_top = []

    # Colunistas: autores de Publicacao (opinião/análise) — dado real.
    colunistas_top: list[dict] = []
    try:
        from comunidade.models import Publicacao

        pubs = (
            Publicacao.objects.filter(status=Publicacao.STATUS_PUBLICADO)
            .values("autor__nome", "autor__email")
            .annotate(total=Count("id"))
            .order_by("-total")[:10]
        )
        colunistas_top = [
            {"label": r["autor__nome"] or r["autor__email"] or "—", "total": r["total"]} for r in pubs
        ]
    except Exception:
        colunistas_top = []

    # Urgentes com views reais.
    urgentes_top: list[dict] = []
    try:
        from catalogo_noticias.models import NewsItem

        urg_ids = set(
            NewsItem.objects.filter(urgente=True).values_list("id", flat=True)[:5000]
        )
        cand = [
            (c, a) for c, a in por_entrada.items()
            if c[0] == "item" and c[1] in urg_ids and a["views"] > 0
        ]
        cand.sort(key=lambda kv: kv[1]["views"], reverse=True)
        for chave, agg in cand[:10]:
            urgentes_top.append({
                "tipo": "item", "id": chave[1],
                "titulo": titulos.get(chave, {}).get("titulo") or "—",
                "total": agg["views"],
            })
    except Exception:
        urgentes_top = []

    # Tráfego: origem + dispositivos (EventoSite).
    trafego_origem = [
        {"label": r["origem"] or "direto", "total": r["total"]}
        for r in ev.exclude(tipo=EventoSite.TIPO_PAGE_VIEW).values("origem").annotate(total=Count("id")).order_by("-total")
    ]
    if not trafego_origem:
        trafego_origem = [
            {"label": r["origem"] or "direto", "total": r["total"]}
            for r in ev.values("origem").annotate(total=Count("id")).order_by("-total")
        ]
    trafego_dispositivos = [
        {"label": r["dispositivo"] or "desconhecido", "total": r["total"]}
        for r in ev.exclude(dispositivo="").values("dispositivo").annotate(total=Count("id")).order_by("-total")
    ]

    # Comportamento: Home / Radar / Comunidade / categorias / autores.
    home_por_secao = [
        {"label": r["secao_home"] or "—", "total": r["total"]}
        for r in ev.filter(
            tipo__in=[EventoSite.TIPO_HOME_SECTION_VIEW, EventoSite.TIPO_HOME_SECTION_CLICK]
        ).exclude(secao_home="").values("secao_home").annotate(total=Count("id")).order_by("-total")
    ]
    home_cliques = ev.filter(tipo=EventoSite.TIPO_HOME_SECTION_CLICK).count()
    home_views = ev.filter(tipo=EventoSite.TIPO_HOME_SECTION_VIEW).count()
    radar_views = ev.filter(tipo=EventoSite.TIPO_RADAR_VIEW).count()
    radar_views_ant = ev_ant.filter(tipo=EventoSite.TIPO_RADAR_VIEW).count()
    community_views = ev.filter(tipo=EventoSite.TIPO_COMMUNITY_VIEW).count()
    community_inter = ev.filter(tipo=EventoSite.TIPO_COMMUNITY_INTERACTION).count()
    cat_views_ev = [
        {"label": r["categoria"], "total": r["total"]}
        for r in ev.filter(tipo__in=[EventoSite.TIPO_CATEGORY_VIEW, EventoSite.TIPO_CATEGORY_CLICK])
        .exclude(categoria="").values("categoria").annotate(total=Count("id")).order_by("-total")[:10]
    ]
    autor_views = [
        {"label": r["autor_ref"], "total": r["total"]}
        for r in ev.filter(tipo__in=[EventoSite.TIPO_AUTHOR_VIEW, EventoSite.TIPO_COLUMNIST_VIEW])
        .exclude(autor_ref="").values("autor_ref").annotate(total=Count("id")).order_by("-total")[:10]
    ]
    top_paths = [
        {"label": r["path"], "total": r["total"]}
        for r in page.exclude(path="").values("path").annotate(total=Count("id")).order_by("-total")[:10]
    ]

    # Localização (só dado consentido — ver models.EventoSite).
    loc_fmt = lambda campo: [
        {"label": r[campo], "total": r["total"]}
        for r in ev.exclude(**{campo: ""}).values(campo).annotate(total=Count("id")).order_by("-total")[:10]
    ]
    try:
        from radar.models import LocalidadeSalva

        salvas_total = LocalidadeSalva.objects.count()
    except Exception:
        salvas_total = 0
    localizacao = {
        "nota": "Somente navegação com consentimento de localização/região.",
        "paises": loc_fmt("pais"),
        "estados": loc_fmt("estado"),
        "cidades": loc_fmt("cidade"),
        "regioes": loc_fmt("regiao"),
        "localidades_salvas_total": salvas_total,
    }

    _, _InteracaoNoticia = _feed_models()
    if _InteracaoNoticia is None:
        qs_views_noticia = _QueryVazia()
    else:
        qs_views_noticia = _InteracaoNoticia.objects.filter(
            tipo__in=[_InteracaoNoticia.TIPO_VIEW, _InteracaoNoticia.TIPO_CLICK,
                      _InteracaoNoticia.TIPO_READ, _InteracaoNoticia.TIPO_SEARCH_CLICK]
        )
    series = {
        "visitas": _serie_diaria(page, "criado_em", dias, ini, fim_dt),
        "sessoes_note": "Sessões são distintas por dia (aproximação sem joins caros).",
        "views_noticia": _serie_diaria(qs_views_noticia, "criado_em", dias, ini, fim_dt),
        "buscas": _serie_diaria(buscas, "criado_em", dias, ini, fim_dt),
    }

    comparativo = {
        "periodo_anterior": {"inicio": ini_ant.isoformat(), "fim": fim_ant.isoformat()},
        "visitas": {"atual": visitas, "anterior": visitas_ant, "delta_pct": _pct(visitas, visitas_ant)},
        "sessoes": {"atual": sessoes, "anterior": sessoes_ant, "delta_pct": _pct(sessoes, sessoes_ant)},
        "views_noticia": {"atual": inter["total_views"], "anterior": inter_ant["total_views"],
                          "delta_pct": _pct(inter["total_views"], inter_ant["total_views"])},
        "buscas": {"atual": total_buscas, "anterior": total_buscas_ant,
                   "delta_pct": _pct(total_buscas, total_buscas_ant)},
        "usuarios_novos": {"atual": usuarios_novos, "anterior": usuarios_novos_ant,
                           "delta_pct": _pct(usuarios_novos, usuarios_novos_ant)},
        "compartilhamentos": {"atual": inter["total_shares"], "anterior": inter_ant["total_shares"],
                              "delta_pct": _pct(inter["total_shares"], inter_ant["total_shares"])},
        "radar_views": {"atual": radar_views, "anterior": radar_views_ant,
                        "delta_pct": _pct(radar_views, radar_views_ant)},
    }

    inteligencia = _gerar_inteligencia(
        ini=ini, fim=fim_dt, ini_ant=ini_ant, fim_ant=fim_ant,
        page=page, ev=ev, por_entrada=por_entrada, titulos=titulos,
        buscas=buscas, buscas_ant=buscas_ant, dias=dias,
    )

    return {
        "periodo": {"chave": rotulo, "inicio": ini.isoformat(), "fim": fim_dt.isoformat(), "dias": dias},
        "audiencia": {
            "visitas": visitas,
            "sessoes": sessoes,
            "usuarios_novos": usuarios_novos,
            "sessoes_recorrentes": sess_rec,
            "usuarios_recorrentes": users_rec,
            "taxa_retorno_pct": taxa_retorno,
            "views_por_noticia": views_por_noticia,
            "noticias_distintas_com_view": distintos_com_view,
            "tempo_medio_leitura_seg": inter["tempo_medio_leitura_seg"],
            "leituras_com_tempo": inter["leituras_com_tempo"],
            "tempo_medio_pagina_seg": tempo_medio_pagina,
            "top_entradas": [{"label": k, "total": v} for k, v in entradas_c.most_common(10)],
            "top_saidas": [{"label": k, "total": v} for k, v in saidas_c.most_common(10)],
        },
        "trafego": {"origens": trafego_origem, "dispositivos": trafego_dispositivos},
        "conteudo": {
            "mais_acessadas": _rank("views"),
            "mais_clicadas": _rank("cliques"),
            "mais_pesquisadas": termos_top,
            "buscas_sem_resultado": buscas_sem_resultado,
            "mais_compartilhadas": _rank("shares"),
            "mais_salvas": _rank("salvos"),
            "maior_tempo_medio": maior_tempo,
            "categorias_top": categorias_top,
            "autores_top": autores_top,
            "autores_sem_dados": autores_sem_dados,
            "colunistas_top": colunistas_top,
            "urgentes_top": urgentes_top,
        },
        "comportamento": {
            "views_noticia": inter["total_views"],
            "cliques_noticia": inter["total_cliques"],
            "shares": inter["total_shares"],
            "salvos": inter["total_salvos"],
            "scroll_medio_pct": scroll_medio,
            "buscas_total": total_buscas,
            "termos_top": termos_top,
            "top_paths": top_paths,
            "home": {"views": home_views, "cliques": home_cliques, "por_secao": home_por_secao},
            "radar_views": radar_views,
            "comunidade": {"views": community_views, "interacoes": community_inter},
            "categorias_navegadas": cat_views_ev,
            "autores_vistos": autor_views,
        },
        "localizacao": localizacao,
        "series": series,
        "comparativo": comparativo,
        "inteligencia": inteligencia,
    }


def _gerar_inteligencia(*, ini, fim, ini_ant, fim_ant, page, ev, por_entrada, titulos,
                        buscas, buscas_ant, dias) -> dict:
    """Insights editoriais automáticos — SÓ com dados reais.

    Cada insight carrega `base` (números que o sustentam). Sem base mínima,
    o insight não é gerado; se nenhum for gerável, `sem_dados: True`.
    """
    insights: list[dict] = []

    # 1) Categorias em crescimento (atual vs anterior).
    cur = Counter()
    for chave, agg in por_entrada.items():
        if agg["views"] and agg.get("categoria"):
            cur[agg["categoria"]] += agg["views"]
    ant = Counter()
    _, _IN = _feed_models()
    if _IN is not None:
        for r in _IN.objects.filter(
            criado_em__gte=ini_ant, criado_em__lt=fim_ant,
            tipo__in=[_IN.TIPO_VIEW, _IN.TIPO_CLICK, _IN.TIPO_READ, _IN.TIPO_SEARCH_CLICK],
        ).exclude(categoria="").values("categoria").annotate(total=Count("id")).iterator(chunk_size=2000):
            ant[r["categoria"]] += r["total"]
    for cat, total in cur.most_common(15):
        if total < 5:
            continue
        base = ant.get(cat, 0)
        if base == 0:
            insights.append({
                "tipo": "categoria_emergente",
                "titulo": f"Assunto emergente: {cat}",
                "detalhe": f"{total} visualizações no período, sem registro no período anterior.",
                "base": {"categoria": cat, "atual": total, "anterior": 0},
            })
        else:
            delta = (total - base) / base * 100
            if delta >= 30:
                insights.append({
                    "tipo": "categoria_crescimento",
                    "titulo": f"Interesse por {cat} subiu {delta:.0f}% no período",
                    "detalhe": f"De {base} para {total} visualizações vs. período anterior.",
                    "base": {"categoria": cat, "atual": total, "anterior": base,
                             "delta_pct": round(delta, 1)},
                })

    # 2) Regiões em crescimento (dado consentido).
    top_estados = [
        {"label": r["estado"], "total": r["total"]}
        for r in ev.exclude(estado="").values("estado").annotate(total=Count("id")).order_by("-total")[:10]
    ]
    ant_est = {
        r["estado"]: r["total"]
        for r in EventoSite.objects.filter(criado_em__gte=ini_ant, criado_em__lt=fim_ant)
        .exclude(estado="").values("estado").annotate(total=Count("id"))
    }
    for e in top_estados:
        if e["total"] < 5:
            continue
        base = ant_est.get(e["label"], 0)
        if base and (e["total"] - base) / base * 100 >= 30:
            insights.append({
                "tipo": "regiao_crescimento",
                "titulo": f"Acessos de {e['label']} cresceram no período",
                "detalhe": f"De {base} para {e['total']} eventos com região vs. período anterior.",
                "base": {"regiao": e["label"], "atual": e["total"], "anterior": base},
            })

    # 3) Picos anormais de audiência (série diária de visitas).
    serie = _serie_diaria(page, "criado_em", dias, ini, fim)
    totais = [p["total"] for p in serie]
    if len(totais) >= 3 and sum(totais) >= 10:
        media = sum(totais) / len(totais)
        for p in serie:
            if media > 0 and p["total"] >= max(2 * media, media + 5):
                insights.append({
                    "tipo": "pico_audiencia",
                    "titulo": f"Pico anormal em {p['dia']}",
                    "detalhe": f"{p['total']} visitas no dia vs. média de {media:.1f}/dia no período.",
                    "base": {"dia": p["dia"], "visitas": p["total"], "media_dia": round(media, 1)},
                })

    # 4) Horários de pico (histograma hora do dia — page_views + interações).
    horas = Counter()
    for r in page.values("criado_em").iterator(chunk_size=2000):
        horas[r["criado_em"].hour] += 1
    if _IN is not None:
        for r in _IN.objects.filter(criado_em__gte=ini, criado_em__lte=fim).values("criado_em").iterator(chunk_size=2000):
            horas[r["criado_em"].hour] += 1
    if sum(horas.values()) >= 10:
        top_horas = horas.most_common(3)
        insights.append({
            "tipo": "horarios_pico",
            "titulo": "Horários de pico: " + ", ".join(f"{h}h" for h, _ in top_horas),
            "detalhe": "Horas com mais atividade (visitas + interações) no período.",
            "base": {"horas": [{"hora": h, "total": t} for h, t in top_horas]},
        })

    # 5) Retenção alta/baixa (tempo médio por notícia, 3+ leituras).
    com_tempo = [
        (c, a["tempo_total"] / a["leituras"]) for c, a in por_entrada.items() if a["leituras"] >= 3
    ]
    if len(com_tempo) >= 2:
        com_tempo.sort(key=lambda kv: kv[1])
        (c_baixa, m_baixa), (c_alta, m_alta) = com_tempo[0], com_tempo[-1]
        if m_alta - m_baixa >= 15:
            insights.append({
                "tipo": "retencao_alta",
                "titulo": f"Alta retenção: “{(titulos.get(c_alta, {}).get('titulo') or '—')[:80]}”",
                "detalhe": f"Tempo médio de {m_alta:.0f}s por leitura ({por_entrada[c_alta]['leituras']} leituras).",
                "base": {"tipo": c_alta[0], "id": c_alta[1], "media_seg": round(m_alta, 1),
                         "leituras": por_entrada[c_alta]["leituras"]},
            })
            insights.append({
                "tipo": "retencao_baixa",
                "titulo": f"Baixa retenção: “{(titulos.get(c_baixa, {}).get('titulo') or '—')[:80]}”",
                "detalhe": f"Tempo médio de {m_baixa:.0f}s por leitura ({por_entrada[c_baixa]['leituras']} leituras).",
                "base": {"tipo": c_baixa[0], "id": c_baixa[1], "media_seg": round(m_baixa, 1),
                         "leituras": por_entrada[c_baixa]["leituras"]},
            })

    # 6) Buscas emergentes (termos novos ou em alta vs. período anterior).
    cur_t = Counter(dict(
        buscas.exclude(query_normalizada="").values("query_normalizada")
        .annotate(total=Count("id")).values_list("query_normalizada", "total")[:200]
    ))
    ant_t = Counter(dict(
        buscas_ant.exclude(query_normalizada="").values("query_normalizada")
        .annotate(total=Count("id")).values_list("query_normalizada", "total")[:200]
    ))
    for termo, total in cur_t.most_common(20):
        if total < 3:
            continue
        base = ant_t.get(termo, 0)
        if base == 0:
            insights.append({
                "tipo": "busca_emergente",
                "titulo": f"Busca emergente: “{termo}”",
                "detalhe": f"{total} buscas no período, termo ausente no período anterior.",
                "base": {"termo": termo, "atual": total, "anterior": 0},
            })
        elif (total - base) / base >= 0.5:
            insights.append({
                "tipo": "busca_em_alta",
                "titulo": f"Busca em alta: “{termo}”",
                "detalhe": f"De {base} para {total} buscas vs. período anterior.",
                "base": {"termo": termo, "atual": total, "anterior": base},
            })

    if not insights:
        return {"sem_dados": True,
                "mensagem": "Sem dados suficientes no período para gerar insights — os cards aparecem automaticamente quando houver eventos."}
    return {"sem_dados": False, "total": len(insights), "itens": insights[:30]}
