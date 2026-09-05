"""Serviço de agregação de métricas (run 20260902-1521-painel-metricas-negocio)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from assinatura.models import HistoricoPagamento, Subscription
from b2b.models import CriterioMonitoramento, Organizacao
from catalogo_noticias.models import NewsItem, RegistroExecucaoIngestao
from catalogo_noticias.services import orcamento as orcamento_llm
from comunidade.models import Comentario, Publicacao, Seguidor
from credenciamento.models import SolicitacaoCredenciamento
from landing.models import InscricaoListaEspera
from moderacao.models import AcaoModeracao, Denuncia
from newsletter.models import InscricaoNewsletter

User = get_user_model()


def _serie_contagem(queryset, campo: str, dias: int):
    hoje = timezone.now().date()
    inicio = hoje - timedelta(days=dias - 1)
    dados = (
        queryset.filter(**{f"{campo}__date__gte": inicio})
        .annotate(dia=TruncDate(campo))
        .values("dia")
        .annotate(total=Count("id"))
        .order_by("dia")
    )
    mapa = {r["dia"]: r["total"] for r in dados if r["dia"] is not None}
    return [{"dia": (inicio + timedelta(days=i)).isoformat(), "total": mapa.get(inicio + timedelta(days=i), 0)} for i in range(dias)]


def _serie_soma(queryset, campo_data: str, campo_soma: str, dias: int):
    hoje = timezone.now().date()
    inicio = hoje - timedelta(days=dias - 1)
    dados = (
        queryset.filter(**{f"{campo_data}__date__gte": inicio})
        .annotate(dia=TruncDate(campo_data))
        .values("dia")
        .annotate(total=Sum(campo_soma))
        .order_by("dia")
    )
    mapa = {}
    for r in dados:
        if r["dia"] is None:
            continue
        v = r["total"]
        mapa[r["dia"]] = float(v) if v is not None else 0.0
    serie = []
    for i in range(dias):
        dia = inicio + timedelta(days=i)
        serie.append({"dia": dia.isoformat(), "total": round(mapa.get(dia, 0.0), 2)})
    return serie


def _top_distribuicao(queryset, campo: str, limite: int = 6):
    dados = list(queryset.values(campo).annotate(total=Count("id")).order_by("-total"))
    norm = []
    for r in dados:
        valor = r[campo] or "—"
        if isinstance(valor, str):
            valor = valor.strip() or "—"
        norm.append({"label": valor, "total": r["total"]})
    if len(norm) > limite:
        top = norm[:limite]
        resto = sum(x["total"] for x in norm[limite:])
        if resto:
            top.append({"label": "Outros", "total": resto})
        return top
    return norm


def painel(dias: int = 30) -> dict:
    """Critérios de aceite 1, 3 — tudo via agregação do ORM (Count/Sum), nunca iterando em Python."""
    agora = timezone.now()
    corte = agora - timedelta(days=dias)

    usuarios_cadastrados_total = User.objects.count()
    usuarios_cadastrados_periodo = User.objects.filter(date_joined__gte=corte).count()

    assinaturas_ativas = Subscription.objects.filter(
        status__in=[Subscription.STATUS_ATIVA, Subscription.STATUS_TESTE]
    ).count()

    conversao_free_premium = (
        round(assinaturas_ativas / usuarios_cadastrados_total, 4) if usuarios_cadastrados_total else 0.0
    )

    receita_recorrente = (
        HistoricoPagamento.objects.filter(
            status=HistoricoPagamento.STATUS_APROVADO, criado_em__gte=corte
        ).aggregate(total=Sum("valor"))["total"]
        or Decimal("0")
    )

    assinaturas_ativas_inicio_periodo = Subscription.objects.filter(
        status__in=[Subscription.STATUS_ATIVA, Subscription.STATUS_TESTE], criado_em__lt=corte
    ).count()
    canceladas_ou_expiradas_periodo = Subscription.objects.filter(
        status__in=[
            Subscription.STATUS_CANCELADA,
            Subscription.STATUS_EXPIRADA,
            Subscription.STATUS_ENCERRADA,
        ],
        atualizado_em__gte=corte,
    ).count()
    churn = (
        round(canceladas_ou_expiradas_periodo / assinaturas_ativas_inicio_periodo, 4)
        if assinaturas_ativas_inicio_periodo
        else 0.0
    )

    usuarios_ativos_diarios = User.objects.filter(last_login__gte=agora - timedelta(days=1)).count()
    usuarios_ativos_mensais = User.objects.filter(last_login__gte=agora - timedelta(days=30)).count()

    usuarios_anteriores_ao_periodo = User.objects.filter(date_joined__lt=corte)
    total_usuarios_anteriores = usuarios_anteriores_ao_periodo.count()
    retencao_periodo = (
        round(usuarios_anteriores_ao_periodo.filter(last_login__gte=corte).count() / total_usuarios_anteriores, 4)
        if total_usuarios_anteriores
        else 0.0
    )

    vencimentos_no_periodo = Subscription.objects.filter(vencimento__gte=corte, vencimento__lte=agora)
    total_vencimentos_no_periodo = vencimentos_no_periodo.count()
    taxa_renovacao_periodo = (
        round(
            vencimentos_no_periodo.filter(
                status__in=[Subscription.STATUS_ATIVA, Subscription.STATUS_TESTE]
            ).count()
            / total_vencimentos_no_periodo,
            4,
        )
        if total_vencimentos_no_periodo
        else 0.0
    )

    receita_media_por_assinante = (
        round(receita_recorrente / assinaturas_ativas, 2) if assinaturas_ativas else Decimal("0")
    )

    custo_llm_hoje_usd = orcamento_llm.gasto_llm_hoje_usd()
    teto_llm_diario_usd = orcamento_llm.teto_diario_usd()
    teto_llm_excedido_hoje = orcamento_llm.teto_excedido(custo_llm_hoje_usd)

    try:
        series_cadastros = _serie_contagem(User.objects.all(), "date_joined", dias)
    except Exception:
        series_cadastros = []
    try:
        series_receita = _serie_soma(
            HistoricoPagamento.objects.filter(status=HistoricoPagamento.STATUS_APROVADO),
            "criado_em",
            "valor",
            dias,
        )
    except Exception:
        series_receita = []
    try:
        series_noticias = _serie_contagem(NewsItem.objects.all(), "timestamp_ingestao", dias)
    except Exception:
        series_noticias = []
    try:
        series_assinaturas = _serie_contagem(Subscription.objects.all(), "criado_em", dias)
    except Exception:
        series_assinaturas = []
    try:
        series_ingestao_custo = _serie_soma(RegistroExecucaoIngestao.objects.all(), "executado_em", "custo_estimado_summarization_usd", dias)
    except Exception:
        series_ingestao_custo = []
    try:
        series_lista_espera = _serie_contagem(InscricaoListaEspera.objects.all(), "criado_em", dias)
    except Exception:
        series_lista_espera = []
    try:
        series_comentarios = _serie_contagem(Comentario.objects.all(), "criado_em", dias)
    except Exception:
        series_comentarios = []
    try:
        series_publicacoes = _serie_contagem(Publicacao.objects.all(), "criado_em", dias)
    except Exception:
        series_publicacoes = []

    try:
        distribuicao_papel = _top_distribuicao(User.objects.all(), "papel", limite=5)
    except Exception:
        distribuicao_papel = []
    try:
        distribuicao_assinaturas_status = _top_distribuicao(Subscription.objects.all(), "status", limite=7)
    except Exception:
        distribuicao_assinaturas_status = []
    try:
        distribuicao_noticias_categoria = _top_distribuicao(NewsItem.objects.filter(timestamp_ingestao__gte=corte), "categoria", limite=6)
    except Exception:
        distribuicao_noticias_categoria = []
    try:
        distribuicao_noticias_fonte = _top_distribuicao(NewsItem.objects.filter(timestamp_ingestao__gte=corte), "nome_fonte", limite=6)
    except Exception:
        distribuicao_noticias_fonte = []
    try:
        distribuicao_noticias_status = _top_distribuicao(NewsItem.objects.all(), "status_revisao", limite=4)
    except Exception:
        distribuicao_noticias_status = []
    try:
        distribuicao_publicacoes_status = _top_distribuicao(Publicacao.objects.all(), "status", limite=4)
    except Exception:
        distribuicao_publicacoes_status = []
    try:
        distribuicao_denuncias_status = _top_distribuicao(Denuncia.objects.all(), "status", limite=3)
    except Exception:
        distribuicao_denuncias_status = []
    try:
        distribuicao_acoes_tipo = _top_distribuicao(AcaoModeracao.objects.all(), "tipo", limite=4)
    except Exception:
        distribuicao_acoes_tipo = []
    try:
        distribuicao_credenciamento_status = _top_distribuicao(SolicitacaoCredenciamento.objects.all(), "status", limite=4)
    except Exception:
        distribuicao_credenciamento_status = []
    try:
        distribuicao_newsletter_tipo = _top_distribuicao(InscricaoNewsletter.objects.all(), "tipo", limite=3)
    except Exception:
        distribuicao_newsletter_tipo = []
    try:
        distribuicao_b2b_plano = _top_distribuicao(Organizacao.objects.all(), "plano", limite=3)
    except Exception:
        distribuicao_b2b_plano = []
    try:
        distribuicao_criterio_tipo = _top_distribuicao(CriterioMonitoramento.objects.all(), "tipo", limite=4)
    except Exception:
        distribuicao_criterio_tipo = []

    try:
        comunidade_total = Publicacao.objects.count()
        comunidade_publicadas = Publicacao.objects.filter(status=Publicacao.STATUS_PUBLICADO).count()
        comunidade_comentarios = Comentario.objects.count()
        comunidade_seguidores = Seguidor.objects.count()
    except Exception:
        comunidade_total = comunidade_publicadas = comunidade_comentarios = comunidade_seguidores = 0

    try:
        denuncias_pendentes = Denuncia.objects.filter(status=Denuncia.STATUS_PENDENTE).count()
        denuncias_total = Denuncia.objects.count()
        acoes_total = AcaoModeracao.objects.count()
    except Exception:
        denuncias_pendentes = denuncias_total = acoes_total = 0

    try:
        lista_espera_total = InscricaoListaEspera.objects.count()
    except Exception:
        lista_espera_total = 0

    try:
        newsletter_ativas = InscricaoNewsletter.objects.filter(ativa=True).count()
        newsletter_total = InscricaoNewsletter.objects.count()
    except Exception:
        newsletter_ativas = newsletter_total = 0

    try:
        orgs_ativas = Organizacao.objects.filter(ativo=True).count()
        orgs_total = Organizacao.objects.count()
        criterios_ativos = CriterioMonitoramento.objects.filter(ativo=True).count()
    except Exception:
        orgs_ativas = orgs_total = criterios_ativos = 0

    try:
        noticias_periodo = NewsItem.objects.filter(timestamp_ingestao__gte=corte).count()
        noticias_pendentes = NewsItem.objects.filter(status_revisao=NewsItem.STATUS_PENDENTE).count()
        taxa_aprovacao = round((NewsItem.objects.filter(status_revisao__in=[NewsItem.STATUS_APROVADO, NewsItem.STATUS_NAO_APLICAVEL]).count() / NewsItem.objects.count()), 4) if NewsItem.objects.count() else 0.0
    except Exception:
        noticias_periodo = noticias_pendentes = 0
        taxa_aprovacao = 0.0

    try:
        custo_periodo = RegistroExecucaoIngestao.objects.filter(executado_em__gte=corte).aggregate(t=Sum("custo_estimado_summarization_usd"))["t"] or 0.0
        custo_periodo = round(float(custo_periodo), 4)
    except Exception:
        custo_periodo = 0.0

    funil = {
        "lista_espera": lista_espera_total,
        "cadastrados": usuarios_cadastrados_total,
        "assinantes": assinaturas_ativas,
        "taxa_lista_para_cadastro": round(usuarios_cadastrados_total / lista_espera_total, 4) if lista_espera_total else 0.0,
        "taxa_cadastro_para_premium": conversao_free_premium,
    }

    return {
        "periodo_dias": dias,
        "usuarios_cadastrados_total": usuarios_cadastrados_total,
        "usuarios_cadastrados_periodo": usuarios_cadastrados_periodo,
        "usuarios_ativos_diarios": usuarios_ativos_diarios,
        "usuarios_ativos_mensais": usuarios_ativos_mensais,
        "retencao_periodo": retencao_periodo,
        "assinaturas_ativas": assinaturas_ativas,
        "conversao_free_premium": conversao_free_premium,
        "receita_recorrente_periodo": str(receita_recorrente),
        "receita_media_por_assinante": str(receita_media_por_assinante),
        "churn_periodo": churn,
        "taxa_renovacao_periodo": taxa_renovacao_periodo,
        "organizacoes_b2b_ativas": Organizacao.objects.filter(ativo=True).count(),
        "custo_llm_hoje_usd": custo_llm_hoje_usd,
        "teto_llm_diario_usd": teto_llm_diario_usd,
        "teto_llm_excedido_hoje": teto_llm_excedido_hoje,
        "series": {
            "cadastros": series_cadastros,
            "receita": series_receita,
            "noticias": series_noticias,
            "assinaturas": series_assinaturas,
            "ingestao_custo": series_ingestao_custo,
            "lista_espera": series_lista_espera,
            "comentarios": series_comentarios,
            "publicacoes": series_publicacoes,
        },
        "distribuicoes": {
            "papel": distribuicao_papel,
            "assinaturas_status": distribuicao_assinaturas_status,
            "noticias_categoria": distribuicao_noticias_categoria,
            "noticias_fonte": distribuicao_noticias_fonte,
            "noticias_status": distribuicao_noticias_status,
            "publicacoes_status": distribuicao_publicacoes_status,
            "denuncias_status": distribuicao_denuncias_status,
            "acoes_tipo": distribuicao_acoes_tipo,
            "credenciamento_status": distribuicao_credenciamento_status,
            "newsletter_tipo": distribuicao_newsletter_tipo,
            "b2b_plano": distribuicao_b2b_plano,
            "criterio_tipo": distribuicao_criterio_tipo,
        },
        "kpis": {
            "comunidade": {
                "publicacoes_total": comunidade_total,
                "publicacoes_publicadas": comunidade_publicadas,
                "comentarios_total": comunidade_comentarios,
                "seguidores_total": comunidade_seguidores,
            },
            "moderacao": {
                "denuncias_pendentes": denuncias_pendentes,
                "denuncias_total": denuncias_total,
                "acoes_total": acoes_total,
            },
            "lista_espera": {"total": lista_espera_total},
            "newsletter": {"ativas": newsletter_ativas, "total": newsletter_total},
            "b2b": {"ativas": orgs_ativas, "total": orgs_total, "criterios_ativos": criterios_ativos},
            "ingestao": {
                "noticias_periodo": noticias_periodo,
                "noticias_pendentes": noticias_pendentes,
                "taxa_aprovacao": taxa_aprovacao,
                "custo_periodo": custo_periodo,
            },
        },
        "funil": funil,
    }
