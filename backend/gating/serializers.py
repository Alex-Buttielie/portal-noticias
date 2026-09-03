from rest_framework import serializers


class MeuRecursoSerializer(serializers.Serializer):
    chave = serializers.CharField()
    valor = serializers.CharField(allow_null=True)
    disponivel = serializers.BooleanField()


class MeusRecursosResponseSerializer(serializers.Serializer):
    plano = serializers.ChoiceField(choices=["free", "premium"])
    recursos = MeuRecursoSerializer(many=True)
