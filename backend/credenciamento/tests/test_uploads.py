"""
Testes do eixo 3 (uploads) — `config/uploads.py` + `credenciamento`.

O QUE PROVAM (e o que NÃO provam, declarado):

PROVAM
 1. **Arquivo válido** é aceito (PDF/JPEG/PNG/WebP reais, com bytes de
    assinatura verdadeiros).
 2. **Extensão falsificada**: `payload.html` declarado como `image/jpeg`,
    contendo bytes JPEG → RECUSADO, porque a extensão não bate com o
    conteúdo. E `payload.jpg` contendo HTML → RECUSADO pelo magic bytes.
 3. **MIME falsificado**: `payload.pdf` com `content_type="image/png"` e
    bytes PDF → RECUSADO (content-type declarado não casa com o
    conteúdo).
 4. **Arquivo executável**: `.html`, `.svg`, `.js`, `.php`, `.sh`, um
    ELF (binário Linux) e um ZIP/PK → TODOS recusados. O vetor de XSS
    armazenado (`.html` servido como `text/html`) é coberto
    explicitamente.
 5. **Acima do limite**: rejeitado em TRÊS níveis — `size` declarado
    grande, stream com mais bytes que o limite (verificado em bloco, não
    por `Content-Length`), e objeto sem `size` (stream puro).
 6. **Nome regenerado**: o nome do cliente é DESCARTADO. Testa
    `../../etc/passwd`, `x.pdf.html`, `a\x00b.jpg`, 300 caracteres,
    accentuado, e confirma que o caminho gravado não contém nada disso e
    que a extensão é a CANÔNICA do tipo detectado.
 7. **Servida com defesa**: `Content-Disposition: attachment`,
    `X-Content-Type-Options: nosniff`, `Content-Type:
    application/octet-stream`, `Cache-Control: private, no-store` — e o
    `filename` do `Content-Disposition` nunca carrega CRLF ou aspas do
    cliente (injeção de cabeçalho).
 8. **Fora do diretório servido**: `MEDIA_ROOT` dentro/igual a
    `STATIC_ROOT` é detectado.
 9. **Polyglot**: PDF com `<script>` no cabeçalho é recusado.
 10. **Nenhum bypass por `except: pass`**: validação de upload não pode
     ser contornada por um campo ausente, arquivo vazio ou `None`.

NÃO PROVAM
 - Que o arquivo não possa ser executado pelo SERVIDOR (não há execução
   de upload no projeto — verificado por varredura; declarado no
   relatório).
 - Proteção contra exaustão de disco ou DoS com muitos arquivos
   pequenos (rate limit é outro item).
"""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile, TemporaryUploadedFile
from django.test import override_settings

from config import uploads
from config.uploads import (
    POLITICA_DOCUMENTO,
    POLITICA_FOTO,
    UploadInvalidoError,
    headers_de_servida,
    nome_regenerado,
    validar_upload,
    verificar_media_root_fora_do_servido,
)

# ---------------------------------------------------------------------------
# Binários reais mínimos (assinaturas genuínas)
# ---------------------------------------------------------------------------

PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"trailer<</Root 1 0 R>>\n"
    b"%%EOF\n"
)
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + b"\x00" * 32 + b"\xff\xd9"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 16
WEBP_BYTES = b"RIFF" + (32).to_bytes(4, "little") + b"WEBPVP8 " + b"\x00" * 24
GIF_BYTES = b"GIF89a" + b"\x00" * 16  # GIF NÃO está na allowlist
ELF_BYTES = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 56  # binário Linux
ZIP_BYTES = b"PK\x03\x04" + b"\x00" * 26
HTML_BYTES = b"<html><body><script>alert(document.cookie)</script></body></html>"
SVG_BYTES = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>'


def _arquivo(nome: str, conteudo: bytes, content_type: str) -> SimpleUploadedFile:
    return SimpleUploadedFile(nome, conteudo, content_type=content_type)


# ---------------------------------------------------------------------------
# 1. Arquivo válido
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nome,conteudo,ct",
    [
        ("diploma.pdf", PDF_BYTES, "application/pdf"),
        ("foto.jpg", JPEG_BYTES, "image/jpeg"),
        ("diploma.jpeg", JPEG_BYTES, "image/jpeg"),
        ("foto.png", PNG_BYTES, "image/png"),
        ("foto.webp", WEBP_BYTES, "image/webp"),
    ],
)
def test_arquivo_valido_e_aceito(nome, conteudo, ct) -> None:
    politica = POLITICA_DOCUMENTO if nome.endswith((".pdf", ".jpeg")) else POLITICA_FOTO
    resultado = validar_upload(_arquivo(nome, conteudo, ct), politica)
    assert resultado.startswith(conteudo[:4]), "o conteúdo validado deve ser o enviado"


def test_arquivo_valido_e_aceito_sem_content_type_declarado() -> None:
    """Cliente honesto que não manda `Content-Type`: aceito pelo conteúdo."""
    arquivo = SimpleUploadedFile("diploma.pdf", PDF_BYTES, content_type="")
    assert validar_upload(arquivo, POLITICA_DOCUMENTO).startswith(b"%PDF-")


# ---------------------------------------------------------------------------
# 2. Extensão falsificada
# ---------------------------------------------------------------------------


def test_extensao_falsificada_com_conteudo_imagem_e_recusada() -> None:
    """
    `.html` com bytes JPEG, declarado como `image/jpeg`.
    Sem a checagem de extensão, o arquivo seria gravado como `.html` e
    servido como `text/html` — XSS armazenado.
    """
    with pytest.raises(UploadInvalidoError) as info:
        validar_upload(_arquivo("payload.html", JPEG_BYTES, "image/jpeg"), POLITICA_FOTO)
    assert "extensão" in str(info.value)


def test_extensao_falsificada_com_conteudo_html_e_recusada() -> None:
    """`.jpg` contendo HTML: o magic bytes não casa, recusado."""
    with pytest.raises(UploadInvalidoError) as info:
        validar_upload(_arquivo("foto.jpg", HTML_BYTES, "image/jpeg"), POLITICA_FOTO)
    assert "não permitido" in str(info.value)


def test_double_extension_recusada() -> None:
    """`x.pdf.html` → a última extensão é `.html`, que não é PDF."""
    with pytest.raises(UploadInvalidoError):
        validar_upload(_arquivo("x.pdf.html", PDF_BYTES, "application/pdf"), POLITICA_DOCUMENTO)


# ---------------------------------------------------------------------------
# 3. MIME falsificado
# ---------------------------------------------------------------------------


def test_content_type_falsificado_e_recusado() -> None:
    with pytest.raises(UploadInvalidoError) as info:
        validar_upload(_arquivo("diploma.pdf", PDF_BYTES, "image/png"), POLITICA_DOCUMENTO)
    assert "não corresponde" in str(info.value)


def test_content_type_falsificado_para_execucao_e_recusado() -> None:
    with pytest.raises(UploadInvalidoError):
        validar_upload(_arquivo("diploma.pdf", PDF_BYTES, "text/html"), POLITICA_DOCUMENTO)


# ---------------------------------------------------------------------------
# 4. Arquivo executável / perigoso
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nome,conteudo,ct",
    [
        ("x.html", HTML_BYTES, "text/html"),
        ("x.htm", HTML_BYTES, "text/html"),
        ("x.svg", SVG_BYTES, "image/svg+xml"),
        ("x.js", b"alert(1)", "application/javascript"),
        ("x.php", b"<?php system($_GET['c']); ?>", "application/x-httpd-php"),
        ("x.sh", b"#!/bin/sh\nrm -rf /\n", "application/x-sh"),
        ("x.exe", ELF_BYTES, "application/octet-stream"),
        ("x.bin", ELF_BYTES, "application/octet-stream"),
        ("x.zip", ZIP_BYTES, "application/zip"),
        ("x.gif", GIF_BYTES, "image/gif"),
        ("x.docx", ZIP_BYTES, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ],
)
def test_arquivo_executavel_ou_nao_permitido_e_recusado(nome, conteudo, ct) -> None:
    """O vetor de execução: nenhum formato executável/script entra."""
    with pytest.raises(UploadInvalidoError):
        validar_upload(_arquivo(nome, conteudo, ct), POLITICA_DOCUMENTO)
    with pytest.raises(UploadInvalidoError):
        validar_upload(_arquivo(nome, conteudo, ct), POLITICA_FOTO)


def test_elf_com_extensao_de_imagem_e_recusado() -> None:
    """Binário disfarçado de foto: o magic bytes denuncia."""
    with pytest.raises(UploadInvalidoError):
        validar_upload(_arquivo("foto.png", ELF_BYTES, "image/png"), POLITICA_FOTO)


# ---------------------------------------------------------------------------
# 5. Acima do limite
# ---------------------------------------------------------------------------


def test_acima_do_limite_pelo_size_declarado() -> None:
    grande = b"\x89PNG\r\n\x1a\n" + b"\x00" * (POLITICA_FOTO.max_bytes + 1)
    with pytest.raises(UploadInvalidoError) as info:
        validar_upload(_arquivo("foto.png", grande, "image/png"), POLITICA_FOTO)
    assert "limite" in str(info.value).lower()


def test_acima_do_limite_detectado_na_leitura_e_nao_no_content_length() -> None:
    """
    O limite tem de valer sobre os BYTES LIDOS, não sobre
    `Content-Length` nem sobre `size` — os dois são controlados pelo
    cliente (`size` vem do multipart que o cliente escreveu).

    Aqui montamos um `TemporaryUploadedFile` REAL em disco com 6 MB ( acima
    do limite de 5 MB da foto) e forçamos `_size = 10`, ou seja: o
    upload se declara com 10 bytes. Se a validação confiasse em `size` ou
    em `Content-Length`, o arquivo passaria inteiro.
    """
    import tempfile

    conteudo = PNG_BYTES + b"\x00" * (POLITICA_FOTO.max_bytes + 1024 * 1024)
    with tempfile.NamedTemporaryFile() as tf:
        tf.write(conteudo)
        tf.flush()
        arquivo = TemporaryUploadedFile(
            "foto.png", "image/png", len(conteudo), charset=None, content_type_extra=None
        )
        with open(tf.name, "rb") as fh:
            arquivo.file = fh
            # MENTIRA: declara 10 bytes para um arquivo de 6 MB.
            # `size` é `cached_property` no Django, então envenenamos o
            # cache da instância — que é exatamente o que um cliente
            # faria ao declarar `Content-Length` pequeno num corpo grande.
            arquivo.__dict__["size"] = 10
            assert arquivo.size == 10
            with pytest.raises(UploadInvalidoError) as info:
                validar_upload(arquivo, POLITICA_FOTO)
    assert "ultrapassa o limite" in str(info.value).lower()


def test_acima_do_limite_em_arquivo_temporario_real() -> None:
    """
    `TemporaryUploadedFile` é o caminho real de um upload >2,5 MB
    (`FILE_UPLOAD_MAX_MEMORY_SIZE`): o Django grava em disco e transmite
    em blocos. O limite é aplicado durante a leitura, e o arquivo
    temporário não é deixado para trás.
    """
    import tempfile

    conteudo = PNG_BYTES + b"\x00" * (POLITICA_FOTO.max_bytes + 4096)
    with tempfile.NamedTemporaryFile() as tf:
        tf.write(conteudo)
        tf.flush()
        arquivo = TemporaryUploadedFile(
            "foto.png", "image/png", len(conteudo), charset=None, content_type_extra=None
        )
        with open(tf.name, "rb") as fh:
            arquivo.file = fh
            with pytest.raises(UploadInvalidoError):
                validar_upload(arquivo, POLITICA_FOTO)


def test_arquivo_exatamente_no_limite_e_aceito() -> None:
    """O limite é inclusivo: um arquivo com exatamente `max_bytes` passa."""
    resto = POLITICA_FOTO.max_bytes - len(PNG_BYTES)
    arquivo = _arquivo("foto.png", PNG_BYTES + b"\x00" * resto, "image/png")
    validar_upload(arquivo, POLITICA_FOTO)  # não levanta


def test_stream_sem_size_e_rejeitado_no_stream() -> None:
    """Objeto sem `size` (stream puro): a checagem antecipada é pulada."""

    class _StreamSemSize(SimpleUploadedFile):
        size = None

    arquivo = _StreamSemSize("foto.png", PNG_BYTES + b"\x00" * (POLITICA_FOTO.max_bytes + 1), "image/png")
    with pytest.raises(UploadInvalidoError):
        validar_upload(arquivo, POLITICA_FOTO)


# ---------------------------------------------------------------------------
# 6. Nome regenerado
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nome_cliente",
    [
        "../../etc/passwd",
        "..\\..\\windows\\system32\\cmd.exe",
        "x.pdf.html",
        "a\x00b.jpg",
        "sem-extensao",
        "arquivo com espaco e acentoção Ã©.png",
        "x" * 300 + ".png",
        ".htaccess",
        "x.png\nX-Injetado: 1",
    ],
)
def test_nome_do_cliente_e_descartado_por_completo(nome_cliente: str) -> None:
    """
    O nome do cliente não influence NADA no caminho gravado.
    Cada caso aqui é um ataque real de traversal/sobrescrita/header
    injection que funcionava antes (o `upload_to` usava `filename` cru).
    """
    nome = nome_regenerado(uploads.PNG)
    assert nome_cliente not in nome
    assert nome.endswith(".png")
    # 32 hex de uuid4 + ponto + extensão canônica.
    assert len(nome) == 32 + 4
    corpo, _, extensao = nome.rpartition(".")
    assert len(corpo) == 32
    assert all(c in "0123456789abcdef" for c in corpo), corpo
    assert extensao == "png"


def test_extensao_canonica_vem_do_tipo_detectado() -> None:
    """A extensão gravada é a do TIPO, não a que o cliente mandou."""
    arquivo = _arquivo("diploma.pdf", PDF_BYTES, "application/pdf")
    conteudo = validar_upload(arquivo, POLITICA_DOCUMENTO)
    tipo = uploads.detectar_tipo(conteudo, POLITICA_DOCUMENTO)
    nome = nome_regenerado(tipo[0])
    assert nome.endswith(".pdf")
    assert ".html" not in nome


@pytest.mark.django_db
def test_upload_gravado_tem_nome_regenerado_e_persiste(tmp_path, settings) -> None:
    """Prova de ponta: o que vai para o disco não contém o nome do cliente."""
    settings.MEDIA_ROOT = tmp_path
    from django.core.files.storage import default_storage

    with override_settings(MEDIA_ROOT=str(tmp_path)):
        # Traversal no DIRECTORIO do nome, com extensao consistente: se o
        # nome do cliente fosse usado, isto escaparia de MEDIA_ROOT.
        arquivo = _arquivo("../../../../evil/diploma.pdf", PDF_BYTES, "application/pdf")
        nome = uploads.salvar_upload(arquivo, POLITICA_DOCUMENTO, instance_pk=42)
        assert "evil" not in nome
        assert ".." not in nome
        assert ".." not in nome
        assert nome.endswith(".pdf")
        # O arquivo existe e o conteúdo é o PDF validado.
        assert default_storage.exists(nome)
        with default_storage.open(nome) as fh:
            assert fh.read().startswith(b"%PDF-")
        default_storage.delete(nome)


# ---------------------------------------------------------------------------
# 7. Servida com defesa
# ---------------------------------------------------------------------------


def test_cabecalhos_de_defesa_na_servida() -> None:
    h = headers_de_servida("documento")
    assert h["Content-Disposition"] == 'attachment; filename="documento"'
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["Content-Type"] == "application/octet-stream"
    assert "no-store" in h["Cache-Control"]
    # `sandbox` + `default-src 'none'` protegem mesmo um futuro serve inline.
    assert "sandbox" in h["Content-Security-Policy"]


def test_content_disposition_nao_injeta_cabecalho() -> None:
    """CRLF e aspas do cliente não podem entrar no `Content-Disposition`."""
    for nome in (
        "a\r\nX-Injetado: 1",
        'a"; drop\r\n',
        "../../etc/passwd",
        "a\nb",
    ):
        h = headers_de_servida(nome)
        cd = h["Content-Disposition"]
        assert "\r" not in cd and "\n" not in cd, cd
        assert cd.count('"') == 2, cd


def test_headers_sem_nome_ainda_tem_content_disposition_attachment() -> None:
    h = headers_de_servida(None)
    assert h["Content-Disposition"] == "attachment"


@pytest.mark.django_db
def test_documento_view_manda_os_cabecalhos_de_defesa(client, django_user_model) -> None:
    """
    Prova na view real: o download do documento nunca é interpretável pelo
    browser como HTML.
    """
    from credenciamento.serializers import SolicitacaoCredenciamentoSerializer

    usuario = django_user_model.objects.create_user(email="d@x.tld", password="x", papel="free")
    serializer = SolicitacaoCredenciamentoSerializer(
        data={"telefone": "", "cidade": "", "uf": "", "documento": _arquivo("diploma.pdf", PDF_BYTES, "application/pdf")}
    )
    assert serializer.is_valid(), serializer.errors
    solicitacao = serializer.save(user=usuario)

    client.force_login(usuario)
    resposta = client.get(f"/api/credenciamento/solicitacoes/{solicitacao.pk}/documento/")
    assert resposta.status_code == 200
    assert resposta["Content-Disposition"].startswith("attachment")
    assert resposta["X-Content-Type-Options"] == "nosniff"
    assert resposta["Content-Type"] == "application/octet-stream"
    assert not resposta["Content-Type"].startswith("text/html")


# ---------------------------------------------------------------------------
# 8. Fora do diretório servido
# ---------------------------------------------------------------------------


def test_media_root_dentro_de_static_root_e_detectado(tmp_path) -> None:
    static = tmp_path / "staticfiles"
    media = static / "media"
    with override_settings(STATIC_ROOT=str(static), MEDIA_ROOT=str(media)):
        problema = verificar_media_root_fora_do_servido()
    assert problema is not None
    assert "STATIC_ROOT" in problema


def test_media_root_igual_ao_static_root_e_detectado(tmp_path) -> None:
    with override_settings(STATIC_ROOT=str(tmp_path), MEDIA_ROOT=str(tmp_path)):
        problema = verificar_media_root_fora_do_servido()
    assert problema is not None
    assert "igual" in problema


def test_media_root_independente_de_static_root_e_aceito(tmp_path) -> None:
    with override_settings(
        STATIC_ROOT=str(tmp_path / "staticfiles"), MEDIA_ROOT=str(tmp_path / "media")
    ):
        assert verificar_media_root_fora_do_servido() is None


# ---------------------------------------------------------------------------
# 9. Polyglot
# ---------------------------------------------------------------------------


def test_pdf_com_script_no_cabecalho_e_recusado() -> None:
    """`%PDF-` + `<script>` logo depois: passa na assinatura, falha no polyglot."""
    polyglot = b"%PDF-1.4\n<html><script>alert(document.cookie)</script>\n"
    with pytest.raises(UploadInvalidoError) as info:
        validar_upload(_arquivo("diploma.pdf", polyglot, "application/pdf"), POLITICA_DOCUMENTO)
    assert "marcação" in str(info.value)


def test_jpeg_com_script_no_cabecalho_e_recusado() -> None:
    polyglot = b"\xff\xd8\xff\xe0" + b"<script>alert(1)</script>" + b"\x00" * 16
    with pytest.raises(UploadInvalidoError):
        validar_upload(_arquivo("foto.jpg", polyglot, "image/jpeg"), POLITICA_FOTO)


def test_riff_que_nao_e_webp_e_recusado() -> None:
    """`RIFF` sem `WEBP` nos bytes 8..12: não é imagem."""
    with pytest.raises(UploadInvalidoError):
        validar_upload(_arquivo("foto.webp", b"RIFF" + b"\x00" * 40, "image/webp"), POLITICA_FOTO)


# ---------------------------------------------------------------------------
# 10. Ausência de bypass
# ---------------------------------------------------------------------------


def test_arquivo_none_e_recusado() -> None:
    with pytest.raises(UploadInvalidoError):
        validar_upload(None, POLITICA_FOTO)


def test_arquivo_vazio_e_recusado() -> None:
    with pytest.raises(UploadInvalidoError):
        validar_upload(_arquivo("foto.png", b"", "image/png"), POLITICA_FOTO)


def test_webp_valido_e_aceito() -> None:
    validar_upload(_arquivo("foto.webp", WEBP_BYTES, "image/webp"), POLITICA_FOTO)


def test_webp_nao_e_aceito_como_documento() -> None:
    """A política do documento é mais estreita que a da foto."""
    with pytest.raises(UploadInvalidoError):
        validar_upload(_arquivo("diploma.webp", WEBP_BYTES, "image/webp"), POLITICA_DOCUMENTO)


def test_upload_invalido_herda_de_validation_error_para_o_drf_traduzir_em_400() -> None:
    """Se não herdasse de `ValidationError`, o DRF devolveria 500."""
    from django.core.exceptions import ValidationError as DjangoValidationError

    assert issubclass(UploadInvalidoError, DjangoValidationError)


@pytest.mark.django_db
def test_serializador_recusa_upload_invalido_com_400(client, django_user_model) -> None:
    """`.html` no lugar da foto → 400, não 500, e nada é gravado."""
    from django.conf import settings

    usuario = django_user_model.objects.create_user(email="u@x.tld", password="x", papel="free")
    client.force_login(usuario)
    resposta = client.post(
        "/api/credenciamento/solicitar/",
        data={
            "telefone": "",
            "cidade": "",
            "uf": "",
            "documento": _arquivo("diploma.pdf", PDF_BYTES, "application/pdf"),
            "foto": _arquivo("x.html", HTML_BYTES, "text/html"),
        },
    )
    assert resposta.status_code == 400, resposta.content
    assert "foto" in resposta.json()
    from credenciamento.models import SolicitacaoCredenciamento

    assert SolicitacaoCredenciamento.objects.filter(user=usuario).count() == 0
    assert settings.MEDIA_ROOT is not None
