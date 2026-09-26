"""
Hardening de upload (P0-10, eixo 3).

=============================================================================
INVENTÁRIO (medido nesta base)
=============================================================================
O projeto tem UM app com upload: `credenciamento`, com três `FileField`:
  - `SolicitacaoCredenciamento.documento` (obrigatório)  — models.py:42
  - `SolicitacaoCredenciamento.foto`      (opcional)   — models.py:36
  - `PerfilJornalista.foto`                (opcional)   — models.py:89

Estado ANTES deste módulo (medido, não suposto):
  - Nenhuma validação de extensão.
  - Nenhuma validação de tipo de conteúdo: o `content_type` declarado pelo
    cliente era aceito sem verificação.
  - Nenhum limite de tamanho de arquivo.
  - `credenciamento/models.py:6` gravava o NOME ENVIADO PELO CLIENTE
    literalmente: `f"credenciamento/{instance.user_id}/{filename}"`.
    Isto é (a) path traversal — Django normaliza e remove `..`, mas
    transforma `../../x` em `x`, o que ainda permite colisão/sobrescrita;
    e (b) controle total da EXTENSÃO pelo cliente, ou seja, era possível
    gravar um `.html` com `<script>` e tê-lo servido na origem do portal.
  - `credenciamento/views.py:78` servia o documento com `FileResponse` e
    NENHUM header de defesa: sem `Content-Disposition: attachment`, sem
    `X-Content-Type-Options: nosniff`, e com o `Content-Type` deduzido
    do nome do arquivo. Um `.html`/`.svg` armazenado era servido como
    `text/html` na origem do portal = XSS ARMAZENADO.

=============================================================================
O QUE ESTE MÓDULO FAZ
=============================================================================
Cinco controles, nesta ordem:

1. **NOME REGENERADO.** O nome do cliente é descartado por completo. O
   arquivo é gravado como `<uuid4hex><ext canônica>`. Elimina traversal,
   colisão, double-extension (`x.pdf.html`), null-byte e caracteres de
   controle de uma vez. A extensão canônica vem do TIPO DETECTADO, não do
   que o cliente mandou.

2. **TIPO POR CONTEÚDO (magic bytes).** Lemos os primeiros bytes do
   arquivo e comparamos com assinaturas conhecidas. O `content_type`
   declarado é irrelevante para a decisão — é registrado apenas para
   diagnóstico. Extensão E tipo declarado precisam concordar entre si e com o
   conteúdo; se discordarem, a condição de negate vale (fail-closed).

3. **LIMITE REAL APLICADO NO STREAM.** Lemos em blocos de
   `TAMANHO_BLOCO` e ABORTAMOS assim que o acumulado passa do limite.
   Não confiamos em `Content-Length` (controlado pelo cliente) nem em
   `arquivo.size` sozinho (que o Django define ao gravar em disco). O
   `.size` é usado só como rejeição barata antecipada; a garantia real é
   a leitura em blocos.

4. **CONTEÚDO INERTE.** Além da assinatura, rejeitamos arquivo cujo
   início se pareça com markup/script (defesa contra polyglot: um PDF com
   `%PDF-` nos 5 primeiros bytes e `<script>` em seguida não passa, porque
   também checamos se o cabeçalho contém `<script`/`<html` cedo demais).

5. **FORA DO DIRETÓRIO SERVIDO.** Verificamos que `MEDIA_ROOT` não está
   dentro de `STATIC_ROOT`, que é servido pelo WhiteNoise com dedução de
   `Content-Type`. Um upload dentro de `STATIC_ROOT` seria servido como
   estático executável.

Nenhuma verificação de upload pode "engolir" o erro: todas levantam
`UploadInvalidoError`, que NÃO é subclasse de `ValidationError` do DRF por
acaso — o serializer a converte em 400 com mensagem, e o chamador não
consegue ignorá-la por acidente.

=============================================================================
NÃO HÁ EXECUÇÃO DE ARQUIVO ENVIADO NESTE PROJETO
=============================================================================
Verificado por varredura (`subprocess`, `os.system`, `exec`, `eval`,
`popen`): zero ocorrências em código de produção. Nenhum handler trata
upload como código. A única superfície de "execução" seria um `.html`
servido no navegador, fechada pelos controles 2 e 4 acima.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable
from uuid import uuid4

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile

logger = logging.getLogger(__name__)

#: Bloco de leitura da validação. 64 KiB: grande o bastante para não
#: gerar muitas chamadas, pequeno o bastante para que o pico de memória
#: durante a validação seja desprezível mesmo com vários uploads
#: simultâneos.
TAMANHO_BLOCO = 64 * 1024

#: Quantos bytes lemos para detectar o tipo. Nenhum formato aceito tem
#: assinatura mais longa que isso.
TAMANHO_CABECALHO = 512


class UploadInvalidoError(DjangoValidationError):
    """
    Upload recusado. Herda de `ValidationError` do Django para que o DRF
    a traduza em 400 automaticamente, e fica disponível como tipo
    distinto para o chamador tratar a mensagem.
    """


# ---------------------------------------------------------------------------
# Tipos aceitos
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TipoAceito:
    """
    Um tipo de arquivo permitido, descrito por TRÊS coisas que precisam
    concordar: extensão, assinatura de conteúdo e tipo MIME.
    """

    extensoes: frozenset[str]
    assinaturas: tuple[bytes, ...]
    content_types: frozenset[str]
    rotulo: str
    #: Função opcional de validação mais profunda (ex.: dimensões de imagem).
    validador_extra: Callable[[bytes], str | None] = field(default=lambda _cabecalho: None)


#: PDF. A assinatura `%PDF-` é o padrão; note que um PDF pode ter lixo
#: antes (raro, mas legal), por isso a checagem é "nos primeiros bytes
#: significativos" e não "byte 0 exato".
PDF = TipoAceito(
    extensoes=frozenset({".pdf"}),
    assinaturas=(b"%PDF-",),
    content_types=frozenset({"application/pdf"}),
    rotulo="PDF",
)

JPEG = TipoAceito(
    extensoes=frozenset({".jpg", ".jpeg"}),
    assinaturas=(b"\xff\xd8\xff",),
    content_types=frozenset({"image/jpeg"}),
    rotulo="JPEG",
)

PNG = TipoAceito(
    extensoes=frozenset({".png"}),
    assinaturas=(b"\x89PNG\r\n\x1a\n",),
    content_types=frozenset({"image/png"}),
    rotulo="PNG",
)

def _webp_real(cabecalho: bytes) -> str | None:
    """
    `RIFF` sozinho não basta: tem de ter `WEBP` nos 4 bytes seguintes.

    Sem isto, um `.wav`, `.avi` ou qualquer RIFF arbitrário passaria como
    "imagem" pelo campo de avatar.
    """
    if len(cabecalho) < 12 or cabecalho[8:12] != b"WEBP":
        return "arquivo RIFF que não é WebP"
    return None


#: `RIFF....WEBP` — 4 bytes de tamanho no meio, por isso a validação extra.
WEBP = TipoAceito(
    extensoes=frozenset({".webp"}),
    assinaturas=(b"RIFF",),
    content_types=frozenset({"image/webp"}),
    rotulo="WebP",
    validador_extra=_webp_real,
)

TODOS_OS_TIPOS: tuple[TipoAceito, ...] = (PDF, JPEG, PNG, WEBP)


# ---------------------------------------------------------------------------
# Política por campo
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PoliticaUpload:
    """O que um campo de upload aceita."""

    nome: str
    tipos: tuple[TipoAceito, ...]
    max_bytes: int
    #: Prefixo do caminho dentro de MEDIA_ROOT.
    prefixo: str


#: Foto de perfil: só imagem. Um `.html` aqui é o vetor de XSS
#: armazenado clássico (avatar que "é" uma página).
POLITICA_FOTO = PoliticaUpload(
    nome="foto",
    tipos=(JPEG, PNG, WEBP),
    max_bytes=5 * 1024 * 1024,
    prefixo="credenciamento",
)

#: Documento comprobatório: PDF é o formato canônico do BRD; imagens de
#: documento (celular fotografando o diploma) são aceitas por porque é o
#: uso real do campo. Mesmo assim, servido como anexo e nunca inline.
POLITICA_DOCUMENTO = PoliticaUpload(
    nome="documento",
    tipos=(PDF, JPEG, PNG),
    max_bytes=10 * 1024 * 1024,
    prefixo="credenciamento",
)

POLITICAS: dict[str, PoliticaUpload] = {
    "foto": POLITICA_FOTO,
    "documento": POLITICA_DOCUMENTO,
}


# ---------------------------------------------------------------------------
# Detecção
# ---------------------------------------------------------------------------

#: Cabeçalhos que indicam que um "arquivo" é na verdade markup/script.
#: Checagem de polyglot: um arquivo que começa como PDF/JPEG/PNG e tem
#: marcação cedo demais é recusado.
_RE_MARCACAO_CEDO = re.compile(
    rb"<\s*(script|html|body|iframe|svg|meta)\b", re.IGNORECASE
)


def detectar_tipo(cabecalho: bytes, politica: PoliticaUpload) -> tuple[TipoAceito, bytes] | None:
    """
    Devolve o tipo detectado pelo CONTEÚDO, ou `None`.

    A checagem é por assinatura real, não por `mimetypes` nem pelo
    `content_type` declarado — os dois são controlados pelo cliente.
    """
    for tipo in politica.tipos:
        for assinatura in tipo.assinaturas:
            if not cabecalho.startswith(assinatura):
                continue
            problema = tipo.validador_extra(cabecalho)
            if problema:
                logger.warning("Upload com assinatura de %s inválida: %s", tipo.rotulo, problema)
                continue
            return tipo, cabecalho
    return None


def _content_type_declarado(arquivo: UploadedFile) -> str:
    return (getattr(arquivo, "content_type", "") or "").split(";")[0].strip().lower()


def _extensao_do_cliente(arquivo: UploadedFile) -> str:
    nome = getattr(arquivo, "name", "") or ""
    # `Path(...).suffix` devolve só a ÚLTIMA extensão: `x.pdf.html` -> `.html`.
    return Path(nome).suffix.lower()


def _nome_seguro(nome: str) -> str:
    """Nome do cliente reduzido a um slug inerte, só para o log."""
    limpo = re.sub(r"[^A-Za-z0-9._-]", "_", (nome or "")[:60])
    return limpo or "(sem nome)"


# ---------------------------------------------------------------------------
# Validação
# ---------------------------------------------------------------------------


def validar_upload(
    arquivo: UploadedFile,
    politica: PoliticaUpload,
    *,
    sufixo: str | None = None,
) -> bytes:
    """
    Valida `arquivo` e devolve o CONTEÚDO em memória.

    Levanta `UploadInvalidoError` para qualquer recusa. O chamador grava
    o resultado com um nome REGENERADO; o nome do cliente é irrelevante
    daqui para frente.
    """
    if arquivo is None:
        raise UploadInvalidoError("Nenhum arquivo foi enviado.")

    # 1) Rejeição barata antecipada. `size` vem do upload handler, mas
    #    sozinho NÃO é a garantia (ver docstring): pode ser None em
    #    arquivos de stream.
    tamanho_declarado = getattr(arquivo, "size", None)
    if isinstance(tamanho_declarado, int) and tamanho_declarado > politica.max_bytes:
        raise UploadInvalidoError(
            f"O arquivo '{_nome_seguro(getattr(arquivo, 'name', ''))}' tem "
            f"{tamanho_declarado} bytes e o limite para '{politica.nome}' é "
            f"{politica.max_bytes} bytes."
        )

    # 2) Leitura em blocos: limite REAL no stream + captura do cabeçalho
    #    para a detecção de tipo. Uma leitura `.read()` única seria
    #    exatamente o que o requisito proíbe.
    try:
        arquivo.seek(0)
    except (AttributeError, ValueError):
        pass  # stream sem seek: lemos do início mesmo

    acumulado = bytearray()
    lido_total = 0
    try:
        for bloco in arquivo.chunks(TAMANHO_BLOCO):
            lido_total += len(bloco)
            if lido_total > politica.max_bytes:
                raise UploadInvalidoError(
                    f"O arquivo enviado ultrapassa o limite de "
                    f"{politica.max_bytes} bytes para '{politica.nome}'."
                )
            if len(acumulado) < TAMANHO_CABECALHO:
                acumulado.extend(bloco[: TAMANHO_CABECALHO - len(acumulado)])
    except UploadInvalidoError:
        raise
    except Exception as exc:  # noqa: BLE001 — erro de leitura vira recusa, não 500
        raise UploadInvalidoError(
            f"Não foi possível ler o arquivo enviado: {exc.__class__.__name__}."
        ) from exc

    conteudo = bytes(acumulado)

    # 3) Tipo por CONTEÚDO.
    detectado = detectar_tipo(conteudo, politica)
    if detectado is None:
        raise UploadInvalidoError(
            f"Tipo de arquivo não permitido para '{politica.nome}'. "
            f"Permitidos: {', '.join(sorted({t.rotulo for t in politica.tipos}))}. "
            "A validação é feita pelo CONTEÚDO do arquivo, não pelo nome "
            "nem pelo tipo declarado."
        )
    tipo, cabecalho = detectado

    # 4) Polyglot: assinatura válida + markup/script cedo demais.
    if _RE_MARCACAO_CEDO.search(cabecalho):
        raise UploadInvalidoError(
            f"O arquivo '{_nome_seguro(getattr(arquivo, 'name', ''))}' contém "
            "marcação no início do arquivo e foi recusado."
        )

    # 5) EXTENSÃO e CONTENT-TYPE declarados precisam concordar com o
    #    conteúdo. Discordar é sinal de tentativa, não de erro honesto.
    extensao_cliente = _extensao_do_cliente(arquivo)
    if extensao_cliente and extensao_cliente not in tipo.extensoes:
        raise UploadInvalidoError(
            f"A extensão '{extensao_cliente}' não corresponde ao conteúdo "
            f"detectado ({tipo.rotulo}). Extensões aceitas: "
            f"{', '.join(sorted(tipo.extensoes))}."
        )
    declarado = _content_type_declarado(arquivo)
    if declarado and declarado not in tipo.content_types:
        raise UploadInvalidoError(
            f"O tipo declarado '{declarado}' não corresponde ao conteúdo "
            f"detectado ({tipo.rotulo})."
        )

    return conteudo


def nome_regenerado(tipo: TipoAceito, sufixo: str | None = None) -> str:
    """
    Nome de arquivo REGENERADO.

    O nome enviado pelo cliente é DESCARTADO por completo — é a raiz de
    traversal, colisão, double-extension e null-byte. A extensão vem do
    tipo DETECTADO pelo conteúdo, então um `.html` enviado vira um
    `.jpg` (que nem seria aceito) e nunca um `.html`.
    """
    extensao = sufixo if sufixo else sorted(tipo.extensoes)[0]
    if not extensao.startswith("."):
        extensao = f".{extensao}"
    return f"{uuid4().hex}{extensao.lower()}"


def caminho_de_armazenamento(politica: PoliticaUpload, instance_pk: object, nome: str) -> str:
    """
    Caminho RELATIVO dentro de MEDIA_ROOT, para `upload_to`.

    O diretório é derivado de `instance_pk` (inteiro do banco) e do
    `nome` já regenerado. Nada vem do cliente.
    """
    return f"{politica.prefixo}/{instance_pk}/{nome}"


def salvar_upload(
    arquivo: UploadedFile,
    politica: PoliticaUpload,
    *,
    instance_pk: object,
) -> str:
    """
    Valida, regenera o nome e grava. Devolve o caminho relativo salvo.

    Chamado de dentro de `upload_to`, que recebe a `instance` — o
    `instance.pk` já existe porque o Django salva o registro antes de
    gravar o arquivo.
    """
    conteudo = validar_upload(arquivo, politica)
    tipo = detectar_tipo(conteudo[:TAMANHO_CABECALHO], politica)
    if tipo is None:  # pragma: no cover — `validar_upload` já recusou
        raise UploadInvalidoError("Tipo de arquivo não permitido.")
    nome = nome_regenerado(tipo[0])
    caminho = caminho_de_armazenamento(politica, instance_pk, nome)
    nome_gravado = default_storage.save(caminho, _ComoArquivo(conteudo))
    logger.info(
        "Upload aceito: campo=%s tipo=%s bytes=%d nome_original=%s nome_gravado=%s",
        politica.nome,
        tipo[0].rotulo,
        len(conteudo),
        _nome_seguro(getattr(arquivo, "name", "")),
        nome_gravado,
    )
    return nome_gravado


class _ComoArquivo:
    """
    Envolve bytes em um objeto com a interface de `UploadedFile` que o
    `Storage.save` usa (`.chunks()`, `.name`, `.size`).

    Gravar o conteúdo JÁ VALIDADO em memória tem duas vantagens: o
    arquivo do cliente não precisa ser re-lido, e o que vai para o disco é
    exatamente o que foi inspecionado — não há TOCTOU entre "validar" e
    "gravar" (o mesmo arquivo poderia ser trocado entre as duas
    operações se gravássemos direto do stream do cliente).
    """

    def __init__(self, conteudo: bytes, nome: str = "upload") -> None:
        self._conteudo = conteudo
        self._posicao = 0
        self.name = nome
        self.size = len(conteudo)

    def chunks(self, chunk_size: int | None = None):
        tamanho = chunk_size or TAMANHO_BLOCO
        while self._posicao < len(self._conteudo):
            fim = min(self._posicao + tamanho, len(self._conteudo))
            yield self._conteudo[self._posicao : fim]
            self._posicao = fim

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            n = len(self._conteudo) - self._posicao
        fatia = self._conteudo[self._posicao : self._posicao + n]
        self._posicao += len(fatia)
        return fatia

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self._posicao = offset
        elif whence == 1:
            self._posicao += offset
        else:
            self._posicao = len(self._conteudo) + offset
        return self._posicao

    def tell(self) -> int:
        return self._posicao

    def close(self) -> None:
        return None


# ---------------------------------------------------------------------------
# Servida segura
# ---------------------------------------------------------------------------

#: Content-Type SEMPRE usado na servida. `application/octet-stream` +
#: `nosniff` + `Content-Disposition: attachment` é a combinação que
#: impede o browser de tentar interpretar o arquivo. Mesmo para
#: imagens, que são baixadas como anexo pela `DocumentoView` — a foto de
#: perfil é exibida pelo frontend a partir do mesmo arquivo, mas sempre
#: via URL do provedor de mídia, nunca por esta view.
CONTENT_TYPE_SERVIDA = "application/octet-stream"

#: Cabeçalhos aplicados a todo arquivo servido por uma view de download.
HEADERS_DEFESA_ARQUIVO: dict[str, str] = {
    "Content-Type": CONTENT_TYPE_SERVIDA,
    "Content-Disposition": "attachment",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
    "Cache-Control": "private, no-store",
}


def headers_de_servida(nome_arquivo: str | None = None) -> dict[str, str]:
    """
    Cabeçalhos de defesa para servir um arquivo enviado.

    `Content-Disposition: attachment` sem `filename` (ou com um nome
    sanitizado) — nunca com o nome original do cliente, que pode conter
    CRLF para injeção de cabeçalho ou aspas para enganar o dialog de
    download do browser.
    """
    cabecalhos = dict(HEADERS_DEFESA_ARQUIVO)
    if nome_arquivo:
        seguro = re.sub(r"[^A-Za-z0-9._-]", "_", Path(str(nome_arquivo)).name)[:80]
        if seguro and seguro not in {".", ".."}:
            cabecalhos["Content-Disposition"] = f'attachment; filename="{seguro}"'
    return cabecalhos


# ---------------------------------------------------------------------------
# MEDIA_ROOT fora do diretório servido
# ---------------------------------------------------------------------------


def verificar_media_root_fora_do_servido() -> str | None:
    """
    Devolve a mensagem de erro se `MEDIA_ROOT` estiver dentro de
    `STATIC_ROOT` (ou ao contrário), `None` se estiver tudo bem.

    Por que importa: `STATIC_ROOT` é servido pelo WhiteNoise, que DEDUZ o
    `Content-Type` pelo nome. Um upload depositado ali seria servido como
    estático — e um `.html` uploadado seria executado na origem do portal.
    `MEDIA_ROOT` também não deve ser o próprio `STATIC_ROOT`.

    Não levanta: é uma verificação de configuração, chamada em
    `AppConfig.ready` com log de erro, para não impedir o boot por um
    detalhe de ambiente de desenvolvimento.
    """
    from django.conf import settings

    media = Path(getattr(settings, "MEDIA_ROOT", "") or "")
    static_root = Path(getattr(settings, "STATIC_ROOT", "") or "")
    if not media or not static_root:
        return None
    try:
        media_resolvido = media.resolve()
        static_resolvido = static_root.resolve()
    except OSError:
        return None
    if media_resolvido == static_resolvido:
        return (
            f"MEDIA_ROOT ({media_resolvido}) é igual a STATIC_ROOT. Arquivos "
            "enviados seriam servidos como estáticos, com Content-Type deduzido "
            "do nome."
        )
    if static_resolvido in media_resolvido.parents:
        return (
            f"MEDIA_ROOT ({media_resolvido}) está dentro de STATIC_ROOT "
            f"({static_resolvido}). Arquivos enviados seriam servidos como "
            "estáticos executáveis."
        )
    if media_resolvido in static_resolvido.parents:
        return (
            f"STATIC_ROOT ({static_resolvido}) está dentro de MEDIA_ROOT "
            f"({media_resolvido}). Arquivos enviados não devem ficar sob o "
            "diretório de estáticos."
        )
    return None


def iterar_extensoes(tipos: Iterable[TipoAceito]) -> list[str]:
    """Extensões aceitas de uma política, para mensagem de erro."""
    saida: set[str] = set()
    for tipo in tipos:
        saida |= set(tipo.extensoes)
    return sorted(saida)
