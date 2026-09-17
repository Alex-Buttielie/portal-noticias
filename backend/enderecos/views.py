from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from config.throttling import EnderecosAnonThrottle

from . import services


def _erro(exc: Exception):
    if isinstance(exc, services.EnderecoInvalidoError):
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, services.CepNaoEncontradoError):
        return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
    return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


class CepView(APIView):
    """GET /api/enderecos/cep/<cep>/ — público, cache 24h, throttle."""

    permission_classes = [AllowAny]
    throttle_classes = [EnderecosAnonThrottle]

    def get(self, request, cep: str):
        try:
            return Response(services.consultar_cep(cep))
        except Exception as exc:  # noqa: BLE001 — mapeamento intencional p/ HTTP
            return _erro(exc)


class BuscaEnderecoView(APIView):
    """GET /api/enderecos/busca/?uf=SP&cidade=...&logradouro=... — público."""

    permission_classes = [AllowAny]
    throttle_classes = [EnderecosAnonThrottle]

    def get(self, request):
        try:
            dados = services.buscar_por_endereco(
                request.query_params.get("uf", ""),
                request.query_params.get("cidade", ""),
                request.query_params.get("logradouro", ""),
            )
            return Response(dados)
        except Exception as exc:  # noqa: BLE001 — mapeamento intencional p/ HTTP
            return _erro(exc)


class EstadosView(APIView):
    """GET /api/enderecos/estados/ — público, cache 7 dias."""

    permission_classes = [AllowAny]
    throttle_classes = [EnderecosAnonThrottle]

    def get(self, request):
        try:
            return Response(services.listar_estados())
        except Exception as exc:  # noqa: BLE001 — mapeamento intencional p/ HTTP
            return _erro(exc)


class MunicipiosView(APIView):
    """GET /api/enderecos/estados/<uf>/municipios/ — público, cache 7 dias."""

    permission_classes = [AllowAny]
    throttle_classes = [EnderecosAnonThrottle]

    def get(self, request, uf: str):
        try:
            return Response(services.listar_municipios(uf))
        except Exception as exc:  # noqa: BLE001 — mapeamento intencional p/ HTTP
            return _erro(exc)
