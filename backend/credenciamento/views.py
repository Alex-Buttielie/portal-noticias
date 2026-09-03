from django.http import FileResponse, Http404
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import PerfilJornalista, SolicitacaoCredenciamento
from .serializers import PerfilJornalistaSerializer, SolicitacaoCredenciamentoSerializer
from .services import solicitar


class SolicitarCredenciamentoView(APIView):
    """POST /api/credenciamento/solicitar/ — critério de aceite 1."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        ja_tem_pendente = SolicitacaoCredenciamento.objects.filter(
            user=request.user,
            status__in=[
                SolicitacaoCredenciamento.STATUS_PENDENTE,
                SolicitacaoCredenciamento.STATUS_INFO_SOLICITADA,
            ],
        ).exists()
        if ja_tem_pendente:
            return Response(
                {"detail": "Você já tem uma solicitação de credenciamento em análise."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SolicitacaoCredenciamentoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        solicitacao = solicitar(request.user, **serializer.validated_data)
        return Response(
            SolicitacaoCredenciamentoSerializer(solicitacao).data, status=status.HTTP_201_CREATED
        )


class MinhaSolicitacaoView(APIView):
    """GET /api/credenciamento/minha-solicitacao/ — critério de aceite 4."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        solicitacao = (
            SolicitacaoCredenciamento.objects.filter(user=request.user).order_by("-criado_em").first()
        )
        if solicitacao is None:
            return Response({"detail": "Nenhuma solicitação encontrada."}, status=status.HTTP_404_NOT_FOUND)
        return Response(SolicitacaoCredenciamentoSerializer(solicitacao).data)


class DocumentoView(APIView):
    """
    GET /api/credenciamento/solicitacoes/<id>/documento/ — critério de
    aceite 5: só o próprio solicitante ou um admin (`papel=admin`) pode
    baixar o documento. Nunca servido via URL estática pública.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, solicitacao_id):
        try:
            solicitacao = SolicitacaoCredenciamento.objects.get(pk=solicitacao_id)
        except SolicitacaoCredenciamento.DoesNotExist:
            raise Http404

        eh_dono = solicitacao.user_id == request.user.id
        eh_admin = getattr(request.user, "papel", None) == "admin"
        if not (eh_dono or eh_admin):
            return Response(status=status.HTTP_403_FORBIDDEN)

        if not solicitacao.documento:
            raise Http404
        return FileResponse(solicitacao.documento.open("rb"))


class MeuPerfilView(APIView):
    """
    GET/PATCH /api/credenciamento/meu-perfil/ — BRD §14, "Gerenciar perfil
    profissional". Só existe (200 no GET) para quem já foi aprovado — sem
    `PerfilJornalista`, é 404 nos dois métodos.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        perfil = PerfilJornalista.objects.filter(user=request.user).first()
        if perfil is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(PerfilJornalistaSerializer(perfil).data)

    def patch(self, request):
        serializer = PerfilJornalistaSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            perfil = services.atualizar_perfil(request.user, **serializer.validated_data)
        except services.PerfilInexistenteError:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(PerfilJornalistaSerializer(perfil).data)
