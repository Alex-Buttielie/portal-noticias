from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.throttling import DenunciaUserThrottle, EscritaPublicaAnonThrottle
from credenciamento.services import pode_publicar

from . import services
from .models import Comentario, Publicacao, Seguidor
from .serializers import ComentarioSerializer, PublicacaoSerializer

User = get_user_model()


class PublicacoesListCreateView(APIView):
    permission_classes = [AllowAny]

    def get_throttles(self):
        # Rate limiting (implementation-contract.md run
        # 20260903-1134-seo-lgpd-design-system, escopo C): só a ESCRITA
        # (POST — "criação de post em comunidade" listada explicitamente no
        # contrato) é limitada; GET é a listagem pública lida com frequência
        # normal de navegação e não deve ser throttled por esta regra.
        if self.request.method == "POST":
            return [EscritaPublicaAnonThrottle()]
        return []

    def get(self, request):
        qs = Publicacao.objects.filter(status=Publicacao.STATUS_PUBLICADO, oculto=False)
        if request.query_params.get("destaque"):
            qs = qs.filter(destaque=True)
        autor_id = request.query_params.get("autor")
        if autor_id:
            qs = qs.filter(autor_id=autor_id)
        return Response(PublicacaoSerializer(qs, many=True).data)

    def post(self, request):
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        serializer = PublicacaoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            publicacao = services.criar_rascunho(request.user, **serializer.validated_data)
        except services.PermissaoNegadaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(PublicacaoSerializer(publicacao).data, status=status.HTTP_201_CREATED)


class PublicacaoDetailView(APIView):
    """
    GET /api/comunidade/publicacoes/<id>/ — lacuna encontrada ao montar a
    tela de detalhe do frontend (run 20260902-frontend-comunidade-credenciamento):
    só existia listagem, sem endpoint de buscar uma publicação isolada.
    Publicada é pública; rascunho/enviado só visível ao próprio autor (nunca
    vaza conteúdo não publicado para outro usuário).
    """

    permission_classes = [AllowAny]

    def get(self, request, publicacao_id):
        try:
            publicacao = Publicacao.objects.get(pk=publicacao_id)
        except Publicacao.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        eh_autor = request.user.is_authenticated and request.user.id == publicacao.autor_id
        if publicacao.status != Publicacao.STATUS_PUBLICADO and not eh_autor:
            return Response(status=status.HTTP_404_NOT_FOUND)
        # Removida por moderação (BRD §16): some das listagens/links públicos,
        # mas o próprio autor ainda consegue ver (nunca apagamento silencioso
        # — ele precisa poder contestar via canal de recurso).
        if publicacao.oculto and not eh_autor:
            return Response(status=status.HTTP_404_NOT_FOUND)

        return Response(PublicacaoSerializer(publicacao).data)

    def patch(self, request, publicacao_id):
        """BRD seção 14 — o autor pode editar o conteúdo da própria publicação."""
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            publicacao = Publicacao.objects.get(pk=publicacao_id)
        except Publicacao.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = PublicacaoSerializer(publicacao, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            publicacao = services.editar_publicacao(
                publicacao, request.user, **serializer.validated_data
            )
        except services.PermissaoNegadaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(PublicacaoSerializer(publicacao).data)


class EnviarPublicacaoView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, publicacao_id):
        try:
            publicacao = Publicacao.objects.get(pk=publicacao_id, autor=request.user)
        except Publicacao.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            publicacao = services.enviar_para_publicacao(publicacao)
        except services.PermissaoNegadaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(PublicacaoSerializer(publicacao).data)


class ComentariosListCreateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        qs = Comentario.objects.filter(oculto=False)
        publicacao_id = request.query_params.get("publicacao")
        news_item_id = request.query_params.get("news_item")
        if publicacao_id:
            qs = qs.filter(publicacao_id=publicacao_id)
        if news_item_id:
            qs = qs.filter(news_item_id=news_item_id)
        return Response(ComentarioSerializer(qs, many=True).data)

    def post(self, request):
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        serializer = ComentarioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data
        try:
            comentario = services.comentar(
                request.user,
                dados["conteudo"],
                publicacao=dados.get("publicacao"),
                news_item=dados.get("news_item"),
                resposta_de=dados.get("resposta_de"),
            )
        except services.PermissaoNegadaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except (services.RespostaAninhadaError, ValidationError) as exc:
            mensagem = exc.message if isinstance(exc, ValidationError) else str(exc)
            return Response({"detail": mensagem}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ComentarioSerializer(comentario).data, status=status.HTTP_201_CREATED)


class SeguirAutorView(APIView):
    permission_classes = [IsAuthenticated]

    def _obter_autor(self, autor_id):
        try:
            return User.objects.get(pk=autor_id)
        except User.DoesNotExist:
            raise Http404

    def post(self, request, autor_id):
        services.seguir(request.user, self._obter_autor(autor_id))
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request, autor_id):
        services.deixar_de_seguir(request.user, self._obter_autor(autor_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class PerfilAutorPublicoView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, autor_id):
        try:
            autor = User.objects.get(pk=autor_id)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        publicacoes = Publicacao.objects.filter(autor=autor, status=Publicacao.STATUS_PUBLICADO)
        return Response(
            {
                "id": autor.id,
                "nome": autor.nome,
                "credenciado": pode_publicar(autor),
                "numero_seguidores": Seguidor.objects.filter(autor=autor).count(),
                "publicacoes": PublicacaoSerializer(publicacoes, many=True).data,
            }
        )


class DenunciarView(APIView):
    """Critério de aceite 7."""

    permission_classes = [IsAuthenticated]
    # Achado de revisão de segurança (minor): sem throttle, uma única conta
    # podia enviar volume arbitrário de denúncias, inflando a fila de
    # moderação (NFR anti-spam, BRD §30).
    throttle_classes = [DenunciaUserThrottle]

    def post(self, request):
        motivo = request.data.get("motivo", "")
        comentario_id = request.data.get("comentario")
        publicacao_id = request.data.get("publicacao")
        comentario = Comentario.objects.filter(pk=comentario_id).first() if comentario_id else None
        publicacao = Publicacao.objects.filter(pk=publicacao_id).first() if publicacao_id else None
        if not comentario and not publicacao:
            return Response(
                {"detail": "Informe 'comentario' ou 'publicacao' para denunciar."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        denuncia = services.denunciar(request.user, motivo, comentario=comentario, publicacao=publicacao)
        return Response({"id": denuncia.id, "detail": "Denúncia registrada."}, status=status.HTTP_201_CREATED)
