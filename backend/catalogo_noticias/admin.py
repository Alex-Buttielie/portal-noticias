from django.contrib import admin

from .models import NewsCluster, NewsItem, RegistroExecucaoIngestao


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

    @admin.action(description="Marcar selecionados como aprovado")
    def marcar_como_aprovado(self, request, queryset):
        queryset.update(status_revisao=NewsItem.STATUS_APROVADO)

    @admin.action(description="Marcar selecionados como rejeitado")
    def marcar_como_rejeitado(self, request, queryset):
        queryset.update(status_revisao=NewsItem.STATUS_REJEITADO)


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
