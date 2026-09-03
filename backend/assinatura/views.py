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

        try:
            plan = Plan.objects.get(pk=serializer.validated_data["plan_id"], ativo=True)
        except Plan.DoesNotExist:
            return Response({"detail": "Plano inválido ou inativo."}, status=http_status.HTTP_400_BAD_REQUEST)

        try:
            subscription = services.assinar_plano(request.user, plan)
        except services.AssinaturaJaExisteError as exc:
            return Response({"detail": str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)

        return Response(SubscriptionSerializer(subscription).data, status=http_status.HTTP_201_CREATED)


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
