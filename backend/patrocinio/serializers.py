from rest_framework import serializers

from .models import Patrocinio


class PatrocinioAtivoSerializer(serializers.ModelSerializer):
    """Payload público mínimo — sem `ativo`/datas/timestamps internos."""

    class Meta:
        model = Patrocinio
        fields = ["id", "anunciante", "criativo_url", "texto_alt", "url", "posicao"]
