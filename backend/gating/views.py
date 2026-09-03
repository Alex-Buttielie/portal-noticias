from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import FeatureLimit
from .serializers import MeusRecursosResponseSerializer


class MeusRecursosView(APIView):
    """
    Critério de aceite 8 (implementation-contract.md run
    20260902-1420-gating-free-premium; spec, user story 2): o usuário sabe
    quais recursos tem disponíveis no plano atual, sem adivinhar. Funciona
    para requisição anônima (tratada como Free — `services.plano_do_usuario`)
    e autenticada, sem exigir login.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        plano = services.plano_do_usuario(request.user)
        chaves = FeatureLimit.objects.values_list("chave", flat=True).distinct().order_by("chave")

        recursos = [
            {
                "chave": chave,
                "valor": services.obter_valor(chave, plano),
                "disponivel": services.has_feature(request.user, chave),
            }
            for chave in chaves
        ]

        serializer = MeusRecursosResponseSerializer({"plano": plano, "recursos": recursos})
        return Response(serializer.data)
