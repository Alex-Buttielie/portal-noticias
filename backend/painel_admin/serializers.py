from django.contrib.auth import password_validation
from django.contrib.auth import get_user_model
from rest_framework import serializers

from assinatura.models import Plan, Subscription
from catalogo_noticias.models import NewsCluster, NewsItem
from catalogo_noticias.providers.fallback_local import (
    motivo_fallback_local,
    origem_fallback_local,
)
from gating.models import FeatureLimit, FeatureLimitAlteracaoLog
from moderacao.models import AcaoModeracao, Denuncia
from painel_admin.models import AuditoriaAdmin

User = get_user_model()


class UsuarioAdminSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    nome = serializers.CharField(read_only=True)
    papel = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    email_verificado = serializers.BooleanField(read_only=True)
    date_joined = serializers.DateTimeField(read_only=True)


class UsuarioUpdateSerializer(serializers.Serializer):
    papel = serializers.ChoiceField(choices=["free", "premium", "admin"], required=False)
    is_active = serializers.BooleanField(required=False)


class UsuarioCriacaoSerializer(serializers.Serializer):
    """
    `POST /api/admin/usuarios/` — criação de usuário pelo admin (C-01).

    Reaproveita a MESMA validação de e-mail único e senha forte que
    `identidade.serializers.CadastroSerializer` usa no cadastro público
    (`validate_senha` chama o mesmo `password_validation.validate_password`;
    a checagem de duplicidade usa o mesmo `User.objects.normalize_email` +
    `filter(email__iexact=...)`). Diferente do cadastro público, aqui a
    duplicidade É informada ao chamador (400) — o admin não é um atacante
    tentando enumerar a base, é quem está cadastrando a conta.
    """

    email = serializers.EmailField()
    nome = serializers.CharField(required=False, allow_blank=True, default="")
    senha = serializers.CharField(write_only=True, min_length=8)
    papel = serializers.ChoiceField(choices=["free", "premium", "admin"], required=False, default="free")
    is_active = serializers.BooleanField(required=False, default=True)

    def validate_email(self, value):
        normalizado = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=normalizado).exists():
            raise serializers.ValidationError("Já existe uma conta com este e-mail.")
        return normalizado

    def validate_senha(self, value):
        password_validation.validate_password(value)
        return value


class AuditoriaAdminSerializer(serializers.ModelSerializer):
    alterado_por_email = serializers.CharField(source="alterado_por.email", read_only=True, default=None)

    class Meta:
        model = AuditoriaAdmin
        fields = ["id", "acao", "alvo_tipo", "alvo_id", "detalhe", "alterado_por_email", "criado_em"]


class FeatureLimitAlteracaoLogSerializer(serializers.ModelSerializer):
    alterado_por_email = serializers.CharField(source="alterado_por.email", read_only=True, default=None)

    class Meta:
        model = FeatureLimitAlteracaoLog
        fields = [
            "id",
            "feature_limit_chave",
            "plano",
            "valor_anterior",
            "valor_novo",
            "alterado_por_email",
            "alterado_em",
        ]


class FilaItemSerializer(serializers.Serializer):
    tipo = serializers.CharField()
    id = serializers.IntegerField()
    titulo = serializers.CharField()
    categoria = serializers.CharField(allow_blank=True)
    status_revisao = serializers.CharField()
    nome_fonte = serializers.CharField(allow_blank=True)
    url_fonte_original = serializers.CharField(allow_blank=True)
    urgente = serializers.BooleanField()
    cluster = serializers.IntegerField(allow_null=True)
    timestamp_ingestao = serializers.DateTimeField()
    cluster_titulo = serializers.CharField(allow_blank=True, required=False)
    # P1-02 (WS-08/GP-5): procedencia do `resumo_proprio`, lida do marcador
    # tecnico gravado em `NewsItem.tags` (sem migration). O editorial precisa
    # distinguir na fila o resumo vindo do provedor externo daquele gerado
    # pelo fallback local — e saber POR QUE (timeout, sem credencial, ...).
    # `resumo_fallback_local=False` = resumo do provedor.
    resumo_fallback_local = serializers.SerializerMethodField()
    motivo_fallback_resumo = serializers.SerializerMethodField()

    def get_resumo_fallback_local(self, obj) -> bool:
        return origem_fallback_local(getattr(obj, "tags", None))

    def get_motivo_fallback_resumo(self, obj) -> str:
        return motivo_fallback_local(getattr(obj, "tags", None))


class PlanAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["id", "nome", "preco", "duracao_dias", "ativo", "criado_em", "atualizado_em"]


class PlanCreateSerializer(serializers.Serializer):
    nome = serializers.CharField(max_length=100)
    preco = serializers.DecimalField(max_digits=10, decimal_places=2)
    duracao_dias = serializers.IntegerField(min_value=1)
    ativo = serializers.BooleanField(required=False, default=True)


class FeatureLimitAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureLimit
        fields = ["id", "chave", "plano", "valor", "descricao", "atualizado_em"]


class FeatureLimitUpdateSerializer(serializers.Serializer):
    valor = serializers.CharField(max_length=200)
    descricao = serializers.CharField(required=False, allow_blank=True)


class AssinaturaAdminSerializer(serializers.ModelSerializer):
    plan = PlanAdminSerializer(read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_nome = serializers.CharField(source="user.nome", read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "user_email",
            "user_nome",
            "plan",
            "status",
            "preco_cobrado",
            "duracao_dias_no_momento",
            "inicio",
            "vencimento",
            "renovacao_automatica",
            "grace_period_termina_em",
            "criado_em",
        ]


class DenunciaAdminSerializer(serializers.ModelSerializer):
    denunciante_email = serializers.CharField(source="denunciante.email", read_only=True)
    alvo_repr = serializers.SerializerMethodField()

    class Meta:
        model = Denuncia
        fields = [
            "id",
            "motivo",
            "detalhe",
            "status",
            "denunciante_email",
            "content_type",
            "object_id",
            "alvo_repr",
            "criado_em",
            "resolvido_em",
        ]

    def get_alvo_repr(self, obj):
        try:
            alvo = obj.alvo
            if alvo is None:
                return None
            return str(alvo)[:200]
        except Exception:
            return None


class FilaDecisaoSerializer(serializers.Serializer):
    acao = serializers.ChoiceField(choices=["aprovar", "rejeitar"])


class DenunciaAcaoSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=[c[0] for c in AcaoModeracao.TIPO_CHOICES])
    motivo = serializers.CharField()
    procedente = serializers.BooleanField(required=False, default=True)


# ---------------------------------------------------------------------------
# FRENTE 6 — Central de Inteligência: controles editoriais.
# ---------------------------------------------------------------------------


class DestaqueEditorialAdminSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    tipo = serializers.ChoiceField(choices=["destaque", "manchete", "bloqueio"])
    entry_tipo = serializers.ChoiceField(choices=["item", "cluster"])
    entry_id = serializers.IntegerField()
    titulo = serializers.CharField(read_only=True, required=False, allow_blank=True)
    posicao = serializers.IntegerField(required=False, default=0)
    ativo = serializers.BooleanField(required=False, default=True)
    inicio = serializers.DateTimeField(required=False, allow_null=True, default=None)
    fim = serializers.DateTimeField(required=False, allow_null=True, default=None)
    motivo = serializers.CharField(required=False, allow_blank=True, default="")
    vigente = serializers.BooleanField(read_only=True, required=False)
    criado_em = serializers.DateTimeField(read_only=True, required=False)


class RegraCuradoriaAdminSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    tipo = serializers.ChoiceField(
        choices=[
            "boost_entrada", "bloqueio_entrada", "boost_categoria", "bloqueio_categoria",
            "ordem_categorias", "colunista_destaque", "selo_forcado",
            "urgente_forcado", "exclusivo_forcado",
        ]
    )
    entry_tipo = serializers.ChoiceField(choices=["item", "cluster"], required=False, allow_blank=True, default="")
    entry_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    alvo = serializers.CharField(required=False, allow_blank=True, default="")
    ordem = serializers.IntegerField(required=False, default=0)
    ativo = serializers.BooleanField(required=False, default=True)
    inicio = serializers.DateTimeField(required=False, allow_null=True, default=None)
    fim = serializers.DateTimeField(required=False, allow_null=True, default=None)
    motivo = serializers.CharField(required=False, allow_blank=True, default="")
    vigente = serializers.BooleanField(read_only=True, required=False)
    criado_em = serializers.DateTimeField(read_only=True, required=False)
