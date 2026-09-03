from rest_framework import serializers


class InscricaoListaEsperaSerializer(serializers.Serializer):
    nome = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    interesses = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    localidade = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    canal_preferido = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    aceite_comunicacao = serializers.BooleanField()

    def validate_aceite_comunicacao(self, value):
        if not value:
            raise serializers.ValidationError("É necessário aceitar receber comunicações para entrar na lista.")
        return value
