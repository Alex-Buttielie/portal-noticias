from django.core.exceptions import ValidationError
from django.db import models


class NewsCluster(models.Model):
    """
    Agrupamento de `NewsItem` que cobrem o MESMO acontecimento, publicados
    por fontes diferentes (ARCHITECTURE.md secao 3). Criado pelo pipeline de
    ingestao (`services/ingestao.py`, a partir do resultado de
    `services/deduplicacao.py`) — nunca diretamente por um `NewsItem`
    isolado sem cobertura duplicada.
    """

    titulo_acontecimento = models.CharField(max_length=300)
    categoria_dominante = models.CharField(max_length=100, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "cluster de noticias"
        verbose_name_plural = "clusters de noticias"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.titulo_acontecimento

    @property
    def numero_fontes_distintas(self) -> int:
        return self.itens.values("nome_fonte").distinct().count()


class NewsItem(models.Model):
    """
    Uma noticia individual ingerida de uma fonte (ARCHITECTURE.md secao 3).

    Direitos autorais (BRD secao 18, implementation-contract.md criterio de
    aceite 3): `url_fonte_original` e `nome_fonte` sao OBRIGATORIOS — a
    ausencia de qualquer um deles impede a criacao/atualizacao do item (ver
    `save()` abaixo + constraint de banco), nunca e best-effort.
    """

    STATUS_PENDENTE = "pendente"
    STATUS_APROVADO = "aprovado"
    STATUS_REJEITADO = "rejeitado"
    STATUS_NAO_APLICAVEL = "nao_aplicavel"
    STATUS_REVISAO_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_APROVADO, "Aprovado"),
        (STATUS_REJEITADO, "Rejeitado"),
        (STATUS_NAO_APLICAVEL, "Nao aplicavel (nao exige revisao)"),
    ]

    titulo = models.CharField(max_length=300)
    resumo_proprio = models.TextField(
        blank=True,
        help_text="Conteudo proprio gerado pelo SummarizationProvider — NUNCA copia do texto bruto original.",
    )
    conteudo_bruto = models.TextField(
        blank=True,
        help_text=(
            "Conteudo bruto ingerido da fonte (snippet/summary do RSS), guardado apenas para "
            "auditoria/depuracao interna — nunca deve ser exibido como resumo_proprio "
            "(implementation-contract.md, criterio de aceite 4)."
        ),
    )

    url_fonte_original = models.URLField(max_length=1000, unique=True)
    nome_fonte = models.CharField(max_length=150)

    categoria = models.CharField(max_length=100, blank=True)

    # Localidade (run 20260902-radar-tendencias-localizacao, BRD §11) —
    # campos livres, preenchidos best-effort pelo pipeline de ingestão
    # (inferência textual/fonte) quando disponível; nunca bloqueiam a
    # criação do item se vazios (ao contrário de url_fonte_original/nome_fonte).
    pais = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=150, blank=True)

    timestamp_publicacao_fonte = models.DateTimeField(null=True, blank=True)
    timestamp_ingestao = models.DateTimeField(auto_now_add=True)

    urgente = models.BooleanField(default=False)
    status_revisao = models.CharField(
        max_length=20, choices=STATUS_REVISAO_CHOICES, default=STATUS_PENDENTE
    )

    cluster = models.ForeignKey(
        NewsCluster, null=True, blank=True, on_delete=models.SET_NULL, related_name="itens"
    )

    class Meta:
        verbose_name = "noticia"
        verbose_name_plural = "noticias"
        ordering = ["-timestamp_ingestao"]
        constraints = [
            # Defesa em profundidade: alem da validacao em `save()`, o
            # proprio banco recusa registrar um NewsItem sem
            # url_fonte_original/nome_fonte preenchidos (funciona tanto em
            # PostgreSQL quanto em SQLite).
            models.CheckConstraint(
                condition=~models.Q(url_fonte_original="") & ~models.Q(nome_fonte=""),
                name="newsitem_fonte_obrigatoria",
            ),
        ]

    def __str__(self):
        return self.titulo

    def clean(self):
        super().clean()
        if not self.url_fonte_original:
            raise ValidationError(
                {"url_fonte_original": "URL da fonte original e obrigatoria (rastreabilidade — BRD secao 18)."}
            )
        if not self.nome_fonte:
            raise ValidationError(
                {"nome_fonte": "Nome da fonte e obrigatorio (rastreabilidade — BRD secao 18)."}
            )

    def save(self, *args, **kwargs):
        # Validacao explicita, nao best-effort (implementation-contract.md,
        # criterio de aceite 3): qualquer tentativa de criar/atualizar um
        # NewsItem sem url_fonte_original ou nome_fonte e rejeitada aqui,
        # antes de tocar o banco (e reforcada pela CheckConstraint acima).
        self.clean()
        super().save(*args, **kwargs)

    @property
    def publicado_automaticamente(self) -> bool:
        return self.status_revisao == self.STATUS_NAO_APLICAVEL


class FonteRobo(models.Model):
    nome = models.CharField(max_length=150, unique=True)
    url = models.URLField(max_length=1000, unique=True)
    ativo = models.BooleanField(default=True)
    categoria_padrao = models.CharField(max_length=100, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "fonte de robo"
        verbose_name_plural = "fontes de robos"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({'ativo' if self.ativo else 'inativo'})"


class ConfiguracaoRobo(models.Model):
    intervalo_minutos = models.PositiveIntegerField(default=15)
    ativo = models.BooleanField(default=True)
    categorias_sensiveis = models.CharField(max_length=500, default="política,economia,segurança pública")
    limiar_fontes_alta_relevancia = models.PositiveIntegerField(default=3)
    dedup_limiar_similaridade = models.FloatField(default=0.55)
    dedup_janela_horas = models.FloatField(default=24)
    dedup_max_itens = models.PositiveIntegerField(default=300)
    resumo_similaridade_maxima = models.FloatField(default=0.6)
    resumo_trecho_copiado_maximo = models.FloatField(default=0.6)
    dedup_cluster_sempre_exige_revisao = models.BooleanField(default=True)
    llm_model = models.CharField(max_length=100, default="gpt-4o-mini")
    llm_api_base_url = models.URLField(max_length=500, default="https://api.openai.com/v1")
    llm_tamanho_lote = models.PositiveIntegerField(default=10)
    llm_max_tokens_por_item = models.PositiveIntegerField(default=220)
    llm_teto_gasto_diario_usd = models.FloatField(default=5.0)
    llm_preco_por_1k_tokens = models.FloatField(default=0.15)
    llm_timeout_segundos = models.PositiveIntegerField(default=30)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "configuracao de robo"
        verbose_name_plural = "configuracao de robos"

    def __str__(self):
        return "Configuracao de Robos"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


class RegistroExecucaoIngestao(models.Model):
    """
    Registro consultavel de UMA execucao do pipeline de ingestao
    (implementation-contract.md, criterio de aceite 6): quantidade de itens
    por fonte, duplicatas agrupadas e uso/custo do `SummarizationProvider` —
    observabilidade de custo de IA exigida desde o MVP (BRD secao 30).
    """

    executado_em = models.DateTimeField(auto_now_add=True)

    itens_por_fonte = models.JSONField(default=dict, help_text="Ex.: {'G1': 12, 'UOL': 9}")
    erros_por_fonte = models.JSONField(
        default=dict, blank=True, help_text="Fontes que falharam nesta execucao e a mensagem de erro registrada."
    )

    total_itens_ingeridos = models.PositiveIntegerField(default=0)
    total_grupos_formados = models.PositiveIntegerField(default=0)
    total_duplicatas_agrupadas = models.PositiveIntegerField(
        default=0, help_text="total_itens_ingeridos - total_grupos_formados"
    )

    chamadas_summarization_provider = models.PositiveIntegerField(default=0)
    tokens_utilizados_summarization = models.PositiveIntegerField(null=True, blank=True)
    custo_estimado_summarization_usd = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "registro de execucao de ingestao"
        verbose_name_plural = "registros de execucao de ingestao"
        ordering = ["-executado_em"]

    def __str__(self):
        return f"Ingestao {self.executado_em:%Y-%m-%d %H:%M} — {self.total_itens_ingeridos} itens"
