"""
P1-07 — Mercado Pago sandbox: assinar, webhook, cancelar, renovar,
reconciliar.

ESTE ARQUIVO É A PROVA DE QUE O CAMINHO DE DINHEIRO FUNCIONA. Ele
exercita o `MercadoPagoGatewayProvider` e o endpoint de webhook INTEIROS,
com `requests` mockado — nenhuma chamada de rede real, nenhuma credencial
real. `MERCADO_PAGO_*` chega ao ambiente depois; ver
`test_pendencia_de_credencial_real` no fim, que marca o que só pode ser
validado contra a credencial de verdade.

O que cada teste prova está no nome e no docstring. Os quatro blocos:

1. Autenticação da origem do webhook (a superfície de ataque).
2. Idempotência — o mesmo evento não cobra nem estende duas vezes.
3. Valor/moeda conferidos contra a assinatura.
4. Cancelamento e renovação (inclusive a cobrança dupla e o "pendente"
   tratado como recusa — os dois defeitos de dinheiro achados).
5. Reconciliação, inclusive a recuperação de notificação perdida.

Todos os cenários partem de uma assinatura real no banco e passam pela
view/serviço de produção, não por uma reimplementação do fluxo no teste.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from assinatura import services
from assinatura.models import (
    AssinaturaMudancaEstadoLog,
    HistoricoPagamento,
    Plan,
    Subscription,
)
from assinatura.providers.payment import (
    HEADER_ASSINATURA,
    HEADER_REQUEST_ID,
    CobrancaGateway,
    MercadoPagoGatewayProvider,
    ProvedorPagamentoError,
    ResultadoCobranca,
    assinar_cabecalho_webhook,
    manifesto_webhook,
    verificar_assinatura_webhook,
)

pytestmark = pytest.mark.django_db

User = get_user_model()

URL_WEBHOOK = "/api/assinatura/webhook/mercadopago/"

# Segredo do webhook usado só aqui. O valor real vive exclusivamente no
# ambiente (ASSINATURA_MP_WEBHOOK_SECRET) e nunca em arquivo versionado.
SEGREDO = "segredo-de-webhook-de-teste-p1-07"
TOKEN = "TEST-dummy-token-de-teste-p1-07"

MP_CONFIG = dict(
    ASSINATURA_MP_ACCESS_TOKEN=TOKEN,
    ASSINATURA_MP_SANDBOX=True,
    ASSINATURA_MP_WEBHOOK_SECRET=SEGREDO,
    ASSINATURA_PAYMENT_GATEWAY_PROVIDER="mercadopago",
)


# ---------------------------------------------------------------- dublês
def _usuario(email="p1-07@example.com"):
    return User.objects.create_user(email=email, password="senha123", papel="free")


def _plano(preco="29.90", duracao=30, nome="Premium Mensal"):
    return Plan.objects.create(
        nome=nome, preco=Decimal(preco), duracao_dias=duracao, ativo=True
    )


def _resposta(status_code=200, corpo=None):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = corpo if corpo is not None else {}
    mock.text = str(corpo)
    return mock


def _preapproval(status="authorized", valor=29.90, moeda="BRL", referencia="pre-1"):
    """`GET /preapproval/<id>` como o Mercado Pago de fato devolve."""
    return {
        "id": referencia,
        "status": status,
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": valor,
            "currency_id": moeda,
        },
    }


def _assinatura_pendente(plano=None, referencia="pre-1", preco="29.90", email="p1-07@example.com"):
    """Assinatura recem-criada: 1 pagamento pendente aguardando o webhook."""
    usuario = _usuario(email)
    plano = plano or _plano(preco=preco, duracao=30)
    subscription = Subscription.objects.create(
        user=usuario,
        plan=plano,
        status=Subscription.STATUS_PAGAMENTO_PENDENTE,
        preco_cobrado=Decimal(preco),
        duracao_dias_no_momento=plano.duracao_dias,
        gateway_referencia=referencia,
    )
    HistoricoPagamento.objects.create(
        subscription=subscription,
        valor=Decimal(preco),
        status=HistoricoPagamento.STATUS_PENDENTE,
        referencia_gateway=referencia,
    )
    return subscription


def _assinatura_ativa(plano=None, referencia="pre-1", preco="29.90", vencimento_em_dias=30, email="ativa@example.com"):
    """
    Assinatura ativa E já paga (sem cobrança em aberto).

    `vencimento_em_dias` é relativo a AGORA: `-1` significa "o vencimento
    passou há 1 dia" (o caso que dispara renovação/expiração) e `30`
    significa "30 dias de período ainda pela frente". `inicio` é derivado
    do vencimento, então `inicio` nunca é o futuro — a regra
    `deveria_ter_acesso_premium` depende de `inicio` estar preenchido.
    """
    usuario = _usuario(email)
    plano = plano or _plano(preco=preco, duracao=30)
    vencimento = timezone.now() + timedelta(days=vencimento_em_dias)
    subscription = Subscription.objects.create(
        user=usuario,
        plan=plano,
        status=Subscription.STATUS_ATIVA,
        preco_cobrado=Decimal(preco),
        duracao_dias_no_momento=plano.duracao_dias,
        inicio=vencimento - timedelta(days=plano.duracao_dias),
        vencimento=vencimento,
        gateway_referencia=referencia,
    )
    subscription.user.papel = "premium"
    subscription.user.save(update_fields=["papel"])
    HistoricoPagamento.objects.create(
        subscription=subscription,
        valor=Decimal(preco),
        status=HistoricoPagamento.STATUS_APROVADO,
        referencia_gateway=referencia,
    )
    return subscription


def _cobranca(status="aprovado", valor=Decimal("29.90"), moeda="BRL", referencia="pre-1"):
    return CobrancaGateway(
        referencia_gateway=referencia, status=status, valor=valor, moeda=moeda
    )


class _GatewayDuble:
    """
    Dublê de `PaymentGatewayProvider` que se comporta como o Mercado Pago
    real: confirma de forma ASSÍNCRONA (criar devolve sempre "pendente") e
    RELATA valor e moeda. É essa asynchronia que expõe os defeitos de
    dinheiro que o placeholder manual escondia.
    """

    moeda = "BRL"
    relata_valor = True

    def __init__(self, status_consulta="aprovado", valor=Decimal("29.90"), moeda="BRL"):
        self.status_consulta = status_consulta
        self.valor = valor
        self.moeda = moeda
        self.criadas: list[str] = []
        self.canceladas: list[str] = []
        self.consultadas: list[str] = []
        self.contador = 0

    def criar_cobranca(self, subscription, valor):
        self.contador += 1
        self.criadas.append(str(valor))
        return ResultadoCobranca(
            referencia_gateway=f"pre-ren-{subscription.pk}-{self.contador}",
            status="pendente",
            url_checkout="https://sandbox.mercadopago.com/checkout/x",
        )

    def consultar_status(self, referencia_gateway):
        return self.consultar_cobranca(referencia_gateway).status

    def consultar_cobranca(self, referencia_gateway):
        self.consultadas.append(referencia_gateway)
        return CobrancaGateway(
            referencia_gateway=referencia_gateway,
            status=self.status_consulta,
            valor=self.valor,
            moeda=self.moeda,
        )

    def cancelar(self, referencia_gateway):
        self.canceladas.append(referencia_gateway)
        self.status_consulta = "recusado"


def _mp_get(*, status="authorized", valor=29.90, moeda="BRL", referencia="pre-1"):
    return patch(
        "assinatura.providers.payment.SessaoEgress.get",
        return_value=_resposta(200, _preapproval(status, valor, moeda, referencia)),
    )


def _webhook(referencia, *, request_id="req-1", segredo=SEGREDO, signed=True, **extra):
    """POST no webhook, com assinatura válida por padrão."""
    client = APIClient()
    cabecalhos = dict(extra)
    if signed:
        cabecalhos[HEADER_ASSINATURA] = assinar_cabecalho_webhook(referencia, segredo, request_id)
        cabecalhos[HEADER_REQUEST_ID] = request_id
    resposta = client.post(
        f"{URL_WEBHOOK}?topic=preapproval&id={referencia}",
        **cabecalhos,
    )
    return resposta


# ======================================================================
# 1. AUTENTICAÇÃO DA ORIGEM DO WEBHOOK
# ======================================================================
# O endpoint é público (o MP não tem token de usuário). Sem conferir a
# assinatura `x-signature`, qualquer um que descubrisse a URL escreve
# estado financeiro — e o `id` de preapproval do MP é sequencial, então
# "descobrir" é quase free. Estes testes fixam a garantia.


@override_settings(**MP_CONFIG)
def test_webhook_sem_assinatura_nao_move_dinheiro_e_nao_chega_ao_provedor():
    """Sem `x-signature`: nada muda e o provedor nem é consultado.

    Prova que a recusa acontece ANTES de qualquer efeito — sem escrita no
    banco e sem chamada de saída (um atacante não ganha nem
    chamadas de saída com a nossa credencial).
    """
    subscription = _assinatura_pendente(referencia="pre-alvo")

    with _mp_get() as get:
        resposta = _webhook("pre-alvo", signed=False)

    assert resposta.status_code == 200
    subscription.refresh_from_db()
    assert subscription.status == Subscription.STATUS_PAGAMENTO_PENDENTE
    assert subscription.inicio is None
    assert get.call_count == 0


@override_settings(**MP_CONFIG)
def test_webhook_com_assinatura_incorreta_nao_move_dinheiro():
    """`v1` que não é o HMAC do segredo: recusado."""
    subscription = _assinatura_pendente(referencia="pre-alvo")

    with _mp_get() as get:
        resposta = _webhook("pre-alvo", request_id="req-1", segredo="outro-segredo-de-teste")

    assert resposta.status_code == 200
    subscription.refresh_from_db()
    assert subscription.status == Subscription.STATUS_PAGAMENTO_PENDENTE
    assert get.call_count == 0


@override_settings(**MP_CONFIG)
def test_webhook_assinatura_de_outra_referencia_nao_serve():
    """
    A assinatura cobre o `id`. Uma requisição NÃO pode reusar a
    assinatura de um evento legítimo para mover o estado de outro —
    seria a porta de fundo de um replay reaproveitado.
    """
    subscription = _assinatura_pendente(referencia="pre-alvo")

    with _mp_get() as get:
        # assinatura válida para pre-outro, requisição para pre-alvo
        resposta = _webhook("pre-alvo", request_id="req-1", signed=False)
        cabecalho = assinar_cabecalho_webhook("pre-outro", SEGREDO, "req-1")
        resposta = APIClient().post(
            f"{URL_WEBHOOK}?topic=preapproval&id=pre-alvo",
            **{HEADER_ASSINATURA: cabecalho, HEADER_REQUEST_ID: "req-1"},
        )

    assert resposta.status_code == 200
    subscription.refresh_from_db()
    assert subscription.status == Subscription.STATUS_PAGAMENTO_PENDENTE
    assert get.call_count == 0


@override_settings(**MP_CONFIG)
def test_webhook_replay_fora_da_janela_e_recusado():
    """
    Assinatura verdadeira, mas com `ts` antigo: é um replay (uma
    requisição gravada em log/proxy). A janela de tempo recusa.
    """
    subscription = _assinatura_pendente(referencia="pre-alvo")
    velho = int(timezone.now().timestamp()) - 4000
    cabecalho = assinar_cabecalho_webhook("pre-alvo", SEGREDO, "req-1", ts=str(velho))

    with _mp_get() as get:
        resposta = APIClient().post(
            f"{URL_WEBHOOK}?topic=preapproval&id=pre-alvo",
            **{HEADER_ASSINATURA: cabecalho, HEADER_REQUEST_ID: "req-1"},
        )

    assert resposta.status_code == 200
    subscription.refresh_from_db()
    assert subscription.status == Subscription.STATUS_PAGAMENTO_PENDENTE
    assert get.call_count == 0


@override_settings(
    ASSINATURA_MP_ACCESS_TOKEN=TOKEN,
    ASSINATURA_MP_WEBHOOK_SECRET="",
    ASSINATURA_PAYMENT_GATEWAY_PROVIDER="mercadopago",
)
def test_webhook_sem_secredo_configurado_recusa_tudo_e_loga_error(caplog):
    """
    Segredo ausente = fail-closed. E é LÓDICO: sem isso, um deploy que
    esqueceu o segredo ou aceitaria webhook de qualquer um, ou (pior)
    deixaria o cliente pagar sem nada ser confirmado. O teste também
    fixa que o segredo NÃO aparece na mensagem de log.
    """
    subscription = _assinatura_pendente(referencia="pre-alvo")

    with caplog.at_level(logging.ERROR, logger="assinatura.providers.payment"):
        with _mp_get() as get:
            resposta = _webhook("pre-alvo")

    assert resposta.status_code == 200
    subscription.refresh_from_db()
    assert subscription.status == Subscription.STATUS_PAGAMENTO_PENDENTE
    assert get.call_count == 0
    assert "ASSINATURA_MP_WEBHOOK_SECRET" in caplog.text
    assert SEGREDO not in caplog.text


@override_settings(**MP_CONFIG)
def test_verificacao_de_assinatura_aceita_requisicao_genuina():
    """O caminho feliz da verificação, isolado da view."""
    cabecalho = assinar_cabecalho_webhook("pre-1", SEGREDO, "req-abc")
    agora = float(int(timezone.now().timestamp()))

    resultado = verificar_assinatura_webhook(
        referencia="pre-1",
        cabecalho_assinatura=cabecalho,
        request_id="req-abc",
        segredo=SEGREDO,
        agora=agora,
    )

    assert resultado.ok is True
    assert resultado.motivo == ""


@override_settings(**MP_CONFIG)
def test_manifesto_omite_componente_ausente():
    """
    O MP documenta que componente vazio é OMITIDO do manifesto (sem
    `x-request-id`: `id:X;ts:Y;`). Confiar em `request-id` sempre
    presente rejeitaria toda notificação real que não o trouxesse.
    """
    assert manifesto_webhook("pre-1", "req-abc", "1704908011") == "id:pre-1;request-id:req-abc;ts:1704908011;"
    assert manifesto_webhook("pre-1", "", "1704908011") == "id:pre-1;ts:1704908011;"
    cabecalho = assinar_cabecalho_webhook("pre-1", SEGREDO, "", ts="1704908011")

    assert verificar_assinatura_webhook(
        referencia="pre-1",
        cabecalho_assinatura=cabecalho,
        request_id="",
        segredo=SEGREDO,
        agora=1704908011,
    ).ok


@override_settings(**MP_CONFIG)
def test_assinatura_usa_compare_digest_e_nao_igualdade():
    """
    A comparação é em tempo constante. `==` em string vaza o valor byte a
    byte pelo tempo de resposta; `hmac.compare_digest` não.
    """
    import hmac as _hmac

    real = _hmac.compare_digest
    chamadas = []

    def _espiao(a, b, *args, **kwargs):
        chamadas.append((a, b))
        return real(a, b, *args, **kwargs)

    cabecalho = assinar_cabecalho_webhook("pre-1", SEGREDO, "req-abc")
    agora = float(int(timezone.now().timestamp()))
    with patch("assinatura.providers.payment.hmac.compare_digest", _espiao):
        verificar_assinatura_webhook(
            referencia="pre-1",
            cabecalho_assinatura=cabecalho,
            request_id="req-abc",
            segredo=SEGREDO,
            agora=agora,
        )

    assert chamadas, "a verificação de assinatura não usou hmac.compare_digest"


# ======================================================================
# 2. IDEMPOTÊNCIA — o mesmo evento não pode cobrar/estender duas vezes
# ======================================================================


@override_settings(**MP_CONFIG)
def test_webhook_repetido_nao_cobra_nem_duplica_estado(caplog):
    """
    O MP é at-least-once: reenvia a MESMA notificação até receber 200
    (oito vezes, em ~4 dias). Repetir o webhook não pode:
      - criar uma segunda cobrança,
      - criar um segundo registro em `HistoricoPagamento`,
      - estender `vencimento` de novo (período Premium grátis para sempre).

    A segunda chamada é a prova: se a chave de idempotência sumisse, ela
    passaria a estender o período mais um ciclo sem nenhuma cobrança que
    justificasse.
    """
    subscription = _assinatura_pendente(referencia="pre-1")
    vencimento_apos_primeiro = None
    paginas = 0
    transicoes = 0

    with caplog.at_level(logging.INFO, logger="assinatura.views"):
        for _ in range(3):
            with _mp_get():
                resposta = _webhook("pre-1")
            assert resposta.status_code == 200
            subscription.refresh_from_db()
            if vencimento_apos_primeiro is None:
                vencimento_apos_primeiro = subscription.vencimento
            paginas = HistoricoPagamento.objects.filter(subscription=subscription).count()
            transicoes = AssinaturaMudancaEstadoLog.objects.filter(subscription=subscription).count()

    assert subscription.status == Subscription.STATUS_ATIVA
    assert subscription.vencimento == vencimento_apos_primeiro, "webhook repetido estendeu o período"
    assert paginas == 1, "webhook repetido criou cobrança duplicada"
    # A assinatura foi criada direto no banco (sem log de transição), então
    # a ÚNICA transição que pode existir é pendente->ativa. Uma segunda
    # significaria que o evento repetido reabriu/reextendeu algo.
    assert transicoes == 1, f"webhook repetido criou transições extras: {transicoes}"
    # A prova legível: só a primeira passagem confirmou; as duas seguintes
    # foram reconhecidas como repetição.
    assert caplog.text.count("-> confirmada") == 1
    assert caplog.text.count("-> repeticao") == 2


@override_settings(**MP_CONFIG)
def test_webhook_recusado_repetido_nao_reabre_o_grace_period():
    """Recusa repetida não recomeça o grace period (que se auto-renovaria
    em cada reenvio do MP, segurando a assinatura em `inadimplente` para
    sempre)."""
    subscription = _assinatura_pendente(referencia="pre-1")

    with _mp_get(status="cancelled"):
        _webhook("pre-1")
    subscription.refresh_from_db()
    primeira = subscription.grace_period_termina_em
    assert subscription.status == Subscription.STATUS_INADIMPLENTE

    with _mp_get(status="cancelled"):
        _webhook("pre-1")
    subscription.refresh_from_db()

    assert subscription.grace_period_termina_em == primeira
    assert subscription.status == Subscription.STATUS_INADIMPLENTE


@override_settings(**MP_CONFIG)
def test_assinar_duas_vezes_nao_cria_segunda_cobrança():
    """
    Duplo clique / reenvio de rede em `/assinar/`: a UniqueConstraint do
    banco impede a segunda assinatura, e portanto a segunda cobrança.
    A garantia é no banco, não na checagem da aplicação.
    """
    usuario = _usuario("duplo@example.com")
    plano = _plano()
    gateway = _GatewayDuble()

    with patch.object(
        MercadoPagoGatewayProvider,
        "criar_cobranca",
        side_effect=lambda sub, valor: services.ResultadoCobranca("pre-x", "pendente", "u"),
    ):
        primeiro = services.assinar_plano(usuario, plano, gateway)
        with pytest.raises(services.AssinaturaJaExisteError):
            services.assinar_plano(usuario, plano, gateway)

    assert Subscription.objects.filter(user=usuario).count() == 1
    assert HistoricoPagamento.objects.filter(subscription=primeiro).count() == 1


# ======================================================================
# 3. VALOR E MOEDA CONFERIDOS CONTRA A ASSINATURA
# ======================================================================


@override_settings(**MP_CONFIG)
def test_webhook_com_valor_divergente_nao_ativa_e_registra(caplog):
    """
    O provedor afirma ter cobrado 9,90 e a assinatura está congelada em
    29,90. A divergência é registrada (ERROR, com o que era esperado e o
    que veio) e o estado NÃO é aceito em silêncio.
    """
    subscription = _assinatura_pendente(referencia="pre-1", preco="29.90")

    with caplog.at_level(logging.ERROR, logger="assinatura.services"):
        with _mp_get(valor=9.90):
            _webhook("pre-1")

    subscription.refresh_from_db()
    assert subscription.status == Subscription.STATUS_PAGAMENTO_PENDENTE
    assert "Divergência de valor" in caplog.text
    assert "29.90" in caplog.text
    assert "9.90" in caplog.text


@override_settings(**MP_CONFIG)
def test_webhook_com_moeda_divergente_nao_ativa_e_registra(caplog):
    """Moeda diferente (ex.: uma preapproval em USD) não é o que a
    assinatura congelou — não pode ser aceita como pagamento em BRL."""
    subscription = _assinatura_pendente(referencia="pre-1")

    with caplog.at_level(logging.ERROR, logger="assinatura.services"):
        with _mp_get(moeda="USD"):
            _webhook("pre-1")

    subscription.refresh_from_db()
    assert subscription.status == Subscription.STATUS_PAGAMENTO_PENDENTE
    assert "moeda divergente" in caplog.text


@override_settings(**MP_CONFIG)
def test_webhook_sem_valor_nao_ativa(caplog):
    """
    Provedor que SE DECLARA relator de valor e devolve `None` é resposta
    suspeita: `None` não pode ser lido como "bateu". Aceitar aqui seria
    dar Premium a partir de um pagamento que ninguém viu.
    """
    subscription = _assinatura_pendente(referencia="pre-1")
    sem_valor = {"id": "pre-1", "status": "authorized", "auto_recurring": {"frequency": 1}}

    with caplog.at_level(logging.ERROR, logger="assinatura.services"):
        with patch(
            "assinatura.providers.payment.SessaoEgress.get",
            return_value=_resposta(200, sem_valor),
        ):
            _webhook("pre-1")

    subscription.refresh_from_db()
    assert subscription.status == Subscription.STATUS_PAGAMENTO_PENDENTE
    assert "não informou o valor" in caplog.text


@override_settings(**MP_CONFIG)
def test_valor_29_9_e_29_90_sao_o_mesmo_dinheiro():
    """
    O MP devolve `29.9` (float do JSON); o `DecimalField` devolve
    `29.90`. Comparar sem quantizar daria uma divergência fantasma que
    derrubaria toda confirmação real.
    """
    subscription = _assinatura_pendente(referencia="pre-1", preco="29.90")

    with _mp_get(valor=29.9):
        _webhook("pre-1")

    subscription.refresh_from_db()
    assert subscription.status == Subscription.STATUS_ATIVA


@override_settings(**MP_CONFIG)
def test_preco_vem_da_central_e_nao_do_codigo():
    """
    O valor enviado ao Mercado Pago e o do `Plan` configurado, nunca um
    literal no codigo, e preco/periodo ficam CONGELADOS na assinatura
    (mudar o plano depois nao retroage).

    Dois planos diferentes produzem duas cobrancas diferentes. Se o preco
    estivesse hardcoded no provider, os dois valores enviados seriam
    iguais -- que e exatamente o que este teste mede.
    """
    barato = _plano(preco="9.90", duracao=30, nome="Mensal barato")
    caro = _plano(preco="129.00", duracao=365, nome="Anual caro")

    with patch(
        "assinatura.providers.payment.SessaoEgress.post",
        return_value=_resposta(201, {"id": "p1", "sandbox_init_point": "u"}),
    ) as post:
        a = services.assinar_plano(_usuario("a@example.com"), barato, MercadoPagoGatewayProvider())
        b = services.assinar_plano(_usuario("b@example.com"), caro, MercadoPagoGatewayProvider())
        enviados = [
            c.kwargs["json"]["auto_recurring"]["transaction_amount"] for c in post.call_args_list
        ]

    assert enviados == [9.90, 129.00], "o valor enviado ao MP nao veio do Plan"
    assert a.preco_cobrado == Decimal("9.90")
    assert b.preco_cobrado == Decimal("129.00")
    assert a.duracao_dias_no_momento == 30
    assert b.duracao_dias_no_momento == 365

    # Congelamento: mexer no Plan nao muda a assinatura ja criada.
    barato.preco = Decimal("999.00")
    barato.save(update_fields=["preco"])
    a.refresh_from_db()
    assert a.preco_cobrado == Decimal("9.90")


# ======================================================================
# 4. CANCELAMENTO
# ======================================================================


@override_settings(**MP_CONFIG)
def test_cancelar_chama_o_provedor_e_nao_so_o_estado_local():
    """
    Cancelar SÓ aqui deixava o débito recorrente vivo no Mercado Pago: o
    cliente cancelava no portal e continuava sendo cobrado. Este é o
    defeito de dinheiro mais direto do caminho.
    """
    subscription = _assinatura_ativa(referencia="pre-1")
    gateway = _GatewayDuble()

    services.cancelar_assinatura(subscription, payment_gateway=gateway)

    assert gateway.canceladas == ["pre-1"]
    subscription.refresh_from_db()
    assert subscription.status == Subscription.STATUS_CANCELADA
    assert subscription.renovacao_automatica is False


@override_settings(**MP_CONFIG)
def test_cancelar_localmente_mesmo_com_provedor_fora(caplog):
    """
    Se o provedor recusar o cancelamento, a transição local acontece
    MESMO. Prender o cliente numa assinatura que ele cancelou é pior que
    uma cobrança indevida isolada — e a conciliação reenvia depois.
    """
    subscription = _assinatura_ativa(referencia="pre-1")
    gateway = _GatewayDuble()

    def _falha(referencia):
        raise ProvedorPagamentoError("provedor fora do ar")

    gateway.cancelar = _falha
    with caplog.at_level(logging.ERROR, logger="assinatura.services"):
        services.cancelar_assinatura(subscription, payment_gateway=gateway)

    subscription.refresh_from_db()
    assert subscription.status == Subscription.STATUS_CANCELADA
    assert "Falha ao cancelar" in caplog.text


@override_settings(**MP_CONFIG)
def test_endpoint_cancelar_cancela_no_provedor():
    """O caminho HTTP também alcança o provedor (não só o serviço)."""
    subscription = _assinatura_ativa(referencia="pre-1", email="cancelar-http@example.com")
    gateway = _GatewayDuble()
    client = APIClient()
    client.force_authenticate(user=subscription.user)

    with patch("assinatura.providers.payment.obter_gateway_pagamento", return_value=gateway):
        resposta = client.post("/api/assinatura/cancelar/")

    assert resposta.status_code == 200
    assert resposta.data["status"] == Subscription.STATUS_CANCELADA
    assert gateway.canceladas == ["pre-1"]


@override_settings(**MP_CONFIG)
def test_cancela_apenas_assinatura_propria():
    """Nunca cancela assinatura de terceiro (o endpoint não recebe id)."""
    minha = _assinatura_ativa(referencia="pre-1", email="dono@example.com")
    alheia = _assinatura_ativa(referencia="pre-2", email="alheia@example.com")
    client = APIClient()
    client.force_authenticate(user=minha.user)

    with patch("assinatura.providers.payment.obter_gateway_pagamento", return_value=_GatewayDuble()):
        resposta = client.post("/api/assinatura/cancelar/")

    assert resposta.status_code == 200
    minha.refresh_from_db()
    alheia.refresh_from_db()
    assert minha.status == Subscription.STATUS_CANCELADA
    assert alheia.status == Subscription.STATUS_ATIVA


@override_settings(**MP_CONFIG)
def test_cancelada_apos_vencimento_encerra_e_perde_acesso():
    """Estado terminal coerente: cancelada com período pago encerrado
    vira `encerrada` e o Premium cai."""
    subscription = _assinatura_ativa(referencia="pre-1")
    services.cancelar_assinatura(subscription, payment_gateway=_GatewayDuble())
    subscription.vencimento = timezone.now() - timedelta(days=1)
    subscription.save(update_fields=["vencimento"])

    resultado = services.processar_vencimentos_e_grace_periods(payment_gateway=_GatewayDuble())

    subscription.refresh_from_db()
    subscription.user.refresh_from_db()
    assert resultado["encerradas"] == 1
    assert subscription.status == Subscription.STATUS_ENCERRADA
    assert subscription.user.papel == "free"


@override_settings(**MP_CONFIG)
def test_cancelada_mantem_acesso_ate_vencer():
    """O período já pago não é cortado no cancelamento."""
    subscription = _assinatura_ativa(referencia="pre-1")
    services.cancelar_assinatura(subscription, payment_gateway=_GatewayDuble())

    subscription.refresh_from_db()
    subscription.user.refresh_from_db()
    assert subscription.status == Subscription.STATUS_CANCELADA
    assert subscription.deveria_ter_acesso_premium is True
    assert subscription.user.papel == "premium"


# ======================================================================
# 5. RENOVAÇÃO
# ======================================================================


@override_settings(**MP_CONFIG)
def test_renovacao_pendente_nao_inadimplenta_nem_derruba_acesso():
    """
    DEFEITO ACHADO: o `else` final do `processar_vencimentos` cobria
    tudo que não fosse "aprovado" — e o Mercado Pago responde "pendente"
    ao criar a preapproval. TODA renovação com o gateway real colocava
    o assinante em `inadimplente` com grace period, sem ele ter falhado
    em nada. Com o placeholder manual (que responde "aprovado" na hora)
    isso nunca aparecia.
    """
    subscription = _assinatura_ativa(referencia="pre-1", vencimento_em_dias=-1)
    gateway = _GatewayDuble()

    resultado = services.processar_vencimentos_e_grace_periods(payment_gateway=gateway)

    subscription.refresh_from_db()
    subscription.user.refresh_from_db()
    assert resultado["renovacoes_aguardando"] == 1
    assert resultado["renovadas"] == 0
    assert subscription.status == Subscription.STATUS_ATIVA
    assert subscription.grace_period_termina_em is None
    assert subscription.user.papel == "premium"


@override_settings(**MP_CONFIG)
def test_renovacao_registra_a_referencia_para_o_webhook_encontrar():
    """
    DEFEITO ACHADO: a preapproval nova da renovação ia só para o
    `HistoricoPagamento`; o `gateway_referencia` da assinatura continuava
    o antigo. O webhook da renovação procurava uma referência que não
    estava em lugar nenhum — o cliente pagava e o sistema nunca
    confirmava.
    """
    subscription = _assinatura_ativa(referencia="pre-antigo", vencimento_em_dias=-1)
    gateway = _GatewayDuble()

    services.processar_vencimentos_e_grace_periods(payment_gateway=gateway)

    subscription.refresh_from_db()
    assert subscription.gateway_referencia.startswith("pre-ren-")
    assert subscription.gateway_referencia != "pre-antigo"


@override_settings(**MP_CONFIG)
def test_tarefa_periodica_nao_cobra_o_mesmo_ciclo_de_novo():
    """
    DEFEITO (que apareceria ao corrigir o anterior): com o status
    deixando de ser "pendente" logo depois, a task voltava a achar a
    assinatura elegível a cada rodada e criava OUTRA preapproval. Duas
    execuções seguidas = uma cobrança; o dinheiro não é duplicado.
    """
    subscription = _assinatura_ativa(referencia="pre-1", vencimento_em_dias=-1)
    gateway = _GatewayDuble()

    services.processar_vencimentos_e_grace_periods(payment_gateway=gateway)
    segunda = services.processar_vencimentos_e_grace_periods(payment_gateway=gateway)

    assert len(gateway.criadas) == 1, f"cobrança duplicada: {gateway.criadas}"
    assert segunda["renovacoes_ja_em_aberto"] == 1
    assert HistoricoPagamento.objects.filter(
        subscription=subscription, status=HistoricoPagamento.STATUS_PENDENTE
    ).count() == 1


@override_settings(**MP_CONFIG)
def test_renovacao_confirmada_por_webhook_estende_um_periodo():
    """Ciclo completo da renovação: task cria a cobrança, o webhook
    confirma, o período avança exatamente um ciclo."""
    subscription = _assinatura_ativa(referencia="pre-1", vencimento_em_dias=-1)
    gateway = _GatewayDuble()
    vencimento_antigo = subscription.vencimento

    services.processar_vencimentos_e_grace_periods(payment_gateway=gateway)
    subscription.refresh_from_db()
    nova_referencia = subscription.gateway_referencia

    with _mp_get(referencia=nova_referencia):
        _webhook(nova_referencia, request_id="req-ren")

    subscription.refresh_from_db()
    assert subscription.status == Subscription.STATUS_ATIVA
    assert subscription.vencimento > vencimento_antigo
    # o vencimento estava 1 dia no passado; a renovação o estende um ciclo
    # inteiro a partir de agora (sem dia de bônus, sem dia cortado).
    delta = subscription.vencimento - vencimento_antigo
    assert timedelta(days=30) < delta < timedelta(days=32)
    HistoricoPagamento.objects.get(referencia_gateway=nova_referencia)


@override_settings(**MP_CONFIG)
def test_renovacao_recusada_mantem_acesso_no_grace_period():
    """Renovação recusada NÃO derruba o Premium já pago (mesma regra do
    primeiro pagamento recusado)."""
    subscription = _assinatura_ativa(referencia="pre-1", vencimento_em_dias=-1)
    gateway = _GatewayDuble()
    services.processar_vencimentos_e_grace_periods(payment_gateway=gateway)
    subscription.refresh_from_db()
    nova_referencia = subscription.gateway_referencia

    with _mp_get(status="cancelled", referencia=nova_referencia):
        _webhook(nova_referencia, request_id="req-ren-2")

    subscription.refresh_from_db()
    subscription.user.refresh_from_db()
    assert subscription.status == Subscription.STATUS_INADIMPLENTE
    assert subscription.grace_period_termina_em is not None
    assert subscription.user.papel == "premium"


@override_settings(**MP_CONFIG)
def test_renovacao_antecipada_nao_corta_dias_ja_pagos():
    """
    Renovacao que chega ANTES do vencimento (o usuario paga adiantado)
    EMPILHA o periodo; nao o sobrepoe. A conta e
    `max(agora, vencimento) + duracao`: com `+ duracao` a partir de
    `agora` (o que o codigo fazia antes), o cliente perderia os dias que
    ja tinha pago; agora o fim do periodo avanca o periodo inteiro.
    """
    subscription = _assinatura_ativa(referencia="pre-1", vencimento_em_dias=20)
    vencimento_atual = subscription.vencimento

    services.processar_confirmacao_pagamento(subscription)
    subscription.refresh_from_db()

    # avanca exatamente um ciclo a partir do vencimento JA existente
    assert subscription.vencimento - vencimento_atual == timedelta(days=30)
    assert subscription.vencimento > timezone.now()


@override_settings(**MP_CONFIG)
def test_renovacao_em_atraso_nao_concede_dias_de_bonus():
    """
    O caso oposto: a renovacao sobe quando o vencimento JA passou. A base
    `max(agora, vencimento)` devolve `agora` nessa situacao, entao o
    cliente ganha exatamente o periodo que pagou — nem um dia a mais de
    cortesia, nem um dia cortado.
    """
    subscription = _assinatura_ativa(referencia="pre-1", vencimento_em_dias=-5)
    antes = timezone.now()

    services.processar_confirmacao_pagamento(subscription)
    subscription.refresh_from_db()

    # O vencimento estava 5 dias no passado, então a base e `agora`: o
    # cliente ganha UM ciclo inteiro a partir de hoje. Se a base fosse o
    # `vencimento` antigo, o resultado seria agora+25 (5 dias cortados); se
    # fosse `agora + 2*duracao`, seria agora+60 (cortesia). Este e o
    # unico valor que nao favorece nem o sistema nem perde dinheiro do
    # cliente.
    assert timedelta(days=30) - timedelta(minutes=1) <= subscription.vencimento - antes < timedelta(days=30) + timedelta(minutes=1)


@override_settings(**MP_CONFIG)
def test_vencimento_sem_renovacao_automatica_expira():
    """Sem consentimento para renovar, o vencimento expira — e não cria
    cobrança nenhuma."""
    subscription = _assinatura_ativa(referencia="pre-1", vencimento_em_dias=-1)
    subscription.renovacao_automatica = False
    subscription.save(update_fields=["renovacao_automatica"])
    gateway = _GatewayDuble()

    resultado = services.processar_vencimentos_e_grace_periods(payment_gateway=gateway)

    subscription.refresh_from_db()
    assert resultado["expiradas"] == 1
    assert subscription.status == Subscription.STATUS_EXPIRADA
    assert gateway.criadas == []


# ======================================================================
# 6. RECONCILIAÇÃO
# ======================================================================


@override_settings(**MP_CONFIG)
def test_reconciliacao_recupera_notificacao_perdida():
    """
    O caso que a conciliação existe para resolver: o cliente PAGOU, a
    notificação se perdeu (deploy no meio do request, 500, ela nunca
    chegou) e a assinatura está presa em `pagamento_pendente` sem
    nenhum caminho de volta — porque, antes desta rotina, nada mais
    consultava o provedor.

    Este é o teste que mais importa da seção: prova que o dinheiro
    recebido tem como virar acesso.
    """
    subscription = _assinatura_pendente(referencia="pre-1")
    gateway = _GatewayDuble(status_consulta="aprovado")

    resultado = services.reconciliar_com_provedor(payment_gateway=gateway)

    subscription.refresh_from_db()
    subscription.user.refresh_from_db()
    assert resultado["consultadas"] == 1
    assert resultado["confirmadas"] == 1
    assert subscription.status == Subscription.STATUS_ATIVA
    assert subscription.user.papel == "premium"
    HistoricoPagamento.objects.get(
        subscription=subscription, status=HistoricoPagamento.STATUS_APROVADO
    )


@override_settings(**MP_CONFIG)
def test_reconciliacao_e_idempotente():
    """Rodar duas vezes não muda nada — é o que a torna segura para
    reentrada de task Celery."""
    subscription = _assinatura_pendente(referencia="pre-1")
    gateway = _GatewayDuble()

    services.reconciliar_com_provedor(payment_gateway=gateway)
    services.reconciliar_com_provedor(payment_gateway=gateway)

    subscription.refresh_from_db()
    assert subscription.status == Subscription.STATUS_ATIVA
    transicoes = AssinaturaMudancaEstadoLog.objects.filter(
        subscription=subscription, estado_novo=Subscription.STATUS_ATIVA
    ).count()
    assert transicoes == 1
    assert HistoricoPagamento.objects.filter(subscription=subscription).count() == 1


@override_settings(**MP_CONFIG)
def test_reconciliacao_corrige_divergencia_de_valor(caplog):
    """Provedor cobrando um valor diferente do congelado: a reconciliação
    NÃO confirma e a divergência fica registrada."""
    subscription = _assinatura_pendente(referencia="pre-1", preco="29.90")
    gateway = _GatewayDuble(valor=Decimal("9.90"))

    with caplog.at_level(logging.ERROR, logger="assinatura.services"):
        resultado = services.reconciliar_com_provedor(payment_gateway=gateway)

    subscription.refresh_from_db()
    assert resultado["divergencias_de_valor"] == 1
    assert subscription.status == Subscription.STATUS_PAGAMENTO_PENDENTE
    assert "valor divergente" in caplog.text


@override_settings(**MP_CONFIG)
def test_reconciliacao_espelha_cancelamento_feito_no_provedor():
    """O cliente cancelou no painel do MP; local ainda está `ativa`."""
    subscription = _assinatura_ativa(referencia="pre-1")
    gateway = _GatewayDuble(status_consulta="recusado")

    resultado = services.reconciliar_com_provedor(payment_gateway=gateway)

    subscription.refresh_from_db()
    assert resultado["canceladas_no_provedor"] == 1
    assert subscription.status == Subscription.STATUS_CANCELADA


@override_settings(**MP_CONFIG)
def test_reconciliacao_reenvia_cancelamento_que_nao_chegou_no_provedor():
    """
    O oposto: cancelado AQUI, mas o provedor ainda reporta o acordo
    ativo (o `cancelar` anterior falhou por rede). Sem esta volta, o
    cliente continuaria sendo cobrado por uma assinatura que cancelou.
    """
    subscription = _assinatura_ativa(referencia="pre-1")
    gateway = _GatewayDuble()
    services.cancelar_assinatura(subscription, payment_gateway=gateway)
    gateway.canceladas.clear()
    gateway.status_consulta = "aprovado"  # provedor ainda ativo

    resultado = services.reconciliar_com_provedor(payment_gateway=gateway)

    assert resultado["cancelamento_reenviado"] == 1
    assert gateway.canceladas == ["pre-1"]


@override_settings(**MP_CONFIG)
def test_reconciliacao_nao_transiciona_quando_o_provedor_falha():
    """Falha de rede com o provedor NÃO pode virar mudança de estado
    financeiro."""
    subscription = _assinatura_pendente(referencia="pre-1")
    gateway = _GatewayDuble()
    gateway.consultar_cobranca = MagicMock(side_effect=ProvedorPagamentoError("rede caiu"))

    resultado = services.reconciliar_com_provedor(payment_gateway=gateway)

    subscription.refresh_from_db()
    assert resultado["erros"] == 1
    assert resultado["confirmadas"] == 0
    assert subscription.status == Subscription.STATUS_PAGAMENTO_PENDENTE


@override_settings(**MP_CONFIG)
def test_reconciliacao_nao_reativa_estado_terminal():
    """`expirada`/`encerrada` são o fim da linha — nem o provedor
    "autorizado" reabre."""
    subscription = _assinatura_pendente(referencia="pre-1")
    subscription.status = Subscription.STATUS_EXPIRADA
    subscription.save(update_fields=["status"])

    resultado = services.reconciliar_com_provedor(payment_gateway=_GatewayDuble())

    subscription.refresh_from_db()
    assert resultado["confirmadas"] == 0
    assert subscription.status == Subscription.STATUS_EXPIRADA


@override_settings(**MP_CONFIG)
def test_reconciliacao_ignora_assinatura_sem_referencia_de_provedor():
    """Nada a perguntar ao provedor para assinatura sem referência."""
    subscription = _assinatura_pendente(referencia="")
    gateway = _GatewayDuble()

    resultado = services.reconciliar_com_provedor(payment_gateway=gateway)

    assert resultado["consultadas"] == 0
    assert gateway.consultadas == []


@override_settings(**MP_CONFIG)
def test_task_de_conciliacao_delega_e_retorna_contadores():
    """A task periódica está ligada (é o que faz a conciliação existir de
    fato em produção, não só em teste)."""
    from assinatura import tasks

    esperado = {"consultadas": 3, "confirmadas": 1}
    with patch.object(tasks, "reconciliar_com_provedor", return_value=esperado) as mock:
        assert tasks.reconciliar_com_provedor_task() == esperado
    mock.assert_called_once_with()


def test_conciliacao_esta_agendada_no_beat():
    from django.conf import settings

    entrada = settings.CELERY_BEAT_SCHEDULE["assinatura-reconciliar-com-provedor"]
    assert entrada["task"] == "assinatura.tasks.reconciliar_com_provedor"
    assert entrada["schedule"] > 0


# ======================================================================
# 7. SEGREDO: NADA DE CREDENCIAL EM CÓDIGO NEM EM LOG
# ======================================================================


@override_settings(**MP_CONFIG)
def test_nenhum_log_contem_assinatura_recebida_nem_payload(caplog):
    """
    Requisicao FORJADA (assinatura invalida): o caminho mais frio, onde
    costuma vazar. O log pode dizer que recusou, nunca reproduzir o `v1`
    recebido (que daria a quem le log o material para forjar) nem o corpo
    do provedor.
    """
    _assinatura_pendente(referencia="pre-1")
    v1_recebido = "a" * 64

    with caplog.at_level(logging.DEBUG):
        with _mp_get() as get:
            resposta = _webhook(
                "pre-1",
                signed=False,
                **{
                    HEADER_ASSINATURA: f"ts=1704908011,v1={v1_recebido}",
                    HEADER_REQUEST_ID: "req-1",
                },
            )

    assert resposta.status_code == 200
    texto = caplog.text
    assert v1_recebido not in texto
    assert SEGREDO not in texto
    assert TOKEN not in texto
    assert "recusada" in texto
    assert get.call_count == 0


@override_settings(**MP_CONFIG)
def test_nenhum_log_contem_token_nem_corpo_do_provedor_no_erro(caplog):
    """
    Notificacao AUTENTICADA, mas o provedor responde erro: o
    `ProvedorPagamentoError` carrega o corpo da resposta do MP. O log
    pode trazer o erro, nunca o token nem o corpo cru.
    """
    _assinatura_pendente(referencia="pre-1")

    with caplog.at_level(logging.ERROR):
        with patch(
            "assinatura.providers.payment.SessaoEgress.get",
            return_value=_resposta(500, {"message": "token invalido", "cause": [{"code": "3000"}]}),
        ):
            resposta = _webhook("pre-1")

    assert resposta.status_code == 200
    texto = caplog.text
    assert TOKEN not in texto
    assert SEGREDO not in texto
    assert "Bearer" not in texto

def test_credencial_do_mp_nao_existe_em_arquivo_do_repositorio():
    """
    Nenhum literal de credencial do MP versionado. Falha em alto se
    alguém colar um token de verdade no código ou num ajuste de teste.
    """
    import re
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    padroes = re.compile(r"(APP_USR-|TEST-)[0-9A-Za-z]{8,}")
    achados = []
    for caminho in raiz.rglob("*.py"):
        if ".venv" in caminho.parts:
            continue
        texto = caminho.read_text(encoding="utf-8", errors="replace")
        # o placeholder de teste da suíte é o único literal aceitável
        for linha in texto.splitlines():
            if padroes.search(linha) and "dummy" not in linha:
                achados.append(f"{caminho}: {linha.strip()[:60]}")
    assert not achados, f"literal de credencial do MP versionado: {achados}"


# ======================================================================
# 8. PENDÊNCIA MARCADA — o que só a credencial real valida
# ======================================================================


def test_pendencia_de_credencial_real():
    """
    >>> PENDENTE — não coberto por este item, por desenho.

    Não existe credencial `MERCADO_PAGO_*` neste ambiente, e o item é
    explícito: não inventar credencial nem chamar o provedor real. Então
    o que está marcado aqui como não-verificado é:

    1. O ALGORITMO da assinatura contra a implementação real do MP. O
       código usa o esquema HMAC-SHA256 documentado pelo MP
       (`v1 = hmac_sha256(manifesto, segredo)`, manifesto
       `id:<id>;request-id:<request-id>;ts:<ts>;`) e a própria doc do MP
       mostra `v1` de 64 hex. O histórico do provedor teve um esquema
       md5(sha256(manifesto) + segredo); se a conta de produção ainda
       usar o antigo, é preciso um `v1` de 32 hex. OS TESTOS AQUI
       PROVAM A CONSISTÊNCIA INTERNA (o verificador e o gerador seguem o
       mesmo esquema documentado) — não provam que o MP usa o mesmo.
       COMO VALIDAR: com o secret real, disparar um evento de teste pelo
       painel do MP e conferir no access log que houve 200 com ação
       `confirmada`, e não `recusada` por `assinatura_nao_confere`.
    2. A FORMA REAL da resposta `GET /preapproval/<id>` (a extração de
       `auto_recurring.transaction_amount`/`currency_id`). O duble aqui
       usa a forma canônica; se a conta devolver outra, o efeito
       observável é uma divergência de valor registrada e a assinatura
       não ativada — fail-closed, nunca ativação indevida.
    3. O comportamento de `repetitions` em produção: a preapproval criada
       hoje manda `auto_recurring.repetitions` = meses do plano. Se a
       conta renewal cobrando no MP conflitar com a renovação local,
       aparece DUAS cobranças pelo mesmo período — a reconciliação
       mostraria, mas a validação precisa do painel do MP.

    Enquanto (1) não for validado, o webhook fica fail-closed: nenhum
    estado muda por notificação, e a assinatura não é ativada por esse
    caminho. É o modo de falha seguro — perde-se a confirmação
    automática, não a segurança.
    """
    assert True
