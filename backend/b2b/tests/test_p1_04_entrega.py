"""O alerta B2B não pode dizer que entregou o que não entregou.

Este é o QUARTO lugar do furo que o P0-02c documentou, e o único que NINGUÉM
achou quando o `config/email_entrega.py` foi extraído (P1-04): `b2b/services.py`
importava `django.core.mail.send_mail` e chamava direto.

POR QUE ESSE LUGAR É PIOR QUE OS OUTROS TRÊS
=============================================
O `contato` mentia num 200; a newsletter mentia num `total_enviados` gravado
no banco. O B2B mente num **log de task** (`b2b/tasks.py:10`) e — este é o
agravante — **consome o ratchet**.

`CriterioMonitoramento.ultimo_alerta_em` é o corte de
`_itens_novos_para_criterio`: uma vez gravado, aquelas notícias NUNCA mais
entram em alerta. Na base `623a0e9` o `send_mail` era chamado, o retorno era
ignorado e o ratchet era gravado em seguida. Com
`DJANGO_EMAIL_BACKEND=console.EmailBackend` — o default de
`config/settings.py:652-654` — isso significava, medido antes da correção:

    total_alertas_enviados = 1
    total_falhas           = 0
    ultimo_alerta_em       = 2026-09-28 22:42:56+00:00   (gravado)
    stdout                 = a mensagem MIME inteira, com o destinatário

Ou seja: o cliente pagava por um monitoramento que nunca avisou, nunca voltaria
a avisar, e o job logava "1 alerta(s) enviado(s)". Este arquivo existe para que
esse número não possa voltar a mentir.

A TABELA DE MENTIRAS QUE CADA TESTE FECHA
========================================
| teste                                                   | mentira que ele mata                        |
|---------------------------------------------------------|---------------------------------------------|
| `console` recusa, não envia, conta como falha           | "1 alerta enviado" sem entrega nenhuma      |
| o corpo NEM chega a ser impresso no stdout               | montar/printar e-mail sem canal             |
| o ratchet NÃO anda sem entrega                          | a notícia ser marcada como já alertada      |
| o que faltou sai inteiro na execução seguinte           | a perda permanente do alerta                |
| provedor devolvendo 0 / estourando                      | a mesma mentira, com um backend "de verdade"|
| o `ERROR` nomeia a configuração                         | o operador sem saber o que definir          |
| métrica `sem_canal`                                      | o contador de entrega mentindo              |
| `services` não tem `send_mail`                          | a regressão do contorno do gate            |
| o log não leva endereço, notícia nem organização        | PII no log de entrega                       |

NENHUM TESTE DESTE ARQUIVO SAI PARA A REDE: os provedores são os dublês de
`config/tests/backends.py`, e a guarda `nenhum_teste_sai_para_a_rede`
(autouse, em `b2b/tests/conftest.py`) cobre `requests` e `SessaoEgress`.
"""

from __future__ import annotations

import logging

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings

from b2b import services
from b2b.models import CriterioMonitoramento
from catalogo_noticias.models import NewsItem
from config.email_entrega import BACKENDS_SEM_ENTREGA_REAL
from config.health import METRICAS
from config.tests.backends import (
    EntregaSimuladaBackend,
    ErroDeRedeBackend,
    ExplodindoBackend,
    RecusaBackend,
    caminho_de,
)

pytestmark = pytest.mark.django_db
User = get_user_model()

BACKEND_QUE_ENTREGA = caminho_de(EntregaSimuladaBackend)

CONSOLE = "django.core.mail.backends.console.EmailBackend"

#: Corpo que só existe se o e-mail foi MONTADO. Com o portão de canal ele
#: nunca aparece no stdout — e é isso que distingue "recusou antes de montar"
#: de "recusou depois de mandar para o vazio".
MARCA_DO_ALERTO = "Mercado fecha em alta"

DESTINATARIO = "membro-b2b@example.com"


# ---------------------------------------------------------------------------
# Ajudantes
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _zera_metricas():
    """`METRICAS` é um registro de processo, compartilhado entre testes."""
    METRICAS._contadores.clear()
    METRICAS._rotulos.clear()
    yield
    METRICAS._contadores.clear()
    METRICAS._rotulos.clear()


def _org_com_um_criterio(email=DESTINATARIO, noticia=MARCA_DO_ALERTO):
    admin = User.objects.create_user(email=email, password="senha123", papel="free")
    org = services.criar_organizacao_com_admin("Empresa Alerta B2B", admin)
    criterio = services.criar_criterio(org, CriterioMonitoramento.TIPO_PALAVRA_CHAVE, "mercado")
    if noticia is not None:
        NewsItem.objects.create(
            titulo=noticia,
            resumo_proprio="Resumo.",
            conteudo_bruto="Conteudo bruto longo o bastante para o modelo de resumo.",
            url_fonte_original="https://g1/alerta-b2b-1",
            nome_fonte="G1",
            categoria="economia",
            status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
        )
    return org, criterio


def _valor_da_metrica(nome: str, **rotulos) -> float:
    total = 0.0
    for (nome_medido, rotulos_medidos), valor in METRICAS._contadores.items():
        if nome_medido == nome and dict(rotulos_medidos) == rotulos:
            total += valor
    return total


# ---------------------------------------------------------------------------
# O portão: console recusa, não envia, e conta como falha
# ---------------------------------------------------------------------------


class TestConsoleNaoEEntrega:

    def test_padrao_do_projeto_recusa_e_nao_conta_nada_como_enviado(self, settings, caplog):
        """Este é o cenário real de hoje: o default do projeto é `console`."""
        settings.EMAIL_BACKEND = CONSOLE
        _org_com_um_criterio()

        with caplog.at_level(logging.ERROR, logger="b2b.services"):
            resultado = services.verificar_e_enviar_alertas()

        assert resultado["total_alertas_enviados"] == 0, (
            "console não entrega a ninguém e mesmo assim o job contou "
            f"{resultado['total_alertas_enviados']} como enviado(s) — esta é a "
            "mesma mentira de entrega que o P0-02c documentou"
        )
        # "Falha", e não "não processada": o cliente esperava o alerta e não o
        # recebeu, e é `total_falhas` que o operador olha.
        assert resultado["total_falhas"] == 1
        assert resultado["total_criterios_verificados"] == 1

    @pytest.mark.parametrize("backend", sorted(BACKENDS_SEM_ENTREGA_REAL))
    def test_todo_backend_sem_entrega_real_e_recusado(self, settings, backend):
        settings.EMAIL_BACKEND = backend
        _org_com_um_criterio()

        resultado = services.verificar_e_enviar_alertas()

        assert resultado["total_alertas_enviados"] == 0, backend
        assert resultado["total_falhas"] == 1, backend

    def test_o_corpo_do_alerta_nao_chega_a_ser_impresso_no_stdout(self, settings, capfd):
        """
        Prova mais forte que "não foi entregue": o corpo NEM É MONTADO.

        Se alguém "consertar" isso com console + `total_alertas_enviados=1`,
        este teste quebra — e quebra porque a marca do corpo apareceu no
        stdout, não porque um contador mudou.
        """
        settings.EMAIL_BACKEND = CONSOLE
        _org_com_um_criterio()

        services.verificar_e_enviar_alertas()

        saida = capfd.readouterr().out
        assert MARCA_DO_ALERTO not in saida
        assert DESTINATARIO not in saida, "o destinatário não pode ser impresso"
        assert "Subject:" not in saida, "nenhuma mensagem pode ser montada sem canal"
        assert mail.outbox == [], "nenhum envio pode ter sido tentado"

    def test_o_error_nomeia_a_configuracao_e_diz_o_que_fazer(self, settings, caplog):
        """Quem lê o log tem que saber QUAL configuração falta — o item do
        P0-02c foi o de um caminho que recusa entrega e não diz o que definir."""
        settings.EMAIL_BACKEND = CONSOLE
        _org_com_um_criterio()

        with caplog.at_level(logging.ERROR, logger="b2b.services"):
            services.verificar_e_enviar_alertas()

        registros = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(registros) == 1, "um ERROR só por execução, não um por critério"
        texto = registros[0].getMessage()
        assert "DJANGO_EMAIL_BACKEND" in texto
        assert "console.EmailBackend" in texto
        # A orientação de fonte única, que é quem nomeia a credencial.
        assert "RESEND_API_KEY" in texto
        assert "NENHUM alerta entregue" in texto

    def test_a_metrica_conta_sem_canal_e_nao_conta_entregue(self, settings):
        settings.EMAIL_BACKEND = CONSOLE
        _org_com_um_criterio()

        services.verificar_e_enviar_alertas()

        assert _valor_da_metrica(
            "portal_email_entrega_total", destino="b2b_alerta", situacao="sem_canal"
        ) == 1
        assert _valor_da_metrica(
            "portal_email_entrega_total", destino="b2b_alerta", situacao="entregue"
        ) == 0

    def test_o_log_nao_leva_endereco_nem_noticia(self, settings, caplog):
        """
        O que NÃO pode entrar no log de uma execução sem canal é o dado
        PESSOAL: o endereço do membro e o título da notícia.

        O NOME DA ORGANIZAÇÃO entra, e isso é de propósito e anterior a este
        item: `_registrar_anomalia` (P1-13) loga `organizacao=<nome>` porque a
        anomalia é **de tenant** e o operador precisa saber de qual empresa ela
        é. Nome de empresa é dado contratual, não dado pessoal de membro, e é o
        identificador que o operador já usava antes deste item. O que este item
        garante é que a recusa do canal não **acrescente** nada disso.
        """
        settings.EMAIL_BACKEND = CONSOLE
        _org_com_um_criterio()

        with caplog.at_level(logging.DEBUG):
            services.verificar_e_enviar_alertas()

        for proibido in (DESTINATARIO, MARCA_DO_ALERTO, "G1"):
            assert proibido not in caplog.text, f"o log vaza {proibido!r}"
        # Nenhum endereço, em nenhuma forma: nem o local, nem o domínio.
        assert "example.com" not in caplog.text
        assert "@" not in caplog.text, "o log não pode conter endereço de membro"


# ---------------------------------------------------------------------------
# O ratchet: a falha consome a notícia, e não pode
# ---------------------------------------------------------------------------


class TestRatchetSoAndaComEntrega:

    def test_sem_canal_o_ratchet_nao_anda(self, settings):
        """O bug que este item fecha. Com `console`, a base `623a0e9` gravava
        `ultimo_alerta_em` — e aquela notícia nunca mais era alertada, nem
        depois que a configuração fosse corrigida."""
        settings.EMAIL_BACKEND = CONSOLE
        _, criterio = _org_com_um_criterio()

        services.verificar_e_enviar_alertas()

        criterio.refresh_from_db()
        assert criterio.ultimo_alerta_em is None, (
            "o ratchet avançou sem entrega: a notícia foi marcada como já "
            "alertada e nunca mais sai"
        )

    def test_o_que_ficou_pendente_sai_integral_na_execucao_seguinte(self, settings):
        """
        O caminho inverso do teste acima, e é o que dá sentido a ele: corrigir
        a configuração entrega tudo o que foi perdido — nada foi consumido.
        """
        settings.EMAIL_BACKEND = CONSOLE
        _, criterio = _org_com_um_criterio()

        services.verificar_e_enviar_alertas()
        criterio.refresh_from_db()
        assert criterio.ultimo_alerta_em is None

        settings.EMAIL_BACKEND = BACKEND_QUE_ENTREGA
        segunda = services.verificar_e_enviar_alertas()

        assert segunda["total_alertas_enviados"] == 1
        criterio.refresh_from_db()
        assert criterio.ultimo_alerta_em is not None
        assert len(mail.outbox) == 1
        assert MARCA_DO_ALERTO in mail.outbox[0].body

    @override_settings(EMAIL_BACKEND=BACKEND_QUE_ENTREGA)
    def test_com_entrega_o_ratchet_anda(self, canal_entregando):
        _, criterio = _org_com_um_criterio()

        services.verificar_e_enviar_alertas()

        criterio.refresh_from_db()
        assert criterio.ultimo_alerta_em is not None

    def test_provedor_que_devolve_zero_nao_anda_o_ratchet(self, settings):
        settings.EMAIL_BACKEND = caminho_de(RecusaBackend)
        _, criterio = _org_com_um_criterio()

        resultado = services.verificar_e_enviar_alertas()

        assert resultado["total_alertas_enviados"] == 0
        assert resultado["total_falhas"] == 1
        criterio.refresh_from_db()
        assert criterio.ultimo_alerta_em is None

    def test_provedor_que_estoura_nao_anda_o_ratchet(self, settings):
        settings.EMAIL_BACKEND = caminho_de(ExplodindoBackend)
        _, criterio = _org_com_um_criterio()

        resultado = services.verificar_e_enviar_alertas()

        assert resultado["total_alertas_enviados"] == 0
        assert resultado["total_falhas"] == 1
        criterio.refresh_from_db()
        assert criterio.ultimo_alerta_em is None

    def test_erro_de_rede_nao_anda_o_ratchet(self, settings):
        settings.EMAIL_BACKEND = caminho_de(ErroDeRedeBackend)
        _, criterio = _org_com_um_criterio()

        resultado = services.verificar_e_enviar_alertas()

        assert resultado["total_alertas_enviados"] == 0
        assert resultado["total_falhas"] == 1
        criterio.refresh_from_db()
        assert criterio.ultimo_alerta_em is None


# ---------------------------------------------------------------------------
# "Enviado" significa entregue
# ---------------------------------------------------------------------------


class TestEntregueRealmente:

    def test_com_canal_real_o_alerta_chega_ao_membro_da_organizacao(self, canal_entregando):
        _org_com_um_criterio()

        resultado = services.verificar_e_enviar_alertas()

        assert resultado["total_alertas_enviados"] == 1
        assert resultado["total_falhas"] == 0
        assert len(mail.outbox) == 1
        mensagem = mail.outbox[0]
        assert mensagem.to == [DESTINATARIO]
        assert MARCA_DO_ALERTO in mensagem.body
        # Fonte original sempre presente (mesmo contrato do BRD da newsletter).
        assert "https://g1/alerta-b2b-1" in mensagem.body
        assert "[Alerta]" in mensagem.subject
        assert len(EntregaSimuladaBackend.entregues) == 1

    def test_sem_item_novo_nao_tenta_enviar_e_nao_falha(self, settings):
        """Um job ocioso não é falha: nada tinha para sair."""
        settings.EMAIL_BACKEND = CONSOLE
        _org_com_um_criterio(noticia=None)

        resultado = services.verificar_e_enviar_alertas()

        assert resultado["total_alertas_enviados"] == 0
        assert resultado["total_falhas"] == 0

    def test_sem_membro_com_email_nao_tenta_enviar_e_nao_falha(self, settings):
        """A anomalia `sem_destinatario` já cobre o porquê (P1-13)."""
        settings.EMAIL_BACKEND = CONSOLE
        _org_com_um_criterio()
        User.objects.filter(email=DESTINATARIO).update(email="")

        resultado = services.verificar_e_enviar_alertas()

        assert resultado["total_alertas_enviados"] == 0
        assert resultado["total_falhas"] == 0

    def test_o_limite_de_execucao_ainda_segura_com_canal_recusado(self, settings):
        """
        O que separa a contagem honesta da contagem inflada.

        Quatro critérios ativos, mas **só um** tem novidade que case: os outros
        três (`p0`, `p1`, `p2`) não têm notícia correspondente. Um portão que
        simplesmente contasse "critérios ativos" como falha daria 4 — e seria
        mentira do outro lado: um critério sem o que entregar não falhou.

        O placar correto é 1 falha (o `mercado`), e nenhum ratchet andou.
        """
        settings.EMAIL_BACKEND = CONSOLE
        settings.B2B_ALERTA_MAX_POR_EXECUCAO = 50
        org, _ = _org_com_um_criterio()
        for i in range(3):
            services.criar_criterio(org, CriterioMonitoramento.TIPO_PALAVRA_CHAVE, f"p{i}")

        resultado = services.verificar_e_enviar_alertas()

        assert resultado["total_criterios_verificados"] == 4
        assert resultado["total_alertas_enviados"] == 0
        assert resultado["total_falhas"] == 1, (
            "só o critério que tinha novidade a entregar é falha; os outros três "
            "não tinham o que enviar"
        )
        assert CriterioMonitoramento.objects.filter(ultimo_alerta_em__isnull=False).count() == 0

    def test_cada_criterio_com_novidade_conta_uma_falha(self, settings):
        """O outro lado da mesma régua: agora os quatro casam."""
        settings.EMAIL_BACKEND = CONSOLE
        org, _ = _org_com_um_criterio()
        for i in range(3):
            services.criar_criterio(org, CriterioMonitoramento.TIPO_PALAVRA_CHAVE, f"p{i}")
            NewsItem.objects.create(
                titulo=f"Novidade especifica p{i}",
                resumo_proprio="Resumo.",
                conteudo_bruto="Conteudo bruto longo o bastante para o modelo de resumo.",
                url_fonte_original=f"https://g1/p{i}",
                nome_fonte="G1",
                categoria="economia",
                status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
            )

        resultado = services.verificar_e_enviar_alertas()

        assert resultado["total_alertas_enviados"] == 0
        assert resultado["total_falhas"] == 4


# ---------------------------------------------------------------------------
# A COSTURA: a prova de que o gate não pode ser contornado por accident
# ---------------------------------------------------------------------------


def test_o_modulo_b2b_nao_tem_mais_send_mail():
    """
    Trava de Honestidade nº 1 deste item: o contorno que existia na base
    `623a0e9` era `from django.core.mail import send_mail` em
    `b2b/services.py`. Se alguém reintroduzir o import **e** o atributo
    voltar a existir neste módulo, este teste quebra.

    Ele é a trava de DEFESA DE ALCANCE (`Identidade` do símbolo). A trava de
    defesa estrutural — que nenhum módulo do projeto contorne o gate, e não
    só o b2b — é
    `config/tests/test_p1_04_email_entrega.py::TestNenhumModuloContornaOGateDeEmail::test_nenhum_modulo_de_producao_chama_o_transporte_de_e-mail_fora_do_gate`.
    """
    assert not hasattr(services, "send_mail"), (
        "b2b/services.py voltou a expor `send_mail`: o alerta B2B deve passar "
        "por `entregar_alerta`, que é o `config.email_entrega.entregar_email`"
    )
    assert services.entregar_alerta.__module__ == "b2b.services"


def test_a_costura_de_transporte_monta_email_message_e_nao_chama_send_mail(canal_entregando):
    """`entregar_alerta` entrega pelo gate: um `console` aqui também recusa."""
    settings_ = canal_entregando
    settings_.EMAIL_BACKEND = CONSOLE
    org, criterio = _org_com_um_criterio()
    from b2b.models import MembroOrganizacao

    with pytest.raises(Exception) as erro:
        services.entregar_alerta(
            criterio, [{"titulo": MARCA_DO_ALERTO, "nome_fonte": "G1", "url_fonte_original": "https://g1/x"}],
            [DESTINATARIO],
        )

    # `CanalIndisponivel`, do gate — e não um retorno 1 de mentira.
    assert type(erro.value).__name__ == "CanalIndisponivel"
    assert MembroOrganizacao.objects.filter(organizacao=org).exists()
