from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .limites import CotaDeCriteriosExcedidaError, cota_de_criterios, remanescente
from .models import CriterioMonitoramento, MembroOrganizacao
from .permissions import PermissaoNegadaError, exigir
from .serializers import CriterioMonitoramentoSerializer, MembroOrganizacaoSerializer

User = get_user_model()

# Resposta única e neutra para TODA falha de convite (e-mail não cadastrado /
# usuário já pertence a outra organização). Ver `MembrosView.post`.
_CONVITE_NAO_CONCLUIDO = (
    "Não foi possível concluir o convite. Confirme que o e-mail pertence a um "
    "usuário já cadastrado na plataforma e que esse usuário ainda não pertence "
    "a uma organização."
)


class _BaseOrganizacaoView(APIView):
    """
    Toda view B2B deriva a organização SEMPRE de `services.organizacao_do_usuario`
    (critério de aceite 5) — nunca de um id na URL/payload.

    `_organizacao_ou_erro` é também a autorização de leitura
    (`ver_painel`/`ver_membros` da matriz de `b2b/permissions.py`): se a
    organização do usuário é resolvida a partir de um `MembroOrganizacao`, ele
    é membro dela, por definição. Por isso as rotas de LEITURA não repetem
    `_exigir_acao` — seria um segundo `if erro: return erro` inalcançável.
    `_exigir_acao` fica nas rotas de ESCRITA, onde a distinção admin/membro
    existe de verdade.
    """

    permission_classes = [IsAuthenticated]

    def _organizacao_ou_erro(self, request):
        organizacao = services.organizacao_do_usuario(request.user)
        if organizacao is None:
            return None, Response(
                {"detail": "Usuário não pertence a nenhuma organização."}, status=status.HTTP_403_FORBIDDEN
            )
        return organizacao, None

    def _exigir_acao(self, request, organizacao, acao):
        """
        Guarda de papel no início do handler, ANTES de qualquer leitura ou
        escrita. É o que impede o vazamento por diferença de resposta: com a
        checagem no fim, um membro sem permissão ainda recebia respostas
        distintas para "e-mail não existe" / "e-mail já pertence a outra
        organização" antes de tomar 403.
        """
        try:
            exigir(request.user, organizacao, acao)
        except PermissaoNegadaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return None


class CriteriosView(_BaseOrganizacaoView):
    def get(self, request):
        organizacao, erro = self._organizacao_ou_erro(request)
        if erro:
            return erro
        # `organizacao.criterios.all()` — a relação reversa já carrega o
        # filtro de tenant; não existe `CriterioMonitoramento.objects` neste
        # caminho. `ativo=False` também volta aqui de propósito: quem
        # desativou um critério precisa vê-lo para reativar/excluir.
        return Response(CriterioMonitoramentoSerializer(organizacao.criterios.all(), many=True).data)

    def post(self, request):
        organizacao, erro = self._organizacao_ou_erro(request)
        if erro:
            return erro
        erro = self._exigir_acao(request, organizacao, "criar_criterio")
        if erro:
            return erro
        serializer = CriterioMonitoramentoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            criterio = services.criar_criterio(
                organizacao, serializer.validated_data["tipo"], serializer.validated_data["valor"]
            )
        except CotaDeCriteriosExcedidaError as exc:
            # A mensagem carrega plano/teto/usado e a saída — o cliente sabe
            # o que fazer. Os campos vão junto para o frontend conseguir
            # desenhar "3/5 critérios" sem outra chamada. Ver `b2b/limites.py`.
            return Response(
                {
                    "detail": str(exc),
                    "cota_criterios": cota_de_criterios(organizacao),
                    "criterios_ativos": len(organizacao.criterios.all()),
                    "criterios_remanescentes": remanescente(organizacao),
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(CriterioMonitoramentoSerializer(criterio).data, status=status.HTTP_201_CREATED)


class CriterioDetailView(_BaseOrganizacaoView):
    def delete(self, request, criterio_id):
        organizacao, erro = self._organizacao_ou_erro(request)
        if erro:
            return erro
        erro = self._exigir_acao(request, organizacao, "excluir_criterio")
        if erro:
            return erro
        # `organizacao.criterios.get(pk=...)`: o escopo é a PRIMEIRA cláusula.
        # Um id de outra organização cai no DoesNotExist e vira 404 — o mesmo
        # corpo (vazio) de um id que nunca existiu, então a resposta não diz
        # se o recurso existe em outro tenant.
        try:
            criterio = organizacao.criterios.get(pk=criterio_id)
        except CriterioMonitoramento.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        criterio.delete()
        services.invalidar_cache_da_organizacao(organizacao)
        return Response(status=status.HTTP_204_NO_CONTENT)


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
        # Papel PRIMEIRO. Antes, a busca por e-mail vinha antes da checagem de
        # papel (a guarda vivia dentro de `services.adicionar_membro`), e um
        # membro comum recebia 404 / 409 / 403 — três respostas distinguíveis
        # que juntos diziam, para qualquer membro de qualquer empresa, se um
        # e-mail arbitrário está cadastrado na plataforma e se ele já pertence
        # a alguma organização. Era um oráculo de enumeração de contas
        # cross-tenant, e não só um problema de papel.
        erro = self._exigir_acao(request, organizacao, "convidar_membro")
        if erro:
            return erro
        email = (request.data.get("email") or "").strip()
        if not email:
            return Response({"detail": "E-mail é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            usuario_convidado = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({"detail": _CONVITE_NAO_CONCLUIDO}, status=status.HTTP_400_BAD_REQUEST)
        if MembroOrganizacao.objects.filter(user=usuario_convidado).exists():
            # `MembroOrganizacao.user` é OneToOne (um usuário, uma
            # organização): este é um atributo GLOBAL da plataforma, e a
            # resposta precisa ser indistinguível da linha anterior.
            return Response({"detail": _CONVITE_NAO_CONCLUIDO}, status=status.HTTP_400_BAD_REQUEST)
        papel = request.data.get("papel_na_organizacao", MembroOrganizacao.PAPEL_MEMBRO)
        try:
            membro = services.adicionar_membro(
                organizacao, usuario_convidado, quem_adiciona=request.user, papel_na_organizacao=papel
            )
        except PermissaoNegadaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(MembroOrganizacaoSerializer(membro).data, status=status.HTTP_201_CREATED)

    def delete(self, request):
        organizacao, erro = self._organizacao_ou_erro(request)
        if erro:
            return erro
        erro = self._exigir_acao(request, organizacao, "remover_membro")
        if erro:
            return erro
        email = (request.data.get("email") or "").strip()
        try:
            usuario_alvo = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(status=status.HTTP_204_NO_CONTENT)
        try:
            services.remover_membro(organizacao, usuario_alvo, quem_remove=request.user)
        except PermissaoNegadaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(status=status.HTTP_204_NO_CONTENT)
