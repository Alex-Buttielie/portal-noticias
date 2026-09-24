from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from django.core.cache import cache

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

    Run 20260923-1216-p1-feed-cache-indices (P1-1): UMA única query em
    `FeatureLimit` (antes: ~3N — `plano_do_usuario` + `obter_valor` +
    `has_feature` por chave, cada um com sua leitura da flag premium) +
    cache curto por plano (invalidado em cada escrita nos modelos).
    """

    permission_classes = [AllowAny]

    def get(self, request):
        plano = services.plano_do_usuario(request.user)
        chave_cache = f"{services._CACHE_MEUS_RECURSOS}:{plano}"
        dados = cache.get(chave_cache)
        if dados is None:
            liberado = services.premium_liberado_geral()
            valores = {}
            chaves = []
            for chave, valor_plano, valor in FeatureLimit.objects.order_by("chave").values_list(
                "chave", "plano", "valor"
            ):
                if chave not in valores:
                    valores[chave] = {}
                    chaves.append(chave)
                valores[chave][valor_plano] = valor
            recursos = [
                {
                    "chave": chave,
                    "valor": valores[chave].get(plano),
                    "disponivel": True
                    if liberado
                    else (valores[chave].get(plano) or "").strip().lower()
                    in services._VALORES_VERDADEIROS,
                }
                for chave in chaves
            ]
            dados = MeusRecursosResponseSerializer({"plano": plano, "recursos": recursos}).data
            cache.set(chave_cache, dados, services._ttl_gating())
        return Response(dados)


class StatusSistemaView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"premium_ativo": services.premium_ativo()})
