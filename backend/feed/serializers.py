from rest_framework import serializers


class FeedEntrySerializer(serializers.Serializer):
    """
    Uma entrada do feed (implementation-contract.md run
    20260902-1409-feed-consumo, critério de aceite 1) — representa um
    `NewsCluster` (`tipo="cluster"`) ou um `NewsItem` standalone
    (`tipo="item"`). Ver `services.construir_feed_entries`.
    """

    tipo = serializers.ChoiceField(choices=["cluster", "item"])
    id = serializers.IntegerField()
    titulo = serializers.CharField()
    resumo = serializers.CharField(allow_blank=True)
    categoria = serializers.CharField(allow_blank=True)
    urgente = serializers.BooleanField()
    numero_fontes = serializers.IntegerField()
    timestamp = serializers.DateTimeField()


class FonteDetalheSerializer(serializers.Serializer):
    nome_fonte = serializers.CharField()
    url_fonte_original = serializers.URLField()
    resumo = serializers.CharField(allow_blank=True)


class FeedDetalheSerializer(serializers.Serializer):
    """
    Página de detalhe de um acontecimento (critério de aceite 5 e 6) —
    lista TODAS as fontes publicáveis, cada uma com seu próprio resumo (ver
    `agentic-framework/state/run-20260902-0727-ingestao-noticias/
    implementation-history.md`, Iteração 5: cada `NewsItem` tem seu PRÓPRIO
    `resumo_proprio`, nunca compartilhado entre itens do mesmo cluster).
    """

    tipo = serializers.ChoiceField(choices=["cluster", "item"])
    id = serializers.IntegerField()
    titulo = serializers.CharField()
    categoria = serializers.CharField(allow_blank=True)
    urgente = serializers.BooleanField()
    timestamp = serializers.DateTimeField()
    fontes = FonteDetalheSerializer(many=True)
