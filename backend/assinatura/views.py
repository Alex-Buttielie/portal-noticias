from django.db import transaction
from rest_framework import status as http_status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import HistoricoPagamento, Plan, Subscription
from .serializers import (
    AssinarPlanoSerializer,
    HistoricoPagamentoSerializer,
    PlanSerializer,
    SubscriptionSerializer,
)


class PlanosListView(APIView):
    """Critério de aceite 1: só planos ativos aparecem publicamente."""

    permission_classes = [AllowAny]

    def get(self, request):
        planos = Plan.objects.filter(ativo=True)
        return Response(PlanSerializer(planos, many=True).data)


class AssinarView(APIView):
    """Critérios de aceite 2, 3, 12."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AssinarPlanoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from gating.services import premium_liberado_geral

        if premium_liberado_geral():
            return Response(
                {"detail": "Assinaturas pausadas no momento — todos os recursos Premium estão liberados."},
                status=409,
            )

        try:
            plan = Plan.objects.get(pk=serializer.validated_data["plan_id"], ativo=True)
        except Plan.DoesNotExist:
            return Response({"detail": "Plano inválido ou inativo."}, status=http_status.HTTP_400_BAD_REQUEST)

        try:
            subscription = services.assinar_plano(request.user, plan)
        except services.AssinaturaJaExisteError as exc:
            return Response({"detail": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)

        dados = SubscriptionSerializer(subscription).data
        checkout_url = getattr(subscription, "checkout_url", None)
        if checkout_url:
            dados["checkout_url"] = checkout_url
        return Response(dados, status=http_status.HTTP_201_CREATED)


class CancelarView(APIView):
    """
    Critério de aceite 7: cancelamento self-service — o usuário só pode
    cancelar a PRÓPRIA assinatura (nunca recebe/usa um id de outro usuário
    aqui, evitando qualquer possibilidade de cancelar assinatura alheia).

    O gateway é montado em `try/except` e a assinatura é cancelada
    localmente MESMO se ele não possa ser construído (provedor real sem
    token no ambiente, por exemplo). O motivo é simples: o cancelamento
    é um direito do cliente e prendê-lo numa assinatura por causa de um
    erro de configuração nosso seria pior do que qualquer cobrança
    indevida. A conciliação reenvia o cancelamento ao provedor assim que
    ele voltar a estar disponível.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        subscription = (
            Subscription.objects.filter(
                user=request.user,
                status__in=[Subscription.STATUS_ATIVA, Subscription.STATUS_TESTE],
            )
            .order_by("-criado_em")
            .first()
        )
        if subscription is None:
            return Response(
                {"detail": "Nenhuma assinatura ativa encontrada para cancelar."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            from .providers.payment import obter_gateway_pagamento

            gateway = obter_gateway_pagamento()
        except Exception:  # noqa: BLE001 — nunca bloqueia o cancelamento
            gateway = None

        subscription = services.cancelar_assinatura(subscription, payment_gateway=gateway)
        return Response(SubscriptionSerializer(subscription).data)


class MinhaAssinaturaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        subscription = Subscription.objects.filter(user=request.user).order_by("-criado_em").first()
        if subscription is None:
            return Response({"detail": "Nenhuma assinatura encontrada."}, status=http_status.HTTP_404_NOT_FOUND)
        return Response(SubscriptionSerializer(subscription).data)


class HistoricoPagamentosView(APIView):
    """Critério de aceite 10: só pagamentos do próprio usuário autenticado."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        pagamentos = HistoricoPagamento.objects.filter(subscription__user=request.user)
        return Response(HistoricoPagamentoSerializer(pagamentos, many=True).data)


class WebhookMercadoPagoView(APIView):
    """
    Webhook do Mercado Pago (assinaturas recorrentes `/preapproval`).

    O MP avisa eventos por querystring (`?topic=...&id=...&data.id=...`) ou
    corpo JSON (`{"type": ..., "data": {"id": ...}}`).

    Quatro garantias, nesta ordem:

    1. **AUTENTICIDADE DA ORIGEM.** O endpoint é público por natureza (o
       MP não tem token de usuário), então a primeira coisa que a view
       faz — antes de tocar o banco e antes de qualquer chamada de
       rede — é conferir a assinatura `x-signature` do Mercado Pago com
       o segredo configurado (`ASSINATURA_MP_WEBHOOK_SECRET`). Sem isso,
       qualquer pessoa que descubrisse a URL poderia escrever estado
       financeiro: o `id` de uma preapproval do MP é sequencial, então
       adivinhar não custa nada. É o defeito mais grave que este item
       encontrou — o relatório da run traz o detalhe.
    2. **NUNCA confiar no payload.** O `status` vem da API do MP
       (`consultar_cobranca`), não do corpo da notificação.
    3. **CONFERÊNCIA DE VALOR E MOEDA.** O que o MP afirma ter cobrado é
       comparado com o `preco_cobrado` congelado na assinatura; divergência
       é registrada e o estado NÃO é alterado (ver
       `services._divergencia_de_valor`).
    4. **IDEMPOTÊNCIA.** A mesma notificação repetida não cobra duas
       vezes nem duplica estado: a chave é a cobrança em aberto (ver
       `services._cobrancas_em_aberto`). O MP reenvia até 8 vezes ao
       longo de ~4 dias, então isto é requisito, não refinamento.

    Toda transição passa por `services.aplicar_resultado_provedor` — o
    MESMO caminho usado pela conciliação, para que as garantias acima não
    valham só aqui.

    Responde SEMPRE 200 (inclusive em recusa de assinatura e em erro
    interno, sempre logado) para o MP não retentar em loop; a resposta é
    a mesma nos três casos, então ela não diz a um atacante qual das
    etapas recusou. Nada do token, da assinatura nem do payload do
    provedor é registrado.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        import logging

        from assinatura.providers.payment import (
            HEADER_ASSINATURA,
            HEADER_REQUEST_ID,
            MercadoPagoGatewayProvider,
            verificar_assinatura_webhook,
        )

        logger = logging.getLogger(__name__)
        corpo = request.data if isinstance(request.data, dict) else {}
        dados = corpo.get("data") if isinstance(corpo.get("data"), dict) else {}
        referencia = (
            request.query_params.get("id")
            or request.query_params.get("data.id")
            or dados.get("id")
            or corpo.get("id")
            or ""
        )
        tipo = (request.query_params.get("topic") or corpo.get("type") or "").strip().lower()
        if not referencia or tipo not in ("preapproval", "subscription_preapproval"):
            # Evento desconhecido ou sem referência: 200 e nada acontece.
            logger.info("Webhook MP: notificação ignorada (tipo=%r, sem referência).", tipo)
            return Response({"detail": "ignorado"}, status=http_status.HTTP_200_OK)

        # (1) autenticidade da origem — ANTES de qualquer efeito.
        verificacao = verificar_assinatura_webhook(
            referencia=str(referencia),
            cabecalho_assinatura=request.META.get(HEADER_ASSINATURA, ""),
            request_id=request.META.get(HEADER_REQUEST_ID, ""),
        )
        if not verificacao.ok:
            # Nível ERROR para "segredo não configurado" e "não confere"
            # (indício de requisição forjada); nenhum valor de segredo é
            # logado — só o rótulo do motivo.
            logger.error(
                "Webhook MP: notificação recusada (motivo=%s, referência=%s). "
                "Nenhum estado foi alterado.",
                verificacao.motivo,
                referencia,
            )
            return Response({"detail": "ignorado"}, status=http_status.HTTP_200_OK)

        # (2) o status é lido da API, nunca do payload.
        try:
            gateway = MercadoPagoGatewayProvider()
            cobranca = gateway.consultar_cobranca(str(referencia))
        except Exception:  # noqa: BLE001 — loga e responde 200 (ver docstring)
            logger.exception("Webhook MP: falha ao consultar a preapproval %s.", referencia)
            return Response({"detail": "ignorado"}, status=http_status.HTTP_200_OK)

        try:
            with transaction.atomic():
                subscription = (
                    Subscription.objects.select_for_update()
                    .filter(gateway_referencia=str(referencia))
                    .order_by("-criado_em")
                    .first()
                )
                if subscription is None:
                    logger.warning("Webhook MP: preapproval %s sem assinatura local.", referencia)
                    return Response({"detail": "ignorado"}, status=http_status.HTTP_200_OK)
                acao = services.aplicar_resultado_provedor(subscription, gateway, cobranca)
        except Exception:  # noqa: BLE001
            logger.exception("Webhook MP: falha ao aplicar a notificação da preapproval %s.", referencia)
            return Response({"detail": "ignorado"}, status=http_status.HTTP_200_OK)

        logger.info("Webhook MP: preapproval %s -> %s.", referencia, acao)
        return Response({"detail": "ok"}, status=http_status.HTTP_200_OK)
