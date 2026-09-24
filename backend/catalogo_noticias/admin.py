from django.contrib import admin
from django.db import transaction

from .models import ConfiguracaoRobo, FonteRobo, NewsCluster, NewsItem, RegistroExecucaoIngestao


@admin.register(FonteRobo)
class FonteRoboAdmin(admin.ModelAdmin):
    list_display = ["nome", "url", "ativo", "categoria_padrao", "atualizado_em"]
    list_filter = ["ativo"]
    search_fields = ["nome", "url"]
    # O validator pertence ao download anterior; operators podem trocar a
    # URL, mas não editar manualmente o resultado de uma requisição HTTP.
    readonly_fields = ["etag", "last_modified", "ultima_revalidacao_completa"]


@admin.register(ConfiguracaoRobo)
class ConfiguracaoRoboAdmin(admin.ModelAdmin):
    list_display = ["intervalo_minutos", "ativo", "llm_model", "atualizado_em"]

    def has_add_permission(self, request):
        return not ConfiguracaoRobo.objects.filter(pk=1).exists()

    def has_delete_permission(self, request, obj=None):
        return False


class NewsItemInline(admin.TabularInline):
    model = NewsItem
    extra = 0
    fields = ["titulo", "nome_fonte", "categoria", "status_revisao", "urgente", "timestamp_publicacao_fonte"]
    readonly_fields = fields
    can_delete = False
    show_change_link = True


@admin.register(NewsCluster)
class NewsClusterAdmin(admin.ModelAdmin):
    list_display = ["titulo_acontecimento", "categoria_dominante", "numero_fontes_distintas_admin", "criado_em"]
    list_filter = ["categoria_dominante"]
    search_fields = ["titulo_acontecimento"]
    inlines = [NewsItemInline]

    @admin.display(description="Nº de fontes")
    def numero_fontes_distintas_admin(self, obj):
        return obj.numero_fontes_distintas

    def save_related(self, request, form, formsets, change):
        # O inline de NewsItem pode associar/desassociar itens ao cluster
        # fora do pipeline de ingestão — recalcula a coluna denormalizada
        # (run 20260923-1216-p1-feed-cache-indices, P1-1) após salvar.
        super().save_related(request, form, formsets, change)
        try:
            form.instance.recalcular_numero_fontes()
        except Exception:
            pass


@admin.register(NewsItem)
class NewsItemAdmin(admin.ModelAdmin):
    """
    Expoe a fila de revisao humana de itens de alta relevancia — filtro por
    `status_revisao` exigido em implementation-contract.md ("Areas/arquivos
    esperados"). Operar a fila (aprovar/rejeitar) e feito diretamente pelo
    admin nativo (nao-objetivo desta execucao construir uma UI propria).
    """

    list_display = [
        "titulo",
        "nome_fonte",
        "categoria",
        "status_revisao",
        "urgente",
        "cluster",
        "timestamp_publicacao_fonte",
        "timestamp_ingestao",
    ]
    list_filter = ["status_revisao", "urgente", "categoria", "nome_fonte"]
    search_fields = ["titulo", "url_fonte_original", "nome_fonte"]
    readonly_fields = ["timestamp_ingestao"]
    actions = ["marcar_como_aprovado", "marcar_como_rejeitado"]

    def save_model(self, request, obj, form, change):
        # A tela de mudança também permite editar status_revisao diretamente;
        # cubra esse caminho, não apenas as actions em lote.
        anterior = None
        if change and obj.pk:
            anterior = NewsItem.objects.filter(pk=obj.pk).values_list(
                "status_revisao", flat=True
            ).first()
        super().save_model(request, obj, form, change)
        if anterior != obj.status_revisao:
            from feed.busca import invalidar_cache_autocomplete

            # changeform_view executa o POST em transaction.atomic. Só invalide
            # depois do commit para que uma leitura concorrente não recoloque
            # no cache o snapshot do estado anterior.
            transaction.on_commit(invalidar_cache_autocomplete)

    @admin.action(description="Marcar selecionados como aprovado")
    def marcar_como_aprovado(self, request, queryset):
        atualizados = queryset.exclude(
            status_revisao=NewsItem.STATUS_APROVADO
        ).update(status_revisao=NewsItem.STATUS_APROVADO)
        from feed.busca import invalidar_cache_autocomplete

        # No Django 5.2, response_action executa em autocommit. on_commit
        # continua sendo a API correta: em autocommit roda após o update; se
        # uma versão futura ou um caller envolver a action em atomic, adia a
        # invalidação até o commit.
        if atualizados:
            transaction.on_commit(invalidar_cache_autocomplete)

    @admin.action(description="Marcar selecionados como rejeitado")
    def marcar_como_rejeitado(self, request, queryset):
        atualizados = queryset.exclude(
            status_revisao=NewsItem.STATUS_REJEITADO
        ).update(status_revisao=NewsItem.STATUS_REJEITADO)
        from feed.busca import invalidar_cache_autocomplete

        if atualizados:
            transaction.on_commit(invalidar_cache_autocomplete)


@admin.register(RegistroExecucaoIngestao)
class RegistroExecucaoIngestaoAdmin(admin.ModelAdmin):
    """
    Observabilidade de execucoes de ingestao (implementation-contract.md,
    criterio de aceite 6) — somente leitura (o registro e gerado pelo
    pipeline, nunca editado manualmente).
    """

    list_display = [
        "executado_em",
        "total_itens_ingeridos",
        "total_grupos_formados",
        "total_duplicatas_agrupadas",
        "chamadas_summarization_provider",
        "tokens_utilizados_summarization",
        "custo_estimado_summarization_usd",
    ]
    readonly_fields = [f.name for f in RegistroExecucaoIngestao._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
