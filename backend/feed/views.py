from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .serializers import FeedDetalheSerializer, FeedEntrySerializer


class FeedPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class FeedListView(APIView):
    """
    Critério de aceite 1: feed público, SEM autenticação obrigatória
    (`AllowAny` — o padrão global do projeto, definido em
    `config/settings.py` após a correção de segurança do run
    `20260901-2135-cadastro-auth`, é `IsAuthenticated`; este endpoint precisa
    do override explícito).
    """

    permission_classes = [AllowAny]

    def get(self, request):
        categoria = request.query_params.get("categoria") or None
        busca = request.query_params.get("busca") or None

        itens = list(services.itens_publicaveis(categoria=categoria, busca=busca))
        entradas = services.construir_feed_entries(itens)
        if not categoria and not busca:
            # BRD seção 10 — equilíbrio entre categorias só se aplica ao
            # feed geral; um filtro explícito de categoria/busca expressa
            # intenção do usuário, que não deve ser rebalanceada.
            entradas = services.equilibrar_por_categoria(entradas)

        paginator = FeedPagination()
        pagina = paginator.paginate_queryset(entradas, request, view=self)
        serializer = FeedEntrySerializer(pagina, many=True)

        resposta = paginator.get_paginated_response(serializer.data)
        resposta.data["exibir_publicidade"] = services.exibir_publicidade(request.user)
        return resposta


class ClusterDetailView(APIView):
    """Detalhe de um acontecimento coberto por 2+ fontes (`NewsCluster`)."""

    permission_classes = [AllowAny]

    def get(self, request, cluster_id):
        detalhe = services.detalhe_cluster(cluster_id)
        if detalhe is None:
            # Critério de aceite 2 e 8: cluster inexistente OU sem nenhum
            # item publicável (todos pendente/rejeitado) — 404 nos dois
            # casos, sem distinguir (não vaza a existência de conteúdo não
            # aprovado).
            return Response(status=status.HTTP_404_NOT_FOUND)

        dados = dict(FeedDetalheSerializer(detalhe).data)
        dados["exibir_publicidade"] = services.exibir_publicidade(request.user)
        return Response(dados)


class ItemDetailView(APIView):
    """Detalhe de uma notícia standalone (`NewsItem` sem cluster)."""

    permission_classes = [AllowAny]

    def get(self, request, item_id):
        detalhe = services.detalhe_item(item_id)
        if detalhe is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        dados = dict(FeedDetalheSerializer(detalhe).data)
        dados["exibir_publicidade"] = services.exibir_publicidade(request.user)
        return Response(dados)


class UrgentesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        limite = min(12, max(1, int(request.query_params.get("limite", 6))))
        entradas = services.urgentes(limite=limite)
        return Response(FeedEntrySerializer(entradas, many=True).data)


class MaisLidasView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        limite = min(12, max(1, int(request.query_params.get("limite", 5))))
        entradas = services.mais_lidas(limite=limite)
        return Response(FeedEntrySerializer(entradas, many=True).data)
