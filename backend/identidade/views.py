import logging

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.throttling import EscritaPublicaAnonThrottle

from . import services
from .emails import enviar_email_redefinicao_senha, enviar_email_verificacao
from .permissions import IsEmailVerified
from .serializers import (
    CadastroSerializer,
    GoogleLoginSerializer,
    LoginSerializer,
    OnboardingSerializer,
    PreferenciasCookiesSerializer,
    RecuperarSenhaSerializer,
    RedefinirSenhaSerializer,
    UserSerializer,
    VerificarEmailSerializer,
)
from .tokens import decode_uidb64, password_reset_token_generator, read_email_verification_token

User = get_user_model()
logger = logging.getLogger(__name__)

# Mensagens genéricas para login/recuperação de senha — não revelam se um
# e-mail está ou não cadastrado (critério de aceite 5 e restrição de
# segurança do implementation-contract.md).
MSG_CREDENCIAIS_INVALIDAS = "E-mail ou senha inválidos."
MSG_RECUPERACAO_GENERICA = (
    "Se o e-mail informado estiver cadastrado, enviaremos instruções de redefinição de senha."
)


class CadastroView(APIView):
    """POST /api/auth/cadastro/ — cadastro por e-mail/senha (critério de aceite 1)."""

    permission_classes = [AllowAny]
    # Rate limiting (implementation-contract.md run
    # 20260903-1134-seo-lgpd-design-system, escopo C): endpoint público de
    # escrita explicitamente listado no contrato.
    throttle_classes = [EscritaPublicaAnonThrottle]

    def post(self, request):
        serializer = CadastroSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        enviar_email_verificacao(user)
        return Response(
            {
                "detail": "Cadastro realizado. Verifique seu e-mail para confirmar a conta.",
                "usuario": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class VerificarEmailView(APIView):
    """POST /api/auth/verificar-email/ — confirmação via token (critério de aceite 2)."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerificarEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resultado = read_email_verification_token(serializer.validated_data["token"])
        if resultado is None:
            return Response(
                {"detail": "Token de verificação inválido ou expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user_pk, email = resultado
        try:
            user = User.objects.get(pk=user_pk, email=email)
        except (User.DoesNotExist, ValueError):
            return Response(
                {"detail": "Token de verificação inválido ou expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.email_verificado = True
        user.save(update_fields=["email_verificado"])
        return Response({"detail": "E-mail verificado com sucesso."}, status=status.HTTP_200_OK)


class LoginView(APIView):
    """
    POST /api/auth/login/ — login por e-mail/senha (critério de aceite 5).

    Retorna um token de API (`rest_framework.authtoken`). Credenciais
    inválidas retornam sempre a mesma mensagem genérica, para não revelar se
    o e-mail existe ou não.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        senha = serializer.validated_data["senha"]

        user = authenticate(request, username=email, password=senha)
        if user is None or not user.is_active:
            return Response({"detail": MSG_CREDENCIAIS_INVALIDAS}, status=status.HTTP_401_UNAUTHORIZED)

        # `last_login` nunca era atualizado neste fluxo de login por token
        # (o helper padrão do Django só dispara em `django.contrib.auth.login`,
        # não usado aqui) — gap real encontrado ao implementar métricas de
        # usuários ativos (BRD §21, "Usuários ativos diários e mensais"),
        # que dependem deste campo para significar algo.
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {"token": token.key, "usuario": UserSerializer(user).data},
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """POST /api/auth/logout/ — invalida o token do usuário autenticado (critério de aceite 6)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response({"detail": "Logout realizado."}, status=status.HTTP_200_OK)


class RecuperarSenhaView(APIView):
    """
    POST /api/auth/recuperar-senha/ — inicia redefinição de senha (critério de aceite 7).

    Sempre responde com a mesma mensagem genérica de sucesso, exista ou não o
    e-mail — o token só é de fato gerado/enviado se o usuário existir.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RecuperarSenhaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            user = None

        if user is not None:
            enviar_email_redefinicao_senha(user)

        return Response({"detail": MSG_RECUPERACAO_GENERICA}, status=status.HTTP_200_OK)


class RedefinirSenhaView(APIView):
    """POST /api/auth/redefinir-senha/ — conclui a redefinição de senha (critério de aceite 7)."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RedefinirSenhaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uid = decode_uidb64(serializer.validated_data["uid"])

        user = None
        if uid is not None:
            try:
                user = User.objects.get(pk=uid)
            except (User.DoesNotExist, ValueError):
                user = None

        if user is None or not password_reset_token_generator.check_token(
            user, serializer.validated_data["token"]
        ):
            return Response(
                {"detail": "Token de redefinição inválido ou expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["nova_senha"])
        user.save(update_fields=["password"])
        # Invalida qualquer sessão/token de API pré-existente.
        Token.objects.filter(user=user).delete()

        return Response({"detail": "Senha redefinida com sucesso."}, status=status.HTTP_200_OK)


class GoogleLoginView(APIView):
    """
    POST /api/auth/google/ — login/cadastro social via Google (critério de aceite 4).

    Recebe o `id_token` (JWT) obtido pelo cliente via Google Identity
    Services e usa `django-allauth` (`GoogleProvider.verify_token`) para
    validar a assinatura/audiência junto ao Google e extrair os dados do
    usuário. Usuário novo nasce com `papel=free` e `email_verificado=True`
    (o Google já validou o e-mail do lado dele) — ver
    `identidade/adapters.py`.

    Em teste, a verificação junto ao Google é mockada (não há credenciais
    reais de Google Cloud neste ambiente — ver task-plan.md, riscos).

    Antes de tratar o login como "usuário novo", verificamos explicitamente
    se já existe um `User` cadastrado com este e-mail (por e-mail/senha, por
    exemplo) mas ainda sem `SocialAccount` do Google vinculado — nesse caso
    associamos a conta Google ao usuário existente em vez de tentar criar um
    `User` duplicado, o que violaria a constraint `unique=True` do campo
    `email` e resultaria em `IntegrityError`/HTTP 500 (code-review-contract.md
    Finding 1).

    Para um usuário verdadeiramente novo, exigimos `aceite_termos=true` no
    payload — análogo ao que `CadastroSerializer` já exige no cadastro por
    e-mail/senha — e persistimos o consentimento LGPD (`consentimento_aceito_em`
    / `consentimento_versao_termos`) nesse momento, antes de criar a conta.
    Sem esse aceite, a conta não é criada (Finding 2).
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Import local para não exigir app social configurado em comandos de
        # management que não usam este endpoint.
        from allauth.socialaccount.adapter import get_adapter as get_social_adapter
        from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter

        adapter = GoogleOAuth2Adapter(request)
        provider = adapter.get_provider()

        try:
            sociallogin = provider.verify_token(
                request, {"id_token": serializer.validated_data["id_token"]}
            )
        except Exception:
            logger.exception("Falha ao validar id_token do Google em POST /api/auth/google/.")
            return Response({"detail": "Token do Google inválido."}, status=status.HTTP_400_BAD_REQUEST)

        sociallogin.lookup()

        if sociallogin.is_existing:
            # Já existe um SocialAccount do Google vinculado a este usuário
            # (login social de retorno).
            user = sociallogin.user
            is_new = False
        else:
            # Nenhum SocialAccount vinculado ainda — mas pode já existir um
            # User com este e-mail (ex.: cadastrado por e-mail/senha
            # anteriormente). Tratar como "novo" sem essa checagem tentaria
            # criar um User duplicado (Finding 1).
            email = sociallogin.user.email
            try:
                existing_user = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                existing_user = None

            if existing_user is not None:
                # Associa a conta Google ao usuário já existente — não cria
                # um novo User, não sobrescreve papel/consentimento já
                # persistidos.
                sociallogin.connect(request, existing_user)
                user = existing_user
                is_new = False
            else:
                # Usuário verdadeiramente novo: exige aceite explícito dos
                # termos, assim como o cadastro por e-mail/senha (Finding 2 —
                # critério de aceite 11, consentimento LGPD).
                if not serializer.validated_data.get("aceite_termos"):
                    return Response(
                        {
                            "detail": (
                                "É necessário aceitar os termos de uso e a "
                                "política de privacidade para se cadastrar."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                sociallogin.user.consentimento_aceito_em = timezone.now()
                sociallogin.user.consentimento_versao_termos = settings.TERMOS_VERSAO_ATUAL
                get_social_adapter(request).save_user(request, sociallogin)
                user = sociallogin.user
                is_new = True

        if not user.is_active:
            return Response({"detail": "Conta inativa."}, status=status.HTTP_403_FORBIDDEN)

        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                "token": token.key,
                "usuario": UserSerializer(user).data,
                "criado_agora": is_new,
            },
            status=status.HTTP_200_OK,
        )


class OnboardingView(APIView):
    """
    GET/PATCH /api/onboarding/ — captura/atualização de interesses,
    localidade e canal preferido (critérios de aceite 8 e 9).

    Exige usuário autenticado com e-mail verificado (`IsEmailVerified`) —
    decisão documentada em implementation-history.md.
    """

    permission_classes = [IsAuthenticated, IsEmailVerified]

    def get(self, request):
        return Response(OnboardingSerializer(request.user).data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = OnboardingSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(OnboardingSerializer(user).data, status=status.HTTP_200_OK)


class PreferenciasCookiesView(APIView):
    """
    GET/PUT /api/preferencias-cookies/ — preferências de cookies do usuário
    AUTENTICADO (implementation-contract.md run
    20260903-1134-seo-lgpd-design-system, escopo B). Lacuna de backend
    encontrada e corrigida nesta run: endpoint não existia antes; o
    frontend precisava dele para persistir a escolha de cookies de um
    usuário logado além do localStorage (que já cobre o visitante anônimo).

    A mutação passa por `services.atualizar_preferencias_cookies` (DDD —
    view nunca escreve direto no model).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(PreferenciasCookiesSerializer(request.user).data, status=status.HTTP_200_OK)

    def put(self, request):
        serializer = PreferenciasCookiesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.atualizar_preferencias_cookies(
            request.user,
            {
                "analytics": serializer.validated_data["analytics"],
                "personalizacao": serializer.validated_data["personalizacao"],
            },
        )
        return Response(PreferenciasCookiesSerializer(user).data, status=status.HTTP_200_OK)
