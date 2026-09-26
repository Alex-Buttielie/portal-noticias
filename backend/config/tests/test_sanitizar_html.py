"""
Testes do eixo 1 (XSS) no backend: sanitização de HTML editorial.

O que estes testes provam, e o que NÃO provam — declarado porque um
teste de sanitização que "passa" sem provar nada é pior que nenhum:

PROVAM
- Que `config.sanitizar_html.sanitizar_html` reconstrói o documento a
  partir de uma ALLOWLIST: tag fora da lista é removida e o texto
  interno preservado; tag perigosa tem o CONTEÚDO removido.
- Que os vetores clássicos não sobrevivem: `<script>`, `on*`, `style=`,
  `<iframe>`/`<object>`/`<svg>`, `javascript:` (incluindo variações com
  tab/controle e caixa), `data:`, scheme-relative `//host`, credenciais
  embutidas, comentários, CDATA.
- Que a API pública NUNCA devolve HTML perigoso, mesmo com o banco
  sujo: o `to_representation` sanitiza na leitura (o teste grava o
  payload direto com `objects.create`, contornando a validação de
  escrita, e prova que a leitura limpa mesmo assim).
- Que HTML editorial legítimo não é degradado (regressão de conteúdo).

NÃO PROVAM
- Que o HTML sanitizado não quebra nenhum parser do mundo. É o mesmo
  limite de qualquer sanitizador baseado em parser; o motivo de usar
  `html.parser` (tokenizador conforme spec) em vez de regex é reduzir
  esse limite, não eliminá-lo.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from config.sanitizar_html import contem_html_perigoso, sanitizar_html
from moderacao.models import PaginaEditorial
from moderacao.serializers import PaginaEditorialSerializer

# Payloads do enunciado do item de backlog, mais as variações clássicas.
PAYLOADS_SCRIPT = [
    "</script><script>alert(1)</script>",
    "<script>alert(document.cookie)</script>",
    "<SCRIPT>alert(1)</SCRIPT>",
    "<scr" + "ipt>alert(1)</scr" + "ipt>",
    "<script\n>alert(1)</script>",
    "<script/xss>alert(1)</script>",
    "<script>alert(1)",  # sem fechamento
    "<script><script>alert(1)</script></script>",
]

PAYLOADS_ATRIBUTO = [
    '"><img src=x onerror=alert(1)>',
    "<img src=x onerror=alert(1)>",
    "<p onerror=alert(1)>x</p>",
    "<p ONMOUSEOVER=alert(1)>x</p>",
    "<p onerror =alert(1)>x</p>",
    "<p onclick=alert(1) autofocus>x</p>",
    '<a href="https://ok.tld" onerror="alert(1)">x</a>',
]

PAYLOADS_URL = [
    '<a href="javascript:alert(1)">x</a>',
    '<a href="JaVaScRiPt:alert(1)">x</a>',
    '<a href=" javascript:alert(1)">x</a>',
    '<a href="java\tscript:alert(1)">x</a>',
    '<a href="java\nscript:alert(1)">x</a>',
    '<a href="java\rscript:alert(1)">x</a>',
    '<a href="vbscript:msgbox(1)">x</a>',
    '<a href="data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==">x</a>',
    '<a href="//evil.tld/x">x</a>',
    '<a href="https://usuario:senha@exemplo.com">x</a>',
    '<a href="file:///etc/passwd">x</a>',
    '<form action="https://evil.tld"><input name=a></form>',
]

PAYLOADS_CONTEUDO_PERIGOSO = [
    "<style>body{display:none}</style>x",
    "<iframe src=//evil.tld></iframe>x",
    "<iframe srcdoc='<script>alert(1)</script>'></iframe>x",
    "<object data=x.swf></object>x",
    "<embed src=x.swf>x",
    "<svg><script>alert(1)</script></svg>x",
    "<svg onload=alert(1)></svg>x",
    "<math><mtext><script>alert(1)</script></mtext></math>x",
    "<template><script>alert(1)</script></template>x",
    "<noscript><p>ok</p></noscript>x",
    "<base href='//evil.tld/'>x",
    "<meta http-equiv=refresh content='0;url=//evil.tld'>x",
    "<!--[if IE]><script>alert(1)</script><![endif]-->x",
]


class _Resultado:
    """Resultado de sanitização com testes derivados do texto resultante.

    Existe porque `sanitizar_html` devolve `str`: quem quiser inspecionar
    o que SOBROU tem que olhar o texto. Estes helpers existem para o teste
    poder afirmar de forma legível.
    """

    def __init__(self, saida: str) -> None:
        self.saida = saida

    @property
    def tem_script(self) -> bool:
        return "<script" in self.saida.lower()

    @property
    def tem_handler(self) -> bool:
        return any(m in self.saida.lower() for m in ("onerror", "onload", "onclick", "onmouseover"))


# ---------------------------------------------------------------------------
# Sanitizador puro
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("payload", PAYLOADS_SCRIPT)
def test_script_nunca_sobrevive(payload: str) -> None:
    r = _Resultado(sanitizar_html(payload))
    assert not r.tem_script, f"tag script sobreviveu: {r.saida!r}"
    assert "<script" not in r.saida.lower()


@pytest.mark.parametrize("payload", PAYLOADS_ATRIBUTO)
def test_handlers_e_tags_de_imagem_nunca_sobrevem(payload: str) -> None:
    r = _Resultado(sanitizar_html(payload))
    assert not r.tem_handler, f"handler sobreviveu: {r.saida!r}"
    assert "<img" not in r.saida.lower()


@pytest.mark.parametrize("payload", PAYLOADS_URL)
def test_url_perigosa_e_removida(payload: str) -> None:
    r = _Resultado(sanitizar_html(payload))
    for esquema in ("javascript:", "vbscript:", "data:", "file:", "//evil.tld", "usuario:senha"):
        assert esquema not in r.saida, f"{esquema!r} sobreviveu: {r.saida!r}"
    # `<form>`/`<input>` também saem (conteúdo perigoso).
    assert "<form" not in r.saida.lower()
    assert "<input" not in r.saida.lower()


@pytest.mark.parametrize("payload", PAYLOADS_CONTEUDO_PERIGOSO)
def test_conteudo_perigoso_e_descartado_com_o_elemento(payload: str) -> None:
    r = _Resultado(sanitizar_html(payload))
    for tag in ("<script", "<style", "<iframe", "<object", "<embed", "<svg", "<math", "<template", "<base", "<meta"):
        assert tag not in r.saida.lower(), f"{tag!r} sobreviveu: {r.saida!r}"


def test_payload_do_enunciado_nao_quebra_nem_ejecuta() -> None:
    """Os dois payloads citados literalmente no item de backlog."""
    # `</script><script>alert(1)</script>`
    saida = sanitizar_html("<p>ok</p></script><script>alert(1)</script>")
    assert "<script" not in saida.lower()
    assert saida == "<p>ok</p>"
    # `"><img src=x onerror=alert(1)>`
    saida = sanitizar_html('"><img src=x onerror=alert(1)>')
    assert "<img" not in saida.lower()
    assert "onerror" not in saida.lower()
    assert saida == "&quot;&gt;"


def test_texto_e_preservado_com_escape() -> None:
    assert sanitizar_html("1 < 2 e 3 > 2") == "1 &lt; 2 e 3 &gt; 2"
    assert sanitizar_html("Tom & Jerry") == "Tom &amp; Jerry"
    assert sanitizar_html("Tom &amp; Jerry") == "Tom &amp; Jerry"  # sem duplo escape
    assert sanitizar_html("") == ""
    assert sanitizar_html(None) == ""
    assert sanitizar_html(42) == ""
    assert sanitizar_html(b"bytes") == ""


def test_html_editorial_legitimo_nao_e_degradado() -> None:
    entrada = (
        "<h2>Termos de Uso</h2>"
        "<p>Aplica-se a <strong>todo</strong> uso do portal desde "
        "<em>25/09/2026</em>.</p>"
        "<ul><li>Item 1</li><li>Item 2</li></ul>"
        "<ol start=\"3\"><li>Terceiro</li></ol>"
        "<blockquote><p>Citação</p></blockquote>"
        "<pre><code>exemplo()</code></pre>"
        '<p><a href="https://exemplo.org/privacidade" target="_blank" rel="noopener noreferrer nofollow">Política</a></p>'
        '<p><a href="/contato">Contato</a></p>'
        '<p><a href="mailto:ola@exemplo.com">E-mail</a></p>'
        "<table><thead><tr><th scope=\"col\">A</th></tr></thead>"
        "<tbody><tr><td colspan=\"2\">B</td></tr></tbody></table>"
        "<hr><p>Até mais.<br>Fim</p>"
    )
    assert sanitizar_html(entrada) == entrada, "HTML editorial legítimo foi degradado"


def test_target_blank_recebe_rel_noopener() -> None:
    saida = sanitizar_html('<a href="https://exemplo.com" target="_blank">x</a>')
    assert 'rel="noopener noreferrer nofollow"' in saida
    # `_top` não é normalizado para `_blank` (não ampliamos o pedido).
    assert "target" not in sanitizar_html('<a href="https://exemplo.com" target="_top">x</a>')


def test_atributo_duplicado_vence_o_primeiro() -> None:
    # `HTMLParser` entrega os dois; o browser usa o primeiro. Se o
    # sanitizador usasse o segundo, `href` poderia divergir do browser.
    saida = sanitizar_html('<a href="https://seguro.tld" href="javascript:alert(1)">x</a>')
    assert saida == '<a href="https://seguro.tld">x</a>'


def test_contem_html_perigoso_detecta_mudanca() -> None:
    assert contem_html_perigoso("<p>limpo</p>") is False
    assert contem_html_perigoso("<script>alert(1)</script>") is True
    assert contem_html_perigoso(None) is False


# ---------------------------------------------------------------------------
# Serializer / API pública
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_api_publica_nunca_devolve_html_perigoso_do_banco_sujo() -> None:
    """
    O banco pode conter HTML gravado ANTES da validação existir, ou por
    um caminho que a contorne (`objects.create`, import, `QuerySet.update`).
    Escrevemos o payload direto no banco e provamos que a LEITURA pela API
    pública limpa.
    """
    PaginaEditorial.objects.create(
        slug="politica",
        titulo="Política",
        conteudo="<p>ok</p><script>alert(1)</script>",
    )
    client = APIClient()
    resposta = client.get("/api/moderacao/paginas/politica/")
    assert resposta.status_code == 200
    conteudo = resposta.json()["conteudo"]
    assert "<script" not in conteudo.lower(), conteudo
    assert conteudo == "<p>ok</p>"


@pytest.mark.django_db
def test_serializador_sanitiza_na_escrita_sem_falhar_a_pagina() -> None:
    serializer = PaginaEditorialSerializer(
        data={
            "slug": "termos",
            "titulo": "Termos",
            "conteudo": '<p>ok</p><img src=x onerror=alert(1)>',
        }
    )
    assert serializer.is_valid(), serializer.errors
    # `validated_data` é o que será gravado — precisa já estar limpo.
    assert "<img" not in serializer.validated_data["conteudo"]
    assert serializer.validated_data["conteudo"] == "<p>ok</p>"


@pytest.mark.django_db
def test_serializador_rejeita_conteudo_sem_nada_aproveitavel() -> None:
    """
    Se o admin enviar SÓ HTML perigoso, o conteúdo salvo seria vazio e a
    página editorial quebraria silenciosamente. Falhar com mensagem
    explícita é melhor que aceitar e servir uma página em branco.
    """
    serializer = PaginaEditorialSerializer(
        data={"slug": "vazia", "titulo": "Vazia", "conteudo": "<script>alert(1)</script>"}
    )
    assert not serializer.is_valid()
    assert "conteudo" in serializer.errors


@pytest.mark.django_db
def test_serializador_aceita_texto_simples_sem_html() -> None:
    serializer = PaginaEditorialSerializer(
        data={"slug": "simples", "titulo": "Simples", "conteudo": "Só texto, sem marcação."}
    )
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["conteudo"] == "Só texto, sem marcação."
