"""P1-04 — a newsletter não pode dizer que entregou o que não entregou.

Este é o TERCEIRO lugar do furo que o P0-02c documentou, e o mais
traiçoeiro dos três, porque aqui a mentira não aparece numa resposta HTTP:
ela aparece num **número gravado no banco**.

O código antigo (`newsletter/services.py`, antes deste item) era:

    send_mail(...)
    total_enviados += 1

Com `DJANGO_EMAIL_BACKEND=console.EmailBackend` (o padrão de
`config/settings.py:615-617`), `send_mail` **devolve 1 e imprime no stdout**.
O `EnvioNewsletter` ficava com `total_enviados == N` para N resumos que
ninguém recebeu, e `newsletter/tasks.py:10` logava "N enviados" — duas
fontes de verdade, ambas mentindo, e nenhuma delas num lugar onde alguém
olha pra dizer que deu errado.

O gate agora é `config/email_entrega.entregar_email`: sem canal de entrega
real, nenhum resumo é enviado, nenhum é impresso, e o `EnvioNewsletter`
registra `total_enviados=0`.

NENHUM TESTE DESTE ARQUIVO SAI PARA A REDE: os provedores são os dublês de
`config/tests/backends.py`.
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone

from catalogo_noticias.models import NewsItem
from config.email_entrega import BACKENDS_SEM_ENTREGA_REAL
from config.tests.backends import (
    EntregaSimuladaBackend,
    ErroDeRedeBackend,
    ExplodindoBackend,
    RecusaBackend,
    caminho_de,
)
from newsletter import services
from newsletter.models import EnvioNewsletter, InscricaoNewsletter

pytestmark = pytest.mark.django_db

User = get_user_model()

BACKEND_QUE_ENTREGA = caminho_de(EntregaSimuladaBackend)


@pytest.fixture(autouse=True)
def _limpa_registro_de_entregas():
    EntregaSimuladaBackend.entregues.clear()
    yield
    EntregaSimuladaBackend.entregues.clear()


def _usuario_inscrito(email):
    usuario = User.objects.create_user(email=email, password="SenhaForte123")
    usuario.consentimento_aceito_em = timezone.now()
    usuario.save(update_fields=["consentimento_aceito_em"])
    services.inscrever(usuario, InscricaoNewsletter.TIPO_PADRAO)
    return usuario


def _item(titulo, url):
    return NewsItem.objects.create(
        titulo=titulo,
        resumo_proprio="Resumo",
        conteudo_bruto="Bruto",
        url_fonte_original=url,
        nome_fonte="G1",
        categoria="geral",
        status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
    )


# ===========================================================================
# O contador não pode mentir
# ===========================================================================


class TestContadorDeEnvio:
    def test_com_canal_real_conta_o_que_entregou(self, settings):
        settings.EMAIL_BACKEND = BACKEND_QUE_ENTREGA
        _item("Noticia", "https://g1/news-1")
        _usuario_inscrito("recebe@example.com")

        envio = services.enviar_newsletters()

        assert envio.total_enviados == 1
        assert envio.total_falhas == 0
        assert len(EntregaSimuladaBackend.entregues) == 1

    @pytest.mark.parametrize("backend", sorted(BACKENDS_SEM_ENTREGA_REAL))
    def test_backend_sem_entrega_real_nao_conta_nada_como_enviado(self, settings, backend):
        settings.EMAIL_BACKEND = backend
        _item("Noticia", "https://g1/news-2")
        _usuario_inscrito("nao-recebe@example.com")

        envio = services.enviar_newsletters()

        assert envio.total_enviados == 0, (
            f"{backend} não entrega a ninguém, e mesmo assim o EnvioNewsletter "
            f"contou {envio.total_enviados} como enviado(s)"
        )
        # As inscrições não chegaram a ser tentadas, e do ponto de vista de
        # quem esperava o resumo da manhã elas falharam.
        assert envio.total_falhas == 1
        assert envio.total_inscricoes_processadas == 1

    def test_backend_console_nao_imprime_o_resumo_no_stdout(self, settings, capsys):
        settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
        _item("Noticia segredo", "https://g1/news-3")
        _usuario_inscrito("imprimido@example.com")

        services.enviar_newsletters()

        capturado = capsys.readouterr()
        assert capturado.out == "", f"o console backend imprimiu o resumo: {capturado.out!r}"
        assert "imprimido@example.com" not in capturado.out

    def test_sem_canal_avisa_no_log_e_nao_diz_que_enviou(self, settings, caplog):
        settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
        _usuario_inscrito("log@example.com")

        with caplog.at_level(logging.ERROR):
            services.enviar_newsletters()

        logs = "\n".join(r.getMessage() for r in caplog.records)
        assert "NENHUM resumo entregue" in logs
        # O endereço do inscrito não precisa estar no log.
        assert "log@example.com" not in logs

    @pytest.mark.parametrize(
        "classe",
        [RecusaBackend, ExplodindoBackend, ErroDeRedeBackend],
        ids=["provedor-devolve-0", "provedor-estoura", "provedor-caiu-a-conexao"],
    )
    def test_falha_por_inscricao_vira_falha_e_nao_enviado(self, settings, classe):
        settings.EMAIL_BACKEND = caminho_de(classe)
        _usuario_inscrito("falhou@example.com")

        envio = services.enviar_newsletters()

        assert envio.total_enviados == 0
        assert envio.total_falhas == 1

    def test_resiliencia_um_por_um_conta_os_dois_desfechos(self, settings, caplog):
        """Critério de aceite 6 (resiliência a falha individual) continua valendo
        com o gate: um provedor que entrega para uns e falha para outros
        produz um registro honesto dos dois desfechos."""
        settings.EMAIL_BACKEND = caminho_de(RecusaBackend)
        _usuario_inscrito("a@example.com")
        _usuario_inscrito("b@example.com")

        envio = services.enviar_newsletters()

        assert envio.total_inscricoes_processadas == 2
        assert envio.total_enviados == 0
        assert envio.total_falhas == 2

    def test_excecao_inesperada_tambem_vira_falha_e_nao_derruba_o_lote(self, settings):
        """O `except Exception` genérico (critério de aceite 6) continua
        existindo: `montar_corpo_email` consulta o feed e o radar, e uma
        falha ali não pode abortar o envio das outras inscrições. O registro
        continua dizendo a verdade: nada foi enviado, tudo falhou.
        """
        settings.EMAIL_BACKEND = BACKEND_QUE_ENTREGA
        _usuario_inscrito("inesperada@example.com")

        def explodir(*args, **kwargs):
            raise RuntimeError("radar fora do ar")

        with patch.object(services, "montar_corpo_email", side_effect=explodir):
            envio = services.enviar_newsletters()

        assert envio.total_enviados == 0
        assert envio.total_falhas == 1
        assert len(EntregaSimuladaBackend.entregues) == 0

    def test_sem_inscricoes_registra_zero_sem_reclamar_de_canal(self, settings):
        """Nenhum erro, nenhum log de erro: não havia o que enviar, então um
        `console.EmailBackend` não é problema de ninguém nesse caso."""
        settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

        envio = services.enviar_newsletters()

        assert envio.total_inscricoes_processadas == 0
        assert envio.total_enviados == 0
        assert envio.total_falhas == 0

    def test_o_registro_gravado_esta_gravado(self, settings):
        """`EnvioNewsletter` é o que o operador e qualquer relatório consultam.
        O objeto devolvido e a linha no banco precisam contar a mesma coisa —
        senão a resposta da função mente e o banco diz a verdade (ou o
        contrário)."""
        settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
        _usuario_inscrito("gravado@example.com")

        retorno = services.enviar_newsletters()
        do_banco = EnvioNewsletter.objects.get(pk=retorno.id)

        assert do_banco.total_enviados == 0
        assert do_banco.total_falhas == retorno.total_falhas
        assert do_banco.total_inscricoes_processadas == retorno.total_inscricoes_processadas

    def test_task_reporta_o_registro_honesto(self, settings, caplog):
        """`newsletter/tasks.py` é quem loga "N enviados" para o operador. Com o
        gate, esse N tem que ser 0 quando nada saiu."""
        from newsletter import tasks

        settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
        _usuario_inscrito("task@example.com")

        with caplog.at_level(logging.INFO):
            envio_id = tasks.enviar_newsletters_manha_task()

        envio = EnvioNewsletter.objects.get(pk=envio_id)
        assert envio.total_enviados == 0
        logs = "\n".join(r.getMessage() for r in caplog.records)
        assert "0 enviados" in logs
