"""O contrato central do P1-15b: **nunca 2xx para uma mensagem não entregue**.

Cada teste aqui existe para fechar uma forma específica de mentira:

| teste                              | mentira que ele mata                                        |
|------------------------------------|-------------------------------------------------------------|
| console/locmem/dummy/filebased     | "enviei" imprimindo num stdout/buffer que ninguém lê          |
| destino vazio ou inválido          | "enviei" para lugar nenhum                                  |
| Resend sem chave                   | 500 (ou 2xx) enquanto a credencial do Alex não chegou        |
| Resend com chave (mock de rede)    | o contrário: prova que o caminho real devolve 2xx            |
| provedor devolvendo 0              | "enviei" contra um provedor que aceitou a conexão e não a msg|
| provedor estourando                | 2xx de mentira e 500 cru para o usuário                      |
| ausência de persistência          | a suposição de que a mensagem ficou guardada em algum lugar   |
| log mínimo                         | vazar corpo da mensagem, endereço de destino ou credencial   |

Todos usam `pytest.mark.django_db` por coerência com os demais testes de
endpoint do projeto, ainda que este endpoint não toque no banco.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest
import requests
from django.apps import apps
from django.core import mail
from rest_framework.test import APIClient

from contato.tests.backends import (
    EntregaSimuladaBackend,
    ExplodindoBackend,
    RecusaBackend,
    caminho_de,
)

pytestmark = pytest.mark.django_db

URL = "/api/contato/"
DESTINO = "redacao@exemplo.org"  # endereço fictício de teste, não domínio do projeto
BACKEND_QUE_ENTREGA = caminho_de(EntregaSimuladaBackend)

# Marcadores únicos: aparecem no corpo da mensagem/log quando algo vaza.
CORPO = "Mensagem de teste do P1-15b, com tamanho suficiente para passar da validação."
EMAIL = "leitor@example.com"


@pytest.fixture(autouse=True)
def _limpa_registro_de_entregas():
    EntregaSimuladaBackend.entregues.clear()
    yield
    EntregaSimuladaBackend.entregues.clear()


@pytest.fixture
def canal_entregando(settings):
    """Configura um canal que o projeto considera de entrega real."""
    settings.EMAIL_BACKEND = BACKEND_QUE_ENTREGA
    settings.CONTATO_DESTINO = DESTINO
    return settings


def _payload(**extra):
    dados = {"nome": "Ana Souza", "email": EMAIL, "mensagem": CORPO}
    dados.update(extra)
    return dados


class TestCaminhoFelizEntregaReal:
    def test_payload_valido_com_entrega_configurada_responde_200(self, canal_entregando):
        resposta = APIClient().post(URL, _payload(), format="json")

        assert resposta.status_code == 200, resposta.data
        assert "id" in resposta.data
        assert resposta.data["id"], "o 2xx precisa trazer identificador opaco"
        assert "detail" in resposta.data

    def test_identificador_opaco_nao_carrega_pii(self, canal_entregando):
        resposta = APIClient().post(URL, _payload(), format="json")

        identificador = resposta.data["id"]
        # Um id de 12 caracteres base64url, sem nada derivado do conteúdo.
        assert 8 <= len(identificador) <= 24
        for pii in (EMAIL, DESTINO, "Ana Souza", CORPO):
            assert pii.lower() not in identificador.lower()

    def test_resposta_nao_ecola_nada_do_usuario_nem_o_destino(self, canal_entregando):
        resposta = APIClient().post(URL, _payload(), format="json")

        corpo = str(resposta.data)
        for proibido in (EMAIL, DESTINO, CORPO, "Ana Souza"):
            assert proibido not in corpo, f"resposta ecoou {proibido!r}: {corpo}"

    def test_mensagem_entregue_chega_com_o_que_a_redacao_precisa(self, canal_entregando):
        APIClient().post(URL, _payload(), format="json")

        assert len(EntregaSimuladaBackend.entregues) == 1
        mime = EntregaSimuladaBackend.entregues[0]
        # O corpo é transportado em base64 (charset utf-8 do Django), então
        # precisa ser decodificado para ser conferido como texto.
        texto = mime.get_payload(decode=True).decode("utf-8")
        assert "Ana Souza" in texto
        assert EMAIL in texto
        assert CORPO in texto
        assert mime["To"] == DESTINO
        # Reply-To é o que permite responder sem digitar o endereço.
        assert mime["Reply-To"] == EMAIL

    def test_identificadores_diferentes_para_cada_mensagem(self, canal_entregando):
        client = APIClient()
        primeiro = client.post(URL, _payload(), format="json").data["id"]
        segundo = client.post(URL, _payload(), format="json").data["id"]

        assert primeiro != segundo


class TestNuncaDoisXxxSemEntrega:
    @pytest.mark.parametrize(
        "backend",
        [
            "django.core.mail.backends.console.EmailBackend",
            "django.core.mail.backends.locmem.EmailBackend",
            "django.core.mail.backends.dummy.EmailBackend",
            "django.core.mail.backends.filebased.EmailBackend",
            "",
        ],
    )
    def test_backends_que_nao_entregam_nada_respondem_503(self, settings, backend):
        settings.EMAIL_BACKEND = backend
        settings.CONTATO_DESTINO = DESTINO

        resposta = APIClient().post(URL, _payload(), format="json")

        assert resposta.status_code == 503, resposta.data
        assert not (200 <= resposta.status_code < 300)
        assert "DJANGO_EMAIL_BACKEND" in resposta.data["detail"]
        assert mail.outbox == [], "nenhum envio pode ter sido tentado"

    def test_padrao_do_projeto_console_e_503_e_nao_chega_a_imprimir(self, settings, capsys):
        """O cenário real de hoje: backend default é `console` (PROD_DECISOES.md:26-29)."""
        settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
        settings.CONTATO_DESTINO = DESTINO

        resposta = APIClient().post(URL, _payload(), format="json")

        assert resposta.status_code == 503
        # Prova mais forte que "não foi entregue": o corpo nem chegou a ser
        # impresso no stdout, porque o portão de entrega barra antes do envio.
        # Se alguém "consertar" isso com console + 200, este teste quebra.
        assert CORPO not in capsys.readouterr().out

    def test_locmem_cheio_de_mensagens_nao_produz_2xx(self, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        settings.CONTATO_DESTINO = DESTINO
        antes = len(mail.outbox)

        resposta = APIClient().post(URL, _payload(), format="json")

        assert resposta.status_code == 503
        assert len(mail.outbox) == antes, "locmem não pode receber a mensagem"

    def test_destino_vazio_responde_503(self, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
        settings.CONTATO_DESTINO = ""

        resposta = APIClient().post(URL, _payload(), format="json")

        assert resposta.status_code == 503
        assert "CONTATO_DESTINO_EMAIL" in resposta.data["detail"]

    def test_destino_invalido_responde_503_sem_ecoar_o_valor(self, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
        settings.CONTATO_DESTINO = "nao-e-um-email"

        resposta = APIClient().post(URL, _payload(), format="json")

        assert resposta.status_code == 503
        assert "nao-e-um-email" not in str(resposta.data)

    def test_provedor_que_devolve_zero_responde_503(self, settings):
        settings.EMAIL_BACKEND = caminho_de(RecusaBackend)
        settings.CONTATO_DESTINO = DESTINO

        resposta = APIClient().post(URL, _payload(), format="json")

        assert resposta.status_code == 503

    def test_provedor_que_estoura_responde_503_e_nao_500(self, settings):
        settings.EMAIL_BACKEND = caminho_de(ExplodindoBackend)
        settings.CONTATO_DESTINO = DESTINO

        resposta = APIClient().post(URL, _payload(), format="json")

        assert resposta.status_code == 503, resposta.data
        assert "provedor" in resposta.data["detail"]


class TestCaminhoResendDoProjeto:
    """`config/email_resend.py` — o backend que a produção vai usar de fato."""

    def test_sem_chave_responde_503_sem_tocar_a_rede(self, settings, monkeypatch):
        settings.EMAIL_BACKEND = "config.email_resend.ResendEmailBackend"
        settings.RESEND_API_KEY = ""
        settings.CONTATO_DESTINO = DESTINO
        called = []
        monkeypatch.setattr(requests, "post", lambda *a, **k: called.append(1))

        resposta = APIClient().post(URL, _payload(), format="json")

        assert resposta.status_code == 503
        assert "RESEND_API_KEY" in resposta.data["detail"]
        assert called == [], "sem chave não pode haver tentativa de rede"

    def test_com_chave_entrega_e_responde_200(self, settings, monkeypatch):
        settings.EMAIL_BACKEND = "config.email_resend.ResendEmailBackend"
        settings.RESEND_API_KEY = "re_chave-de-teste-nao-secreta"
        settings.CONTATO_DESTINO = DESTINO
        capturado = {}

        class _RespostaFake:
            status_code = 201
            text = '{"id":"email-de-teste"}'

        def _post(url, json=None, headers=None, timeout=None):
            capturado["url"] = url
            capturado["json"] = json
            capturado["headers"] = headers
            return _RespostaFake()

        monkeypatch.setattr(requests, "post", _post)

        resposta = APIClient().post(URL, _payload(), format="json")

        assert resposta.status_code == 200, resposta.data
        assert resposta.data["id"]
        # O corpo entregue ao Resend leva o que a redação precisa, e o
        # cabeçalho de autorização prova que o caminho real foi exercitado.
        assert capturado["json"]["to"] == [DESTINO]
        assert capturado["json"]["reply_to"] == [EMAIL]
        assert "text" in capturado["json"] and "html" not in capturado["json"]
        assert capturado["headers"]["Authorization"].endswith(
            settings.RESEND_API_KEY
        )

    def test_resend_recusando_com_http_500_responde_503(self, settings, monkeypatch):
        settings.EMAIL_BACKEND = "config.email_resend.ResendEmailBackend"
        settings.RESEND_API_KEY = "re_chave-de-teste"
        settings.CONTATO_DESTINO = DESTINO

        class _RespostaRecusada:
            status_code = 500
            text = "erro interno do provedor"

        monkeypatch.setattr(requests, "post", lambda *a, **k: _RespostaRecusada())

        resposta = APIClient().post(URL, _payload(), format="json")

        assert resposta.status_code == 503, resposta.data
        assert not (200 <= resposta.status_code < 300)

    def test_resend_com_erro_de_rede_responde_503(self, settings, monkeypatch):
        settings.EMAIL_BACKEND = "config.email_resend.ResendEmailBackend"
        settings.RESEND_API_KEY = "re_chave-de-teste"
        settings.CONTATO_DESTINO = DESTINO

        def _explode(*a, **k):
            raise requests.ConnectionError("provedor inalcançável")

        monkeypatch.setattr(requests, "post", _explode)

        resposta = APIClient().post(URL, _payload(), format="json")

        assert resposta.status_code == 503


class TestNadaEPersistido:
    """O item proíbe migration. Isso é verificado, não prometido."""

    def test_app_contato_nao_esta_registrado_com_models(self):
        # Um app com model e sem migration quebraria `manage.py check`;
        # como não existe model, o app nem precisa estar em INSTALLED_APPS
        # (mesmo desenho de `enderecos/`).
        assert not Path(__file__).resolve().parents[1].joinpath("models.py").exists()
        assert not Path(__file__).resolve().parents[1].joinpath("migrations").exists()
        assert all(cfg.name != "contato" for cfg in apps.get_app_configs())

    def test_uma_mensagem_entregue_nao_cria_nenhum_modelo(self, canal_entregando):
        antes = len(list(apps.get_models()))
        APIClient().post(URL, _payload(), format="json")
        depois = len(list(apps.get_models()))

        assert antes == depois


class TestLogMinimo:
    def test_log_nao_contem_corpo_nome_email_nem_destino(self, canal_entregando, caplog):
        with caplog.at_level(logging.DEBUG):
            APIClient().post(URL, _payload(), format="json")

        for proibido in (CORPO, EMAIL, DESTINO, "Ana Souza"):
            assert proibido not in caplog.text, f"log vazou {proibido!r}"

    def test_log_nao_contem_credencial_do_resend(self, settings, monkeypatch, caplog):
        settings.EMAIL_BACKEND = "config.email_resend.ResendEmailBackend"
        settings.RESEND_API_KEY = "re_segredo-que-nao-pode-aparecer"
        settings.CONTATO_DESTINO = DESTINO

        class _RespostaFake:
            status_code = 201
            text = "{}"

        monkeypatch.setattr(requests, "post", lambda *a, **k: _RespostaFake())

        with caplog.at_level(logging.DEBUG):
            resposta = APIClient().post(URL, _payload(), format="json")

        assert resposta.status_code == 200
        assert "re_segredo-que-nao-pode-aparecer" not in caplog.text

    def test_log_nao_repassa_texto_de_excecao_do_provedor(self, settings, caplog):
        settings.EMAIL_BACKEND = caminho_de(ExplodindoBackend)
        settings.CONTATO_DESTINO = DESTINO

        with caplog.at_level(logging.DEBUG):
            APIClient().post(URL, _payload(), format="json")

        # `ExplodindoBackend` levanta com um texto que o log não pode copiar
        # (num provedor real, o texto de erro pode ecoar o payload enviado).
        assert "provedor fora do ar" not in caplog.text
        assert CORPO not in caplog.text
        # Só o TIPO da exceção entra no log — nem a mensagem dela.
        assert "tipo=RuntimeError" in caplog.text


class TestObservabilidadeDaRespostaDeErro:
    def test_503_traz_request_id_para_correlacao(self, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
        settings.CONTATO_DESTINO = DESTINO

        resposta = APIClient().post(
            URL, _payload(), format="json", HTTP_X_REQUEST_ID="req-abc-123"
        )

        assert resposta.status_code == 503
        # O cliente do frontend (`frontend/lib/api.ts:39-42`) acrescenta
        # `(id: ...)` quando `request_id` vem no corpo.
        assert resposta.data["request_id"] == "req-abc-123"
        assert resposta.headers["X-Request-ID"] == "req-abc-123"

    def test_get_responde_405(self, canal_entregando):
        assert APIClient().get(URL).status_code == 405

    def test_motivo_do_503_e_acionavel(self, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
        settings.CONTATO_DESTINO = ""

        detalhe = APIClient().post(URL, _payload(), format="json").data["detail"]

        # Quem lê a resposta tem que saber O QUE falta, não só que falhou.
        assert "DJANGO_EMAIL_BACKEND" in detalhe
        assert "CONTATO_DESTINO_EMAIL" in detalhe


def test_default_do_settings_declarado_e_console():
    """Trava de Honestidade nº 1: o projeto NÃO nasce com entrega configurada.

    `setup_test_environment()` do Django troca `EMAIL_BACKEND` por `locmem` no
    ambiente de teste (é assim que `mail.outbox` funciona), então o DEFAULT
    DECLARADO é conferido no fonte do módulo de settings — que é a afirmação
    que interessa: sem configuração explícita, o portal não entrega e-mail.
    """
    if os.environ.get("DJANGO_EMAIL_BACKEND"):
        pytest.skip("ambiente define DJANGO_EMAIL_BACKEND explicitamente")

    import config.settings as modulo_settings

    fonte = Path(modulo_settings.__file__).read_text(encoding="utf-8")
    assert (
        '"DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"'
        in fonte
    ), "o default do projeto não pode deixar de ser console (que não entrega)"
    assert 'CONTATO_DESTINO = os.environ.get("CONTATO_DESTINO_EMAIL", "")' in fonte
