from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services


class IndicesView(APIView):
    """
    GET /api/mercado/indices/ — cotações dos índices (ver `services.INDICES`).
    Público. Sem `BRAPI_API_KEY` configurada, devolve 204 (recurso
    desligado, não erro) — o frontend esconde o widget nesse caso, mesmo
    padrão do `AdsSlot` sem publisher ID.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        if not services.habilitado():
            return Response(status=status.HTTP_204_NO_CONTENT)
        try:
            indices = services.obter_indices()
        except services.ServicoMercadoIndisponivelError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"indices": indices}, status=status.HTTP_200_OK)
