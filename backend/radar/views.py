from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from gating.services import has_feature
from config.throttling import EnderecosAnonThrottle

from . import services


def _float_ou_none(valor):
    """Converte `lat`/`lon` da query string — `None` quando ausente/
    inválido, nunca estoura (coordenada ausente é um caso normal, não
    erro: o Radar cai para ordenação por recência)."""
    if valor in (None, ""):
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


class TendenciasView(APIView):
    """Critérios de aceite 1, 2, 4 — público.

    R-02: `estado` substitui `cidade` (nunca populada pela ingestão real) —
    aceita texto livre, resolvido para UF via `enderecos`. `lat`/`lon`
    opcionais ordenam por distância Haversine crescente até a UF; sem eles,
    mantém a ordenação por score/volume (comportamento atual).
    """

    permission_classes = [AllowAny]
    throttle_classes = [EnderecosAnonThrottle]

    def get(self, request):
        dados = services.tendencias(
            pais=request.query_params.get("pais"),
            estado=request.query_params.get("estado"),
            lat=_float_ou_none(request.query_params.get("lat")),
            lon=_float_ou_none(request.query_params.get("lon")),
        )
        return Response(dados)


class EvolucaoView(APIView):
    """Critério de aceite 3/6 — recurso avançado, gated por `radar_avancado`.

    R-02: `estado` substitui `cidade` — mesma resolução de texto livre do
    `TendenciasView`. A série é agregada por dia (sem item individual), por
    isso não há "distância" aplicável aqui — ver `NoticiasView` para a
    ordenação por proximidade de itens de verdade.

    code-review-contract.md (Finding 1): esta view também resolve `estado`
    como texto livre (mesmo caminho de código/egress ao Nominatim), mas,
    diferente de `TendenciasView`/`NoticiasView`, NÃO é `AllowAny` — exige
    `IsAuthenticated` + `has_feature(..., "radar_avancado")` (checado ANTES
    de chamar `services.evolucao_interesse`), então só usuário autenticado
    Premium chega ao código que resolve localidade. `EnderecosAnonThrottle`
    (base `AnonRateThrottle`) não teria efeito aqui — o DRF não aplica
    throttle de `AnonRateThrottle` a requisições autenticadas —, então
    anexá-la seria um no-op; criar uma classe de `UserRateThrottle`
    dedicada para este caso não foi pedida pelo finding e extrapolaria o
    escopo da correção.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_feature(request.user, "radar_avancado"):
            return Response(
                {"detail": "Evolução de tendências é um recurso Premium."},
                status=status.HTTP_403_FORBIDDEN,
            )
        dados = services.evolucao_interesse(
            categoria=request.query_params.get("categoria"),
            pais=request.query_params.get("pais"),
            estado=request.query_params.get("estado"),
        )
        return Response(dados)


class NoticiasView(APIView):
    """R-03 — grid de notícias do Radar (foto + título + UF + tempo +
    categoria), com filtros de categoria/UF/período + busca textual.
    Público; distância calculada quando `lat`/`lon` do usuário vierem
    (R-02) — sem eles, ordena por recência."""

    permission_classes = [AllowAny]
    throttle_classes = [EnderecosAnonThrottle]

    def get(self, request):
        try:
            limite = min(60, max(1, int(request.query_params.get("limite", 30))))
        except (TypeError, ValueError):
            limite = 30
        try:
            periodo_dias = min(90, max(1, int(request.query_params.get("periodo_dias", 30))))
        except (TypeError, ValueError):
            periodo_dias = 30
        dados = services.noticias_regionais(
            pais=request.query_params.get("pais"),
            estado=request.query_params.get("estado"),
            categoria=request.query_params.get("categoria"),
            busca=request.query_params.get("busca"),
            periodo_dias=periodo_dias,
            lat=_float_ou_none(request.query_params.get("lat")),
            lon=_float_ou_none(request.query_params.get("lon")),
            limite=limite,
        )
        return Response(dados)


class LocalidadesSalvasView(APIView):
    """Critério de aceite 5."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        localidades = services.localidades_salvas(request.user)
        return Response(
            [{"pais": loc.pais, "estado": loc.estado, "cidade": loc.cidade} for loc in localidades]
        )

    def post(self, request):
        obj = services.salvar_localidade(
            request.user,
            pais=request.data.get("pais", ""),
            estado=request.data.get("estado", ""),
            cidade=request.data.get("cidade", ""),
        )
        return Response({"id": obj.id}, status=status.HTTP_201_CREATED)

    def delete(self, request):
        services.remover_localidade(
            request.user,
            pais=request.data.get("pais", ""),
            estado=request.data.get("estado", ""),
            cidade=request.data.get("cidade", ""),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ParaVoceRegionalView(APIView):
    """FRENTE 3 — Radar com a mesma lógica da Home + localização autorizada
    (explícita na query ou salva pelo usuário) + tendências regionais."""

    permission_classes = [AllowAny]

    def get(self, request):
        from feed.serializers import SecaoHomeSerializer

        try:
            limite = min(10, max(1, int(request.query_params.get("limite", 6))))
        except (TypeError, ValueError):
            limite = 6
        dados = services.para_voce_regional(
            user=request.user,
            pais=request.query_params.get("pais"),
            estado=request.query_params.get("estado"),
            cidade=request.query_params.get("cidade"),
            limite=limite,
        )
        dados["secoes"] = {
            nome: SecaoHomeSerializer(lista, many=True).data
            for nome, lista in dados["secoes"].items()
        }
        return Response(dados)
