from rest_framework import serializers

from .models import ConfiguracaoRobo, FonteRobo, RegistroExecucaoIngestao


class FonteRoboSerializer(serializers.ModelSerializer):
    class Meta:
        model = FonteRobo
        fields = ["id", "nome", "url", "ativo", "categoria_padrao", "criado_em", "atualizado_em"]
        read_only_fields = ["id", "criado_em", "atualizado_em"]

    def validate_url(self, value):
        v = (value or "").strip()
        if not v.startswith("http://") and not v.startswith("https://"):
            raise serializers.ValidationError("URL deve começar com http:// ou https://.")
        return v


class ConfiguracaoRoboSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracaoRobo
        fields = [
            "intervalo_minutos",
            "ativo",
            "categorias_sensiveis",
            "limiar_fontes_alta_relevancia",
            "dedup_limiar_similaridade",
            "dedup_janela_horas",
            "dedup_max_itens",
            "resumo_similaridade_maxima",
            "resumo_trecho_copiado_maximo",
            "dedup_cluster_sempre_exige_revisao",
            "llm_model",
            "llm_api_base_url",
            "llm_tamanho_lote",
            "llm_max_tokens_por_item",
            "llm_teto_gasto_diario_usd",
            "llm_preco_por_1k_tokens",
            "llm_timeout_segundos",
            "atualizado_em",
        ]
        read_only_fields = ["atualizado_em"]

    def validate_intervalo_minutos(self, v):
        if v < 1 or v > 1440:
            raise serializers.ValidationError("Intervalo deve estar entre 1 e 1440 minutos.")
        return v

    def validate_dedup_limiar_similaridade(self, v):
        if v < 0 or v > 1:
            raise serializers.ValidationError("Deve estar entre 0 e 1.")
        return v

    def validate_resumo_similaridade_maxima(self, v):
        if v < 0 or v > 1:
            raise serializers.ValidationError("Deve estar entre 0 e 1.")
        return v

    def validate_resumo_trecho_copiado_maximo(self, v):
        if v < 0 or v > 1:
            raise serializers.ValidationError("Deve estar entre 0 e 1.")
        return v


class RegistroExecucaoIngestaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistroExecucaoIngestao
        fields = [
            "id",
            "executado_em",
            "itens_por_fonte",
            "erros_por_fonte",
            "total_itens_ingeridos",
            "total_grupos_formados",
            "total_duplicatas_agrupadas",
            "chamadas_summarization_provider",
            "tokens_utilizados_summarization",
            "custo_estimado_summarization_usd",
        ]
