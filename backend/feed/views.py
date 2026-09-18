from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import busca as busca_engine
from . import recomendacao, services
from .models import InteracaoNoticia
from .serializers import (
    CoberturaCompletaSerializer,
    FeedDetalheSerializer,
    FeedEntrySerializer,
    ResultadoBuscaSerializer,
    SecaoHomeSerializer,
)


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
        try:
            # FRENTE 6 — overrides da Central (RegraCuradoria: bloqueios,
            # boosts, ordem de categorias, selos/urgente/exclusivo forçados).
            # Best-effort: qualquer falha aqui nunca derruba o feed público.
            from painel_admin.services_regras import aplicar_regras_curadoria

            entradas = aplicar_regras_curadoria(entradas, itens=itens)
        except Exception:
            pass

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


# ---------------------------------------------------------------------------
# FRENTE 3 — recomendação / destaques / busca / cobertura / interações
# ---------------------------------------------------------------------------

def _perfil_recomendacao(request):
    """Interesses + região SÓ quando autorizados: usuário autenticado com
    onboarding/localidade, ou região explícita via query (opt-in)."""
    interesses: list[str] = []
    user = request.user
    if getattr(user, "is_authenticated", False):
        interesses = list(getattr(user, "interesses", []) or [])
    regiao = {
        "pais": request.query_params.get("pais") or "",
        "estado": request.query_params.get("estado") or "",
        "cidade": request.query_params.get("cidade") or "",
    }
    if getattr(user, "is_authenticated", False) and not any(regiao.values()):
        localidade = (getattr(user, "localidade", "") or "").strip()
        if localidade:
            regiao["cidade"] = localidade
    if not any(regiao.values()):
        regiao = None
    return interesses, regiao


class HomeSecoesView(APIView):
    """Home em seções: manchetes / curadoria / para_voce / populares /
    tendencia / recentes. Pública; personaliza quando há login."""

    permission_classes = [AllowAny]

    def get(self, request):
        interesses, regiao = _perfil_recomendacao(request)
        try:
            limite = min(10, max(1, int(request.query_params.get("limite", 6))))
        except (TypeError, ValueError):
            limite = 6
        itens = list(services.itens_publicaveis())
        entradas = services.construir_feed_entries(itens)
        secoes = recomendacao.montar_home(entradas, interesses=interesses, regiao=regiao, limite_secao=limite)
        dados = {nome: SecaoHomeSerializer(lista, many=True).data for nome, lista in secoes.items()}
        dados["exibir_publicidade"] = services.exibir_publicidade(request.user)
        return Response(dados)


class DestaquesDiaView(APIView):
    """Destaques do Dia dinâmicos (override manual primeiro)."""

    permission_classes = [AllowAny]

    def get(self, request):
        _, regiao = _perfil_recomendacao(request)
        try:
            limite = min(10, max(1, int(request.query_params.get("limite", 5))))
        except (TypeError, ValueError):
            limite = 5
        itens = list(services.itens_publicaveis())
        entradas = services.construir_feed_entries(itens)
        destaques = recomendacao.destaques_do_dia(entradas, regiao=regiao, limite=limite)
        return Response(SecaoHomeSerializer(destaques, many=True).data)


class BuscaView(APIView):
    """Busca principal: título/conteúdo/categoria/autor/tags/fonte/local/data."""

    permission_classes = [AllowAny]

    def get(self, request):
        q = (request.query_params.get("q") or request.query_params.get("busca") or "").strip()
        filtros = {
            "categoria": request.query_params.get("categoria") or None,
            "autor": request.query_params.get("autor") or None,
            "pais": request.query_params.get("pais") or None,
            "estado": request.query_params.get("estado") or None,
            "cidade": request.query_params.get("cidade") or None,
            "data_de": request.query_params.get("data_de") or None,
            "data_ate": request.query_params.get("data_ate") or None,
        }
        try:
            limite = min(30, max(1, int(request.query_params.get("limite", 20))))
        except (TypeError, ValueError):
            limite = 20
        resultados, total = busca_engine.buscar(q, limite=limite, **filtros)
        busca_engine.registrar_busca(
            q, len(resultados),
            user=request.user,
            session_key=request.session.session_key or "",
            filtros={k: v for k, v in filtros.items() if v},
        )
        resposta: dict = {
            "query": q,
            "count": len(resultados),
            "total_candidatos": total,
            "results": ResultadoBuscaSerializer(resultados, many=True).data,
        }
        if len(resultados) < 3:
            sugestao = busca_engine.sugestao_correcao(q)
            if sugestao:
                resposta["sugestao"] = sugestao
        return Response(resposta)


class BuscaAutocompleteView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        prefixo = (request.query_params.get("q") or "").strip()
        return Response({"query": prefixo, "sugestoes": busca_engine.autocomplete(prefixo)})


class BuscaPopularesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"termos": busca_engine.termos_populares()})


class BuscaHistoricoView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        historico = busca_engine.historico(
            user=request.user, session_key=request.session.session_key or ""
        )
        return Response({"historico": historico})


class CoberturaCompletaView(APIView):
    """'Ver cobertura completa': fontes/horários/atualizações/relacionadas."""

    permission_classes = [AllowAny]

    def get(self, request, tipo, entrada_id):
        cobertura = recomendacao.cobertura_completa(tipo, entrada_id)
        if cobertura is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        dados = dict(CoberturaCompletaSerializer(cobertura).data)
        dados["exibir_publicidade"] = services.exibir_publicidade(request.user)
        return Response(dados)


class InteracaoView(APIView):
    """Registra sinais de consumo (view/click/read/save/unsave/share/
    search_click). Público; amarra a usuário logado ou sessão anônima."""

    permission_classes = [AllowAny]
    TIPOS_VALIDOS = {c[0] for c in InteracaoNoticia.TIPO_CHOICES}

    def post(self, request):
        tipo = (request.data.get("tipo") or "").strip()
        entry_tipo = (request.data.get("entry_tipo") or "").strip()
        try:
            entry_id = int(request.data.get("entry_id"))
        except (TypeError, ValueError):
            return Response({"detail": "entry_id inválido."}, status=status.HTTP_400_BAD_REQUEST)
        if tipo not in self.TIPOS_VALIDOS or entry_tipo not in ("cluster", "item"):
            return Response({"detail": "tipo/entry_tipo inválidos."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            tempo = max(0, int(request.data.get("tempo_leitura_seg") or 0))
        except (TypeError, ValueError):
            tempo = 0
        if tipo == InteracaoNoticia.TIPO_SEARCH_CLICK:
            busca_engine.registrar_clique_resultado(
                entry_tipo, entry_id,
                query=str(request.data.get("query") or ""),
                user=request.user, session_key=request.session.session_key or "",
                tempo_leitura_seg=tempo,
            )
            return Response({"detail": "ok"}, status=status.HTTP_201_CREATED)
        try:
            from catalogo_noticias.models import NewsCluster, NewsItem

            kwargs: dict = {
                "tipo": tipo, "entry_tipo": entry_tipo,
                "user": request.user if getattr(request.user, "is_authenticated", False) else None,
                "session_key": request.session.session_key or "",
                "tempo_leitura_seg": tempo,
            }
            if entry_tipo == "cluster":
                obj = NewsCluster.objects.filter(pk=entry_id).first()
                if obj is None:
                    return Response(status=status.HTTP_404_NOT_FOUND)
                kwargs["cluster"] = obj
                primeiro = obj.itens.order_by("-timestamp_ingestao").first()
                kwargs["categoria"] = (obj.categoria_dominante or (primeiro.categoria if primeiro else ""))[:100]
            else:
                obj = NewsItem.objects.filter(pk=entry_id).first()
                if obj is None:
                    return Response(status=status.HTTP_404_NOT_FOUND)
                kwargs["item"] = obj
                kwargs["categoria"] = (obj.categoria or "")[:100]
            InteracaoNoticia.objects.create(**kwargs)
        except Exception:
            return Response({"detail": "ok"})
        return Response({"detail": "ok"}, status=status.HTTP_201_CREATED)
