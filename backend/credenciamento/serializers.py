"""Serializers de credenciamento (BRD §13/§14).

Os campos `foto` e `documento` são `FileField`. A validação de upload
acontece em DUAS camadas, de propósito:

1. **Aqui, no serializer** — para o cliente receber um 400 com mensagem
   clara ANTES de qualquer byte ser gravado, e antes de o registro ser
   criado. É a experiência correta e evita arquivo órfão no disco.
2. **Em `credenciamento/models.py` (`upload_to`)** — a fronteira de
   armazenamento, que roda para o serializer, para o admin do Django,
   para `manage.py shell` e para qualquer código futuro. Se alguém
   gravar um arquivo por um caminho que não passe pelo serializer, a
   validação ainda acontece.

O `upload_to` sozinho levantaria `ValidationError` do Django DEPOIS de o
modelo já estar instanciado, o que no DRF vira um 500 em vez de 400.
"""

import logging

from rest_framework import serializers

from config.uploads import (
    POLITICA_DOCUMENTO,
    POLITICA_FOTO,
    UploadInvalidoError,
    validar_upload,
)

from .models import PerfilJornalista, SolicitacaoCredenciamento

logger = logging.getLogger(__name__)


class _CampoArquivoValidado(serializers.FileField):
    """
    `FileField` que valida o CONTEÚDO do arquivo (magic bytes) e o
    limite de tamanho real no stream, e devolve um objeto de arquivo
    pronto para gravação.

    O `name` não é normalizado aqui: a regeneração acontece no
    `upload_to`, no momento da gravação, para que validação e caminho
    gravado não possam divergir.
    """

    def __init__(self, *, politica, **kwargs) -> None:
        super().__init__(**kwargs)
        self._politica = politica

    def to_internal_value(self, data):
        arquivo = super().to_internal_value(data)
        try:
            validar_upload(arquivo, self._politica)
        except UploadInvalidoError:
            raise
        except Exception as exc:  # noqa: BLE001 — nunca vazar erro interno ao cliente
            logger.exception("Falha inesperada validando upload")
            raise UploadInvalidoError(
                "Não foi possível validar o arquivo enviado."
            ) from exc
        return arquivo


class SolicitacaoCredenciamentoSerializer(serializers.ModelSerializer):
    # Substituem o `FileField` gerado pelo ModelSerializer, que não valida
    # nada. `required`/`allow_null` preservam a semântica do model.
    foto = _CampoArquivoValidado(politica=POLITICA_FOTO, required=False, allow_null=True)
    documento = _CampoArquivoValidado(politica=POLITICA_DOCUMENTO, required=True, allow_null=False)

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
    foto = _CampoArquivoValidado(politica=POLITICA_FOTO, required=False, allow_null=True)

    class Meta:
        model = PerfilJornalista
        fields = ["foto", "mini_bio", "dados_profissionais", "selo_ativo", "suspenso", "credenciado_em"]
        read_only_fields = ["selo_ativo", "suspenso", "credenciado_em"]
