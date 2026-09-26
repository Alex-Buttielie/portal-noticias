"""Validação do payload, XSS no corpo e armadilha (honeypot) de `POST /api/contato/`.

Os limites testados aqui são os mesmos que a UI já aplica no navegador
(`frontend/app/contato/ContatoForm.tsx`): o servidor não pode aceitar mais do
que o formulário envia, nem recusar o que ele aceita.
"""

from __future__ import annotations

import pytest
from django.core import mail
from rest_framework.test import APIClient

from contato.serializers import (
    LIMITE_EMAIL,
    LIMITE_MENSAGEM,
    LIMITE_NOME,
    MINIMO_MENSAGEM,
)
from contato.tests.backends import EntregaSimuladaBackend, caminho_de

pytestmark = pytest.mark.django_db

URL = "/api/contato/"
DESTINO = "redacao@exemplo.org"
BACKEND_QUE_ENTREGA = caminho_de(EntregaSimuladaBackend)
PADRADA = "Mensagem com comprimento suficiente para a validação."

# Payloads de XSS/XSSI. A resposta esperada é NEUTRALIZAÇÃO (texto puro), não
# recusa: ver a justificativa em `contato/serializers.py` (módulo).
# (O byte nulo é caso aparte: o DRF já o recusa — ver
# `TestNormalizacao.test_byte_nulo_e_recusado_pelo_validador_do_drf`.)
CARACTERES_DE_CONTROLE = "\x07\x1b"


@pytest.fixture(autouse=True)
def _limpa_registro_de_entregas():
    EntregaSimuladaBackend.entregues.clear()
    yield
    EntregaSimuladaBackend.entregues.clear()


@pytest.fixture
def canal_entregando(settings):
    settings.EMAIL_BACKEND = BACKEND_QUE_ENTREGA
    settings.CONTATO_DESTINO = DESTINO
    return settings


def _payload(**extra):
    dados = {"nome": "Ana Souza", "email": "leitor@example.com", "mensagem": PADRADA}
    dados.update(extra)
    return dados


class TestCamposObrigatorios:
    @pytest.mark.parametrize("campo", ["nome", "email", "mensagem"])
    def test_campo_ausente_responde_400(self, canal_entregando, campo):
        dados = _payload()
        dados.pop(campo)

        resposta = APIClient().post(URL, dados, format="json")

        assert resposta.status_code == 400
        assert campo in resposta.data

    @pytest.mark.parametrize("campo", ["nome", "email", "mensagem"])
    def test_campo_em_branco_responde_400(self, canal_entregando, campo):
        resposta = APIClient().post(URL, _payload(**{campo: "   "}), format="json")

        assert resposta.status_code == 400
        assert campo in resposta.data

    def test_payload_vazio_responde_400(self, canal_entregando):
        resposta = APIClient().post(URL, {}, format="json")

        assert resposta.status_code == 400
        assert set(resposta.data) == {"nome", "email", "mensagem"}

    def test_erro_de_validacao_usa_o_formato_que_a_ui_renderiza(self, canal_entregando):
        """`frontend/lib/api.ts:32-56` lê `{campo: ["mensagem"]}`; nada mais."""
        resposta = APIClient().post(URL, _payload(email="nao-e-email"), format="json")

        assert resposta.status_code == 400
        assert isinstance(resposta.data["email"], list)
        assert isinstance(resposta.data["email"][0], str)


class TestEmail:
    SUFIXO = "@exemplo.com"

    def _email_de(self, tamanho: int) -> str:
        """E-mail válido com exatamente `tamanho` caracteres."""
        return f"{'a' * (tamanho - len(self.SUFIXO))}{self.SUFIXO}"

    @pytest.mark.parametrize(
        "email",
        ["nao-e-email", "sem@dominio", "@exemplo.com", "a b@example.com", "x@y..com"],
    )
    def test_email_invalido_responde_400(self, canal_entregando, email):
        resposta = APIClient().post(URL, _payload(email=email), format="json")

        assert resposta.status_code == 400
        assert "email" in resposta.data
        assert mail.outbox == [] and EntregaSimuladaBackend.entregues == []

    def test_email_acima_do_limite_responde_400(self, canal_entregando):
        assert len(self._email_de(LIMITE_EMAIL + 1)) == LIMITE_EMAIL + 1

        resposta = APIClient().post(
            URL, _payload(email=self._email_de(LIMITE_EMAIL + 1)), format="json"
        )

        assert resposta.status_code == 400
        assert "email" in resposta.data

    def test_email_no_limite_exato_e_aceito(self, canal_entregando):
        no_limite = self._email_de(LIMITE_EMAIL)
        assert len(no_limite) == LIMITE_EMAIL

        resposta = APIClient().post(URL, _payload(email=no_limite), format="json")

        assert resposta.status_code == 200, resposta.data


class TestTamanhos:
    def test_nome_acima_do_limite_responde_400(self, canal_entregando):
        resposta = APIClient().post(URL, _payload(nome="N" * (LIMITE_NOME + 1)), format="json")

        assert resposta.status_code == 400
        assert "nome" in resposta.data

    def test_nome_no_limite_exato_e_aceito(self, canal_entregando):
        resposta = APIClient().post(URL, _payload(nome="N" * LIMITE_NOME), format="json")

        assert resposta.status_code == 200

    def test_mensagem_acima_do_limite_responde_400(self, canal_entregando):
        resposta = APIClient().post(
            URL, _payload(mensagem="m" * (LIMITE_MENSAGEM + 1)), format="json"
        )

        assert resposta.status_code == 400
        assert "mensagem" in resposta.data

    def test_mensagem_no_limite_exato_e_aceita(self, canal_entregando):
        """4000 é exatamente o `maxLength` do `<Textarea>` do formulário."""
        resposta = APIClient().post(
            URL, _payload(mensagem="m" * LIMITE_MENSAGEM), format="json"
        )

        assert resposta.status_code == 200, resposta.data
        assert len(EntregaSimuladaBackend.entregues) == 1

    def test_mensagem_abaixo_do_minimo_responde_400(self, canal_entregando):
        curta = "m" * (MINIMO_MENSAGEM - 1)

        resposta = APIClient().post(URL, _payload(mensagem=curta), format="json")

        assert resposta.status_code == 400

    def test_mensagem_no_minimo_exato_e_aceita(self, canal_entregando):
        curta = "m" * MINIMO_MENSAGEM

        resposta = APIClient().post(URL, _payload(mensagem=curta), format="json")

        assert resposta.status_code == 200


class TestNormalizacao:
    def test_quebra_de_linha_no_nome_vira_espaco(self, canal_entregando):
        resposta = APIClient().post(URL, _payload(nome="Ana\nSouza"), format="json")

        assert resposta.status_code == 200
        texto = EntregaSimuladaBackend.entregues[0].get_payload(decode=True).decode("utf-8")
        assert "Ana Souza" in texto
        assert "Ana\nSouza" not in texto

    def test_byte_nulo_e_recusado_pelo_validador_do_drf(self, canal_entregando):
        """Defesa em profundidade: o DRF já recusa byte nulo (3.16+)."""
        resposta = APIClient().post(URL, _payload(mensagem=f"{PADRADA}\x00"), format="json")

        assert resposta.status_code == 400
        assert "mensagem" in resposta.data
        assert EntregaSimuladaBackend.entregues == []

    def test_caracteres_de_controle_sao_removidos(self, canal_entregando):
        """Os demais controles não quebram o envio: saem neutralizados."""
        mensagem = f"{CARACTERES_DE_CONTROLE}{PADRADA}{CARACTERES_DE_CONTROLE}"

        resposta = APIClient().post(URL, _payload(mensagem=mensagem), format="json")

        assert resposta.status_code == 200, resposta.data
        texto = EntregaSimuladaBackend.entregues[0].get_payload(decode=True).decode("utf-8")
        for controle in ("\x07", "\x1b"):
            assert controle not in texto
        assert PADRADA in texto, "só o controle sai, o texto do usuário permanece"

    def test_quebra_de_linha_na_mensagem_e_preservada(self, canal_entregando):
        """Quebra de linha é conteúdo legítimo; só controle se remove."""
        resposta = APIClient().post(
            URL, _payload(mensagem="Primeira linha.\nSegunda linha."), format="json"
        )

        assert resposta.status_code == 200
        texto = EntregaSimuladaBackend.entregues[0].get_payload(decode=True).decode("utf-8")
        assert "Primeira linha.\nSegunda linha." in texto


class TestXssNoCorpo:
    """Tentativa de XSS é NEUTRALIZADA, nunca interpretada."""

    @pytest.mark.parametrize(
        "payload",
        [
            "<script>alert('xss')</script>",
            '<img src=x onerror="alert(1)">',
            "<svg/onload=alert(1)>",
            "javascript:alert(document.cookie)",
            '<a href="https://exemplo.invalido" onclick="alert(1)">clique</a>',
        ],
    )
    def test_html_no_corpo_e_entregue_como_texto_puro(self, canal_entregando, payload):
        resposta = APIClient().post(URL, _payload(mensagem=payload), format="json")

        # A mensagem é entregue (o canal funciona) — mas como DADO, nunca como
        # markup: é isso que neutraliza o XSS.
        assert resposta.status_code == 200, resposta.data
        mime = EntregaSimuladaBackend.entregues[0]

        # (1) O único tipo de conteúdo é text/plain: nenhum cliente de e-mail
        #     vai renderizar o payload como HTML.
        assert mime.get_content_type() == "text/plain"
        assert mime.get_content_subtype() == "plain"
        assert not mime.is_multipart()
        # (2) Nenhuma alternativa text/html em nenhum lugar da mensagem.
        assert not any(
            parte.get_content_type() == "text/html"
            for parte in (mime.walk() if mime.is_multipart() else [mime])
        )
        # (3) O texto não foi silenciosamente adulterado: quem escreveu vê
        #     exatamente o que escreveu (decisão "neutralizar", não "rejeitar").
        texto = mime.get_payload(decode=True).decode("utf-8")
        assert payload in texto

    def test_html_no_nome_tambem_viaja_como_texto(self, canal_entregando):
        resposta = APIClient().post(
            URL, _payload(nome="<b>Ana</b> Souza"), format="json"
        )

        assert resposta.status_code == 200
        mime = EntregaSimuladaBackend.entregues[0]
        assert mime.get_content_type() == "text/plain"
        assert "<b>Ana</b> Souza" in mime.get_payload(decode=True).decode("utf-8")

    def test_nada_do_payload_volta_na_resposta(self, canal_entregando):
        payload = "<script>alert('nao-echoa')</script>"

        resposta = APIClient().post(URL, _payload(mensagem=payload), format="json")

        assert "script" not in str(resposta.data).lower()

    def test_assunto_nao_recebe_dado_do_usuario(self, canal_entregando):
        """Dado do usuário em header é caminho clássico de injeção de header."""
        resposta = APIClient().post(
            URL,
            _payload(nome="Ana\r\nBcc: vitima@example.com"),
            format="json",
        )

        assert resposta.status_code == 200
        mime = EntregaSimuladaBackend.entregues[0]
        assert "Bcc" not in (mime["Subject"] or "")
        assert "vitima@example.com" not in (mime["Subject"] or "")
        assert "Bcc" not in str(mime.items())


class TestHoneypot:
    """Armadilha: o projeto não tem captcha; contato é o alvo natural de spam."""

    def test_honeypot_preenchido_responde_400_e_nao_entrega(self, canal_entregando):
        resposta = APIClient().post(
            URL, _payload(website="http://spam.example.com/oferta"), format="json"
        )

        assert resposta.status_code == 400
        assert not (200 <= resposta.status_code < 300)
        assert EntregaSimuladaBackend.entregues == [], "spam não pode virar e-mail"
        assert mail.outbox == []

    def test_resposta_do_honeypot_nao_denuncia_a_armadilha(self, canal_entregando):
        resposta = APIClient().post(URL, _payload(website="spam"), format="json")

        assert resposta.status_code == 400
        # O erro é de campo não nomeado: não revela o nome do campo nem fala
        # de honeypot/spam, para o bot não aprender a contornar.
        assert set(resposta.data) == {"non_field_errors"}
        assert "website" not in str(resposta.data).lower()
        assert "honeypot" not in str(resposta.data).lower()

    def test_honeypot_ausente_e_o_caminho_normal(self, canal_entregando):
        resposta = APIClient().post(URL, _payload(), format="json")

        assert resposta.status_code == 200

    @pytest.mark.parametrize("valor", ["", "   "])
    def test_honeypot_vazio_e_ignorado(self, canal_entregando, valor):
        resposta = APIClient().post(URL, _payload(website=valor), format="json")

        assert resposta.status_code == 200, resposta.data

    def test_honeypot_nunca_chega_a_ser_processado_como_campo_de_mensagem(
        self, canal_entregando
    ):
        """`validated_data` tem só os três campos — o honeypot é descartado."""
        resposta = APIClient().post(URL, _payload(), format="json")

        assert resposta.status_code == 200
        texto = EntregaSimuladaBackend.entregues[0].get_payload(decode=True).decode("utf-8")
        assert "website" not in texto
