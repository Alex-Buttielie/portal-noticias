"""
Serviço de domínio de assinatura (implementation-contract.md run
20260902-1426-assinatura-premium) — TODA transição de estado de
`Subscription` passa por aqui, nunca é feita diretamente por uma view/admin
sem registrar auditoria e sincronizar `User.papel` (requisito não-funcional
da spec: "decisões financeiras não podem ser silenciosas").
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    AssinaturaMudancaEstadoLog,
    ConfiguracaoAssinatura,
    HistoricoPagamento,
    Plan,
    Subscription,
)
from .providers.payment import (
    CobrancaGateway,
    PaymentGatewayProvider,
    ProvedorPagamentoError,
    obter_gateway_pagamento,
)

logger = logging.getLogger(__name__)


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


def _transicionar(subscription: Subscription, novo_status: str, motivo: str, **campos_extra) -> Subscription:
    estado_anterior = subscription.status
    subscription.status = novo_status
    for campo, valor in campos_extra.items():
        setattr(subscription, campo, valor)
    subscription.save()

    _registrar_mudanca_estado(subscription, estado_anterior, novo_status, motivo)
    _sincronizar_papel_usuario(subscription)
    return subscription


# ======================================================================
# Conferência do que o provedor diz que cobrou
# ======================================================================
_CENTAVOS = Decimal("0.01")


def _divergencia_de_valor(
    subscription: Subscription, gateway: PaymentGatewayProvider, cobranca: CobrancaGateway
) -> str | None:
    """
    Confere o que o PROVEDOR afirma ter cobrado contra o que a assinatura
    está congelada em pagar. Devolve uma descrição da divergência, ou
    `None` quando bate (ou quando a conferência é inaplicável).

    Três decisões, e o motivo de cada uma:

    - **Provedor que não relata valor** (`relata_valor=False`, caso do
      placeholder manual): a conferência é inaplicável, não "aprovada".
      A ausência é registrada em log INFO pelo chamador — nunca um
      silêncio.
    - **Provedor que SE DECLARA relator e devolve `None`**: resposta
      suspeita. `None` não pode ser lido como "bateu", porque aceitar
      aqui significaria aceitar como pago um valor que ninguém viu.
    - **Divergência real** (valor diferente, moeda diferente): devolve a
      descrição e o chamador NÃO transiciona. Registrada em log ERROR e
      deixada para a reconciliação/revisão humana.

    A comparação é feita em centavos via `quantize`, para que `29.9`
    (como o MP devolve, float) e `29.90` (como o `DecimalField`
    devolve) sejam o mesmo dinheiro, e não uma divergência fantasma nem
    um atrito por arredondamento.
    """
    if not getattr(gateway, "relata_valor", False):
        return None
    if cobranca.valor is None:
        return "provedor não informou o valor cobrado"
    moeda_esperada = str(getattr(gateway, "moeda", "") or "").strip().upper()
    moeda_informada = str(cobranca.moeda or "").strip().upper()
    if not moeda_informada:
        return "provedor não informou a moeda"
    if moeda_esperada and moeda_informada != moeda_esperada:
        return f"moeda divergente (esperada {moeda_esperada}, informada {moeda_informada})"
    try:
        informado = Decimal(cobranca.valor).quantize(_CENTAVOS)
        esperado = Decimal(subscription.preco_cobrado).quantize(_CENTAVOS)
    except (InvalidOperation, TypeError, ValueError):
        return "valor do provedor ilegível"
    if informado != esperado:
        return f"valor divergente (esperado {esperado}, informado {informado})"
    return None


def _cobrancas_em_aberto(subscription: Subscription, referencia: str) -> bool:
    """
    Existe uma cobrança AINDA não resolvida para esta referência do
    provedor?

    É a chave de idempotência de TODO o caminho de dinheiro. Um
    "aprovado" do provedor só concede período quando há uma cobrança em
    aberto que ele está fechando; se não há, o evento é uma repetição
    (o MP reenvia a mesma notificação até receber 200, e o documenta
    claramente: 8 tentativas ao longo de ~4 dias) e estender
    `vencimento` de novo daria período Premium grátis para sempre, sem
    segunda cobrança que justificasse.

    A cobrança pendente é a âncora, não o status da assinatura: assim a
    garantia continua valendo mesmo se o status local já tiver sido
    mexido por reconciliação, admin ou task.
    """
    return HistoricoPagamento.objects.filter(
        subscription=subscription,
        referencia_gateway=str(referencia),
        status=HistoricoPagamento.STATUS_PENDENTE,
    ).exists()


@transaction.atomic
def _resolver_cobranca_aprovada(subscription: Subscription, referencia: str, motivo: str) -> Subscription:
    """Fecha a cobrança em aberto como paga e estende o período."""

    def _marcar(status: str) -> None:
        HistoricoPagamento.objects.filter(
            subscription=subscription,
            referencia_gateway=str(referencia),
            status=HistoricoPagamento.STATUS_PENDENTE,
        ).update(status=status)

    _marcar(HistoricoPagamento.STATUS_APROVADO)
    return processar_confirmacao_pagamento(subscription, motivo=motivo)


@transaction.atomic
def _resolver_cobranca_recusada(subscription: Subscription, referencia: str) -> Subscription:
    """Fecha a cobrança em aberto como recusada e entra em grace period."""

    HistoricoPagamento.objects.filter(
        subscription=subscription,
        referencia_gateway=str(referencia),
        status=HistoricoPagamento.STATUS_PENDENTE,
    ).update(status=HistoricoPagamento.STATUS_RECUSADO)
    return processar_pagamento_recusado(subscription)


#: Estados terminais: nenhuma notificação do provedor pode reabri-los.
#: `expirada`/`encerrada` são o fim da linha por definição (BRD §9).
ESTADOS_TERMINAIS = frozenset(
    {Subscription.STATUS_EXPIRADA, Subscription.STATUS_ENCERRADA}
)


def aplicar_resultado_provedor(
    subscription: Subscription,
    gateway: PaymentGatewayProvider,
    cobranca: CobrancaGateway,
) -> str:
    """
    Ponto ÚNICO onde o veredito do provedor vira estado local. Tanto o
    webhook quanto a reconciliação passam por aqui — um caminho só para
    que as garantias (conferência de valor, idempotência, estados
    terminais) valham nos dois, em vez de depender de duas
    implementações que divergem com o tempo.

    Devolve a ação tomada, para log e para o contador da task:

    ``confirmada`` / ``renovada`` / ``recusada`` / ``renovacao_recusada``
    / ``cancelada_por_divergencia_de_estado`` / ``divergencia_de_valor``
    / ``aguardando`` / ``repeticao`` / ``estado_nao_aplicavel``
    """
    referencia = str(cobranca.referencia_gateway or subscription.gateway_referencia or "")

    if subscription.status in ESTADOS_TERMINAIS:
        return "estado_nao_aplicavel"

    divergencia = _divergencia_de_valor(subscription, gateway, cobranca)
    if divergencia:
        # Registrado e NÃO aceito. Log em ERROR com o que foi esperado e
        # o que veio, sem token, sem assinatura e sem o payload do
        # provedor. A assinatura fica como está: estado intocado até
        # revisão humana (ou até a reconciliação ver um valor coerente).
        logger.error(
            "Divergência de valor na assinatura %s (referência %s): %s. "
            "Estado NÃO alterado — revisão humana necessária.",
            subscription.pk,
            referencia,
            divergencia,
        )
        return "divergencia_de_valor"

    if cobranca.status == "aprovado":
        em_aberto = _cobrancas_em_aberto(subscription, referencia)
        if not em_aberto:
            # Já cobrada (ou referência desconhecida): não estende nada.
            return "repeticao"
        if subscription.status == Subscription.STATUS_PAGAMENTO_PENDENTE:
            _resolver_cobranca_aprovada(
                subscription, referencia, "Pagamento confirmado pelo gateway."
            )
            return "confirmada"
        if subscription.status == Subscription.STATUS_ATIVA:
            # Renovação: a assinatura já está ativa e há uma cobrança em
            # aberto (a do ciclo novo) para este ciclo.
            _resolver_cobranca_aprovada(
                subscription, referencia, "Renovação confirmada pelo gateway."
            )
            return "renovada"
        return "estado_nao_aplicavel"

    if cobranca.status == "recusado":
        em_aberto = _cobrancas_em_aberto(subscription, referencia)
        if subscription.status == Subscription.STATUS_PAGAMENTO_PENDENTE:
            _resolver_cobranca_recusada(subscription, referencia)
            return "recusada"
        if subscription.status == Subscription.STATUS_ATIVA and em_aberto:
            # Renegação recusada: grace period, o acesso Premium JÁ pago
            # não cai na hora (mesma regra do primeiro pagamento).
            _resolver_cobranca_recusada(subscription, referencia)
            return "renovacao_recusada"
        if subscription.status == Subscription.STATUS_ATIVA and not em_aberto:
            # O acordo foi cancelado/pausado lá no provedor e não há
            # cobrança em aberto: o cancelamento partiu do cliente (ou de
            # dentro do painel do MP). Espelha localmente, sem derrubar o
            # período já pago.
            cancelar_assinatura(
                subscription,
                motivo="Cancelamento detectado no provedor durante a conciliação.",
                ja_cancelado_no_provedor=True,
            )
            return "cancelada_por_divergencia_de_estado"
        return "estado_nao_aplicavel"

    # "pendente": o provedor ainda não decidiu. Nada a fazer — e nada que
    # possa custar dinheiro ao cliente.
    return "aguardando"


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
    # checkout_url é atributo em memória (não vai ao banco): a view devolve
    # ao frontend para redirecionar ao checkout do gateway quando houver.
    subscription.checkout_url = resultado.url_checkout

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


def processar_confirmacao_pagamento(
    subscription: Subscription, motivo: str = "Pagamento confirmado pelo gateway."
) -> Subscription:
    """
    Critério de aceite 3: ativa a assinatura e libera acesso Premium
    imediatamente.

    O período é contado a partir de `max(agora, vencimento)`, e não de
    `agora`:

    - primeira cobrança (`vencimento` é None) → `agora + duracao`;
    - renovação disparada por vencimento (o caso da task periódica) →
      `vencimento` já está no passado, então `max` devolve `agora` e o
      cliente ganha exatamente o período que pagou, sem dias de bônus e
      sem dias cortados;
    - renovação antecipada (o webhook chegou antes do vencimento) →
      `max` devolve o `vencimento` atual e o período é EMPILHADO em
      vez de sobreposto — o cliente não perde os dias que já tinha pago.

    `inicio` nunca é reiniciado: é a data original da assinatura, e é o
    que distingue "já esteve ativa" (preserva Premium no grace period)
    de "nunca foi ativada" (`deveria_ter_acesso_premium`, models.py).
    """
    agora = timezone.now()
    inicio = subscription.inicio or agora
    base = subscription.vencimento if subscription.vencimento and subscription.vencimento > agora else agora
    vencimento = base + timedelta(days=subscription.duracao_dias_no_momento)
    return _transicionar(
        subscription,
        Subscription.STATUS_ATIVA,
        motivo,
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


def cancelar_assinatura(
    subscription: Subscription,
    motivo: str = "Cancelado pelo usuário.",
    payment_gateway: PaymentGatewayProvider | None = None,
    ja_cancelado_no_provedor: bool = False,
) -> Subscription:
    """
    Critério de aceite 7: cancelamento self-service, sem barreiras. Acesso
    Premium é preservado até `vencimento` (já pago) — ver
    `Subscription.STATUS_COM_ACESSO_PREMIUM`.

    Cancelar SÓ o estado local deixava o débito recorrente vivo no
    provedor: o cliente cancelava aqui e continuava sendo cobrado lá
    (defeito real — `PaymentGatewayProvider.cancelar` existia e não era
    chamado por ninguém). Por isso o cancelamento é tentado no provedor
    ANTES da transição, quando há referência e gateway.

    Se o provedor recusar o cancelamento, a transição local acontece
    MESMO assim: o cliente pediu para sair, e prendê-lo numa assinatura
    que ele cancelou porque o provedor estava fora do ar é pior do que
    uma cobrança indevida isolada. A falha é registrada em ERROR com o
    id da assinatura e a `reconciliar_com_provedor` volta a tentar — é
    ela que fecha o ciclo, porque o próximo `consultar_cobranca` mostra
    o acordo ainda ativo e o cancelamento é reenviado.
    """
    if payment_gateway is not None and subscription.gateway_referencia and not ja_cancelado_no_provedor:
        try:
            payment_gateway.cancelar(subscription.gateway_referencia)
        except ProvedorPagamentoError:
            logger.exception(
                "Falha ao cancelar a assinatura %s no provedor (referência %s): "
                "o cancelamento local prossegue e a conciliação tentará de novo. "
                "Enquanto isso o provedor ainda pode debitar.",
                subscription.pk,
                subscription.gateway_referencia,
            )
    return _transicionar(
        subscription,
        Subscription.STATUS_CANCELADA,
        motivo,
        renovacao_automatica=False,
    )


def _cobrancas_do_ciclo_em_aberto(subscription: Subscription) -> bool:
    """
    Há uma cobrança em aberto que pertence ao ciclo JATÁ PAGO desta
    assinatura?

    O corte é o início do ciclo pago (`vencimento - duracao`), e não
    "qualquer pendente": o que interessa é "esta task já tentou cobrar
    este período?". Uma pendente de um ciclo antigo (esquecida por
    qualquer motivo) não pode travar a renovação para sempre — receita
    deixada de cobrar é dinheiro perdido, e o pior caso de um corte
    errado aqui é cobrar um período que o cliente não pediu, o que
    `aplicar_resultado_provedor` + a conferência de valor impedem de
    virar ativação.

    A assinatura ATIVA só chega aqui com `vencimento <= agora` (é o
    filtro do chamador), então a cobrança em aberto — criada agora — é
    sempre posterior ao corte.
    """
    pendentes = HistoricoPagamento.objects.filter(
        subscription=subscription, status=HistoricoPagamento.STATUS_PENDENTE
    )
    if not subscription.vencimento:
        return pendentes.exists()
    inicio_ciclo = subscription.vencimento - timedelta(days=subscription.duracao_dias_no_momento)
    return pendentes.filter(criado_em__gte=inicio_ciclo).exists()


def _renovar(subscription: Subscription, payment_gateway: PaymentGatewayProvider) -> str:
    """
    Cobra (ou registra a cobrança de) mais um ciclo. Devolve a ação.

    Três defeitos reais corrigidos aqui, todos invisíveis com o
    placeholder manual — que responde "aprovado" de forma síncrona — e
    todos visíveis assim que o provedor é o Mercado Pago, cuja
    confirmação é assíncrona:

    1. **"pendente" era tratado como recusa.** O `else` final cobria
       qualquer coisa que não fosse "aprovado", e o Mercado Pago
       responde "pendente" ao criar a preapproval. Resultado: TODA
       renovação colocava o assinante em `inadimplente` com grace
       period, sem o cliente ter falhado em nada.
    2. **A referência da renovação nunca era guardada.** Só o
       `HistoricoPagamento` recebia a preapproval nova; o
       `gateway_referencia` da assinatura continuava o antigo. O
       webhook da renovação procurava uma referência que não estava em
       lugar nenhum: o cliente pagava e o sistema nunca confirmava.
    3. **Cada nova execução criava OUTRA preapproval.** Como o status
       deixava de ser "pendente" logo depois, a task voltava a achar a
       assinatura elegível a cada rodada. Sem a guarda de
       `_cobrancas_do_ciclo_em_aberto`, corrigir (1) teria trocado
       "marca inadimplente" por "cobra duas vezes".
    """
    if _cobrancas_do_ciclo_em_aberto(subscription):
        logger.info(
            "Renovação da assinatura %s não executada: já existe cobrança em "
            "aberto para o ciclo atual. Nenhuma nova cobrança foi criada.",
            subscription.pk,
        )
        return "renovacao_ja_em_aberto"

    cobranca = payment_gateway.criar_cobranca(subscription, subscription.preco_cobrado)
    # (2) a referência passa a ser a da cobrança corrente — é por ela
    # que o webhook desta renovação vai encontrar a assinatura.
    subscription.gateway_referencia = cobranca.referencia_gateway
    subscription.save(update_fields=["gateway_referencia"])
    HistoricoPagamento.objects.create(
        subscription=subscription,
        valor=subscription.preco_cobrado,
        status=cobranca.status,
        referencia_gateway=cobranca.referencia_gateway,
    )
    if cobranca.status == "aprovado":
        # Confirmação síncrona (placeholder manual): fecha a cobrança e
        # estende o período agora.
        _resolver_cobranca_aprovada(
            subscription, cobranca.referencia_gateway, "Renovação confirmada pelo gateway."
        )
        return "renovada"
    if cobranca.status == "recusado":
        _resolver_cobranca_recusada(subscription, cobranca.referencia_gateway)
        return "renovacao_recusada"
    # (1) "pendente" é o NORMAL do Mercado Pago: a assinatura continua
    # ativa e o acesso Premium NÃO é cortado — o pagamento é da renovação
    # seguinte e o cliente ainda não falhou em nada.
    logger.info(
        "Renovação da assinatura %s cobrada em %s; aguardando confirmação do "
        "provedor. A assinatura permanece ativa.",
        subscription.pk,
        cobranca.referencia_gateway,
    )
    return "renovacao_aguardando"


def processar_vencimentos_e_grace_periods(payment_gateway: PaymentGatewayProvider | None = None) -> dict:
    """
    Critérios de aceite 5, 6, 8: chamada pela task periódica
    (`tasks.processar_vencimentos`). Idempotente por natureza — só afeta
    assinaturas cujo prazo relevante (`grace_period_termina_em`/`vencimento`)
    já passou; rodar de novo sem que o tempo tenha avançado não muda nada.

    As chaves de idempotência do caminho de dinheiro são duas, e ambas
    são testadas: `_cobrancas_do_ciclo_em_aberto` impede a SEGUNDA
    cobrança do mesmo ciclo, e `_cobrancas_em_aberto` (em
    `aplicar_resultado_provedor`) impede que um webhook repetido conceda
    um SEGUNDO período pelo mesmo pagamento.
    """
    payment_gateway = payment_gateway or obter_gateway_pagamento()
    agora = timezone.now()
    resultado = {
        "expiradas": 0,
        "encerradas": 0,
        "renovadas": 0,
        "renovacoes_aguardando": 0,
        "renovacoes_ja_em_aberto": 0,
        "renovacoes_recusadas": 0,
    }

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
        if not subscription.renovacao_automatica:
            _transicionar(
                subscription,
                Subscription.STATUS_EXPIRADA,
                "Vencimento atingido sem renovação automática habilitada.",
            )
            resultado["expiradas"] += 1
            continue
        acao = _renovar(subscription, payment_gateway)
        if acao == "renovada":
            resultado["renovadas"] += 1
        elif acao == "renovacao_aguardando":
            resultado["renovacoes_aguardando"] += 1
        elif acao == "renovacao_ja_em_aberto":
            resultado["renovacoes_ja_em_aberto"] += 1
        elif acao == "renovacao_recusada":
            resultado["renovacoes_recusadas"] += 1

    return resultado


# ======================================================================
# Conciliação com o provedor
# ======================================================================
#: Estados em que o provedor é a fonte da verdade e vale a pena
#: perguntar a ele o que está acontecendo. `expirada`/`encerrada` são
#: terminais; `teste` nunca chega a ter cobrança no provedor.
ESTADOS_RECONCILIAVEIS = (
    Subscription.STATUS_PAGAMENTO_PENDENTE,
    Subscription.STATUS_ATIVA,
    Subscription.STATUS_CANCELADA,
    Subscription.STATUS_INADIMPLENTE,
)


def reconciliar_com_provedor(payment_gateway: PaymentGatewayProvider | None = None) -> dict:
    """
    Compara o que o provedor diz com o que o banco tem, e corrige a
    divergência. É a rede de segurança do dinheiro, não um extra.

    Por que ela é necessária e não "_nice to have_": a notificação do
    MP é *at-least-once*, não *exactly-once*. O MP reenvia até 8 vezes
    ao longo de ~4 dias, e uma janela de 22 s para responder. Se a
    confirmação se perde (deploy no meio do request, queda de rede,
    500 transitório, reconcile já aplicado), o cliente PAGOU e a
    assinatura ficaria presa em `pagamento_pendente` para sempre, sem
    nenhum caminho de volta — porque, sem webhook, nada mais consultava
    o provedor. Antes desta rotina, `consultar_status` só era chamado
    de dentro da própria view de webhook.

    Idempotente por construção: toda correção passa por
    `aplicar_resultado_provedor`, cujas transições são guardadas pelo
    status e pela cobrança em aberto. Rodar duas vezes seguidas não muda
    nada — o que também a torna segura para reentrada de task Celery.
    """
    payment_gateway = payment_gateway or obter_gateway_pagamento()
    contadores = {
        "consultadas": 0,
        "confirmadas": 0,
        "renovadas": 0,
        "recusadas": 0,
        "canceladas_no_provedor": 0,
        "divergencias_de_valor": 0,
        "aguardando": 0,
        "repeticoes": 0,
        "cancelamento_reenviado": 0,
        "erros": 0,
    }

    pendentes = (
        Subscription.objects.exclude(gateway_referencia="")
        .filter(gateway_referencia__isnull=False, status__in=ESTADOS_RECONCILIAVEIS)
        .order_by("pk")
    )
    for subscription in pendentes:
        contadores["consultadas"] += 1
        try:
            cobranca = payment_gateway.consultar_cobranca(subscription.gateway_referencia)
        except ProvedorPagamentoError:
            # Uma falha de rede com o provedor NÃO pode virar mudança de
            # estado financeiro: conta como erro e segue.
            contadores["erros"] += 1
            logger.exception(
                "Conciliação: falha ao consultar a assinatura %s (referência %s) no provedor.",
                subscription.pk,
                subscription.gateway_referencia,
            )
            continue

        acao = aplicar_resultado_provedor(subscription, payment_gateway, cobranca)
        if acao == "confirmada":
            contadores["confirmadas"] += 1
        elif acao == "renovada":
            contadores["renovadas"] += 1
        elif acao == "recusada":
            contadores["recusadas"] += 1
        elif acao == "cancelada_por_divergencia_de_estado":
            contadores["canceladas_no_provedor"] += 1
        elif acao == "divergencia_de_valor":
            contadores["divergencias_de_valor"] += 1
        elif acao == "aguardando":
            contadores["aguardando"] += 1
        elif acao == "repeticao":
            contadores["repeticoes"] += 1

        # Assinatura já cancelada localmente cujo acordo continua ATIVO
        # lá no provedor: o cancelamento anterior não chegou lá (falha
        # de rede no momento) e o cliente continuaria sendo cobrado.
        # Esta é a volta que fecha o ciclo do cancelamento.
        if subscription.status == Subscription.STATUS_CANCELADA and cobranca.status == "aprovado":
            try:
                payment_gateway.cancelar(subscription.gateway_referencia)
                contadores["cancelamento_reenviado"] += 1
                logger.warning(
                    "Assinatura %s está cancelada localmente mas o provedor "
                    "reporta o acordo como ativo: cancelamento reenviado.",
                    subscription.pk,
                )
            except ProvedorPagamentoError:
                contadores["erros"] += 1
                logger.exception(
                    "Conciliação: falha ao reenviar o cancelamento da assinatura %s (referência %s).",
                    subscription.pk,
                    subscription.gateway_referencia,
                )

    return contadores

