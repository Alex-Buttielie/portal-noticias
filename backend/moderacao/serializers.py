from rest_framework import serializers

from .models import AcaoModeracao, Denuncia, PaginaEditorial, RecursoModeracao


class DenunciaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Denuncia
        fields = [
            "id",
            "denunciante",
            "motivo",
            "detalhe",
            "content_type",
            "object_id",
            "status",
            "criado_em",
            "resolvido_em",
            "resolvido_por",
            "resolucao_motivo",
        ]
        read_only_fields = fields


class AcaoModeracaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcaoModeracao
        fields = [
            "id",
            "usuario_alvo",
            "tipo",
            "motivo",
            "aplicado_por",
            "denuncia_relacionada",
            "ativo_ate",
            "criado_em",
        ]
        read_only_fields = ["id", "aplicado_por", "criado_em"]


class RecursoModeracaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecursoModeracao
        fields = ["id", "acao", "usuario", "texto", "status", "criado_em"]
        read_only_fields = ["id", "usuario", "status", "criado_em"]


class PaginaEditorialSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaginaEditorial
        fields = ["slug", "titulo", "conteudo", "atualizado_em"]
