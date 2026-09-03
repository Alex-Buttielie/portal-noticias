from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import InscricaoNewsletter


class InscreverView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tipo = request.data.get("tipo", InscricaoNewsletter.TIPO_PADRAO)
        categorias = request.data.get("categorias", [])
        periodo = request.data.get("periodo")
        try:
            inscricao = services.inscrever(request.user, tipo, categorias, periodo=periodo)
        except services.RecursoGatedError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(
            {"tipo": inscricao.tipo, "periodo": inscricao.periodo, "ativa": inscricao.ativa},
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request):
        services.cancelar_inscricao(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DescadastrarView(APIView):
    """Critério de aceite 4 — sem exigir login."""

    permission_classes = [AllowAny]

    def post(self, request):
        token = request.query_params.get("token") or request.data.get("token")
        if not token or not services.descadastrar_por_token(token):
            return Response({"detail": "Token inválido."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Descadastro realizado."})
