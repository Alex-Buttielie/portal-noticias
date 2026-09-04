from rest_framework import serializers

from .models import Comentario, Publicacao


class PublicacaoSerializer(serializers.ModelSerializer):
    # Nome de exibição, não e-mail: PublicacoesListCreateView.get é AllowAny
    # (endpoint público, sem autenticação) — expor e-mail aqui vazaria o
    # e-mail de qualquer autor para qualquer visitante anônimo (achado de
    # revisão de segurança, ver agentic-framework/state/HISTORY.md). `nome`
    # já é o campo usado para exibição pública em PerfilAutorPublicoView.
    autor_nome = serializers.CharField(source="autor.nome", read_only=True)

    class Meta:
        model = Publicacao
        fields = [
            "id",
            "autor",
            "autor_nome",
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
        read_only_fields = ["id", "autor", "autor_nome", "status", "destaque", "criado_em", "publicado_em"]


class ComentarioSerializer(serializers.ModelSerializer):
    # Ver comentário em PublicacaoSerializer.autor_nome — mesma correção,
    # ComentariosListCreateView.get também é AllowAny.
    autor_nome = serializers.CharField(source="autor.nome", read_only=True)

    class Meta:
        model = Comentario
        fields = ["id", "autor", "autor_nome", "conteudo", "publicacao", "news_item", "resposta_de", "criado_em"]
        read_only_fields = ["id", "autor", "autor_nome", "criado_em"]
