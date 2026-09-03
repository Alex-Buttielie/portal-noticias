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

from django.db.models import Q, QuerySet

from catalogo_noticias.models import NewsCluster, NewsItem

STATUS_PUBLICAVEIS = [NewsItem.STATUS_NAO_APLICAVEL, NewsItem.STATUS_APROVADO]


def _timestamp_ordenacao(item: NewsItem):
    """
    Timestamp usado para ordenar o feed e decidir qual item representa um
    NewsCluster: a data de publicação na fonte quando conhecida (mais fiel
    ao "quando aconteceu"), com fallback para a data de ingestão (sempre
    preenchida, `auto_now_add`).
    """
    return item.timestamp_publicacao_fonte or item.timestamp_ingestao


def itens_publicaveis(categoria: str | None = None, busca: str | None = None) -> QuerySet[NewsItem]:
    """
    Critério de aceite 2 (implementation-contract.md): itens com
    `status_revisao` `pendente` ou `rejeitado` NUNCA são incluídos aqui —
    esta é a única função que o restante do módulo `feed` usa para acessar
    `NewsItem`, então nenhum outro ponto do app precisa reimplementar essa
    checagem.
    """
    qs = NewsItem.objects.filter(status_revisao__in=STATUS_PUBLICAVEIS).select_related("cluster")

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
            }
        elif item.urgente and not entradas[chave]["urgente"]:
            # Qualquer item urgente dentro do subconjunto filtrado do mesmo
            # cluster marca a entrada inteira como urgente, mesmo que não
            # seja o item escolhido como representante (título/resumo).
            entradas[chave]["urgente"] = True

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
        "fontes": [
            {
                "nome_fonte": item.nome_fonte,
                "url_fonte_original": item.url_fonte_original,
                "resumo": item.resumo_proprio,
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
        "fontes": [
            {
                "nome_fonte": item.nome_fonte,
                "url_fonte_original": item.url_fonte_original,
                "resumo": item.resumo_proprio,
            }
        ],
    }


def exibir_publicidade(user) -> bool:
    """
    Critério de aceite 7: `false` só para usuário autenticado com
    `papel=premium`; visitante (`AnonymousUser`, `is_authenticated=False`)
    ou usuário `free` sempre recebe `true`.
    """
    if getattr(user, "is_authenticated", False) and getattr(user, "papel", None) == "premium":
        return False
    return True
