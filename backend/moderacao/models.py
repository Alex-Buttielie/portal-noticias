from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Denuncia(models.Model):
    """
    BRD §16 — aponta para QUALQUER objeto denunciável (`comunidade.Comentario`,
    `comunidade.Publicacao`) via ContentType genérico, para não precisar
    importar `comunidade` aqui (evita dependência de carregamento entre apps
    — `moderacao` não sabe nada sobre `comunidade`, só sobre "algum objeto").
    """

    MOTIVO_AMEACA = "ameaca"
    MOTIVO_ASSEDIO = "assedio"
    MOTIVO_DADO_PESSOAL = "dado_pessoal"
    MOTIVO_SPAM = "spam"
    MOTIVO_OUTRO = "outro"
    MOTIVO_CHOICES = [
        (MOTIVO_AMEACA, "Ameaça"),
        (MOTIVO_ASSEDIO, "Assédio"),
        (MOTIVO_DADO_PESSOAL, "Divulgação indevida de dado pessoal"),
        (MOTIVO_SPAM, "Spam"),
        (MOTIVO_OUTRO, "Outro"),
    ]

    STATUS_PENDENTE = "pendente"
    STATUS_PROCEDENTE = "procedente"
    STATUS_IMPROCEDENTE = "improcedente"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_PROCEDENTE, "Procedente"),
        (STATUS_IMPROCEDENTE, "Improcedente"),
    ]

    denunciante = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="denuncias_feitas"
    )
    motivo = models.CharField(max_length=20, choices=MOTIVO_CHOICES, default=MOTIVO_OUTRO)
    detalhe = models.TextField(blank=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    alvo = GenericForeignKey("content_type", "object_id")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDENTE)
    criado_em = models.DateTimeField(auto_now_add=True)
    resolvido_em = models.DateTimeField(null=True, blank=True)
    resolvido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="denuncias_resolvidas",
    )
    resolucao_motivo = models.TextField(blank=True)

    class Meta:
        verbose_name = "denúncia"
        verbose_name_plural = "denúncias"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Denúncia #{self.pk} ({self.status})"


class AcaoModeracao(models.Model):
    TIPO_AVISO = "aviso"
    TIPO_REMOCAO = "remocao_conteudo"
    TIPO_BLOQUEIO_TEMP = "bloqueio_temporario"
    TIPO_BLOQUEIO_PERMANENTE = "bloqueio_permanente"
    TIPO_CHOICES = [
        (TIPO_AVISO, "Aviso"),
        (TIPO_REMOCAO, "Remoção de conteúdo"),
        (TIPO_BLOQUEIO_TEMP, "Bloqueio temporário"),
        (TIPO_BLOQUEIO_PERMANENTE, "Bloqueio permanente"),
    ]

    usuario_alvo = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="acoes_moderacao_recebidas"
    )
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    motivo = models.TextField()
    aplicado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="acoes_moderacao_aplicadas"
    )
    denuncia_relacionada = models.ForeignKey(
        Denuncia, null=True, blank=True, on_delete=models.SET_NULL, related_name="acoes"
    )
    ativo_ate = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ação de moderação"
        verbose_name_plural = "ações de moderação"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.tipo} em {self.usuario_alvo_id}"


class RecursoModeracao(models.Model):
    """Canal de recurso (BRD §16) — usuário moderado contesta uma AcaoModeracao."""

    STATUS_ABERTO = "aberto"
    STATUS_ANALISADO = "analisado"
    STATUS_CHOICES = [(STATUS_ABERTO, "Aberto"), (STATUS_ANALISADO, "Analisado")]

    acao = models.ForeignKey(AcaoModeracao, on_delete=models.CASCADE, related_name="recursos")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recursos_moderacao")
    texto = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ABERTO)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "recurso de moderação"
        verbose_name_plural = "recursos de moderação"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Recurso de {self.usuario_id} sobre ação #{self.acao_id}"


class Reputacao(models.Model):
    """BRD §15 — nunca o único critério de decisão sensível (aplicado em services.aplicar_acao)."""

    NIVEL_RESTRITO = "restrito"
    NIVEL_PADRAO = "padrao"
    NIVEL_CONFIAVEL = "confiavel"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reputacao")
    pontuacao = models.IntegerField(default=100)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "reputação"
        verbose_name_plural = "reputações"

    def __str__(self):
        return f"Reputação de {self.user_id}: {self.pontuacao}"

    @property
    def nivel(self) -> str:
        if self.pontuacao < 0:
            return self.NIVEL_RESTRITO
        if self.pontuacao <= 50:
            return self.NIVEL_PADRAO
        return self.NIVEL_CONFIAVEL


class ReputacaoEventoLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="eventos_reputacao")
    delta = models.IntegerField()
    motivo = models.CharField(max_length=300)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "evento de reputação"
        verbose_name_plural = "eventos de reputação"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.user_id}: {self.delta:+d} ({self.motivo})"


class PaginaEditorial(models.Model):
    """BRD §17 — política editorial pública (conteúdo estático simples, editável via admin)."""

    slug = models.SlugField(unique=True)
    titulo = models.CharField(max_length=200)
    conteudo = models.TextField()
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "página editorial"
        verbose_name_plural = "páginas editoriais"

    def __str__(self):
        return self.titulo
