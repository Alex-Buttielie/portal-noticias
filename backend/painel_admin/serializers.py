from rest_framework import serializers

from assinatura.models import Plan, Subscription
from catalogo_noticias.models import NewsCluster, NewsItem
from gating.models import FeatureLimit
from moderacao.models import AcaoModeracao, Denuncia


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
