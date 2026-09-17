from rest_framework import serializers


class FeedEntrySerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=["cluster", "item"])
    id = serializers.IntegerField()
    titulo = serializers.CharField()
    resumo = serializers.CharField(allow_blank=True)
    categoria = serializers.CharField(allow_blank=True)
    urgente = serializers.BooleanField()
    numero_fontes = serializers.IntegerField()
    timestamp = serializers.DateTimeField()
    imagem_url = serializers.URLField(allow_blank=True, required=False, default="")


class FonteDetalheSerializer(serializers.Serializer):
    nome_fonte = serializers.CharField()
    url_fonte_original = serializers.URLField()
    resumo = serializers.CharField(allow_blank=True)
    # Texto integral extraído do RSS (limitado no service). O frontend exibe
    # SEMPRE truncado + crédito + link para a original (BRD secao 18).
    conteudo = serializers.CharField(allow_blank=True, required=False, default="")
    imagem_url = serializers.URLField(allow_blank=True, required=False, default="")


class FeedDetalheSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=["cluster", "item"])
    id = serializers.IntegerField()
    titulo = serializers.CharField()
    categoria = serializers.CharField(allow_blank=True)
    urgente = serializers.BooleanField()
    timestamp = serializers.DateTimeField()
    fontes = FonteDetalheSerializer(many=True)
