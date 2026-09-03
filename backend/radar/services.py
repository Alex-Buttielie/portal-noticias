"""Serviço de domínio do radar (run 20260902-1513-radar-tendencias-localizacao)."""

from __future__ import annotations

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


def _itens_publicaveis_no_recorte(pais=None, estado=None, cidade=None, janela_dias=7):
    corte = timezone.now() - timedelta(days=janela_dias)
    qs = NewsItem.objects.filter(
        status_revisao__in=[NewsItem.STATUS_NAO_APLICAVEL, NewsItem.STATUS_APROVADO],
        timestamp_ingestao__gte=corte,
    )
    if pais:
        qs = qs.filter(pais__iexact=pais)
    if estado:
        qs = qs.filter(estado__iexact=estado)
    if cidade:
        qs = qs.filter(cidade__iexact=cidade)
    return qs


def tendencias(pais=None, estado=None, cidade=None, janela_dias=7) -> dict:
    """Critérios de aceite 1, 2, 4 — funciona sem nenhum filtro (recorte nacional/global)."""
    qs = _itens_publicaveis_no_recorte(pais, estado, cidade, janela_dias)
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
    assuntos_em_alta = []
    for entrada in agregado:
        representante = (
            qs.filter(categoria=entrada["categoria"])
            .order_by("-timestamp_ingestao")
            .values("id", "cluster_id")
            .first()
        )
        assuntos_em_alta.append(
            {
                **entrada,
                "cluster_id": representante["cluster_id"] if representante else None,
                "item_id": representante["id"] if representante else None,
            }
        )

    return {
        "aviso_metodologia": AVISO_METODOLOGIA,
        "localidade": {"pais": pais, "estado": estado, "cidade": cidade},
        "assuntos_em_alta": assuntos_em_alta,
    }


def evolucao_interesse(categoria=None, pais=None, estado=None, cidade=None, dias=14) -> dict:
    """Critério de aceite 3 — gating checado na view (services não decide plano)."""
    qs = _itens_publicaveis_no_recorte(pais, estado, cidade, janela_dias=dias)
    if categoria:
        qs = qs.filter(categoria__iexact=categoria)

    serie = (
        qs.annotate(dia=TruncDate("timestamp_ingestao"))
        .values("dia")
        .annotate(numero_noticias=Count("id"))
        .order_by("dia")
    )
    return {"aviso_metodologia": AVISO_METODOLOGIA, "categoria": categoria, "serie": list(serie)}


def salvar_localidade(user, pais="", estado="", cidade="") -> LocalidadeSalva:
    """Critério de aceite 5 — idempotente via get_or_create."""
    obj, _ = LocalidadeSalva.objects.get_or_create(user=user, pais=pais, estado=estado, cidade=cidade)
    return obj


def remover_localidade(user, pais="", estado="", cidade="") -> None:
    LocalidadeSalva.objects.filter(user=user, pais=pais, estado=estado, cidade=cidade).delete()


def localidades_salvas(user):
    return LocalidadeSalva.objects.filter(user=user)
