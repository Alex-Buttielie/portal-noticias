from rest_framework import serializers

from .models import Comentario, Publicacao


class PublicacaoSerializer(serializers.ModelSerializer):
    autor_email = serializers.EmailField(source="autor.email", read_only=True)

    class Meta:
        model = Publicacao
        fields = [
            "id",
            "autor",
            "autor_email",
            "titulo",
            "conteudo",
            "tipo",
            "status",
            "categoria",
            "tags",
            "news_cluster",
            "news_item",
            "destaque",
            "criado_em",
            "publicado_em",
        ]
        read_only_fields = ["id", "autor", "autor_email", "status", "destaque", "criado_em", "publicado_em"]


class ComentarioSerializer(serializers.ModelSerializer):
    autor_email = serializers.EmailField(source="autor.email", read_only=True)

    class Meta:
        model = Comentario
        fields = ["id", "autor", "autor_email", "conteudo", "publicacao", "news_item", "resposta_de", "criado_em"]
        read_only_fields = ["id", "autor", "autor_email", "criado_em"]
