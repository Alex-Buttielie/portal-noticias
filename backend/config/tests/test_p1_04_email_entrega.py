"""P1-04 — o gate de entrega de e-mail (`config/email_entrega.py`).

`config/email_entrega.py` é a EXTRAÇÃO da regra que `contato/services.py`
tinha e que o P0-02c documentou como faltando em `identidade/` e
`newsletter/`. Estes testes cobrem o gate em si; os efeitos por endpoint
estão em `identidade/tests/test_p1_04_entrega_email.py` e
`newsletter/tests/test_p1_04_entrega.py`.

A TABELA DE MENTIRAS QUE CADA TESTE FECHA
========================================
| teste                                        | mentira que ele mata                     |
|----------------------------------------------|------------------------------------------|
| console/locmem/dummy/filebased/vazio recusado| "entreguei" imprimindo num stdout/buffer  |
| recusa ANTES de chamar o backend             | o token/e-mail sendo gerado e impresso   |
| Resend sem `RESEND_API_KEY`                  | 500 cru (o backend levanta `ValueError`) |
| provedor devolvendo 0                        | "entreguei" contra quem aceitou e dropou |
| provedor estourando (`RuntimeError`)         | exceção vazando como 500                 |
| provedor estourando (`ConnectionError`)      | idem, no tipo de erro de REDE            |
| `str(exc)` fora do log                       | vazar o token pelo texto do provedor     |
| métricas `entregue`/`falha`/`sem_canal`      | o contador de entrega mentindo            |

NENHUM DESTES TESTES SAI PARA A REDE
====================================
O `ResendEmailBackend` de verdade (`config/email_resend.py`) é exercitado
apenas com dublês no alvo certo — `SessaoEgress.post`, o alvo depois do
P0-10 (eixo SSRF), e não `requests.post`. Dublê no lugar errado não falha:
ele sai para `api.resend.com` de verdade. `_rede_proibida` abaixo cobre os
dois alvos justamente para essa saída ser um teste que grita.
"""

from __future__ import annotations

import logging

import pytest
from django.core import mail
from django.core.mail import EmailMessage
from django.test import override_settings

from config.email_entrega import (
    BACKEND_RESEND,
    BACKENDS_SEM_ENTREGA_REAL,
    CanalIndisponivel,
    FalhaDeEntrega,
    MOTIVO_FALHA_GENERICO,
    entregar_email,
    orientacao_de_configuracao,
    registrar_evento,
    verificar_canal_email,
)
from config.health import METRICAS
from config.tests.backends import (
    EntregaSimuladaBackend,
    ErroDeRedeBackend,
    ExplodindoBackend,
    RecusaBackend,
    caminho_de,
)

#: Marcador único: se ele aparecer num log, um log vazou o corpo do e-mail.
SEGREDO = "token-de-verificacao-que-nao-pode-vazar"

BACKEND_QUE_ENTREGA = caminho_de(EntregaSimuladaBackend)

_ALVO_POST = "config.email_resend.SessaoEgress.post"

#: Todos os backends que aceitam a mensagem e não a entregam a ninguém.
BACKENDS_SEM_ENTREGA = sorted(BACKENDS_SEM_ENTREGA_REAL)


def _rede_proibida(*args, **kwargs):
    raise AssertionError(
        f"este teste tentou sair para a rede real; o dublê tem que estar em {_ALVO_POST}"
    )


@pytest.fixture(autouse=True)
def _nenhum_teste_sai_para_a_rede(monkeypatch):
    monkeypatch.setattr("requests.post", _rede_proibida)
    monkeypatch.setattr("requests.get", _rede_proibida)
    monkeypatch.setattr("urllib.request.urlopen", _rede_proibida)


@pytest.fixture(autouse=True)
def _zera_metricas():
    """`METRICAS` é um registro de processo, compartilhado entre testes.

    Sem zerar, um contador de um teste anterior "prova" o desfecho do teste
    seguinte — que é exatamente o tipo de teste que passa pelo motivo errado.
    """
    METRICAS._contadores.clear()
    METRICAS._rotulos.clear()
    yield
    METRICAS._contadores.clear()
    METRICAS._rotulos.clear()


def _mensagem():
    return EmailMessage(
        subject="Confirme seu e-mail",
        body=f"Clique no link. token: {SEGREDO}",
        from_email="no-reply@portal-noticias.com.br",
        to=["leitor@example.com"],
    )


def _valor_da_metrica(nome: str, **rotulos) -> float:
    total = 0.0
    for (nome_medido, rotulos_medidos), valor in METRICAS._contadores.items():
        if nome_medido == nome and dict(rotulos_medidos) == rotulos:
            total += valor
    return total


# ---------------------------------------------------------------------------
# A denylist: backends que aceitam e não entregam
# ---------------------------------------------------------------------------


class TestBackendsSemEntregaReal:
    @pytest.mark.parametrize("backend", BACKENDS_SEM_ENTREGA)
    def test_backends_sem_entrega_real_sao_recusados(self, settings, backend):
        settings.EMAIL_BACKEND = backend

        canal = verificar_canal_email()

        assert canal.disponivel is False, f"{backend} não deveria passar pelo gate"
        assert canal.motivos, "a recusa tem que dizer o que falta"

    @pytest.mark.parametrize(
        "backend",
        [
            "django.core.mail.backends.smtp.EmailBackend",
            BACKEND_QUE_ENTREGA,
        ],
    )
    def test_backends_que_entregam_passam(self, settings, backend):
        settings.EMAIL_BACKEND = backend

        assert verificar_canal_email().disponivel is True

    def test_denylist_cobre_console_locmem_dummy_e_filebased(self):
        """A lista é a mesma de `contato/` (mesmo frozenset, importado de lá).

        A regressão que este teste pega é alguém "corrigindo" a lista e
        esquecendo um dos quatro, ou trocando um caminho e deixando o outro
        só num dos dois módulos.
        """
        assert {
            "django.core.mail.backends.console.EmailBackend",
            "django.core.mail.backends.locmem.EmailBackend",
            "django.core.mail.backends.dummy.EmailBackend",
            "django.core.mail.backends.filebased.EmailBackend",
            "",
        } <= set(BACKENDS_SEM_ENTREGA_REAL)

    def test_contato_importa_a_mesma_lista_e_nao_a_duplica(self):
        """Duas listas divergem na primeira correção parcial de uma delas."""
        from contato import services as contato_services

        assert contato_services.BACKENDS_SEM_ENTREGA_REAL is BACKENDS_SEM_ENTREGA_REAL
        assert contato_services.CanalIndisponivel is CanalIndisponivel
        assert contato_services.FalhaDeEntrega is FalhaDeEntrega


# ---------------------------------------------------------------------------
# LACUNA L1 — a MESMA lista, no `newsletter/`, presa por IDENTIDADE
# ---------------------------------------------------------------------------
# POR QUE ESTE BLOCO EXISTE
# ========================
# A resolução do conflito P1-06 × P1-04 é: `config/email_entrega.py` é a
# fonte única da lista, e `newsletter/` importa dela em vez de ter a sua.
# Essa decisão valia — e NÃO estava presa por nada.
#
# O que existia antes deste bloco, em `newsletter/tests/`:
#
#   - `test_lista_de_backends_que_nao_entregam_do_newsletter_contem_a_do_settings`
#     — compara `config.settings._EMAIL_BACKENDS_QUE_NAO_ENTREGAM` com
#     `contato.services.BACKENDS_SEM_ENTREGA_REAL` por SUBCONJUNTO (`<=`).
#     Passaria igual com o `newsletter` tendo a sua própria lista;
#   - `test_locmem_e_console_sao_reconhecidos_como_nao_entregantes` e
#     `test_resend_e_o_unico_backend_de_verdade_que_o_projeto_conhece` —
#     leem de `contato.services`, nunca de `newsletter.services`, e
#     exercitam comportamento, não identidade.
#
# Nenhum teste afirmava `newsletter.services.BACKENDS_SEM_ENTREGA_REAL is
# config.email_entrega.BACKENDS_SEM_ENTREGA_REAL`. Alguém podia escrever
# `BACKENDS_SEM_ENTREGA_REAL = frozenset({...})` no `newsletter/services.py`
# e a suíte inteira passava. Este bloco é o que fecha a porta.
#
# Por que `is` e não `==`: duas listas com o mesmo conteúdo divergem no
# primeiro item corrigido só num dos lados. `is` prende a FONTE, que é
# exatamente a propriedade que a resolução do conflito travou.


class TestL1NewsletterUsaAMesmaListaDeBackends:
    def test_newsletter_importa_a_mesma_lista_e_nao_a_duplica(self):
        """A identidade é a garantia. `==` deixaria passar uma cópia igual
        hoje e divergente amanhã."""
        from newsletter import services as newsletter_services

        assert newsletter_services.BACKENDS_SEM_ENTREGA_REAL is BACKENDS_SEM_ENTREGA_REAL

    def test_newsletter_reexporta_as_mesmas_funcoes_de_entrega(self):
        """
        O `newsletter/services.py` importa da MESMA fonte nao so a lista,
        mas tambem as funcoes de entrega. A garantia que importa no caminho
        do dinheiro e a da ENTREGA: se `newsletter` passar a ter a sua
        propria `entregar_email`, o portao de "so conta como entrega se
        entregou de verdade" (P1-04) deixa de valer para a newsletter —
        e o bug volta a ser invisivel, porque `total_enviados` voltaria a
        contar entregas que foram so para um dicionario em memoria.
        """
        from newsletter import services as newsletter_services

        assert newsletter_services.entregar_email is entregar_email
        assert newsletter_services.verificar_canal_email is verificar_canal_email
        assert newsletter_services.registrar_evento is registrar_evento
        assert newsletter_services.orientacao_de_configuracao is orientacao_de_configuracao

    def test_o_predicado_do_newsletter_consulta_a_lista_por_identidade(self, settings):
        """
        Comportamento, não só identidade: o predicado
        `canal_entrega_real()` precisa ler a MESMA lista. Se alguém
        trocasse o predicado por um conjunto literal, os testes de
        identidade acima continuariam verdes e este reprovaria.
        """
        from newsletter import services as newsletter_services

        for backend in sorted(BACKENDS_SEM_ENTREGA_REAL):
            with override_settings(EMAIL_BACKEND=backend):
                assert newsletter_services.canal_entrega_real() is False, backend
        with override_settings(EMAIL_BACKEND=BACKEND_RESEND):
            assert newsletter_services.canal_entrega_real() is True

    def test_nenhum_dos_tres_modulos_de_fonte_une_redireciona_a_lista(self):
        """
        A lista não pode ser trocada em tempo de execução: se
        `newsletter.services.BACKENDS_SEM_ENTREGA_REAL` virar uma reatribuição
        depois do import, a identidade do teste acima quebra — mas só depois
        que alguém já estiver lendo o objeto trocado. Esta é a rede contra o
        `monkeypatch` de produção e o `settings` forjado.
        """
        from newsletter import services as newsletter_services

        assert newsletter_services.BACKENDS_SEM_ENTREGA_REAL is BACKENDS_SEM_ENTREGA_REAL
        # `contato` e `newsletter` resolvem o MESMO objeto entre si, sem
        # passar por `config` de novo: a identidade dos três.
        from contato import services as contato_services

        assert newsletter_services.BACKENDS_SEM_ENTREGA_REAL is contato_services.BACKENDS_SEM_ENTREGA_REAL


# ---------------------------------------------------------------------------
# Resend: sem credencial é "sem canal", não 500
# ---------------------------------------------------------------------------


class TestResendSemCredencial:
    def test_resend_sem_chave_e_recusado_com_motivo_legivel(self, settings):
        settings.EMAIL_BACKEND = BACKEND_RESEND
        settings.RESEND_API_KEY = ""

        canal = verificar_canal_email()

        assert canal.disponivel is False
        # O motivo nomeia a CONFIGURAÇÃO, nunca o valor da credencial.
        assert "RESEND_API_KEY" in "; ".join(canal.motivos)

    def test_resend_sem_chave_nao_estoura_500_e_nao_chega_a_200(self, settings):
        """`config/email_resend.py:29-33` levanta `ValueError` na construção do
        backend. Quem chama precisa transformar isso em recusa limpa, senão
        o endpoint responde 500 — que é o que o P0-02c registrou como
        "estoura um 500 dentro do send()"."""
        settings.EMAIL_BACKEND = BACKEND_RESEND
        settings.RESEND_API_KEY = ""

        with pytest.raises(CanalIndisponivel):
            entregar_email(_mensagem(), destino="verificacao")

        assert _valor_da_metrica("portal_email_entrega_total", destino="verificacao", situacao="sem_canal") == 1
        assert _valor_da_metrica("portal_email_entrega_total", destino="verificacao", situacao="entregue") == 0

    def test_resend_com_chave_passa_pelo_gate(self, settings):
        settings.EMAIL_BACKEND = BACKEND_RESEND
        settings.RESEND_API_KEY = "re_test_dummy"

        assert verificar_canal_email().disponivel is True


# ---------------------------------------------------------------------------
# A recusa acontece ANTES de o backend ser chamado
# ---------------------------------------------------------------------------


class TestRecusaAntesDoEnvio:
    def test_backend_sem_entrega_real_nao_e_nem_chamado(self, settings, monkeypatch):
        settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

        chamado = []
        monkeypatch.setattr(
            EntregaSimuladaBackend,
            "send_messages",
            lambda self, msgs: chamado.append(msgs) or 1,
        )
        # Mesmo substituting o caminho do setting, o gate lê `settings`.
        monkeypatch.setattr(
            "django.core.mail.backends.console.EmailBackend.send_messages",
            lambda self, msgs: chamado.append(msgs) or 1,
            raising=False,
        )

        with pytest.raises(CanalIndisponivel):
            entregar_email(_mensagem(), destino="cadastro")

        assert chamado == [], "o backend sem entrega real não pode ser chamado"

    def test_backend_console_nao_imprime_nada_no_stdout(self, settings, capsys):
        """A prova mais direta do furo do P0-02c, com o `console` de verdade.

        Sem o gate, `console.EmailBackend` escreveria o e-mail INTEIRO — com o
        token de verificação dentro — no stdout do container. Com o gate, o
        `capsys` abaixo tem que estar vazio.
        """
        settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

        with pytest.raises(CanalIndisponivel):
            entregar_email(_mensagem(), destino="verificacao")

        capturado = capsys.readouterr()
        assert SEGREDO not in capturado.out, "o token de verificação foi impresso no stdout"
        assert "Confirme seu e-mail" not in capturado.out
        assert capturado.out == "", f"o console backend imprimiu algo: {capturado.out!r}"

    def test_locmem_nao_e_chamado_e_nada_vai_para_o_outbox(self, settings):
        """`locmem` é o `EMAIL_BACKEND` que o `pytest-django` injeta. Sem o
        gate, `mail.outbox` enchia e todo teste de "e-mail enviado" passava
        medindo um buffer em memória."""
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        mail.outbox = []

        with pytest.raises(CanalIndisponivel):
            entregar_email(_mensagem(), destino="newsletter")

        assert mail.outbox == []


# ---------------------------------------------------------------------------
# A checagem PÓS-envio: o provedor aceitou e dropou
# ---------------------------------------------------------------------------


class TestProvedorQueNaoEntrega:
    def test_provedor_que_devolve_zero_e_falha_de_entrega(self, settings):
        settings.EMAIL_BACKEND = caminho_de(RecusaBackend)

        with pytest.raises(FalhaDeEntrega):
            entregar_email(_mensagem(), destino="redefinicao")

        assert _valor_da_metrica("portal_email_entrega_total", destino="redefinicao", situacao="falha") == 1
        assert _valor_da_metrica("portal_email_entrega_total", destino="redefinicao", situacao="entregue") == 0

    @pytest.mark.parametrize(
        "classe,tipo",
        [
            (ExplodindoBackend, "RuntimeError"),
            (ErroDeRedeBackend, "ConnectionError"),
        ],
    )
    def test_provedor_que_estoura_e_falha_de_entrega(self, settings, classe, tipo):
        settings.EMAIL_BACKEND = caminho_de(classe)

        with pytest.raises(FalhaDeEntrega):
            entregar_email(_mensagem(), destino="cadastro")

        assert _valor_da_metrica("portal_email_falha_provedor_total", destino="cadastro", tipo=tipo) == 1

    def test_500_do_provedor_nao_vaza_texto_que_pode_ter_o_token(self, settings, caplog):
        """O texto de erro de um provedor real pode ecoar o payload enviado — e
        o payload do e-mail de verificação CONTÉM o token de uso único. Por
        isso o log leva o TIPO da exceção, nunca `str(exc)`, e a exceção
        levada tem texto CONSTANTE."""
        settings.EMAIL_BACKEND = caminho_de(ExplodindoBackend)

        with caplog.at_level(logging.DEBUG), pytest.raises(FalhaDeEntrega) as info:
            entregar_email(_mensagem(), destino="verificacao")

        assert str(info.value) == MOTIVO_FALHA_GENERICO
        texto_do_log = "\n".join(r.getMessage() for r in caplog.records)
        assert SEGREDO not in texto_do_log
        assert "provedor fora do ar" not in texto_do_log, "o log copiou str(exc)"

    def test_falha_nao_e_enrolada_com_a_excecao_do_provedor(self, settings):
        """`raise ... from None`: o `__context__` continuaria sendo a exceção
        original, e um traceback de 500 mostraria o texto dela."""
        settings.EMAIL_BACKEND = caminho_de(ExplodindoBackend)

        with pytest.raises(FalhaDeEntrega) as info:
            entregar_email(_mensagem(), destino="cadastro")

        assert info.value.__cause__ is None
        assert info.value.__suppress_context__ is True


# ---------------------------------------------------------------------------
# O caminho feliz, e o contador que não pode mentir
# ---------------------------------------------------------------------------


class TestCaminhoFeliz:
    def test_provedor_que_aceita_conta_uma_entrega(self, settings):
        settings.EMAIL_BACKEND = BACKEND_QUE_ENTREGA
        EntregaSimuladaBackend.entregues.clear()

        enviados = entregar_email(_mensagem(), destino="verificacao")

        assert enviados == 1
        assert len(EntregaSimuladaBackend.entregues) == 1
        assert _valor_da_metrica("portal_email_entrega_total", destino="verificacao", situacao="entregue") == 1

    def test_metrica_conta_uma_entrega_por_mensagem_e_nao_por_envio(self, settings):
        """Uma chamada de `entregar_email` é UMA mensagem. A contagem é por
        entrega, não por chamada — é o que faz `total_enviados` da newsletter
        significar " quantas pessoas receberam", e não "quantas vezes o
        código rodou"."""
        settings.EMAIL_BACKEND = BACKEND_QUE_ENTREGA
        EntregaSimuladaBackend.entregues.clear()

        assert entregar_email(_mensagem(), destino="newsletter") == 1
        assert (
            _valor_da_metrica("portal_email_entrega_total", destino="newsletter", situacao="entregue")
            == 1
        )

    def test_metrica_nao_carrega_endereco_nem_corpo(self, settings):
        """O rótulo é de fluxo (`cadastro`, `verificacao`, `newsletter`...) e
        o valor é um desfecho. Se um endereço ou o corpo do e-mail entrasse
        no rótulo, a métrica viraria um log com PII — e viraria também um
        oráculo de existência de conta para quem lesse `/metrics`."""
        settings.EMAIL_BACKEND = caminho_de(RecusaBackend)

        with pytest.raises(FalhaDeEntrega):
            entregar_email(_mensagem(), destino="cadastro")

        renderizado = METRICAS.render()
        assert "leitor@example.com" not in renderizado
        assert SEGREDO not in renderizado
        assert 'destino="cadastro"' in renderizado
