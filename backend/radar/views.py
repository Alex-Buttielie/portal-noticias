from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from gating.services import has_feature

from . import services


class TendenciasView(APIView):
    """Critérios de aceite 1, 2, 4 — público."""

    permission_classes = [AllowAny]

    def get(self, request):
        dados = services.tendencias(
            pais=request.query_params.get("pais"),
            estado=request.query_params.get("estado"),
            cidade=request.query_params.get("cidade"),
        )
        return Response(dados)


class EvolucaoView(APIView):
    """Critério de aceite 3/6 — recurso avançado, gated por `radar_avancado`."""

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
            cidade=request.query_params.get("cidade"),
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
