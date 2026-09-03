from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import AcaoModeracao, Denuncia, PaginaEditorial
from .permissions import IsModeradorOuAdmin
from .serializers import (
    AcaoModeracaoSerializer,
    DenunciaSerializer,
    PaginaEditorialSerializer,
    RecursoModeracaoSerializer,
)


class FilaModeracaoView(APIView):
    """Critério de aceite 2 — só moderador/admin."""

    permission_classes = [IsModeradorOuAdmin]

    def get(self, request):
        return Response(DenunciaSerializer(services.fila_de_moderacao(), many=True).data)


class ResolverDenunciaView(APIView):
    """Critério de aceite 3."""

    permission_classes = [IsModeradorOuAdmin]

    def post(self, request, denuncia_id):
        try:
            denuncia = Denuncia.objects.get(pk=denuncia_id)
        except Denuncia.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        procedente = bool(request.data.get("procedente"))
        motivo = request.data.get("motivo", "")
        denuncia = services.resolver_denuncia(denuncia, request.user, procedente, motivo)
        return Response(DenunciaSerializer(denuncia).data)


class AplicarAcaoView(APIView):
    """Critério de aceite 4/6 — só moderador/admin, sempre com decisor humano explícito (request.user)."""

    permission_classes = [IsModeradorOuAdmin]

    def post(self, request):
        serializer = AcaoModeracaoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data
        acao = services.aplicar_acao(
            dados["usuario_alvo"],
            dados["tipo"],
            dados["motivo"],
            request.user,
            ativo_ate=dados.get("ativo_ate"),
            denuncia=dados.get("denuncia_relacionada"),
        )
        return Response(AcaoModeracaoSerializer(acao).data, status=status.HTTP_201_CREATED)


class CriarRecursoView(APIView):
    """Critério de aceite 5 — o próprio usuário moderado contesta."""

    permission_classes = [IsAuthenticated]

    def post(self, request, acao_id):
        try:
            acao = AcaoModeracao.objects.get(pk=acao_id, usuario_alvo=request.user)
        except AcaoModeracao.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        texto = request.data.get("texto", "")
        recurso = services.criar_recurso(acao, request.user, texto)
        return Response(RecursoModeracaoSerializer(recurso).data, status=status.HTTP_201_CREATED)


class PaginaEditorialView(APIView):
    """Critério de aceite 7 — pública."""

    permission_classes = [AllowAny]

    def get(self, request, slug):
        try:
            pagina = PaginaEditorial.objects.get(slug=slug)
        except PaginaEditorial.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(PaginaEditorialSerializer(pagina).data)


class MinhaReputacaoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reputacao = services.obter_reputacao(request.user)
        return Response({"pontuacao": reputacao.pontuacao, "nivel": reputacao.nivel})
