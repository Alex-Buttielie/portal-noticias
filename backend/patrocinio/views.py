from django.core.cache import cache
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Patrocinio
from .serializers import PatrocinioAtivoSerializer

# TTL curto: payload não varia por usuário (GET público), cacheável na
# borda do nginx (ver infra/nginx/portal-*.conf, allowlist estendida nesta
# run) e no cache de app, mesmo padrão de `feed/views.py` (TTL de poucos
# segundos — qualquer alteração no admin aparece quase em tempo real, sem
# sobrecarregar o banco a cada impressão).
_TTL_SEGUNDOS = 60
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
            cache.set(chave, {}, _TTL_SEGUNDOS)
            return Response(status=status.HTTP_404_NOT_FOUND)

        dados = PatrocinioAtivoSerializer(patrocinio).data
        cache.set(chave, dados, _TTL_SEGUNDOS)
        return Response(dados)
