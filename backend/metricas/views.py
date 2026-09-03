from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services


class PainelMetricasView(APIView):
    """Critério de aceite 2 — só admin."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if getattr(request.user, "papel", None) != "admin":
            return Response(status=status.HTTP_403_FORBIDDEN)
        dias = int(request.query_params.get("dias", 30))
        return Response(services.painel(dias))
