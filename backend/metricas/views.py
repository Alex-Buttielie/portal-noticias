from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import EventoSite
from .services_inteligencia import central_inteligencia


class PainelMetricasView(APIView):
    """Critério de aceite 2 — só admin."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if getattr(request.user, "papel", None) != "admin":
            return Response(status=status.HTTP_403_FORBIDDEN)
        dias = int(request.query_params.get("dias", 30))
        return Response(services.painel(dias))


# ---------------------------------------------------------------------------
# FRENTE 6 — Central de Inteligência: ingestão de eventos + painel agregado.
# ---------------------------------------------------------------------------

# Tipos roteados para os modelos do feed (FRENTE 3 — fonte única do sinal
# por notícia/busca, sem duplicar contadores). O resto vai para EventoSite.
_ROTA_FEED = {"news_view", "news_click", "share", "save", "search", "search_result_click"}
_TIPOS_FEED_VALIDOS = {"view", "click", "read", "save", "unsave", "share", "search_click"}
_MAPA_TIPO_FEED = {
    "news_view": "view",
    "news_click": "click",
    "share": "share",
    "save": "save",
    "search_result_click": "search_click",
}
_ORIGENS_VALIDAS = {c[0] for c in EventoSite.ORIGEM_CHOICES}


def _usuario_ou_none(request):
    u = getattr(request, "user", None)
    if u is not None and getattr(u, "is_authenticated", False):
        return u
    return None


def _texto(valor, limite=500):
    if valor is None:
        return ""
    return str(valor)[:limite]


class EventoIngestaoView(APIView):
    """POST /api/metricas/eventos/ — público (tracking respeita o
    consentimento no navegador; ver `frontend/lib/analytics.ts`).

    Nunca quebra a navegação: falha de tracking devolve 202 com
    `registrado: False` em vez de 500.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        dados = request.data if isinstance(request.data, dict) else {}
        tipo = _texto(dados.get("tipo"), 40).strip()
        if not tipo:
            return Response({"detail": "Informe tipo."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            if tipo in _ROTA_FEED:
                registrado = self._rotear_feed(request, tipo, dados)
            elif tipo in EventoSite.TIPOS_VALIDOS:
                registrado = self._registrar_site(request, tipo, dados)
            else:
                return Response(
                    {"detail": f"Tipo desconhecido: {tipo}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response({"registrado": registrado}, status=status.HTTP_201_CREATED)
        except Exception:
            return Response({"registrado": False}, status=status.HTTP_202_ACCEPTED)

    def _base_sessao(self, dados):
        return _texto(dados.get("sessao"), 64)

    def _registrar_site(self, request, tipo, dados) -> bool:
        origem = _texto(dados.get("origem"), 20).strip()
        try:
            EventoSite.objects.create(
                user=_usuario_ou_none(request),
                sessao=self._base_sessao(dados),
                tipo=tipo,
                path=_texto(dados.get("path"), 500),
                categoria=_texto(dados.get("categoria"), 100),
                autor_ref=_texto(dados.get("autor_ref") or dados.get("autor"), 200),
                secao_home=_texto(dados.get("secao_home") or dados.get("secao"), 60),
                origem=origem if origem in _ORIGENS_VALIDAS else "",
                dispositivo=_texto(dados.get("dispositivo"), 20),
                pais=_texto(dados.get("pais"), 100),
                estado=_texto(dados.get("estado"), 100),
                cidade=_texto(dados.get("cidade"), 150),
                regiao=_texto(dados.get("regiao"), 150),
                tempo_permanencia_seg=max(0, int(dados.get("tempo_permanencia_seg") or 0)),
                scroll_max_pct=min(100, max(0, int(dados.get("scroll_max_pct") or 0))),
                extra=dados.get("extra") if isinstance(dados.get("extra"), dict) else {},
            )
            return True
        except Exception:
            return False

    def _rotear_feed(self, request, tipo, dados) -> bool:
        """Roteia para `feed` (fonte única). `search` usa `busca.registrar_busca`."""
        try:
            from feed import busca as busca_services
            from feed.models import InteracaoNoticia

            user = _usuario_ou_none(request)
            sessao = self._base_sessao(dados)
            if tipo == "search":
                busca_services.registrar_busca(
                    _texto(dados.get("termo") or dados.get("query"), 300),
                    int(dados.get("resultados") or 0),
                    user=user,
                    session_key=sessao,
                    filtros=dados.get("filtros") if isinstance(dados.get("filtros"), dict) else {},
                )
                return True
            entry_tipo = _texto(dados.get("entry_tipo"), 10).strip() or "item"
            if entry_tipo not in ("item", "cluster"):
                entry_tipo = "item"
            try:
                entry_id = int(dados.get("entry_id") or dados.get("id") or 0)
            except (TypeError, ValueError):
                return False
            if entry_id <= 0:
                return False
            if tipo == "search_result_click":
                busca_services.registrar_clique_resultado(
                    entry_tipo, entry_id,
                    query=_texto(dados.get("termo") or dados.get("query"), 300),
                    user=user, session_key=sessao,
                    tempo_leitura_seg=max(0, int(dados.get("tempo_leitura_seg") or 0)),
                )
                return True
            tipo_feed = _MAPA_TIPO_FEED.get(tipo)
            if tipo_feed not in _TIPOS_FEED_VALIDOS:
                return False
            from catalogo_noticias.models import NewsCluster, NewsItem

            kwargs: dict = {
                "tipo": tipo_feed,
                "entry_tipo": entry_tipo,
                "user": user,
                "session_key": sessao,
                "categoria": _texto(dados.get("categoria"), 100),
                "tempo_leitura_seg": max(0, int(dados.get("tempo_leitura_seg") or 0)),
                "query": "",
            }
            if entry_tipo == "cluster":
                obj = NewsCluster.objects.filter(pk=entry_id).first()
                if obj is None:
                    return False
                kwargs["cluster"] = obj
                if not kwargs["categoria"]:
                    primeiro = obj.itens.order_by("-timestamp_ingestao").first()
                    kwargs["categoria"] = (obj.categoria_dominante or (primeiro.categoria if primeiro else ""))[:100]
            else:
                obj = NewsItem.objects.filter(pk=entry_id).first()
                if obj is None:
                    return False
                kwargs["item"] = obj
                if not kwargs["categoria"]:
                    kwargs["categoria"] = (obj.categoria or "")[:100]
            InteracaoNoticia.objects.create(**kwargs)
            return True
        except Exception:
            return False


class CentralInteligenciaView(APIView):
    """GET /api/metricas/inteligencia/ — só admin.

    Params: `periodo` = hoje|ontem|7d|30d|90d|custom (+ `inicio`/`fim`
    YYYY-MM-DD quando custom). O comparativo com o período anterior vem
    embutido no payload.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if getattr(request.user, "papel", None) != "admin":
            return Response(status=status.HTTP_403_FORBIDDEN)
        return Response(
            central_inteligencia(
                periodo=request.query_params.get("periodo", "30d"),
                inicio=request.query_params.get("inicio"),
                fim=request.query_params.get("fim"),
            )
        )

