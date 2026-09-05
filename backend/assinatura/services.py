"""
Serviço de domínio de assinatura (implementation-contract.md run
20260902-1426-assinatura-premium) — TODA transição de estado de
`Subscription` passa por aqui, nunca é feita diretamente por uma view/admin
sem registrar auditoria e sincronizar `User.papel` (requisito não-funcional
da spec: "decisões financeiras não podem ser silenciosas").
"""

from __future__ import annotations

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    AssinaturaMudancaEstadoLog,
    ConfiguracaoAssinatura,
    HistoricoPagamento,
    Plan,
    Subscription,
)
from .providers.payment import PaymentGatewayProvider, obter_gateway_pagamento


class AssinaturaJaExisteError(Exception):
    """Usuário já tem uma assinatura ativa/teste/pagamento_pendente — não cria uma segunda concorrente."""


def obter_configuracao() -> ConfiguracaoAssinatura:
    config, _ = ConfiguracaoAssinatura.objects.get_or_create(pk=1)
    return config


def _registrar_mudanca_estado(subscription: Subscription, estado_anterior: str, estado_novo: str, motivo: str) -> None:
    AssinaturaMudancaEstadoLog.objects.create(
        subscription=subscription,
        estado_anterior=estado_anterior or "",
        estado_novo=estado_novo,
        motivo=motivo,
    )


def _sincronizar_papel_usuario(subscription: Subscription) -> None:
    """
    Único ponto do sistema que decide `User.papel` a partir do estado de uma
    assinatura (task-plan.md, "Suposições assumidas": nenhum outro módulo,
    incluindo `gating`, deve escrever em `papel` diretamente). Nunca rebaixa
    um `papel=admin`.
    """
    user = subscription.user
    if user.papel == "admin":
        return

    novo_papel = "premium" if subscription.deveria_ter_acesso_premium else "free"
    if user.papel != novo_papel:
        user.papel = novo_papel
        user.save(update_fields=["papel"])


@transaction.atomic
def _transicionar(subscription: Subscription, novo_status: str, motivo: str, **campos_extra) -> Subscription:
    estado_anterior = subscription.status
    subscription.status = novo_status
    for campo, valor in campos_extra.items():
        setattr(subscription, campo, valor)
    subscription.save()

    _registrar_mudanca_estado(subscription, estado_anterior, novo_status, motivo)
    _sincronizar_papel_usuario(subscription)
    return subscription


def assinar_plano(user, plan: Plan, payment_gateway: PaymentGatewayProvider | None = None) -> Subscription:
    """
    Critérios de aceite 2, 3, 12: cria a `Subscription` em
    `pagamento_pendente`, chama o gateway, e já processa a confirmação/
    recusa imediata quando o gateway responde de forma síncrona (caso do
    `obter_gateway_pagamento()` (default, via
    `ASSINATURA_PAYMENT_GATEWAY_PROVIDER`) — um gateway real com confirmação
    assíncrona via webhook chamaria `processar_confirmacao_pagamento`/
    `processar_pagamento_recusado` a partir de uma view de webhook separada,
    fora do escopo desta execução).
    """
    payment_gateway = payment_gateway or obter_gateway_pagamento()

    # A checagem abaixo (`ja_tem_assinatura_em_andamento`) é só a mensagem de
    # erro amigável no caminho feliz/sem concorrência — a garantia real
    # contra duas assinaturas simultâneas para o mesmo usuário é a
    # UniqueConstraint de banco em Subscription.Meta (achado de revisão de
    # segurança: sem ela, duas requisições quase simultâneas conseguiam
    # passar por esta checagem antes de qualquer uma persistir sua
    # Subscription). `transaction.atomic()` é necessário aqui porque, sem
    # ele, um IntegrityError deixa a conexão numa transação abortada
    # inutilizável até o próximo rollback.
    ja_tem_assinatura_em_andamento = Subscription.objects.filter(
        user=user,
        status__in=[
            Subscription.STATUS_TESTE,
            Subscription.STATUS_ATIVA,
            Subscription.STATUS_PAGAMENTO_PENDENTE,
        ],
    ).exists()
    if ja_tem_assinatura_em_andamento:
        raise AssinaturaJaExisteError("Usuário já possui uma assinatura ativa ou pendente.")

    try:
        with transaction.atomic():
            subscription = Subscription.objects.create(
                user=user,
                plan=plan,
                status=Subscription.STATUS_PAGAMENTO_PENDENTE,
                preco_cobrado=plan.preco,
                duracao_dias_no_momento=plan.duracao_dias,
            )
    except IntegrityError as exc:
        raise AssinaturaJaExisteError("Usuário já possui uma assinatura ativa ou pendente.") from exc

    _registrar_mudanca_estado(
        subscription, "", Subscription.STATUS_PAGAMENTO_PENDENTE, "Assinatura criada, aguardando confirmação de pagamento."
    )

    resultado = payment_gateway.criar_cobranca(subscription, plan.preco)
    subscription.gateway_referencia = resultado.referencia_gateway
    subscription.save(update_fields=["gateway_referencia"])

    HistoricoPagamento.objects.create(
        subscription=subscription,
        valor=plan.preco,
        status=resultado.status,
        referencia_gateway=resultado.referencia_gateway,
    )

    if resultado.status == "aprovado":
        processar_confirmacao_pagamento(subscription)
    elif resultado.status == "recusado":
        processar_pagamento_recusado(subscription)
    # "pendente": permanece em pagamento_pendente, aguardando confirmação
    # posterior (webhook de um gateway real — não implementado nesta
    # execução, ver implementation-contract.md "Não-objetivos").

    subscription.refresh_from_db()
    return subscription


def processar_confirmacao_pagamento(subscription: Subscription) -> Subscription:
    """Critério de aceite 3: ativa a assinatura e libera acesso Premium imediatamente."""
    agora = timezone.now()
    inicio = subscription.inicio or agora
    vencimento = agora + timedelta(days=subscription.duracao_dias_no_momento)
    return _transicionar(
        subscription,
        Subscription.STATUS_ATIVA,
        "Pagamento confirmado pelo gateway.",
        inicio=inicio,
        vencimento=vencimento,
        grace_period_termina_em=None,
    )


def processar_pagamento_recusado(subscription: Subscription) -> Subscription:
    """Critério de aceite 4: inicia o grace period — acesso Premium NÃO é derrubado imediatamente."""
    config = obter_configuracao()
    grace_ate = timezone.now() + timedelta(days=config.grace_period_dias)
    return _transicionar(
        subscription,
        Subscription.STATUS_INADIMPLENTE,
        f"Pagamento recusado pelo gateway — grace period de {config.grace_period_dias} dia(s).",
        grace_period_termina_em=grace_ate,
    )


def cancelar_assinatura(subscription: Subscription, motivo: str = "Cancelado pelo usuário.") -> Subscription:
    """
    Critério de aceite 7: cancelamento self-service, sem barreiras. Acesso
    Premium é preservado até `vencimento` (já pago) — ver
    `Subscription.STATUS_COM_ACESSO_PREMIUM`.
    """
    return _transicionar(
        subscription,
        Subscription.STATUS_CANCELADA,
        motivo,
        renovacao_automatica=False,
    )


def processar_vencimentos_e_grace_periods(payment_gateway: PaymentGatewayProvider | None = None) -> dict:
    """
    Critérios de aceite 5, 6, 8: chamada pela task periódica
    (`tasks.processar_vencimentos`). Idempotente por natureza — só afeta
    assinaturas cujo prazo relevante (`grace_period_termina_em`/`vencimento`)
    já passou; rodar de novo sem que o tempo tenha avançado não muda nada.
    """
    payment_gateway = payment_gateway or obter_gateway_pagamento()
    agora = timezone.now()
    resultado = {"expiradas": 0, "encerradas": 0, "renovadas": 0}

    # Inadimplente com grace period vencido -> expirada (derruba Premium).
    for subscription in Subscription.objects.filter(
        status=Subscription.STATUS_INADIMPLENTE, grace_period_termina_em__lte=agora
    ):
        _transicionar(subscription, Subscription.STATUS_EXPIRADA, "Grace period expirado sem regularização de pagamento.")
        resultado["expiradas"] += 1

    # Cancelada cujo período já pago terminou -> encerrada (finaliza; Premium
    # já não é mais devido a partir daqui — deveria_ter_acesso_premium não
    # inclui "encerrada").
    for subscription in Subscription.objects.filter(
        status=Subscription.STATUS_CANCELADA, vencimento__lte=agora
    ):
        _transicionar(subscription, Subscription.STATUS_ENCERRADA, "Período já pago encerrado após cancelamento.")
        resultado["encerradas"] += 1

    # Ativa cujo vencimento chegou: renova automaticamente (se consentido)
    # ou expira.
    for subscription in Subscription.objects.filter(status=Subscription.STATUS_ATIVA, vencimento__lte=agora):
        if subscription.renovacao_automatica:
            cobranca = payment_gateway.criar_cobranca(subscription, subscription.preco_cobrado)
            HistoricoPagamento.objects.create(
                subscription=subscription,
                valor=subscription.preco_cobrado,
                status=cobranca.status,
                referencia_gateway=cobranca.referencia_gateway,
            )
            if cobranca.status == "aprovado":
                processar_confirmacao_pagamento(subscription)
                resultado["renovadas"] += 1
            else:
                processar_pagamento_recusado(subscription)
        else:
            _transicionar(
                subscription,
                Subscription.STATUS_EXPIRADA,
                "Vencimento atingido sem renovação automática habilitada.",
            )
            resultado["expiradas"] += 1

    return resultado
