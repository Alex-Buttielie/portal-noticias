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

        subscription = services.cancelar_assinatura(subscription)
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

    O MP avisa eventos por querystring (`?topic=...&id=...`) ou corpo JSON
    (`{"type": ..., "data": {"id": ...}}`). A view busca o status real na API
    (nunca confia no payload), localiza a `Subscription` pela
    `gateway_referencia` e confirma/recusa. Responde SEMPRE 200 (mesmo em
    erro interno, só logando) para o MP não retentar em loop. Pública
    (o MP não tem o token do usuário) — não expõe dado algum na resposta.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        import logging

        from assinatura.providers.payment import MercadoPagoGatewayProvider

        logger = logging.getLogger(__name__)
        corpo = request.data if isinstance(request.data, dict) else {}
        dados = corpo.get("data") if isinstance(corpo.get("data"), dict) else {}
        referencia = (
            request.query_params.get("id")
            or dados.get("id")
            or corpo.get("id")
            or ""
        )
        tipo = (request.query_params.get("topic") or corpo.get("type") or "").strip().lower()
        if not referencia or tipo not in ("preapproval", "subscription_preapproval"):
            return Response({"detail": "ignorado"}, status=http_status.HTTP_200_OK)

        try:
            gateway = MercadoPagoGatewayProvider()
            estado = gateway.consultar_status(str(referencia))
        except Exception as exc:  # noqa: BLE001 — loga e responde 200 (ver docstring)
            logger.exception("Webhook MP: falha ao consultar preapproval %s: %s", referencia, exc)
            return Response({"detail": "ignorado"}, status=http_status.HTTP_200_OK)

        try:
            subscription = Subscription.objects.filter(gateway_referencia=str(referencia)).order_by("-criado_em").first()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Webhook MP: falha ao buscar assinatura %s: %s", referencia, exc)
            return Response({"detail": "ignorado"}, status=http_status.HTTP_200_OK)
        if subscription is None:
            logger.warning("Webhook MP: preapproval %s sem assinatura local.", referencia)
            return Response({"detail": "ignorado"}, status=http_status.HTTP_200_OK)

        if estado == "aprovado" and subscription.status == Subscription.STATUS_PAGAMENTO_PENDENTE:
            services.processar_confirmacao_pagamento(subscription)
            HistoricoPagamento.objects.filter(
                subscription=subscription, referencia_gateway=str(referencia)
            ).update(status=HistoricoPagamento.STATUS_APROVADO)
        elif estado == "recusado" and subscription.status == Subscription.STATUS_PAGAMENTO_PENDENTE:
            services.processar_pagamento_recusado(subscription)
            HistoricoPagamento.objects.filter(
                subscription=subscription, referencia_gateway=str(referencia)
            ).update(status=HistoricoPagamento.STATUS_RECUSADO)
        return Response({"detail": "ok"}, status=http_status.HTTP_200_OK)
