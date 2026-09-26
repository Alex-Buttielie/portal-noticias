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
            "deve_trocar_senha",
            "date_joined",
        ]
        read_only_fields = fields


class CadastroSerializer(serializers.ModelSerializer):
    """Validação do payload de `POST /api/auth/cadastro/`.

    NÃO VALIDA DUPLICIDADE — e essa ausência é deliberada (P1-04).

    Antes deste item, a duplicidade era recusada em DOIS lugares, e os dois
    diziam ao cliente que o e-mail já tinha conta: o `validate_email` desta
    serializer (400 com texto "genérico") e o `UniqueValidator` que o DRF
    gera sozinho por causa do `unique=True` do modelo (400 com
    "usuário com este email já existe"). A justificativa do `validate_email`
    original — "não confirmar/negar existência de conta para quem está tentando
    cadastrar" — estava certa e o código a contradizia duas vezes: 400 para
    e-mail existente e 201 para e-mail novo é a definição de oráculo de
    existência. Um `POST` com qualquer senha bastava para varrer a base.

    Quem decide o que fazer com a duplicidade agora é `CadastroView`, e a
    resposta é a mesma nos dois casos. Esta serializer cuida só de payload
    malformado — e-mail inválido, senha fraca, aceite ausente — que é erro de
    requisição, não informação sobre o banco.
    """

    senha = serializers.CharField(write_only=True, min_length=8)
    aceite_termos = serializers.BooleanField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "nome", "senha", "aceite_termos"]
        extra_kwargs = {
            # SEGUNDO oráculo de existência de conta, e mais explícito que o
            # primeiro: `email` é `unique=True` no modelo
            # (`identidade/models.py:36`), então o `ModelSerializer` do DRF
            # gera automaticamente um `UniqueValidator` e devolve
            # **400 `{"email": ["usuário com este email já existe."]}`** para
            # um e-mail cadastrado. Remover só o `validate_email` desta
            # serializer (o oráculo "genérico" que existia antes) não fecha a
            # enumeração — ela simplesmente aparece com outro texto, e pior.
            #
            # `validators: []` desliga o validador gerado. A unicidade REAL
            # continua garantida pelo índice único do banco; o que muda é que
            # a colisão passa a ser tratada por `CadastroView`, que devolve a
            # resposta neutra de duplicidade em vez de um 400 que nomeia o
            # problema.
            "email": {"validators": []},
        }

    def validate_email(self, value):
        # Normaliza a caixa do domínio (`Foo@Exemplo.COM` -> `Foo@example.com`),
        # como o login e o gerenciador fazem, para que a comparação de
        # duplicidade em `CadastroView` use a mesma chave. A normalização
        # também é o que faz `filter(email__iexact=...)` no banco casar com o
        # que o usuário digitou.
        return User.objects.normalize_email(value)

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
        """Cria a conta com `email_verificado=False`.

        O campo `email` que chega aqui já foi normalizado por `validate_email`.
        A unicidade de verdade é garantida pelo índice único do modelo, e quem
        trata a colisão é `CadastroView` — que trata antes de chegar aqui, e
        devolve a resposta neutra de duplicidade.
        """
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
            deve_trocar_senha=True,
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


class TrocarSenhaSerializer(serializers.Serializer):
    senha_atual = serializers.CharField(trim_whitespace=False)
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
