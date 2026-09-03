"""Serviço de agregação de métricas (run 20260902-1521-painel-metricas-negocio)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.utils import timezone

from assinatura.models import HistoricoPagamento, Subscription
from b2b.models import Organizacao
from catalogo_noticias.services import orcamento as orcamento_llm

User = get_user_model()


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

    # BRD §21 lista várias métricas de negócio que o painel ainda não
    # cobria — gap real encontrado na análise do BRD. As adicionadas abaixo
    # são todas calculáveis com dados que JÁ existem no sistema (nunca um
    # valor inventado). As que exigiriam dado que não existe hoje (CAC,
    # LTV, margem, custo médio, receita publicitária real por usuário Free
    # — sem integração de anúncios de verdade) ficam de fora deliberadamente,
    # não fabricadas.

    # Usuários ativos diários/mensais — dependem de `User.last_login`, que
    # só passou a ser atualizado de fato após a correção em
    # `identidade/views.py::LoginView`/`GoogleLoginView` (mesmo gap: o fluxo
    # de login por token nunca chamava `django.contrib.auth.login()`, então
    # `last_login` nunca era gravado).
    usuarios_ativos_diarios = User.objects.filter(last_login__gte=agora - timedelta(days=1)).count()
    usuarios_ativos_mensais = User.objects.filter(last_login__gte=agora - timedelta(days=30)).count()

    # Retenção: entre usuários cadastrados ANTES do início do período
    # (tinham chance de "sumir"), qual fração ainda fez login DENTRO do
    # período — definição simples e defensável a partir do dado real
    # disponível, não a única definição possível de "retenção".
    usuarios_anteriores_ao_periodo = User.objects.filter(date_joined__lt=corte)
    total_usuarios_anteriores = usuarios_anteriores_ao_periodo.count()
    retencao_periodo = (
        round(usuarios_anteriores_ao_periodo.filter(last_login__gte=corte).count() / total_usuarios_anteriores, 4)
        if total_usuarios_anteriores
        else 0.0
    )

    # Taxa de renovação: entre assinaturas cujo `vencimento` caiu dentro do
    # período, quantas seguem ativas/teste depois dessa data — se o
    # vencimento já passou e o status não caiu para expirada/encerrada, é
    # porque renovou (ver `assinatura.services.processar_vencimentos_e_grace_periods`,
    # que é o único código que move para `expirada` quando NÃO renova).
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

    # Observabilidade de custo de IA (implementation-contract.md, run
    # 20260903-1211-teto-gasto-diario-llm) — reaproveita
    # `catalogo_noticias.services.orcamento`, as MESMAS funcoes ja usadas
    # por `services/ingestao.py::executar_ingestao` para decidir se pula o
    # SummarizationProvider, para nao duplicar a logica de agregacao/teto.
    custo_llm_hoje_usd = orcamento_llm.gasto_llm_hoje_usd()
    teto_llm_diario_usd = orcamento_llm.teto_diario_usd()
    teto_llm_excedido_hoje = orcamento_llm.teto_excedido(custo_llm_hoje_usd)

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
    }
