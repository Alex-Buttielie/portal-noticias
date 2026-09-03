from rest_framework import serializers

from .models import PerfilJornalista, SolicitacaoCredenciamento


class SolicitacaoCredenciamentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = SolicitacaoCredenciamento
        fields = [
            "id",
            "telefone",
            "cidade",
            "uf",
            "foto",
            "mini_bio",
            "dados_profissionais",
            "documento",
            "status",
            "criado_em",
            "decidido_em",
            "motivo_decisao",
        ]
        read_only_fields = ["id", "status", "criado_em", "decidido_em", "motivo_decisao"]


class PerfilJornalistaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerfilJornalista
        fields = ["foto", "mini_bio", "dados_profissionais", "selo_ativo", "suspenso", "credenciado_em"]
        read_only_fields = ["selo_ativo", "suspenso", "credenciado_em"]
