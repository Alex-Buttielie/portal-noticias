from rest_framework import serializers

from .models import HistoricoPagamento, Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["id", "nome", "preco", "duracao_dias"]


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "plan",
            "status",
            "preco_cobrado",
            "duracao_dias_no_momento",
            "inicio",
            "vencimento",
            "renovacao_automatica",
            "grace_period_termina_em",
        ]


class HistoricoPagamentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoricoPagamento
        fields = ["id", "valor", "status", "criado_em"]


class AssinarPlanoSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField()
