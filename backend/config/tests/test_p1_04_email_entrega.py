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

import ast
import logging
from pathlib import Path

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


# ===========================================================================
# LACUNA L2 — A GARANTIA É ESTRUTURAL, E NÃO POR BOA VONTADE
# ===========================================================================
# POR QUE ESTE BLOCO EXISTE
# ========================
# O gate acima é perfeito e mesmo assim o `b2b/services.py` ficou anos
# chamando `django.core.mail.send_mail` direto, e a suíte inteira ficava
# verde. Nenhum teste comportamental pega isso: cada módulo tem os seus
# testes, e cada um deles passa — o `b2b` só **contava** uma entrega que não
# acontecia, o que é invisível de dentro do próprio módulo.
#
# Quem achou o `b2b` foi quem revisou, não quem escreveu o módulo. Isso é a
# definição de uma garantia que depende de boa vontade: ela vale até alguém
# escrever o próximo `send_mail`.
#
# O que este bloco trava é a **ESTRUTURA**: no código de produção, fora de
# `config/email_entrega.py`, NENHUM módulo pode obter a posse de uma mensagem
# que sai do processo por um caminho que não seja `entregar_email`. Ele é o
# que o `contato` ganhou do P0-02c e que faltava para os outros três módulos.
#
# O QUE É PROIBIDO, E POR QUE CADA REGRA
# ======================================
# 1. **Importar o transporte de `django.core.mail`.** `send_mail`,
#    `send_mass_mail`, `mail_admins`, `mail_managers` e `get_connection` são
#    atalhos que pulam a checagem de canal e a de pós-envio. `EmailMessage`
#    NÃO está na lista: ele é o *envelope*, não o *transporte* — construí-lo
#    é obrigatório, porque `entregar_email` recebe um.
# 2. **Chamar o transporte por qualquer receptor.** `mail.send_mail(...)`,
#    `django.core.mail.send_mail(...)`, `services.get_connection()`. A
#    assinatura é a mesma em todos, então a regra olha o NOME da chamada, não
#    a origem do objeto.
# 3. **Chamar `.send()` com `fail_silently`.** É a assinatura exata de
#    `EmailMessage.send()`, e o `fail_silently=True` é justamente o
#    mecanismo que transforma falha de entrega em sucesso silencioso — o
#    defeito que `entregar_email` existe para matar. É o dublê exato que
#    `config/egress.py:537` (`super().send(request, **kwargs)`) NÃO dispara,
#    porque `requests` não tem essa palavra-chave.
# 4. **Definir uma costureira `send_mail` que não seja um repasse.** O
#    `newsletter/services.py:298` define uma função chamada `send_mail` — e
#    isso é legítimo, é a costura de transporte daquele app, Testada por
#    identidade em `TestL1NewsletterUsaAMesmaListaDeBackends`. Mas a
#    autorização precisa ser **verificada**, não presumida: a função tem que
#    chamar `entregar_email` no corpo. Se alguém reescrever a costura para
#    fazer o que quiser, a regra 4 reprova.

#: O único módulo autorizado a falar com o transporte. `config/email_resend.py`
#: também é transporte — ele É o provedor, implementa `send_messages` e é
#: chamado pelo Django, não por um fluxo de negócio. Nenhum dos dois é um
#: "contorno": são as duas pontas legítimas do caminho.
MODULOS_COM_TRANSPORTE = frozenset(
    {
        Path("config") / "email_entrega.py",
        Path("config") / "email_resend.py",
    }
)

#: `django.core` é amplo demais para casar por prefixo de string
#: (`django.core.files`, `django.core.signing`...), então o módulo importado é
#: comparado por nome de tuple.
APP_EMAIL = "django.core.mail"
APP_CORE = "django.core"

#: Atalhos de transporte do Django. `EmailMessage` e `EmailMultiAlternatives`
#: NÃO estão aqui: são classes de envelope, não funções que entregam.
TRANSPORTE_PROIBIDO = frozenset(
    {"send_mail", "send_mass_mail", "mail_admins", "mail_managers", "get_connection"}
)

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _modulos_de_producao():
    """Todo `.py` de produção do backend, menos o que não roda em produção."""
    for caminho in sorted(BACKEND_DIR.rglob("*.py")):
        partes = set(caminho.relative_to(BACKEND_DIR).parts)
        if partes & {"migrations", "tests", "__pycache__", "management"}:
            continue
        yield caminho


def _arvore(caminho: Path):
    # `utf-8-sig`: alguns módulos versionados começam com BOM (ex.:
    # `painel_admin/__init__.py`) e `ast.parse` rejeita U+FEFF.
    return ast.parse(caminho.read_text(encoding="utf-8-sig"))


def _chamadas(no):
    """Todo `ast.Call` da árvore."""
    return (n for n in ast.walk(no) if isinstance(n, ast.Call))


def _nome_da_chamada(chamada: ast.Call) -> str | None:
    """O nome do callable, venha de `Nome` (`send_mail(...)`) ou de
    `Atributo` (`mail.send_mail(...)`)."""
    func = chamada.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _infracoes_do_modulo(arvore: ast.AST) -> list[str]:
    """As infrações de UM módulo. Função pura: recebe a árvore, devolve a lista.

    Ela é pura de propósito. Uma varredura que só existe embutida no teste que
    a roda não pode ser testada sozinha — e uma varredura não testada é uma
    varredura que pode estar olhando para o vazio sem ninguém perceber. O
    "o sensor funciona?" é `TestASensorDaVarreduraEnxerga`, abaixo.
    """
    infracoes: list[str] = []

    # `def` do próprio módulo — as costuras locais, que a regra 4 julga.
    defs_locais = {
        no.name for no in ast.walk(arvore) if isinstance(no, ast.FunctionDef)
    }

    # Regra 1 — o import do transporte.
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and no.module == APP_EMAIL:
            for alias in no.names:
                if alias.name in TRANSPORTE_PROIBIDO:
                    infracoes.append(
                        f"linha {no.lineno} importa {alias.name} de {APP_EMAIL}"
                    )
        # `from django.core import mail` — o módulo inteiro, que dá acesso a
        # `mail.send_mail` e `mail.get_connection` sem nome qualificado.
        if isinstance(no, ast.ImportFrom) and no.module == APP_CORE:
            for alias in no.names:
                if alias.name == "mail":
                    infracoes.append(f"linha {no.lineno} importa `mail` de {APP_CORE}")

    # Regras 2 e 3 — as chamadas.
    #
    # A distinção que resolve o único falso positivo legítimo do projeto: uma
    # chamada a `send_mail` como NOME SOLTO (`send_mail(...)`) só é
    # admissível se o próprio módulo DEFINE essa função — porque aí não é o
    # transporte do Django, é a costura local do app (que a regra 4 verifica
    # ser um repasse ao gate). Uma chamada como ATRIBUTO
    # (`mail.send_mail(...)`, `django.core.mail.send_mail(...)`) é sempre
    # infração: não existe como ela ser a costura local.
    for chamada in _chamadas(arvore):
        nome = _nome_da_chamada(chamada)
        if nome in TRANSPORTE_PROIBIDO:
            e_costura_local = isinstance(chamada.func, ast.Name) and nome in defs_locais
            if not e_costura_local:
                infracoes.append(f"linha {chamada.lineno} chama {nome}()")
        if nome == "send" and any(kw.arg == "fail_silently" for kw in chamada.keywords):
            infracoes.append(
                f"linha {chamada.lineno} chama .send(fail_silently=...) — é a "
                "assinatura de EmailMessage.send() e o que engole falha de entrega"
            )
    return infracoes


def _costuras_que_nao_repassam(arvore: ast.AST) -> list[str]:
    """Regra 4: `def send_mail` que não chama `entregar_email` no corpo."""
    infracoes = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.FunctionDef) or no.name != "send_mail":
            continue
        repasse = any(
            isinstance(interno, ast.Name) and interno.id == "entregar_email"
            for interno in ast.walk(no)
        )
        if not repasse:
            infracoes.append(
                f"linha {no.lineno} define `send_mail` sem chamar `entregar_email` "
                "— ou não é uma costura, ou é um contorno"
            )
    return infracoes


class TestNenhumModuloContornaOGateDeEmail:
    """A varredura de código de produção. Ver o docstring do bloco acima."""

    def test_nenhum_modulo_de_producao_chama_o_transporte_fora_do_gate(self):
        """
        Falha se qualquer módulo de produção — FORA de `config/email_entrega.py`
        e `config/email_resend.py` — tocar o transporte de e-mail do Django.

        Esta é a regra que teria reprovado o `b2b/services.py` da base
        `623a0e9` no mesmo dia em que ele foi escrito.
        """
        infracoes = []
        for caminho in _modulos_de_producao():
            where = caminho.relative_to(BACKEND_DIR)
            if where in MODULOS_COM_TRANSPORTE:
                continue
            infracoes += [f"{where}: {i}" for i in _infracoes_do_modulo(_arvore(caminho))]

        assert infracoes == [], (
            "módulos de produção contornando `config.email_entrega`:\n  "
            + "\n  ".join(infracoes)
            + "\n\nEntregar e-mail por fora do gate é o furo do P0-02c: com "
            "`EMAIL_BACKEND=console` o código responde que entregou e imprimeu "
            "num stdout que ninguém lê. Passe por "
            "`config.email_entrega.entregar_email`."
        )

    def test_toda_costureira_send_mail_local_e_um_repasso_ao_gate(self):
        """
        Regra 4. Um módulo pode DEFINIR uma função chamada `send_mail` — o
        `newsletter/services.py:298` faz isso, e é legítimo, porque ela é a
        costura de transporte daquele app.

        O que não é legítimo é a função não ser um repasse. Se alguém
        reescrever a costura para imprimir, engole a exceção ou chamar o
        Django direto, a função deixa de ser uma costura e vira um contorno
        com um nome que engana a leitura.
        """
        infracoes = []
        for caminho in _modulos_de_producao():
            where = caminho.relative_to(BACKEND_DIR)
            if where in MODULOS_COM_TRANSPORTE:
                continue
            infracoes += [
                f"{where}: {i}" for i in _costuras_que_nao_repassam(_arvore(caminho))
            ]

        assert infracoes == [], (
            "costuras `send_mail` que não repassam ao gate:\n  " + "\n  ".join(infracoes)
        )

    def test_a_costura_do_newsletter_e_reconhecida_como_costura(self):
        """
        O contra-teste da resolução do falso positivo: a costura do `newsletter`
        passa, e a identidade dela com o gate continua provada por
        `TestL1NewsletterUsaAMesmaListaDeBackends`. Uma regra estrutural que
        obrigasse o `newsletter` a duplicar `entregar_email` seria uma regra
        que empurraria o código para fora do gate, não para dentro dele.
        """
        from newsletter import services as newsletter_services

        arvore = ast.parse(Path(newsletter_services.__file__).read_text(encoding="utf-8"))
        assert _infracoes_do_modulo(arvore) == [], (
            "a costura `send_mail` do newsletter foi confundida com o transporte "
            "do Django"
        )
        assert _costuras_que_nao_repassam(arvore) == []

    def test_a_varredura_enxerga_o_b2b_na_base(self):
        """
        A varredura NÃO pode estar vazia por acidente.

        Este teste a exercita com o que a base `623a0e9` realmente tinha em
        `b2b/services.py` — o import e a chamada — e afirma que a regra marca.
        Sem isto, uma refatoração que quebrasse a regra (trocar `ast.Call` por
        outra coisa, ampliar a exceção, errar o `parents`, casar o nome errado)
        deixaria a varredura aprovando o vazio e ela continuaria verde. Um
        alarme que não testa o próprio sensor não é alarme.
        """
        # O `b2b` da base, literal.
        infracoes = _infracoes_do_modulo(
            ast.parse(
                "from django.core.mail import send_mail\n"
                "\n"
                "def alerta(criterio, itens, destinatarios):\n"
                "    send_mail(subject='x', message='y', from_email='a@b.c',\n"
                "               recipient_list=destinatarios, fail_silently=False)\n"
            )
        )
        assert len(infracoes) == 2, infracoes
        assert any("importa send_mail" in i for i in infracoes)
        assert any("chama send_mail()" in i for i in infracoes)

    @pytest.mark.parametrize(
        "fonte,trecho_que_deve_ser_marcado",
        [
            # Cada uma das quatro regras, com a fonte mínima que a dispara.
            (
                "from django.core.mail import get_connection\n",
                "importa get_connection",
            ),
            (
                "from django.core.mail import mail_admins\n",
                "importa mail_admins",
            ),
            (
                "from django.core import mail\n",
                "importa `mail`",
            ),
            (
                "import django.core.mail\ndjango.core.mail.send_mail( subject='a')\n",
                "chama send_mail()",
            ),
            (
                "from django.core import mail\nmail.send_mail(subject='a')\n",
                "chama send_mail()",
            ),
            # O alias não escapa: a REGRA 1 pega no import, que é onde o nome
            # original ainda está. É por isso que a regra 1 existe separada da
            # regra 2 — `import send_mail as _sm` chama `_sm()` e a regra 2,
            # que olha o nome da chamada, não veria nada.
            (
                "from django.core.mail import send_mail as _sm\n_sm(subject='a')\n",
                "importa send_mail",
            ),
            (
                "conexao = get_connection()\n",
                "chama get_connection()",
            ),
            # A regra 3, com a assinatura exata de `EmailMessage.send()`.
            (
                "mensagem.send(fail_silently=False)\n",
                ".send(fail_silently=...)",
            ),
            (
                "EmailMessage(...).send(fail_silently=True)\n",
                ".send(fail_silently=...)",
            ),
        ],
    )
    def test_cada_regra_dispara_no_escopo_delegado(self, fonte, trecho_que_deve_ser_marcado):
        """Uma regra por linha, e cada uma com o seu caso."""
        infracoes = _infracoes_do_modulo(ast.parse(fonte))
        assert any(trecho_que_deve_ser_marcado in i for i in infracoes), (
            f"a regra parou de enxergar: {fonte!r} produziu {infracoes!r}"
        )

    @pytest.mark.parametrize(
        "fonte",
        [
            # `config/egress.py:537` — `requests`, que NÃO tem `fail_silently`.
            "def send(self, request, **kwargs):\n    return super().send(request, **kwargs)\n",
            # A costura legítima do newsletter: `def` local que repasssa.
            "from config.email_entrega import entregar_email\n"
            "def send_mail(*, subject, message, from_email, recipient_list):\n"
            "    return entregar_email(montar(), destino='newsletter')\n"
            "def enviar():\n"
            "    send_mail(subject='a', message='b', from_email='c', recipient_list=[])\n",
            # O caminho felix: constrói o envelope e entrega pelo gate.
            "from django.core.mail import EmailMessage\n"
            "from config.email_entrega import entregar_email\n"
            "def enviar(destinatarios):\n"
            "    return entregar_email(EmailMessage(subject='a', body='b',\n"
            "        from_email='c', to=destinatarios), destino='b2b_alerta')\n",
        ],
    )
    def test_o_que_e_legitimo_nao_e_marcado(self, fonte):
        """
        O contra-teste, e ele vale tanto quanto o anterior.

        Uma regra que reprova o caminho correto empurra o código para fora do
        gate — e o sintoma disso é pior que o bug original: um módulo que
        precisa contornar a regra para funcionar. `EmailMessage` (envelope),
        a costura local que repasssa e a chamada a `entregar_email` têm que
        passar.
        """
        assert _infracoes_do_modulo(ast.parse(fonte)) == []
        assert _costuras_que_nao_repassam(ast.parse(fonte)) == []

    def test_uma_costura_que_deixa_de_repassar_e_marcada(self):
        """
        O outro lado da regra 4: a costura que para de ser costura.

        Este é o contorno "de boa-fé" — alguém reescreve a costura do
        newsletter para tratar a exceção e devolver 0, e o nome `send_mail`
        continua fazendo o código parecer em conformidade. A regra 4 pega
        porque olha o CORPO da função, não o nome.
        """
        fonte = (
            "from django.core.mail import get_connection\n"
            "def send_mail(*, subject, message, from_email, recipient_list):\n"
            "    conexao = get_connection()\n"
            "    return conexao.send_messages([])\n"
        )
        assert _costuras_que_nao_repassam(ast.parse(fonte)), (
            "uma `def send_mail` que não chama `entregar_email` precisa ser marcada"
        )
        assert _infracoes_do_modulo(ast.parse(fonte)), (
            "e o transporte que ela usa também precisa ser marcado"
        )

    def test_o_gate_e_o_resend_sao_os_unicos_com_transporte(self):
        """A lista de autorização é explícita e mínima. Ela crescer é decisão,
        não consequência."""
        assert MODULOS_COM_TRANSPORTE == {
            Path("config") / "email_entrega.py",
            Path("config") / "email_resend.py",
        }
        for relativo in MODULOS_COM_TRANSPORTE:
            assert (BACKEND_DIR / relativo).exists(), relativo

    def test_a_varredura_esta_de_fato_olhando_para_o_projeto(self):
        """
        O sensor não pode estar apontando para o nada.

        Um `BACKEND_DIR` errado (por exemplo, `parents[3]`, que é a raiz do
        repositório e não tem nenhum `.py` de produção) faria a varredura
        encontrar zero arquivos e passar. Este teste conta os módulos que ela
        vê e exige que sejam os apps reais.
        """
        vistos = {c.relative_to(BACKEND_DIR).parts[0] for c in _modulos_de_producao()}
        for app in ("b2b", "contato", "identidade", "newsletter", "config"):
            assert app in vistos, f"a varredura não enxergou o app `{app}`"
        # E nenhum arquivo de teste entrou na contagem.
        assert not any("tests" in p.parts for p in _modulos_de_producao())
