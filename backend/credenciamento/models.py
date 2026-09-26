from django.conf import settings
from django.db import models

from config.uploads import (
    POLITICA_DOCUMENTO,
    POLITICA_FOTO,
    UploadInvalidoError,
    detectar_tipo,
    nome_regenerado,
    validar_upload,
)


def _caminho_validado(instance, arquivo, politica, campo: str) -> str:
    """
    Valida `arquivo` e devolve o caminho com nome REGENERADO.

    Este é o `upload_to` de todos os campos de upload do app, e é a
    última fronteira antes do disco: roda para POST do serializer, para
    o admin do Django, para `manage.py shell` e para qualquer código
    futuro. Não importa como o arquivo chegou aqui.
    """
    conteudo = validar_upload(arquivo, politica)
    tipo = detectar_tipo(conteudo, politica)
    if tipo is None:  # pragma: no cover — `validar_upload` já recusou
        raise UploadInvalidoError(f"Tipo de arquivo não permitido para '{campo}'.")
    nome = nome_regenerado(tipo[0])
    return f"{politica.prefixo}/{instance.user_id}/{nome}"


def caminho_documento(instance, filename):
    """
    `upload_to` do documento comprobatório (`SolicitacaoCredenciamento`).

    ANTES (P0-10, eixo 3): `f"credenciamento/{instance.user_id}/{filename}"`
    — o nome vinha LITERALMENTE do cliente. Controlava a extensão (gravar
    um `.html` e tê-lo servido como `text/html` na origem do portal = XSS
    armazenado) e permitia colisão/sobrescrita.

    AGORA: `filename` é IGNORADO. O tipo vem dos magic bytes e o nome é
    `<uuid4hex><ext canônica>`.

    A assinatura da função não mudou, e é ela que as migrations referenciam
    (`credenciamento.models.caminho_documento`) — por isso nenhuma migration
    precisa ser criada nem alterada.
    """
    return _caminho_validado(instance, instance.documento, POLITICA_DOCUMENTO, "documento")


def caminho_foto_solicitacao(instance, filename):
    """`upload_to` da foto na solicitação de credenciamento."""
    return _caminho_validado(instance, instance.foto, POLITICA_FOTO, "foto")


def caminho_foto_perfil(instance, filename):
    """`upload_to` da foto no perfil do jornalista credenciado."""
    return _caminho_validado(instance, instance.foto, POLITICA_FOTO, "foto")


class SolicitacaoCredenciamento(models.Model):
    """
    Solicitação de credenciamento de jornalista (BRD §13;
    implementation-contract.md run 20260902-1503-credenciamento-jornalistas).
    """

    STATUS_PENDENTE = "pendente"
    STATUS_APROVADO = "aprovado"
    STATUS_REPROVADO = "reprovado"
    STATUS_INFO_SOLICITADA = "info_solicitada"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_APROVADO, "Aprovado"),
        (STATUS_REPROVADO, "Reprovado"),
        (STATUS_INFO_SOLICITADA, "Informação adicional solicitada"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="solicitacoes_credenciamento"
    )
    # BRD §13 — "Cadastro básico: nome, e-mail, telefone opcional,
    # cidade/UF, foto opcional, mini bio e dados profissionais." Gap real
    # encontrado na análise do BRD: telefone nunca foi implementado (nome/
    # e-mail vêm do User, os demais já existiam abaixo).
    telefone = models.CharField(max_length=30, blank=True)
    cidade = models.CharField(max_length=150, blank=True)
    uf = models.CharField(max_length=2, blank=True)
    foto = models.FileField(upload_to=caminho_foto_solicitacao, blank=True, null=True)
    mini_bio = models.TextField(blank=True)
    dados_profissionais = models.TextField(blank=True)
    # Documento comprobatório (diploma/registro). Nunca exposto via URL
    # pública direta — só através de credenciamento/views.py::DocumentoView,
    # que checa se o requisitante é o próprio solicitante ou um admin.
    documento = models.FileField(upload_to=caminho_documento)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDENTE)
    criado_em = models.DateTimeField(auto_now_add=True)
    decidido_em = models.DateTimeField(null=True, blank=True)
    decidido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decisoes_credenciamento",
    )
    motivo_decisao = models.TextField(blank=True)

    class Meta:
        verbose_name = "solicitação de credenciamento"
        verbose_name_plural = "solicitações de credenciamento"
        ordering = ["criado_em"]

    def __str__(self):
        return f"Solicitação de {self.user} ({self.status})"


class PerfilJornalista(models.Model):
    """
    Selo de jornalista credenciado (BRD §14) — criado quando uma
    `SolicitacaoCredenciamento` é aprovada. `services.pode_publicar(user)` é
    a função pública que outros módulos (`comunidade`) devem usar — nunca
    checar este modelo diretamente fora deste app.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil_jornalista"
    )
    selo_ativo = models.BooleanField(default=True)
    credenciado_em = models.DateTimeField(auto_now_add=True)
    suspenso = models.BooleanField(default=False)
    motivo_suspensao = models.TextField(blank=True)

    # BRD §14 — "Gerenciar perfil profissional" é um poder explícito do
    # autor credenciado. Gap real encontrado na análise do BRD: esses dados
    # só existiam na SolicitacaoCredenciamento (registro histórico da
    # candidatura, nunca editado depois da decisão) — não havia nenhum
    # lugar que representasse o perfil VIVO, editável pelo próprio
    # jornalista após aprovado. Copiados da solicitação no momento da
    # aprovação (`services.decidir`) e, a partir daí, editáveis
    # independentemente via `services.atualizar_perfil`.
    foto = models.FileField(upload_to=caminho_foto_perfil, blank=True, null=True)
    mini_bio = models.TextField(blank=True)
    dados_profissionais = models.TextField(blank=True)

    class Meta:
        verbose_name = "perfil de jornalista"
        verbose_name_plural = "perfis de jornalista"

    def __str__(self):
        return f"Jornalista: {self.user}"

    @property
    def credenciamento_valido(self) -> bool:
        return self.selo_ativo and not self.suspenso
