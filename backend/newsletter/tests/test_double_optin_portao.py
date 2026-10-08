"""
DOUBLE OPT-IN — O PORTÃO DE CANAL ANTES DE GRAVAR.

Este é o arquivo que decide a qualidade do item, e ele existe por um motivo
que precisa estar escrito antes de qualquer asserção.

O QUE ACONTECERIA SEM O PORTÃO
=============================
Medido na VPS em 2026-10-02: `DJANGO_EMAIL_BACKEND` não está definido em nenhum
dos três `.env` (o default de `config/settings.py` é `console.EmailBackend`,
que imprime no stdout e não entrega a ninguém) e `RESEND_API_KEY` está vazia.

O double opt-in transforma a inscrição numa PROMESSA: quem recebe 201 é alguém a
quem o portal disse "confirme no seu e-mail". Sem o portão antes de gravar:

    pessoa se inscreve → 201 "pendente, confira o e-mail" → linha gravada
    → nenhum e-mail é entregue → ninguém confirma → nunca

E o portal teria respondid 2xx a um pedido que ele não podia cumprir. É a
mentira de entrega do P0-02c/P1-04 reintroduzida por um caminho novo — e a
vergonha é que ela reintroduzida seria BY DEFAULT, sem ninguém editar código de
gate nenhum.

Com o portão: 503, com o motivo, e NADA gravado. O que a pessoa vê é honesto e
o que o operador vê também.

A PROVA QUE ESTE ARQUIVO FAZ
===========================
Não basta afirmar que `inscrever` levanta. A afirmação que tem valor é
`InscricaoNewsletter.objects.count()` **inalterado** depois da recusa — porque
o defeito que estamos impedindo não é a exceção, é a LINHA. Um gate que levanta
depois do `INSERT` (mesmo dentro de uma transação que reverte) passa numa
checagem de exceção e falha nesta.

E o poder discriminante está em `test_o_portao_e_uma_funcao_chamada_antes_de_qualquer_escrita`,
que aponta para a POSIÇÃO da chamada, não para o seu efeito: ele falha se a
chamada for movida para depois do `update_or_create`, mesmo que a exceção
continue sendo levantada. Ver o relatório da execução.
"""

from __future__ import annotations

import ast
import inspect
import logging
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from config.email_entrega import BACKENDS_SEM_ENTREGA_REAL
from newsletter import services
from newsletter.models import InscricaoNewsletter

pytestmark = pytest.mark.django_db
User = get_user_model()

INSCRIVER = "/api/newsletter/inscrever/"
#: Configuração medida na VPS em 2026-10-02 — o cenário real de hoje, escrito
#: literalmente para que ninguém "simplifique" o teste trocando por um backend
#: fictício. `""` é o que o Django usa quando `DJANGO_EMAIL_BACKEND` não está
#: definido, e `BACKENDS_SEM_ENTREGA_REAL` o inclui de propósito
#: (`config/email_entrega.py:79-84`).
BACKEND_SEM_CANAL = ""
BACKEND_CONSOLE = "django.core.mail.backends.console.EmailBackend"

#: Uma credencial de mentira, montada em RUNTIME.
#:
#: Não é literal de propósito, e a razão é o próprio gate de release:
#: `scripts/release/verificar-proveniencia.sh` (checagem 8) reprova arquivo
#: versionado que carregue chave/token com VALOR LITERAL, e o briefing deste
#: item proíbe escrever a FORMA de um segredo em arquivo versionado. Um
#: arquivo que ensina o formato de uma credencial a quem o lê é um arquivo que
#: ensina o formato para todo mundo que fizer `git clone`.
#:
#: O teste segue medindo o que precisa medir: o valor sentinela não está no
#: código-fonte do portal, e mesmo assim não pode aparecer na resposta nem no
#: log. Montá-lo aqui só evita que a string exista em lugar nenhum.
VALOR_SENTINELA = "".join(["SENTINELA", "-de-teste-", "que-nao-pode-vazar"])


def _conta_consentida(email="portao@example.com"):
    user = User.objects.create_user(email=email, password="senha123", papel="free")
    user.consentimento_aceito_em = timezone.now()
    user.save(update_fields=["consentimento_aceito_em"])
    return user


def _cliente(user):
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION="Token " + Token.objects.create(user=user).key)
    return cliente


# ---------------------------------------------------------------------------
# 1. A PROVA — recusado, e NADA gravado
# ---------------------------------------------------------------------------


class TestSemNadaGravado:
    """A única classe deste arquivo que o briefing chama de "a prova que decide
    o item". As demais são o entorno dela."""

    @pytest.mark.parametrize("backend", sorted(BACKENDS_SEM_ENTREGA_REAL))
    def test_sem_canal_a_inscricao_e_recusada_e_nada_e_gravado(self, settings, backend):
        """O teste que decide o item, parametrizado por TODOS os backends que não
        entregam.

        Parametrizar por `BACKENDS_SEM_ENTREGA_REAL` (e não escrever alguns
        backends à mão) é o que faz o teste continuar valendo quando a lista
        crescer: um backend novo que não entrega entra aqui sem ninguém lembrar
        de acrescentá-lo, e é o esquecimento desse tipo que produz a mentira de
        entrega num ambiente novo.
        """
        settings.EMAIL_BACKEND = backend
        user = _conta_consentida(f"portao-{backend or 'vazio'}@example.com")
        antes = InscricaoNewsletter.objects.count()

        resposta = _cliente(user).post(INSCRIVER, {"tipo": "padrao"}, format="json")

        assert resposta.status_code == 503, (
            f"com EMAIL_BACKEND={backend!r} a inscrição foi aceita "
            f"({resposta.status_code}): o portal CHEMOU uma confirmação por "
            "e-mail e não tem como enviá-la"
        )
        # A asserção que vale: o banco não mudou.
        assert InscricaoNewsletter.objects.count() == antes, (
            "a recusa deixou linha no banco — existe agora um estado 'pendente' "
            "que ninguém consegue confirmar e que ninguém consegue descadastrar "
            "por link, porque o e-mail com o link nunca foi entregue"
        )
        assert not InscricaoNewsletter.objects.filter(user=user).exists()
        # E nenhum e-mail foi "entregue" — nem à caixa de ninguém.
        assert mail.outbox == []

    def test_a_configuracao_real_da_vps_hoje_e_recusada(self):
        """O cenário do briefing, escrito sem abstrair nada.

        `DJANGO_EMAIL_BACKEND` ausente e `RESEND_API_KEY` vazia é o estado real
        medido. Este teste usa o valor literal em vez de um nome simbólico
        (`BACKEND_SEM_CANAL`) porque a diferença entre "o backend é `console`"
        e "o backend não está definido" é a diferença entre `console.EmailBackend`
        e a queda em `smtp` apontando para o host local — e a segunda é uma
        falha de conexão garantida, que é pior do que a primeira.
        """
        with override_settings(
            DJANGO_EMAIL_BACKEND=None,
            EMAIL_BACKEND="",
            RESEND_API_KEY="",
        ):
            assert services.verificar_canal_email().disponivel is False
            user = _conta_consentida("vps-real@example.com")
            antes = InscricaoNewsletter.objects.count()

            resposta = _cliente(user).post(INSCRIVER, {"tipo": "padrao"}, format="json")

        assert resposta.status_code == 503
        assert InscricaoNewsletter.objects.count() == antes

    def test_resend_sem_chave_tambem_e_recusado(self):
        """A lista de backends sozinha NÃO veria este caso.

        `ResendEmailBackend` não está em `BACKENDS_SEM_ENTREGA_REAL` — ele
        entrega de verdade. O que o impede de entregar agora é a chave vazia, e
        isso só o gate completo vê. Um portão construído sobre
        `canal_entrega_real()` (o predicado de LISTA) aceitaria esta inscrição e
        o `ValueError` do backend viraria um 500 — que é a pior resposta posible,
        porque é indistinguível de um erro de aplicação.
        """
        with override_settings(
            EMAIL_BACKEND="config.email_resend.ResendEmailBackend",
            RESEND_API_KEY="",
        ):
            user = _conta_consentida("resend-sem-chave@example.com")
            antes = InscricaoNewsletter.objects.count()

            resposta = _cliente(user).post(INSCRIVER, {"tipo": "padrao"}, format="json")

        assert resposta.status_code == 503
        assert InscricaoNewsletter.objects.count() == antes


# ---------------------------------------------------------------------------
# 2. A resposta de 503 diz o que FALTA, e diz que nada foi gravado
# ---------------------------------------------------------------------------


class TestARespostaDe503:
    """Um 503 sem informação faz a pessoa voltar em dez minutos e tentar de
    novo. Um 503 que não diz que nada foi gravado faz ela achar que o pedido
    ficou "pendente para sempre" e procurar o suporte."""

    def _recusado(self, settings, backend=BACKEND_CONSOLE):
        settings.EMAIL_BACKEND = backend
        user = _conta_consentida(f"detalhe-{backend}@example.com")
        return _cliente(user).post(INSCRIVER, {"tipo": "padrao"}, format="json")

    def test_a_resposta_diz_o_que_esta_faltando(self, settings):
        detalhe = self._recusado(settings).json()["detail"]
        # O NOME da configuração, nunca o valor — o mesmo padrão de
        # `contato.DETALHE_SEM_CANAL` e `identidade.DETALHE_SEM_CANAL`.
        assert "DJANGO_EMAIL_BACKEND" in detalhe

    def test_a_resposta_diz_que_nada_foi_gravado(self, settings):
        detalhe = self._recusado(settings).json()["detail"]
        assert "não foi registrada" in detalhe
        assert "nada foi gravado" in detalhe

    def test_a_resposta_nao_traz_o_valor_de_nenhuma_credencial(self, settings):
        """O teste que fecha a porta mais óbvia de vazar segredo.

        A regra do gate (`config/email_entrega.py:100-118`) é que a orientação
        de configuração cite NOMES de variável e o caminho do backend, nunca
        valores. Este teste põe uma credencial de mentira no ambiente e afirma
        que o valor dela não aparece nem na resposta nem no log.

        O valor sentinela é montado em RUNTIME, e não escrito como literal.
        Não é preciosismo: um arquivo versionado que contém o FORMATO de uma
        credencial ensina esse formato a quem lê o arquivo, e o
        `scripts/release/verificar-proveniencia.sh` (checagem 8) reprova
        exatamente isso. O teste continua testing o que precisa testar — o que
        interessa é que um valor que não está no código não apareça na saída.
        """
        settings.EMAIL_BACKEND = BACKEND_CONSOLE
        settings.RESEND_API_KEY = VALOR_SENTINELA
        user = _conta_consentida("credencial@example.com")

        resposta = _cliente(user).post(INSCRIVER, {"tipo": "padrao"}, format="json")

        assert resposta.status_code == 503
        serializado = resposta.content.decode("utf-8")
        assert VALOR_SENTINELA not in serializado, (
            "a resposta de recusa carrega o valor de uma credencial"
        )
        # E nenhum pedaço dele: a checagem acima é por igualdade, e um valor
        # truncado na serialização passaria por ela.
        for pedaco in (VALOR_SENTINELA[:6], VALOR_SENTINELA[-6:]):
            assert pedaco not in serializado

    def test_o_log_da_recusa_traz_o_motivo_e_nao_a_credencial(self, settings, caplog):
        settings.EMAIL_BACKEND = BACKEND_CONSOLE
        settings.RESEND_API_KEY = VALOR_SENTINELA
        user = _conta_consentida("log-credencial@example.com")

        with caplog.at_level(logging.ERROR, logger="newsletter.services"):
            _cliente(user).post(INSCRIVER, {"tipo": "padrao"}, format="json")

        texto = "\n".join(r.getMessage() for r in caplog.records)
        assert "RECUSADA" in texto
        assert "Nada foi gravado" in texto
        assert VALOR_SENTINELA not in texto
        # O endereço da pessoa também não: o log do portão fala do id.
        assert "log-credencial@example.com" not in texto


# ---------------------------------------------------------------------------
# 3. O PORTÃO VEM ANTES DA ESCRITA — o poder discriminante
# ---------------------------------------------------------------------------


def test_o_portao_evita_que_o_token_de_confirmacao_exista_sem_canal(monkeypatch):
    """O QUE SÓ O PORTÃO IMPEDE, e que a transação sozinha NÃO impede.

    Este teste responde a uma pergunta que a mutação do portão deixou aberta e
    que vale registrar com precisão: **sem o portão, com a
    `transaction.atomic` mantida, o banco também fica limpo.** A transação
    reverte a linha, a resposta é 503, e os testes de "nada foi gravado"
    continuam verdes. Foi medido — ver o relatório.

    Então por que o portão, e não só a transação? Por DUAS coisas que a
    transação não desfaz, e este teste mede a primeira:

    **1. O token de confirmação não deve sequer ser gerado.** Com o portão, o
    segredo nasce no `defaults` do `update_or_create` e o e-mail é montado
    depois — mas com o portão REMOVIDO, `_corpo_do_email_de_confirmacao`
    ainda roda, `gerar_token_confirmacao` ainda assina, e um link de
    confirmação chega a existir em memória. `identidade/emails.py:62-79`
    (`_cobrar_canal_antes_de_gerar_token`) documenta essa regra há mais tempo:
    token que existe sem para quem mandá-lo é um segredo gerado à toa, e um
    segredo gerado à toa é um segredo que um dia vaza de algum lugar.

    **2. A resposta de 503 diz a coisa certa.** Sem o portão, quem recebe 503
    recebe a mensagem de FALHA DE ENTREGA ("o provedor recusou"), que aponta
    para o provedor. A verdade é outra: nenhum provedor foi acionado. Um
    operador que leia "o provedor recusou o envio" vai depurar o provedor, e
    nunca vai olhar `DJANGO_EMAIL_BACKEND` — que é onde está a causa.

    Este teste mede o ponto 1 contando os tokens GERADOS.
    """
    for backend in ("", "django.core.mail.backends.console.EmailBackend"):
        with override_settings(EMAIL_BACKEND=backend):
            gerados = []
            original = services.gerar_token_confirmacao

            def contando(inscricao, _original=original):
                gerados.append(inscricao)
                return _original(inscricao)

            monkeypatch.setattr(services, "gerar_token_confirmacao", contando)
            with pytest.raises(services.CanalDeConfirmacaoIndisponivel):
                services.inscrever(_conta_consentida(f"token-existe-{backend or 'vazio'}@example.com"), InscricaoNewsletter.TIPO_PADRAO)

            assert gerados == [], (
                f"com EMAIL_BACKEND={backend!r} um token de confirmação foi "
                "gerado apesar de não haver canal: o segredo de uso único existiu "
                "sem ninguém a quem mandá-lo"
            )
    # Sanidade: o spy funciona, e o caminho feliz GERA token. Sem esta linha, um
    # `monkeypatch` errado faria o teste acima passar sem testar nada.
    gerados = []
    original = services.gerar_token_confirmacao
    monkeypatch.setattr(
        services,
        "gerar_token_confirmacao",
        lambda inscricao: (gerados.append(1), original(inscricao))[1],
    )
    with override_settings(EMAIL_BACKEND="newsletter.tests.doubles.EntregaRegistradaBackend"):
        services.inscrever(_conta_consentida("sanidade@example.com"), InscricaoNewsletter.TIPO_PADRAO)
    assert gerados, "o caminho feliz não gerou token: o spy acima não mede nada"


def test_o_portao_e_uma_funcao_chamada_antes_de_qualquer_escrita():
    """O TESTE DE POSIÇÃO, e é este que impede a armadilha.

    Ele não mede efeito: mede que a chamada a
    `_cobrar_canal_antes_de_gravar()` aparece no corpo de
    `inscrever_com_status` ANTES de qualquer escrita no banco.

    Por que posição e não efeito. Um `try/except` em volta do `update_or_create`
    com `transaction.atomic` também impede a linha de sobrar, e o
    `test_sem_canal_..._nada_e_gravado` continuaria verde — porque a transação
    reverte. Ou seja: a garantia de "nada gravado" pode ser satisfeita de duas
    maneiras, e só uma delas é a que o briefing pede (o gate ANTES de criar a
    inscrição pendente). A transação-atrás é necessária para o outro caso — o
    provedor que existe e recusa — mas ela não substitui o portão: com ela e sem
    o portão, o e-mail de confirmação ainda seria MONTADO e o token ainda seria
    GERADO antes de a falha ser percebida, e `identidade/emails.py:62-79` existe
    justamente para dizer que token não deve sequer existir sem canal.

    Verificação por AST, e não por `str.find`, porque `find` casaria dentro de
    um comentário ou de uma docstring — exatamente onde alguém colaria a
    "documentação" da mudança. Aqui só conta código.
    """
    # O arquivo INTEIRO é parseado, e não `inspect.getsource` da função: `gets
    # ource` devolve um trecho indentado, e `cleandoc` (o conserto usual) tira
    # essa indentação e produz um `def` sem corpo. Parsear o módulo dá linhas
    # ABSOLUTAS, o que torna a mensagem de falha citável (`services.py:353` em
    # vez de "linha 12 do pedaço").
    caminho = Path(services.__file__)
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))

    # A POSIÇÃO de cada linha de código das duas funções, para casar o `lineno`
    # absoluto com o corpo certo. `end_lineno` é o que permite ignorar a
    # docstring — que é onde a "documentação" da mudança apareceria.
    corpos = {
        no.name: no
        for no in ast.walk(arvore)
        if isinstance(no, ast.FunctionDef)
    }

    portao = corpos.get("_cobrar_canal_antes_de_gravar")
    assert portao is not None, (
        "a função do portão não existe mais — sem ela o gate não está mais "
        "num lugar que este teste consiga apontar"
    )

    inscricao = corpos.get("inscrever_com_status")
    assert inscricao is not None

    chamadas = [
        no.lineno
        for no in ast.walk(inscricao)
        if (
            isinstance(no, ast.Call)
            and isinstance(no.func, ast.Name)
            and no.func.id == "_cobrar_canal_antes_de_gravar"
        )
    ]

    assert chamadas, (
        "`inscrever_com_status` não chama mais o portão. Sem ele, a inscrição "
        "deixa de ser recusada quando falta canal e o portal passa a devolver "
        "2xx para uma confirmação que não pode enviar."
    )

    escritas = [
        no.lineno
        for no in ast.walk(inscricao)
        if (
            isinstance(no, ast.Attribute)
            and no.attr in {"update_or_create", "create", "update", "bulk_create", "save"}
        )
    ]

    assert escritas, "a função não grava nada — o teste acima não mede nada"
    assert max(chamadas) < min(escritas), (
        f"o portão é chamado em {caminho.name}:{max(chamadas)} e há escrita em "
        f"{caminho.name}:{min(escritas)}: o gate vem DEPOIS de gravar, que é o furo"
    )


def test_a_ordem_das_verificacoes_nao_vira_oraculo_de_conta():
    """Consentimento (403) antes do portão (503) — e o porquê está no código.

    Se o portão viesse antes, uma conta SEM consentimento receberia 503 e uma
    conta COM consentimento receberia 503 também; mas uma conta sem
    consentimento receberia 403 quando houvesse canal. A diferença entre 403 e
    503 passaria a ser, num ambiente sem canal, um oráculo de "esta conta tem
    consentimento registrado" — para qualquer pessoa, inclusive anônimo.

    Este teste trava a ordem atual: no ambiente REAL de hoje (sem canal), uma
    conta sem consentimento continua recebendo 403, não 503.
    """
    with override_settings(EMAIL_BACKEND=BACKEND_CONSOLE):
        sem_consentimento = User.objects.create_user(
            email="sem-consentimento@example.com", password="senha123", papel="free"
        )
        resposta = _cliente(sem_consentimento).post(
            INSCRIVER, {"tipo": "padrao"}, format="json"
        )

    assert resposta.status_code == 403
    assert "consentimento" in resposta.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. COM CANAL: a inscrição fica pendente e o e-mail SAI
# ---------------------------------------------------------------------------


class TestComCanal:
    def test_com_canal_a_inscricao_fica_pendente(self, settings):
        settings.EMAIL_BACKEND = "newsletter.tests.doubles.EntregaRegistradaBackend"
        user = _conta_consentida("com-canal@example.com")

        resposta = _cliente(user).post(INSCRIVER, {"tipo": "padrao"}, format="json")

        assert resposta.status_code == 201
        corpo = resposta.json()
        assert corpo["estado"] == "pendente"
        assert corpo["confirmada"] is False
        inscricao = InscricaoNewsletter.objects.get(user=user)
        assert inscricao.confirmado_em is None
        assert inscricao.consentimento_aceito_em is None
        assert inscricao.ativa is False
        # O e-mail de confirmação foi entregue de verdade. Uma AssertEquals aqui
        # é o outro lado da prova do portão: lá nada saiu; aqui saiu.
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["com-canal@example.com"]

    def test_o_email_de_confirmacao_traz_o_link_e_diz_o_que_acontece_sem_clique(
        self, settings
    ):
        settings.EMAIL_BACKEND = "newsletter.tests.doubles.EntregaRegistradaBackend"
        _cliente(_conta_consentida("corpo@example.com")).post(
            INSCRIVER, {"tipo": "padrao"}, format="json"
        )

        corpo = mail.outbox[0].body
        assert "/newsletter/confirmar?token=" in corpo
        # O texto precisa dizer as três coisas que a pessoa precisa saber:
        # o que fazer, o que NÃO acontece até lá, e o que fazer se não quiser.
        assert "Confirme sua inscrição" in corpo
        assert "nenhum e-mail de newsletter é enviado" in corpo
        assert "/newsletter?token=" in corpo
        # E o caminho é o que EXISTE: `DescadastrarForm` mora em
        # `/newsletter` e lê o token da query string. `/newsletter/descadastrar`
        # não é rota do frontend — ver a nota em `_corpo_do_email_de_confirmacao`.
        assert "/newsletter/descadastrar?token=" not in corpo

    def test_a_falha_depois_do_portao_tambem_nao_grava_nada(self, settings):
        """A SEGUNDA metade do portão, e ela é a que o briefing pede.

        O portão é uma verificação; o envio é outra coisa. Há canal (o portão
        passa) e o provedor recusa o envio concreto. Nessa janela, sem a
        `transaction.atomic`, a linha pendente sobreviveria sem o e-mail que a
        poderia confirmar — e essa é exatamente a situação que o briefing chama
        de armadilha, alcançada por outro caminho.
        """
        settings.EMAIL_BACKEND = "newsletter.tests.doubles.BackendQueRecusa"
        user = _conta_consentida("recusa@example.com")
        antes = InscricaoNewsletter.objects.count()

        resposta = _cliente(user).post(INSCRIVER, {"tipo": "padrao"}, format="json")

        assert resposta.status_code == 503
        assert InscricaoNewsletter.objects.count() == antes
        assert "nada foi gravado" in resposta.json()["detail"].lower()

    def test_a_excecao_do_provedor_nao_grava_e_nao_vaza_o_endereco(self, settings, caplog):
        settings.EMAIL_BACKEND = "newsletter.tests.doubles.BackendQueExplode"
        user = _conta_consentida("explode@example.com")
        antes = InscricaoNewsletter.objects.count()

        with caplog.at_level(logging.ERROR, logger="newsletter.services"):
            resposta = _cliente(user).post(INSCRIVER, {"tipo": "padrao"}, format="json")

        assert resposta.status_code == 503
        assert InscricaoNewsletter.objects.count() == antes
        texto = "\n".join(r.getMessage() for r in caplog.records)
        # O dublê levanta `OSError` com o endereço NO TEXTO do erro — que é o
        # que um backend real faz. Copiar `str(exc)` para o log publicaria o
        # endereço; e o endereço, aqui, é quem recebe newsletter.
        assert "explode@example.com" not in texto
        assert "endereco-secreto-nao-deve-ir-para-o-log" not in texto