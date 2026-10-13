from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Patrocinio
from .serializers import PatrocinioAtivoSerializer


def _ttl_patrocinio() -> int:
    """
    TTL curto: payload não varia por usuário (GET público), cacheável na
    borda do nginx (ver infra/nginx/portal-*.conf, allowlist estendida
    nesta run) e no cache de app, MESMO TTL do cache de `feed/views.py`
    (`settings.FEED_CACHE_TTL_SEGUNDOS`, 45s) — mesma zona/regra de cache
    de borda do nginx usada pelas duas rotas, então os dois TTLs de app
    precisam estar alinhados para o pior caso de defasagem ser o mesmo
    (~45-90s, não ~105s). Remediação do Finding 3 (nit) do
    code-review-contract.md desta run: o valor anterior (60s, literal
    próprio) dizia no comentário "mesmo desenho" de `feed/views.py` mas
    usava um número diferente — agora lê a mesma constante.
    """
    try:
        return max(1, int(getattr(settings, "FEED_CACHE_TTL_SEGUNDOS", 45)))
    except (TypeError, ValueError):
        return 45


CACHE_NAMESPACE = "patrocinio:v1"


class PatrocinioAtivoView(APIView):
    """
    GET /api/patrocinio/ativo/?posicao=<posicao> — público.

    Dado um `Patrocinio` com `ativo=True` e hoje dentro de
    `[data_inicio, data_fim]` para a posição pedida, devolve esse registro.
    Fora do intervalo, `ativo=False`, ou nenhum patrocínio cadastrado para
    a posição: 404 (vazio) — nunca inventa um patrocínio.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        posicao = (request.query_params.get("posicao") or "").strip()
        if not posicao:
            return Response({"detail": "Informe posicao."}, status=status.HTTP_400_BAD_REQUEST)

        chave = f"{CACHE_NAMESPACE}:ativo:{posicao}"
        em_cache = cache.get(chave)
        if em_cache is not None:
            return Response(em_cache) if em_cache != {} else Response(status=status.HTTP_404_NOT_FOUND)

        patrocinio = Patrocinio.vigente_para_posicao(posicao)
        if patrocinio is None:
            cache.set(chave, {}, _ttl_patrocinio())
            return Response(status=status.HTTP_404_NOT_FOUND)

        dados = PatrocinioAtivoSerializer(patrocinio).data
        cache.set(chave, dados, _ttl_patrocinio())
        return Response(dados)
