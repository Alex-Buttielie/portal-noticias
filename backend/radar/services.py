"""Serviço de domínio do radar (run 20260902-1513-radar-tendencias-localizacao)."""

from __future__ import annotations

import math
from collections import Counter
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from catalogo_noticias.models import NewsItem

from .models import LocalidadeSalva

AVISO_METODOLOGIA = (
    "Estas tendências refletem volume de COBERTURA jornalística agrupada pelo produto, "
    "não dados de busca/interesse real dos usuários (BRD §11)."
)


def _itens_publicaveis_no_recorte(pais=None, estado=None, janela_dias=7):
    corte = timezone.now() - timedelta(days=janela_dias)
    qs = NewsItem.objects.filter(
        status_revisao__in=[NewsItem.STATUS_NAO_APLICAVEL, NewsItem.STATUS_APROVADO],
        timestamp_ingestao__gte=corte,
    )
    if pais:
        qs = qs.filter(pais__iexact=pais)
    if estado:
        qs = qs.filter(estado__iexact=estado)
    return qs


def _resolver_estado(estado):
    """R-02 — resolve texto livre (sigla UF, nome do estado ou de uma
    cidade) para a sigla da UF, via `enderecos.services.resolver_uf`.
    `cidade` nunca é usada como filtro aqui: a ingestão real nunca a
    popula (0% de cobertura medida), então filtrar por ela sempre
    devolveria vazio silenciosamente — a UF (que tem ~58% de cobertura) é
    o recorte regional real disponível.

    Retorna `(uf, erro)`: quando não resolve, `uf` é `None` e `erro` é uma
    mensagem pronta para a UI — nunca inventa estado, nunca estoura 500.
    """
    texto = (estado or "").strip()
    if not texto:
        return None, None
    from enderecos.services import resolver_uf

    uf = resolver_uf(texto)
    if uf:
        return uf, None
    return None, (
        f'Não foi possível identificar o estado para "{texto}". '
        "Tente a sigla da UF (ex.: GO) ou o nome da cidade/estado."
    )


def tendencias(pais=None, estado=None, lat=None, lon=None, janela_dias=7) -> dict:
    """Critérios de aceite 1, 2, 4 — funciona sem nenhum filtro (recorte nacional/global).

    R-02: `estado` aceita texto livre (resolvido para UF via `enderecos`);
    quando `lat`/`lon` do usuário vêm, os assuntos são ordenados por
    distância Haversine crescente até a UF do item mais recente de cada
    categoria; sem coordenada, mantém a ordenação por score (comportamento
    atual).
    """
    from feed import recomendacao as rec

    uf, erro = _resolver_estado(estado)
    if erro:
        return {
            "aviso_metodologia": AVISO_METODOLOGIA,
            "localidade": {"pais": pais, "estado": estado},
            "assuntos_em_alta": [],
            "erro_localidade": erro,
        }

    qs = _itens_publicaveis_no_recorte(pais, uf, janela_dias)
    agregado = (
        qs.exclude(categoria="")
        .values("categoria")
        .annotate(numero_noticias=Count("id"), numero_fontes=Count("nome_fonte", distinct=True))
        .order_by("-numero_noticias")
    )

    # BRD seção 11, requisito funcional "Acesso ao acontecimento agrupado" —
    # gap real encontrado na análise do BRD: o radar mostrava contagens por
    # categoria mas não linkava para nenhuma notícia de verdade. Para cada
    # assunto em alta, buscamos o item mais recente do recorte como
    # representante — cluster_id quando existe (o "acontecimento agrupado"
    # coberto por múltiplas fontes, propriamente dito), senão item_id
    # standalone.
    #
    # FRENTE 3 — mesma lógica da Home + localização + tendências regionais:
    # cada assunto ganha `crescimento_24h` (fração de interações nas últimas
    # 24h), `buscas` (nº de buscas recentes conversando com a categoria) e
    # `score` (popularidade+crescimento+engajamento), sem mudar as chaves
    # que o frontend já consome.
    sinais = rec.agregar_sinais()
    termos = [t["termo"] for t in rec.termos_em_alta()]
    busca_por_termo = {t["termo"]: t["total"] for t in rec.termos_em_alta()}
    agora = timezone.now()
    corte_24h = agora - timedelta(hours=1 * 24)

    from feed.models import InteracaoNoticia

    interacoes_24h = Counter(
        InteracaoNoticia.objects.filter(criado_em__gte=corte_24h)
        .exclude(categoria="").values_list("categoria", flat=True)
    )
    interacoes_7d = Counter(
        InteracaoNoticia.objects.filter(criado_em__gte=agora - timedelta(days=janela_dias))
        .exclude(categoria="").values_list("categoria", flat=True)
    )

    assuntos_em_alta = []
    for entrada in agregado:
        representante = (
            qs.filter(categoria=entrada["categoria"])
            .order_by("-timestamp_ingestao")
            .values("id", "cluster_id", "estado")
            .first()
        )
        cat_norm = (entrada["categoria"] or "").lower()
        tot_7d = interacoes_7d.get(entrada["categoria"], 0) or interacoes_7d.get(cat_norm, 0)
        tot_24h = interacoes_24h.get(entrada["categoria"], 0) or interacoes_24h.get(cat_norm, 0)
        crescimento_24h = round(tot_24h / tot_7d, 3) if tot_7d >= 5 else 0.0
        buscas = sum(total for termo, total in busca_por_termo.items() if termo and termo in cat_norm)
        score = round(
            min(20.0, 20.0 * math.log1p(tot_7d) / math.log1p(50))
            + 15.0 * crescimento_24h
            + min(10.0, 3.0 * buscas),
            2,
        )
        assuntos_em_alta.append(
            {
                **entrada,
                "cluster_id": representante["cluster_id"] if representante else None,
                "item_id": representante["id"] if representante else None,
                "estado": representante["estado"] if representante else None,
                "crescimento_24h": crescimento_24h,
                "buscas_relacionadas": buscas,
                "score": score,
            }
        )
    # Comportamento atual preservado: sem coordenada do usuário, ordena por
    # score/volume. Com lat/lon, a distância Haversine até a UF do
    # representante manda (R-02) — score permanece como critério de
    # desempate para UFs desconhecidas/ausentes.
    assuntos_em_alta.sort(key=lambda a: (a["score"], a["numero_noticias"]), reverse=True)
    if lat is not None and lon is not None:
        from .geografia import distancia_km_uf

        for assunto in assuntos_em_alta:
            assunto["distancia_km"] = distancia_km_uf(assunto.get("estado"), lat, lon)
        assuntos_em_alta.sort(key=lambda a: (a["distancia_km"] is None, a["distancia_km"] or 0.0))

    return {
        "aviso_metodologia": AVISO_METODOLOGIA,
        "localidade": {"pais": pais, "estado": uf},
        "assuntos_em_alta": assuntos_em_alta,
    }


def evolucao_interesse(categoria=None, pais=None, estado=None, dias=14) -> dict:
    """Critério de aceite 3 — gating checado na view (services não decide plano).

    R-02: `estado` aceita texto livre, resolvido para UF via `enderecos`
    (mesma regra de `tendencias`). Sem resolução, devolve série vazia com
    `erro_localidade` — nunca 500, nunca estado inventado.
    """
    uf, erro = _resolver_estado(estado)
    if erro:
        return {
            "aviso_metodologia": AVISO_METODOLOGIA,
            "categoria": categoria,
            "serie": [],
            "erro_localidade": erro,
        }

    qs = _itens_publicaveis_no_recorte(pais, uf, janela_dias=dias)
    if categoria:
        qs = qs.filter(categoria__iexact=categoria)

    serie = (
        qs.annotate(dia=TruncDate("timestamp_ingestao"))
        .values("dia")
        .annotate(numero_noticias=Count("id"))
        .order_by("dia")
    )
    return {"aviso_metodologia": AVISO_METODOLOGIA, "categoria": categoria, "serie": list(serie)}


def noticias_regionais(
    pais=None,
    estado=None,
    categoria=None,
    busca=None,
    periodo_dias=30,
    lat=None,
    lon=None,
    limite=30,
) -> dict:
    """R-03 — lista de notícias para o grid estilo marketplace do Radar
    (foto + título + UF + tempo + categoria), com filtros de categoria/UF/
    período + busca textual.

    R-02: ordena por distância Haversine crescente até a UF de cada item
    quando `lat`/`lon` do usuário vêm; sem coordenada, mantém a ordenação
    por recência (comportamento já existente no restante do Radar).
    """
    uf, erro = _resolver_estado(estado)
    if erro:
        return {
            "aviso_metodologia": AVISO_METODOLOGIA,
            "localidade": {"pais": pais, "estado": estado},
            "itens": [],
            "erro_localidade": erro,
        }

    dias = max(1, min(90, int(periodo_dias or 30)))
    limite = max(1, min(60, int(limite or 30)))

    qs = _itens_publicaveis_no_recorte(pais, uf, janela_dias=dias)
    if categoria:
        qs = qs.filter(categoria__iexact=categoria)
    texto_busca = (busca or "").strip()
    if texto_busca:
        qs = qs.filter(titulo__icontains=texto_busca)

    usa_distancia = lat is not None and lon is not None
    # Com distância, buscamos uma janela maior antes de reordenar em Python
    # (a ordenação por distância não é expressável no `ORDER BY` do banco
    # sem persistir coordenada por item, que é não-objetivo do contrato).
    janela_busca = limite * 3 if usa_distancia else limite
    campos = list(
        qs.order_by("-timestamp_ingestao")
        .values("id", "cluster_id", "titulo", "categoria", "estado", "pais", "timestamp_ingestao", "imagem_url", "nome_fonte")[:janela_busca]
    )

    itens = []
    for campo in campos:
        item = dict(campo)
        item["tipo"] = "cluster" if item.get("cluster_id") else "item"
        item["timestamp"] = item.pop("timestamp_ingestao")
        itens.append(item)

    if usa_distancia:
        from .geografia import distancia_km_uf

        for item in itens:
            item["distancia_km"] = distancia_km_uf(item.get("estado"), lat, lon)
        itens.sort(key=lambda i: (i["distancia_km"] is None, i["distancia_km"] or 0.0))
        itens = itens[:limite]
    else:
        for item in itens:
            item["distancia_km"] = None

    return {
        "aviso_metodologia": AVISO_METODOLOGIA,
        "localidade": {"pais": pais, "estado": uf},
        "itens": itens,
        "ordenado_por": "distancia" if usa_distancia else "recencia",
    }


def salvar_localidade(user, pais="", estado="", cidade="") -> LocalidadeSalva:
    """Critério de aceite 5 — idempotente via get_or_create."""
    obj, _ = LocalidadeSalva.objects.get_or_create(user=user, pais=pais, estado=estado, cidade=cidade)
    return obj


def remover_localidade(user, pais="", estado="", cidade="") -> None:
    LocalidadeSalva.objects.filter(user=user, pais=pais, estado=estado, cidade=cidade).delete()


def localidades_salvas(user):
    return LocalidadeSalva.objects.filter(user=user)


# ---------------------------------------------------------------------------
# FRENTE 3 — Radar com a mesma lógica da Home + localização autorizada
# ---------------------------------------------------------------------------

def para_voce_regional(user=None, pais=None, estado=None, cidade=None, limite: int = 6) -> dict:
    """Seções da Home filtradas para o recorte regional, com personalização
    pelos interesses do usuário quando autenticado. Localização SÓ entra
    quando explícita (query) ou salva pelo usuário — nunca inferida."""
    from feed import recomendacao as rec
    from feed import services as feed_services

    regiao = None
    if user is not None and getattr(user, "is_authenticated", False) and not any([pais, estado, cidade]):
        salva = localidades_salvas(user).first()
        if salva:
            pais, estado, cidade = salva.pais or None, salva.estado or None, salva.cidade or None
    if any([pais, estado, cidade]):
        regiao = {"pais": pais or "", "estado": estado or "", "cidade": cidade or ""}

    itens = list(feed_services.itens_publicaveis())
    if pais:
        itens = [i for i in itens if (i.pais or "").lower() == pais.lower()]
    if estado:
        itens = [i for i in itens if (i.estado or "").lower() == estado.lower()]
    if cidade:
        itens = [i for i in itens if (i.cidade or "").lower() == cidade.lower()]
    entradas = feed_services.construir_feed_entries(itens)
    interesses = list(getattr(user, "interesses", []) or []) if user is not None and getattr(user, "is_authenticated", False) else []
    secoes = rec.montar_home(entradas, interesses=interesses, regiao=regiao, limite_secao=limite)
    return {
        "aviso_metodologia": AVISO_METODOLOGIA,
        "localidade": {"pais": pais, "estado": estado, "cidade": cidade},
        "secoes": secoes,
    }
