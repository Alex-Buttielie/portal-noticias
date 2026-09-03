from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import CriterioMonitoramento, MembroOrganizacao
from .serializers import CriterioMonitoramentoSerializer, MembroOrganizacaoSerializer

User = get_user_model()


class _BaseOrganizacaoView(APIView):
    """
    Toda view B2B deriva a organização SEMPRE de `services.organizacao_do_usuario`
    (critério de aceite 5) — nunca de um id na URL/payload.
    """

    permission_classes = [IsAuthenticated]

    def _organizacao_ou_erro(self, request):
        organizacao = services.organizacao_do_usuario(request.user)
        if organizacao is None:
            return None, Response(
                {"detail": "Usuário não pertence a nenhuma organização."}, status=status.HTTP_403_FORBIDDEN
            )
        return organizacao, None


class CriteriosView(_BaseOrganizacaoView):
    def get(self, request):
        organizacao, erro = self._organizacao_ou_erro(request)
        if erro:
            return erro
        return Response(CriterioMonitoramentoSerializer(organizacao.criterios.all(), many=True).data)

    def post(self, request):
        organizacao, erro = self._organizacao_ou_erro(request)
        if erro:
            return erro
        serializer = CriterioMonitoramentoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        criterio = services.criar_criterio(
            organizacao, serializer.validated_data["tipo"], serializer.validated_data["valor"]
        )
        return Response(CriterioMonitoramentoSerializer(criterio).data, status=status.HTTP_201_CREATED)


class ItensMonitoradosView(_BaseOrganizacaoView):
    def get(self, request):
        organizacao, erro = self._organizacao_ou_erro(request)
        if erro:
            return erro
        return Response(services.itens_monitorados(organizacao))


class ResumoExecutivoView(_BaseOrganizacaoView):
    def get(self, request):
        organizacao, erro = self._organizacao_ou_erro(request)
        if erro:
            return erro
        return Response(services.resumo_executivo(organizacao))


class MembrosView(_BaseOrganizacaoView):
    """Critério de aceite 2/6 — admin da organização convida/remove membros."""

    def get(self, request):
        organizacao, erro = self._organizacao_ou_erro(request)
        if erro:
            return erro
        return Response(MembroOrganizacaoSerializer(organizacao.membros.all(), many=True).data)

    def post(self, request):
        organizacao, erro = self._organizacao_ou_erro(request)
        if erro:
            return erro
        email = (request.data.get("email") or "").strip()
        if not email:
            return Response({"detail": "E-mail é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            usuario_convidado = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "Não existe usuário cadastrado com esse e-mail."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if MembroOrganizacao.objects.filter(user=usuario_convidado).exists():
            return Response(
                {"detail": "Este usuário já pertence a uma organização."},
                status=status.HTTP_409_CONFLICT,
            )
        papel = request.data.get("papel_na_organizacao", MembroOrganizacao.PAPEL_MEMBRO)
        try:
            membro = services.adicionar_membro(
                organizacao, usuario_convidado, quem_adiciona=request.user, papel_na_organizacao=papel
            )
        except services.PermissaoNegadaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(MembroOrganizacaoSerializer(membro).data, status=status.HTTP_201_CREATED)

    def delete(self, request):
        organizacao, erro = self._organizacao_ou_erro(request)
        if erro:
            return erro
        email = (request.data.get("email") or "").strip()
        try:
            usuario_alvo = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(status=status.HTTP_204_NO_CONTENT)
        try:
            services.remover_membro(organizacao, usuario_alvo, quem_remove=request.user)
        except services.PermissaoNegadaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(status=status.HTTP_204_NO_CONTENT)
