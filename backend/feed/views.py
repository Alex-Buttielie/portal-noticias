from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

import logging

from django.conf import settings
from django.core.cache import cache

from . import busca as busca_engine
from . import microservice_client, recomendacao, services
from .microservice_client import MicroserviceIndisponivelError
from .models import InteracaoNoticia
from .serializers import (
    CoberturaCompletaSerializer,
    FeedDetalheSerializer,
    FeedEntrySerializer,
    ResultadoBuscaSerializer,
    SecaoHomeSerializer,
)

logger = logging.getLogger(__name__)


def _ttl_feed() -> int:
    """TTL do cache das listagens (`settings.FEED_CACHE_TTL_SEGUNDOS`)."""
    try:
        return max(1, int(getattr(settings, "FEED_CACHE_TTL_SEGUNDOS", 45)))
    except (TypeError, ValueError):
        return 45


def _chave_cache_listagem(request, prefixo: str) -> str:
    """
    Chave por querystring normalizada (ordenada) + usuário (pk ou "anon").

    Run 20260923-1216-p1-feed-cache-indices (P1-1): o cache só é correto
    porque NENHUM payload listado aqui varia por usuário — `exibir_publicidade`
    saiu do feed (vai via `GET /api/gating/status`). O sufixo de usuário é
    defesa em profundidade (ex.: seções personalizam por interesses de quem
    está logado) — tráfego anônimo (dominante) compartilha a chave "anon".
    """
    params = sorted((k, v) for k, v in request.query_params.items())
    base = "&".join(f"{k}={v}" for k, v in params)
    usuario = getattr(request.user, "pk", None) or "anon"
    return f"feed:v1:{prefixo}:u{usuario}:{base}"


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

        # P1-1 (run 20260923-1216): cache curto da resposta paginada final
        # (payload não varia por usuário — sem `exibir_publicidade`).
        chave = _chave_cache_listagem(request, "lista")
        em_cache = cache.get(chave)
        if em_cache is not None:
            return Response(em_cache)

        # Frente D — microserviço primeiro quando ativo; qualquer falha cai
        # silenciosamente para o serviço local (contrato de resposta idêntico:
        # o microserviço usa os mesmos shapes de FeedEntrySerializer).
        if microservice_client.servico_ativo():
            try:
                payload = microservice_client.obter_feed(
                    categoria=categoria,
                    busca=busca,
                    page=request.query_params.get("page") or 1,
                    page_size=request.query_params.get("page_size") or None,
                )
                # O microserviço pode ainda espelhar o contrato antigo com a
                # flag per-user — nunca repassar ao frontend (contrato novo:
                # ads via `GET /api/gating/status`).
                payload.pop("exibir_publicidade", None)
                cache.set(chave, payload, _ttl_feed())
                return Response(payload)
            except MicroserviceIndisponivelError:
                logger.warning("Microserviço de ingestão indisponível; usando feed local.", exc_info=True)

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
        cache.set(chave, resposta.data, _ttl_feed())
        return resposta


class ClusterDetailView(APIView):
    """Detalhe de um acontecimento coberto por 2+ fontes (`NewsCluster`)."""

    permission_classes = [AllowAny]

    def get(self, request, cluster_id):
        # Frente D — microserviço primeiro quando ativo, com fallback
        # silencioso para o serviço local (mesmo shape de FeedDetalheSerializer).
        if microservice_client.servico_ativo():
            try:
                detalhe_remoto = microservice_client.obter_detalhe_cluster(cluster_id)
                if detalhe_remoto is None:
                    return Response(status=status.HTTP_404_NOT_FOUND)
                dados_remotos = dict(detalhe_remoto)
                dados_remotos.pop("exibir_publicidade", None)
                return Response(dados_remotos)
            except MicroserviceIndisponivelError:
                logger.warning(
                    "Microserviço de ingestão indisponível; usando detalhe de cluster local.",
                    exc_info=True,
                )
        detalhe = services.detalhe_cluster(cluster_id)
        if detalhe is None:
            # Critério de aceite 2 e 8: cluster inexistente OU sem nenhum
            # item publicável (todos pendente/rejeitado) — 404 nos dois
            # casos, sem distinguir (não vaza a existência de conteúdo não
            # aprovado).
            return Response(status=status.HTTP_404_NOT_FOUND)

        return Response(FeedDetalheSerializer(detalhe).data)


class ItemDetailView(APIView):
    """Detalhe de uma notícia standalone (`NewsItem` sem cluster)."""

    permission_classes = [AllowAny]

    def get(self, request, item_id):
        # Frente D — microserviço primeiro quando ativo, com fallback
        # silencioso para o serviço local (mesmo shape de FeedDetalheSerializer).
        if microservice_client.servico_ativo():
            try:
                detalhe_remoto = microservice_client.obter_detalhe_item(item_id)
                if detalhe_remoto is None:
                    return Response(status=status.HTTP_404_NOT_FOUND)
                dados_remotos = dict(detalhe_remoto)
                dados_remotos.pop("exibir_publicidade", None)
                return Response(dados_remotos)
            except MicroserviceIndisponivelError:
                logger.warning(
                    "Microserviço de ingestão indisponível; usando detalhe de item local.",
                    exc_info=True,
                )
        detalhe = services.detalhe_item(item_id)
        if detalhe is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        return Response(FeedDetalheSerializer(detalhe).data)


class UrgentesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            limite = min(12, max(1, int(request.query_params.get("limite", 6))))
        except (TypeError, ValueError):
            limite = 6
        # P1-1 (run 20260923-1216): cache curto por querystring, como nas
        # demais listagens (payload não varia por usuário).
        chave = _chave_cache_listagem(request, "urgentes")
        em_cache = cache.get(chave)
        if em_cache is not None:
            return Response(em_cache)
        # Frente D — microserviço primeiro quando ativo, com fallback
        # silencioso para o serviço local (mesmo shape de FeedEntrySerializer).
        if microservice_client.servico_ativo():
            try:
                dados_remotos = microservice_client.obter_urgentes(limite=limite)
                # O microserviço pode ainda espelhar o contrato antigo com a
                # flag per-user — nunca repassar ao frontend (contrato novo:
                # ads via `GET /api/gating/status`).
                for entrada in dados_remotos:
                    if isinstance(entrada, dict):
                        entrada.pop("exibir_publicidade", None)
                cache.set(chave, dados_remotos, _ttl_feed())
                return Response(dados_remotos)
            except MicroserviceIndisponivelError:
                logger.warning(
                    "Microserviço de ingestão indisponível; usando urgentes locais.",
                    exc_info=True,
                )
        entradas = services.urgentes(limite=limite)
        dados = FeedEntrySerializer(entradas, many=True).data
        cache.set(chave, dados, _ttl_feed())
        return Response(dados)


class MaisLidasView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        limite = min(12, max(1, int(request.query_params.get("limite", 5))))
        chave = _chave_cache_listagem(request, "mais-lidas")
        em_cache = cache.get(chave)
        if em_cache is not None:
            return Response(em_cache)
        entradas = services.mais_lidas(limite=limite)
        dados = FeedEntrySerializer(entradas, many=True).data
        cache.set(chave, dados, _ttl_feed())
        return Response(dados)


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
        chave = _chave_cache_listagem(request, "home")
        em_cache = cache.get(chave)
        if em_cache is not None:
            return Response(em_cache)
        itens = list(services.itens_publicaveis())
        entradas = services.construir_feed_entries(itens)
        secoes = recomendacao.montar_home(entradas, interesses=interesses, regiao=regiao, limite_secao=limite)
        dados = {nome: SecaoHomeSerializer(lista, many=True).data for nome, lista in secoes.items()}
        cache.set(chave, dados, _ttl_feed())
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
        chave = _chave_cache_listagem(request, "destaques")
        em_cache = cache.get(chave)
        if em_cache is not None:
            return Response(em_cache)
        itens = list(services.itens_publicaveis())
        entradas = services.construir_feed_entries(itens)
        destaques = recomendacao.destaques_do_dia(entradas, regiao=regiao, limite=limite)
        dados = SecaoHomeSerializer(destaques, many=True).data
        cache.set(chave, dados, _ttl_feed())
        return Response(dados)


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
            request_id=getattr(request, "request_id", None),
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
        return Response(CoberturaCompletaSerializer(cobertura).data)


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
