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


class ObjetivoAssinaturaSerializer(serializers.Serializer):
    """GET/PUT de `objetivo_assinatura` (texto livre do usuário Premium,
    usado por `feed.AfinidadeView` para enviesar o ranqueamento do feed)."""

    objetivo = serializers.CharField(source="objetivo_assinatura", allow_blank=True, max_length=500)
    atualizado_em = serializers.DateTimeField(source="objetivo_assinatura_atualizado_em", read_only=True)
