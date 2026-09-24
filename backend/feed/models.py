from django.conf import settings
from django.db import models


class EventoBusca(models.Model):
    """FRENTE 3 — registro de cada busca executada (mecanismo principal de
    descoberta). Alimenta termos populares, autocomplete, histórico e o
    sinal de "tendência" da recomendação. Nunca duplica dado de negócio:
    guarda só a query + contagem de resultados + filtros usados."""

    query = models.CharField(max_length=300)
    query_normalizada = models.CharField(max_length=300, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="buscas",
    )
    session_key = models.CharField(max_length=64, blank=True)
    # Correlaciona uma métrica com a requisição que a originou. NULL é
    # permitido para eventos antigos/diretos; quando preenchido, a task
    # pode usar get_or_create e uma reentrega do Celery não duplica a linha.
    request_id = models.CharField(max_length=64, null=True, blank=True, unique=True)
    resultados = models.PositiveIntegerField(default=0)
    filtros = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "evento de busca"
        verbose_name_plural = "eventos de busca"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["query_normalizada", "-criado_em"]),
        ]

    def __str__(self):
        return f"{self.query_normalizada} ({self.criado_em:%d/%m %H:%M})"


class InteracaoNoticia(models.Model):
    """FRENTE 3 — sinais de consumo por entrada do feed (acessos, cliques,
    tempo de leitura, salvos, compartilhamentos, cliques em resultado de
    busca). user NULL + session_key = visitante anônimo. Métricas
    (popularidade/crescimento/engajamento) são SEMPRE agregações sobre esta
    tabela — nenhum contador duplicado em NewsItem/NewsCluster."""

    TIPO_VIEW = "view"
    TIPO_CLICK = "click"
    TIPO_READ = "read"
    TIPO_SAVE = "save"
    TIPO_UNSAVE = "unsave"
    TIPO_SHARE = "share"
    TIPO_SEARCH_CLICK = "search_click"
    TIPO_CHOICES = [
        (TIPO_VIEW, "Visualização"),
        (TIPO_CLICK, "Clique"),
        (TIPO_READ, "Leitura com tempo"),
        (TIPO_SAVE, "Salvo"),
        (TIPO_UNSAVE, "Removido dos salvos"),
        (TIPO_SHARE, "Compartilhado"),
        (TIPO_SEARCH_CLICK, "Clique em resultado de busca"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="interacoes_noticia",
    )
    session_key = models.CharField(max_length=64, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, db_index=True)
    entry_tipo = models.CharField(max_length=10, help_text="'cluster' ou 'item'")
    cluster = models.ForeignKey(
        "catalogo_noticias.NewsCluster", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="interacoes",
    )
    item = models.ForeignKey(
        "catalogo_noticias.NewsItem", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="interacoes",
    )
    categoria = models.CharField(max_length=100, blank=True, db_index=True)
    tempo_leitura_seg = models.PositiveIntegerField(default=0)
    query = models.CharField(max_length=300, blank=True,
                             help_text="Query de origem quando tipo=search_click")
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "interação com notícia"
        verbose_name_plural = "interações com notícias"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["entry_tipo", "cluster", "-criado_em"]),
            models.Index(fields=["entry_tipo", "item", "-criado_em"]),
            models.Index(fields=["tipo", "-criado_em"]),
        ]

    def __str__(self):
        alvo = f"{self.entry_tipo}:{self.cluster_id or self.item_id}"
        return f"{self.tipo} {alvo}"


class DestaqueEditorial(models.Model):
    """FRENTE 3 — overrides editoriais que a recomendação PRECISA respeitar:
    - manchete: fixada no topo da Home (posição ordena entre elas);
    - destaque: entra primeiro na seção "Destaques do Dia";
    - bloqueio: entrada NUNCA aparece (em nenhuma seção).
    Janela opcional inicio/fim; fora da janela o override é ignorado sem
    precisar desativar manualmente."""

    TIPO_DESTAQUE = "destaque"
    TIPO_MANCHETE = "manchete"
    TIPO_BLOQUEIO = "bloqueio"
    TIPO_CHOICES = [
        (TIPO_DESTAQUE, "Destaque do Dia (override manual)"),
        (TIPO_MANCHETE, "Manchete fixa no topo"),
        (TIPO_BLOQUEIO, "Bloqueio (não exibir)"),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, db_index=True)
    entry_tipo = models.CharField(max_length=10, help_text="'cluster' ou 'item'")
    cluster = models.ForeignKey(
        "catalogo_noticias.NewsCluster", null=True, blank=True,
        on_delete=models.CASCADE, related_name="destaques_editoriais",
    )
    item = models.ForeignKey(
        "catalogo_noticias.NewsItem", null=True, blank=True,
        on_delete=models.CASCADE, related_name="destaques_editoriais",
    )
    posicao = models.PositiveIntegerField(default=0,
                                          help_text="Ordena manchetes entre si (menor primeiro)")
    ativo = models.BooleanField(default=True, db_index=True)
    inicio = models.DateTimeField(null=True, blank=True)
    fim = models.DateTimeField(null=True, blank=True)
    motivo = models.CharField(max_length=300, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "override editorial"
        verbose_name_plural = "overrides editoriais"
        ordering = ["posicao", "-criado_em"]

    def __str__(self):
        alvo = f"{self.entry_tipo}:{self.cluster_id or self.item_id}"
        return f"{self.tipo} {alvo}"

    def vigente(self, agora=None) -> bool:
        from django.utils import timezone

        agora = agora or timezone.now()
        if not self.ativo:
            return False
        if self.inicio and agora < self.inicio:
            return False
        if self.fim and agora > self.fim:
            return False
        return True
