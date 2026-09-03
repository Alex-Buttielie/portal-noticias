from rest_framework import serializers

from .models import CriterioMonitoramento, MembroOrganizacao


class CriterioMonitoramentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CriterioMonitoramento
        fields = ["id", "tipo", "valor", "ativo", "criado_em"]
        read_only_fields = ["id", "criado_em"]


class MembroOrganizacaoSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = MembroOrganizacao
        fields = ["id", "email", "papel_na_organizacao", "criado_em"]
        read_only_fields = ["id", "email", "criado_em"]
