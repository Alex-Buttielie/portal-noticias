from django.conf import settings
from django.db import models


class Publicacao(models.Model):
    """Opinião/análise de autor credenciado (BRD §12, §14)."""

    TIPO_OPINIAO = "opiniao"
    TIPO_ANALISE = "analise"
    TIPO_CHOICES = [(TIPO_OPINIAO, "Opinião"), (TIPO_ANALISE, "Análise")]

    STATUS_RASCUNHO = "rascunho"
    STATUS_ENVIADO = "enviado"
    STATUS_PUBLICADO = "publicado"
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, "Rascunho"),
        (STATUS_ENVIADO, "Enviado"),
        (STATUS_PUBLICADO, "Publicado"),
    ]

    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="publicacoes")
    titulo = models.CharField(max_length=300)
    conteudo = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO)
    categoria = models.CharField(max_length=100, blank=True)
    tags = models.JSONField(default=list, blank=True)

    # Associação a um acontecimento (BRD §14, requisito 2) — ambos opcionais
    # e independentes (uma publicação pode não estar ligada a nada).
    news_cluster = models.ForeignKey(
        "catalogo_noticias.NewsCluster",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="publicacoes",
    )
    news_item = models.ForeignKey(
        "catalogo_noticias.NewsItem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="publicacoes",
    )

    destaque = models.BooleanField(default=False)

    # BRD §16, requisito 3 ("remoção de conteúdo" como ação de moderação) —
    # setado por moderacao.services.aplicar_acao via a GenericForeignKey de
    # Denuncia.alvo (moderacao nunca importa este model diretamente, ver
    # comentário em moderacao/models.py). Achado de revisão de segurança:
    # antes desta correção, uma ação de remoção só descontava reputação, sem
    # nunca de fato ocultar o conteúdo denunciado das listagens públicas.
    oculto = models.BooleanField(default=False)
    ocultado_em = models.DateTimeField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    publicado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "publicação"
        verbose_name_plural = "publicações"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.titulo} ({self.tipo}, {self.status})"


class Comentario(models.Model):
    """
    Comentário em uma `Publicacao` OU em um `NewsItem` do feed — exatamente
    um dos dois (constraint de banco). `resposta_de` permite só 1 nível de
    resposta (validado em `services.comentar`, reforçado aqui só como dado).
    """

    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comentarios")
    conteudo = models.TextField()

    publicacao = models.ForeignKey(
        Publicacao, null=True, blank=True, on_delete=models.CASCADE, related_name="comentarios"
    )
    news_item = models.ForeignKey(
        "catalogo_noticias.NewsItem",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="comentarios",
    )
    resposta_de = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="respostas"
    )

    # Ver comentário equivalente em Publicacao.oculto.
    oculto = models.BooleanField(default=False)
    ocultado_em = models.DateTimeField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "comentário"
        verbose_name_plural = "comentários"
        ordering = ["criado_em"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(publicacao__isnull=False, news_item__isnull=True)
                    | models.Q(publicacao__isnull=True, news_item__isnull=False)
                ),
                name="comentario_exatamente_um_alvo",
            ),
        ]

    def __str__(self):
        return f"Comentário de {self.autor_id} em {self.publicacao_id or self.news_item_id}"


class Seguidor(models.Model):
    seguidor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="seguindo")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="seguidores")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "seguidor"
        verbose_name_plural = "seguidores"
        unique_together = [("seguidor", "autor")]

    def __str__(self):
        return f"{self.seguidor_id} segue {self.autor_id}"
