from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "nome",
            "papel",
            "email_verificado",
            "interesses",
            "localidade",
            "canal_preferido",
            "onboarding_concluido",
            "onboarding_pulado",
            "consentimento_aceito_em",
            "consentimento_versao_termos",
            "date_joined",
        ]
        read_only_fields = fields


class CadastroSerializer(serializers.ModelSerializer):
    senha = serializers.CharField(write_only=True, min_length=8)
    aceite_termos = serializers.BooleanField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "nome", "senha", "aceite_termos"]

    def validate_email(self, value):
        value = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=value).exists():
            # Mensagem genérica proposital — não confirmar/negar existência
            # de conta para quem está tentando cadastrar (mitigação de
            # enumeração, mesmo espírito do critério de aceite 5, aplicado
            # aqui de forma defensiva; o formulário de cadastro em si pode
            # revelar duplicidade sem grande risco, mas mantemos consistente).
            raise serializers.ValidationError("Não foi possível concluir o cadastro com os dados informados.")
        return value

    def validate_senha(self, value):
        password_validation.validate_password(value)
        return value

    def validate_aceite_termos(self, value):
        if not value:
            raise serializers.ValidationError(
                "É necessário aceitar os termos de uso e a política de privacidade para se cadastrar."
            )
        return value

    def create(self, validated_data):
        from django.utils import timezone

        senha = validated_data.pop("senha")
        validated_data.pop("aceite_termos")
        user = User(
            email=validated_data["email"],
            nome=validated_data.get("nome", ""),
            papel=User.PAPEL_FREE,
            email_verificado=False,
            consentimento_aceito_em=timezone.now(),
            consentimento_versao_termos=settings.TERMOS_VERSAO_ATUAL,
        )
        user.set_password(senha)
        user.save()
        return user


class VerificarEmailSerializer(serializers.Serializer):
    token = serializers.CharField()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    senha = serializers.CharField(trim_whitespace=False)


class RecuperarSenhaSerializer(serializers.Serializer):
    email = serializers.EmailField()


class RedefinirSenhaSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    nova_senha = serializers.CharField(min_length=8)

    def validate_nova_senha(self, value):
        password_validation.validate_password(value)
        return value


class GoogleLoginSerializer(serializers.Serializer):
    # ID token (JWT) obtido pelo cliente via Google Identity Services
    # (chamado de "credential" na lib JS do Google). O backend valida a
    # assinatura/audiência junto ao Google via django-allauth.
    id_token = serializers.CharField()
    # Exigido apenas quando o login resulta em um cadastro novo (nenhum User
    # nem SocialAccount pré-existente para este e-mail) — análogo ao
    # `aceite_termos` de `CadastroSerializer`. A view valida a obrigatoriedade
    # condicionalmente, pois só é possível saber se o usuário é novo depois
    # de consultar o banco (ver GoogleLoginView.post, Finding 1/2 do
    # code-review-contract.md).
    aceite_termos = serializers.BooleanField(required=False, default=False)


class OnboardingSerializer(serializers.ModelSerializer):
    pular = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = User
        fields = [
            "interesses",
            "localidade",
            "canal_preferido",
            "onboarding_concluido",
            "onboarding_pulado",
            "pular",
        ]
        read_only_fields = ["onboarding_concluido", "onboarding_pulado"]

    def update(self, instance, validated_data):
        from django.utils import timezone

        pular = validated_data.pop("pular", False)

        for field in ("interesses", "localidade", "canal_preferido"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])

        if pular:
            # Critério de aceite 9: pular não perde a informação de que deve
            # ser reapresentado depois — `onboarding_concluido` permanece
            # False, só marcamos que foi pulado (não bloqueia o uso da conta,
            # pois nenhuma permissão do restante da API depende disso).
            instance.onboarding_pulado = True
        elif any(field in validated_data for field in ("interesses", "localidade", "canal_preferido")):
            instance.onboarding_concluido = True
            instance.onboarding_pulado = False

        instance.onboarding_atualizado_em = timezone.now()
        instance.save()
        return instance


class PreferenciasCookiesSerializer(serializers.Serializer):
    """
    GET/PUT de preferências de cookies (implementation-contract.md run
    20260903-1134-seo-lgpd-design-system, escopo B). Só as categorias
    OPCIONAIS — "essenciais" é sempre ativo e não é aceito aqui.
    """

    analytics = serializers.BooleanField(default=False)
    personalizacao = serializers.BooleanField(default=False)
    atualizado_em = serializers.DateTimeField(source="preferencias_cookies_atualizado_em", read_only=True)

    def to_representation(self, instance):
        preferencias = instance.preferencias_cookies or {}
        return {
            "analytics": bool(preferencias.get("analytics", False)),
            "personalizacao": bool(preferencias.get("personalizacao", False)),
            "atualizado_em": instance.preferencias_cookies_atualizado_em,
        }
