"""
Lógica de leitura/agrupamento do feed (implementation-contract.md run
20260902-1409-feed-consumo) — nenhuma escrita: só consulta `NewsItem`/
`NewsCluster` já existentes em `catalogo_noticias`.

Decisão de design: o feed é construído a partir do QUERYSET DE NewsItem
publicáveis (não a partir de NewsCluster diretamente), porque os filtros de
categoria/busca (critérios de aceite 3 e 4) operam sobre campos do item
(`categoria`, `titulo`, `resumo_proprio`). Depois de filtrar, os itens são
agrupados em memória: itens do MESMO NewsCluster viram UMA entrada de feed
(representada pelo item mais recente do subconjunto filtrado que pertence a
esse cluster); itens standalone (cluster=None) viram sua própria entrada.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db.models import Q, QuerySet
from django.utils import timezone

from catalogo_noticias.models import NewsCluster, NewsItem

STATUS_PUBLICAVEIS = [NewsItem.STATUS_NAO_APLICAVEL, NewsItem.STATUS_APROVADO]

# Run 20260923-1216-p1-feed-cache-indices (P1-1): campos do `NewsItem` lidos
# pelo caminho de LISTA do feed (`construir_feed_entries`,
# `_timestamp_ordenacao`, `equilibrar_por_categoria` — que só toca dicts — e
# `painel_admin.services_regras.aplicar_regras_curadoria`, que lê
# `id`/`cluster_id`/`autor` dos itens). `conteudo_bruto`/`conteudo_completo`
# ficam DE FORA de propósito: só as views de detalhe os exibem, com fetch
# completo (`detalhe_cluster`/`detalhe_item` abaixo, sem `.only()`).
# REGRA: quem adicionar leitura de campo de `NewsItem` no caminho de lista
# deve incluí-lo aqui, senão reintroduz N+1 de deferred fields.
CAMPOS_LISTA_FEED = (
    "titulo",
    "resumo_proprio",
    "categoria",
    "urgente",
    "imagem_url",
    "pais",
    "estado",
    "cidade",
    "nome_fonte",
    "autor",
    "timestamp_publicacao_fonte",
    "timestamp_ingestao",
    "cluster",
    "cluster__numero_fontes_distintas",
)

# Subconjunto de `CAMPOS_LISTA_FEED` válido para `.only()` (sem travessias
# de relação — `cluster__...` vai via `select_related`, não via `.only()`).
CAMPOS_SEM_RELACAO = tuple(c for c in CAMPOS_LISTA_FEED if "__" not in c)


def _timestamp_ordenacao(item: NewsItem):
    """
    Timestamp usado para ordenar o feed e decidir qual item representa um
    NewsCluster: a data de publicação na fonte quando conhecida (mais fiel
    ao "quando aconteceu"), com fallback para a data de ingestão (sempre
    preenchida, `auto_now_add`).
    """
    return item.timestamp_publicacao_fonte or item.timestamp_ingestao


def itens_publicaveis(
    categoria: str | None = None,
    busca: str | None = None,
    aplicar_janela: bool = True,
) -> QuerySet[NewsItem]:
    """
    Critério de aceite 2 (implementation-contract.md): itens com
    `status_revisao` `pendente` ou `rejeitado` NUNCA são incluídos aqui —
    esta é a única função que o restante do módulo `feed` usa para acessar
    `NewsItem`, então nenhum outro ponto do app precisa reimplementar essa
    checagem.

    Run 20260923-1216-p1-feed-cache-indices (P1-1):
    - janela de listagem (`settings.FEED_JANELA_HORAS`, default 72h): o feed
      público cobre o ciclo de notícias sem varrer o acervo inteiro;
    - `.only(*CAMPOS_LISTA_FEED)` + `select_related("cluster")`: as colunas
      pesadas (`conteudo_bruto`/`conteudo_completo`) nunca são selecionadas
      nas listagens — detalhe tem fetch próprio completo.

    Run 20261012-1806-monetizacao-sprint1 (remediação do Finding 1 do
    code-review-contract.md, M-02): `aplicar_janela=False` desliga o corte
    de `timestamp_ingestao__gte`. Usado por `entradas_sitemap()`, que
    precisa cobrir TODO o acervo publicável/indexável (não só os últimos
    `FEED_JANELA_HORAS`, 72h em produção) — o sitemap existe justamente
    para dar alcance orgânico a notícias que já saíram do ciclo recente do
    feed de lista. `.only()`/`select_related("cluster")` continuam
    aplicados nos dois casos, para não reintroduzir N+1.
    """
    filtros: dict = {"status_revisao__in": STATUS_PUBLICAVEIS}
    if aplicar_janela:
        janela_horas = float(getattr(settings, "FEED_JANELA_HORAS", 72))
        corte = timezone.now() - timedelta(hours=janela_horas)
        filtros["timestamp_ingestao__gte"] = corte

    qs = (
        NewsItem.objects.filter(**filtros)
        .select_related("cluster")
        .only(*CAMPOS_LISTA_FEED)
    )

    if categoria:
        qs = qs.filter(categoria__iexact=categoria)
    if busca:
        qs = qs.filter(Q(titulo__icontains=busca) | Q(resumo_proprio__icontains=busca))

    return qs


def construir_feed_entries(itens: list[NewsItem]) -> list[dict]:
    """
    Agrupa uma lista de `NewsItem` JÁ PUBLICÁVEIS (normalmente o resultado de
    `itens_publicaveis`, já filtrado) em entradas de feed. Retorna uma lista
    de dicts (não instâncias de modelo) ordenada da mais recente para a mais
    antiga — `FeedEntrySerializer` serializa esses dicts diretamente.
    """
    entradas: dict[tuple[str, int], dict] = {}

    for item in itens:
        if item.cluster_id is not None:
            chave = ("cluster", item.cluster_id)
        else:
            chave = ("item", item.id)

        timestamp_item = _timestamp_ordenacao(item)
        existente = entradas.get(chave)

        if existente is None or timestamp_item > existente["timestamp"]:
            # P1-1 (run 20260923-1216): coluna denormalizada — leitura direta
            # do campo, sem COUNT por cluster. Exige `select_related("cluster")`
            # (garantido por `itens_publicaveis`); passar itens sem o cluster
            # pré-carregado reintroduz query por cluster.
            numero_fontes = item.cluster.numero_fontes_distintas if item.cluster_id else 1
            entradas[chave] = {
                "tipo": chave[0],
                "id": chave[1],
                "titulo": item.titulo,
                "resumo": item.resumo_proprio,
                "categoria": item.categoria,
                "urgente": item.urgente,
                "numero_fontes": numero_fontes,
                "timestamp": timestamp_item,
                "imagem_url": getattr(item, "imagem_url", "") or "",
                # Localidade e fonte do item representante — nunca inventadas,
                # vazias quando o pipeline não inferiu (frontend só exibe se existirem).
                "pais": getattr(item, "pais", "") or "",
                "estado": getattr(item, "estado", "") or "",
                "cidade": getattr(item, "cidade", "") or "",
                "nome_fonte": getattr(item, "nome_fonte", "") or "",
                # FRENTE 3 — autor/colunista creditado no RSS (best-effort).
                "autor": getattr(item, "autor", "") or "",
            }
        else:
            if item.urgente and not entradas[chave]["urgente"]:
                # Qualquer item urgente dentro do subconjunto filtrado do mesmo
                # cluster marca a entrada inteira como urgente, mesmo que não
                # seja o item escolhido como representante (título/resumo).
                entradas[chave]["urgente"] = True
            # Completa localidade/fonte vazias do representante com outro item
            # do mesmo cluster (best-effort, sem inventar dado).
            for campo in ("pais", "estado", "cidade", "nome_fonte", "imagem_url", "autor"):
                if not entradas[chave].get(campo) and getattr(item, campo, ""):
                    entradas[chave][campo] = getattr(item, campo) or ""

    return sorted(entradas.values(), key=lambda entrada: entrada["timestamp"], reverse=True)


def equilibrar_por_categoria(entradas: list[dict]) -> list[dict]:
    """
    BRD seção 10 — "Manter equilíbrio entre categorias para evitar
    concentração excessiva em um único assunto." Gap real encontrado na
    análise do BRD: o feed era só ordenado por recência, sem nenhum
    controle de concentração — um dia com muita cobertura de uma única
    categoria (ex.: eleições) podia lotar o topo do feed inteiro,
    empurrando as demais categorias para muito longe.

    Intercala por categoria (round-robin), preservando a ordem de recência
    DENTRO de cada categoria — cada "rodada" contribui no máximo 1 entrada
    por categoria, então nenhuma categoria consegue dominar posições
    consecutivas do feed. Não é uma cota rígida: uma categoria com mais
    volume ainda aparece mais vezes no total, só não consegue mais
    monopolizar o topo.

    Só deve ser aplicada ao feed GERAL (sem filtro de categoria/busca
    ativo) — um usuário que já escolheu uma categoria ou fez uma busca quer
    exatamente aquele recorte, sem rebalanceamento.
    """
    por_categoria: dict[str, list[dict]] = {}
    ordem_categorias: list[str] = []
    for entrada in entradas:
        categoria = entrada.get("categoria") or ""
        if categoria not in por_categoria:
            por_categoria[categoria] = []
            ordem_categorias.append(categoria)
        por_categoria[categoria].append(entrada)

    resultado: list[dict] = []
    indice = 0
    total = len(entradas)
    while len(resultado) < total:
        for categoria in ordem_categorias:
            fila = por_categoria[categoria]
            if indice < len(fila):
                resultado.append(fila[indice])
        indice += 1
    return resultado


def detalhe_cluster(cluster_id: int) -> dict | None:
    """
    Critério de aceite 5: lista TODAS as fontes publicáveis associadas ao
    cluster. Se o cluster não existir, ou existir mas não tiver nenhum item
    publicável (todos pendente/rejeitado), retorna None — o caller (view)
    trata isso como 404 (critério de aceite 8), nunca vazando a existência
    de conteúdo não aprovado.
    """
    try:
        cluster = NewsCluster.objects.get(pk=cluster_id)
    except NewsCluster.DoesNotExist:
        return None

    itens = list(
        cluster.itens.filter(status_revisao__in=STATUS_PUBLICAVEIS).order_by("-timestamp_ingestao")
    )
    if not itens:
        return None

    representante = max(itens, key=_timestamp_ordenacao)

    return {
        "tipo": "cluster",
        "id": cluster.id,
        "titulo": cluster.titulo_acontecimento or representante.titulo,
        "categoria": cluster.categoria_dominante or representante.categoria,
        "urgente": any(item.urgente for item in itens),
        "timestamp": _timestamp_ordenacao(representante),
        "pais": getattr(representante, "pais", "") or "",
        "estado": getattr(representante, "estado", "") or "",
        "cidade": getattr(representante, "cidade", "") or "",
        "fontes": [
            {
                "nome_fonte": item.nome_fonte,
                "url_fonte_original": item.url_fonte_original,
                "resumo": item.resumo_proprio,
                "imagem_url": getattr(item, "imagem_url", "") or "",
                # M-01 (run 20261012-1806-monetizacao-sprint1): `conteudo`
                # (texto raspado, até 6.000 caracteres) NÃO é mais exposto no
                # JSON público — risco de direito autoral/BRD §18. O texto
                # completo continua no banco (`conteudo_completo`), acessível
                # só por rota autenticada de admin, se algum dia necessário.
            }
            for item in itens
        ],
    }


def detalhe_item(item_id: int) -> dict | None:
    """
    Critério de aceite 6: item standalone funciona igual ao de cluster, só
    com uma "fonte" na lista. Mesma regra de 404 do `detalhe_cluster` acima.
    """
    try:
        item = NewsItem.objects.get(pk=item_id, status_revisao__in=STATUS_PUBLICAVEIS)
    except NewsItem.DoesNotExist:
        return None

    return {
        "tipo": "item",
        "id": item.id,
        "titulo": item.titulo,
        "categoria": item.categoria,
        "urgente": item.urgente,
        "timestamp": _timestamp_ordenacao(item),
        "pais": getattr(item, "pais", "") or "",
        "estado": getattr(item, "estado", "") or "",
        "cidade": getattr(item, "cidade", "") or "",
        "fontes": [
            {
                "nome_fonte": item.nome_fonte,
                "url_fonte_original": item.url_fonte_original,
                "resumo": item.resumo_proprio,
                "imagem_url": getattr(item, "imagem_url", "") or "",
                # M-01: ver nota equivalente em `detalhe_cluster` acima.
            }
        ],
    }


def entradas_sitemap() -> list[dict]:
    """
    M-02 (run 20261012-1806-monetizacao-sprint1): lista de entradas
    publicáveis E indexáveis (com resumo próprio — ver M-03/`lib/seo.ts` no
    frontend, que marca `noindex` quando `resumo` está vazio) para o
    `/sitemap.xml` do Next.

    Reaproveita `itens_publicaveis`/`construir_feed_entries` (`.only()` +
    `select_related("cluster")`, sem N+1 novo) e filtra por `resumo` não
    vazio, para o sitemap nunca anunciar ao Google uma página que a própria
    página marca como `noindex`.

    Remediação do Finding 1 do code-review-contract.md desta run: chama
    `itens_publicaveis(aplicar_janela=False)` DE PROPÓSITO — sem isso, uma
    notícia com mais de `FEED_JANELA_HORAS` (72h em produção) nunca
    apareceria aqui, mesmo publicável e indexável, contradizendo o próprio
    objetivo de negócio do M-02 (dar alcance orgânico ao acervo que hoje não
    está em nenhum sitemap). A paginação (`SitemapView`/`SitemapPagination`,
    500/página) continua responsável por não devolver o acervo inteiro de
    uma vez — aqui só deixamos de FILTRAR por tempo, não de paginar.
    """
    itens = list(itens_publicaveis(aplicar_janela=False))
    entradas = construir_feed_entries(itens)
    return [e for e in entradas if (e.get("resumo") or "").strip()]


def urgentes(limite: int = 8) -> list[dict]:
    itens = list(itens_publicaveis().filter(urgente=True).order_by("-timestamp_ingestao")[: limite * 3])
    entries = construir_feed_entries(itens)
    urg = [e for e in entries if e["urgente"]]
    return urg[:limite]


def mais_lidas(limite: int = 5) -> list[dict]:
    itens = list(itens_publicaveis().order_by("-timestamp_ingestao")[:120])
    entries = construir_feed_entries(itens)
    entries.sort(key=lambda e: (e["numero_fontes"], e["timestamp"]), reverse=True)
    return entries[:limite]


def seguir_fonte(user, nome_fonte: str) -> "FonteSeguida":  # noqa: F821
    from .models import FonteSeguida

    nome = (nome_fonte or "").strip()[:150]
    obj, _ = FonteSeguida.objects.get_or_create(user=user, nome_fonte=nome)
    return obj


def deixar_de_seguir_fonte(user, nome_fonte: str) -> None:
    from .models import FonteSeguida

    FonteSeguida.objects.filter(user=user, nome_fonte=(nome_fonte or "").strip()[:150]).delete()


def fontes_seguidas(user) -> "QuerySet[FonteSeguida]":  # noqa: F821
    from .models import FonteSeguida

    return FonteSeguida.objects.filter(user=user)
