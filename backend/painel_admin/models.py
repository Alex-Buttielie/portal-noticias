from django.conf import settings
from django.db import models


class AuditoriaAdmin(models.Model):
    acao = models.CharField(max_length=100)
    alvo_tipo = models.CharField(max_length=100)
    alvo_id = models.CharField(max_length=100)
    detalhe = models.JSONField(default=dict, blank=True)
    alterado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "auditoria admin"
        verbose_name_plural = "auditorias admin"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.acao} {self.alvo_tipo}#{self.alvo_id}"


class RegraCuradoria(models.Model):
    """FRENTE 6 — controles editoriais amplos da Central, além do
    `DestaqueEditorial` por entrada (FRENTE 3: manchete/destaque/bloqueio).

    Tipos:
    - boost_entrada / bloqueio_entrada: entrada específica (entry_tipo+entry_id);
    - boost_categoria / bloqueio_categoria: `alvo` = nome da categoria;
    - ordem_categorias: `alvo` = lista separada por vírgula, na ordem desejada;
    - colunista_destaque: `alvo` = nome do autor/colunista (casa com
      `NewsItem.autor` quando o campo existir);
    - selo_forcado / urgente_forcado / exclusivo_forcado: entrada específica
      (`alvo` = nome do selo a exibir; urgente só marca a flag).

    Janela opcional inicio/fim; fora dela a regra é ignorada. O feed geral
    (`feed/views.py::FeedListView`, via `painel_admin.services_regras`)
    aplica bloqueios, boosts e ordem — o algoritmo respeita os overrides.
    """

    TIPO_BOOST_ENTRADA = "boost_entrada"
    TIPO_BLOQUEIO_ENTRADA = "bloqueio_entrada"
    TIPO_BOOST_CATEGORIA = "boost_categoria"
    TIPO_BLOQUEIO_CATEGORIA = "bloqueio_categoria"
    TIPO_ORDEM_CATEGORIAS = "ordem_categorias"
    TIPO_COLUNISTA_DESTAQUE = "colunista_destaque"
    TIPO_SELO_FORCADO = "selo_forcado"
    TIPO_URGENTE_FORCADO = "urgente_forcado"
    TIPO_EXCLUSIVO_FORCADO = "exclusivo_forcado"
    TIPO_CHOICES = [
        (TIPO_BOOST_ENTRADA, "Boost de entrada"),
        (TIPO_BLOQUEIO_ENTRADA, "Bloqueio de entrada"),
        (TIPO_BOOST_CATEGORIA, "Boost de categoria"),
        (TIPO_BLOQUEIO_CATEGORIA, "Bloqueio de categoria"),
        (TIPO_ORDEM_CATEGORIAS, "Ordem fixa de categorias"),
        (TIPO_COLUNISTA_DESTAQUE, "Colunista em destaque"),
        (TIPO_SELO_FORCADO, "Selo forçado"),
        (TIPO_URGENTE_FORCADO, "Urgente forçado"),
        (TIPO_EXCLUSIVO_FORCADO, "Exclusivo forçado"),
    ]
    TIPOS_ENTRADA = {TIPO_BOOST_ENTRADA, TIPO_BLOQUEIO_ENTRADA, TIPO_SELO_FORCADO,
                     TIPO_URGENTE_FORCADO, TIPO_EXCLUSIVO_FORCADO}

    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, db_index=True)
    entry_tipo = models.CharField(max_length=10, blank=True, help_text="'cluster' ou 'item' (só tipos por entrada)")
    entry_id = models.PositiveIntegerField(null=True, blank=True)
    alvo = models.CharField(max_length=300, blank=True, help_text="Categoria, autor, selo ou lista de categorias")
    ordem = models.PositiveIntegerField(default=0, help_text="Menor primeiro (boosts/manchetes extras)")
    ativo = models.BooleanField(default=True, db_index=True)
    inicio = models.DateTimeField(null=True, blank=True)
    fim = models.DateTimeField(null=True, blank=True)
    motivo = models.CharField(max_length=300, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "regra de curadoria"
        verbose_name_plural = "regras de curadoria"
        ordering = ["ordem", "-criado_em"]

    def __str__(self):
        return f"{self.tipo} {self.alvo or (self.entry_tipo + ':' + str(self.entry_id))}"

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
