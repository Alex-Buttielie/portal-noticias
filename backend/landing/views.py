from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from config.throttling import EscritaPublicaAnonThrottle

from .models import InscricaoListaEspera
from .serializers import InscricaoListaEsperaSerializer


class ListaEsperaView(APIView):
    """Critérios de aceite 1, 2, 4 — público, sem autenticação."""

    permission_classes = [AllowAny]
    # Rate limiting (implementation-contract.md run
    # 20260903-1134-seo-lgpd-design-system, escopo C): endpoint público de
    # escrita explicitamente listado no contrato.
    throttle_classes = [EscritaPublicaAnonThrottle]

    def post(self, request):
        serializer = InscricaoListaEsperaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data

        _, criado = InscricaoListaEspera.inscrever(
            nome=dados["nome"],
            email=dados["email"],
            interesses=dados.get("interesses", []),
            localidade=dados.get("localidade", ""),
            canal_preferido=dados.get("canal_preferido", ""),
            aceite=dados["aceite_comunicacao"],
        )
        if not criado:
            return Response({"detail": "Este e-mail já está na lista de espera."}, status=status.HTTP_200_OK)
        return Response({"detail": "Cadastro na lista de espera realizado."}, status=status.HTTP_201_CREATED)
