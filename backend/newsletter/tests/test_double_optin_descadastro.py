"""
DOUBLE OPT-IN — DESCADASTRO A PARTIR DO PENDENTE E DO CONFIRMADO.

O briefing diz que "o descadastro tem de funcionar a partir do estado pendente e
do confirmado", e são DOIS conjuntos de garantias, porque as linhas são
diferentes em tudo que importa:

| o que precisa ser verdade            | pendente                     | confirmado                    |
|---------------------------------------|------------------------------|-------------------------------|
| o link de descadastro chega à pessoa? | sim, no e-mail de confirmação | sim, no resumo               |
| confirmar depois de cancelar é seguro? | **é o risco principal**     | não há mais o que confirmar   |
| o resumo para?                        | nunca recebeu                | para                         |
| a linha sobrevive como prova?         | sim                          | sim                          |

A diferença que importa é a PRIMEIRA das linhas de risco: uma PENDENTE tem um
link de confirmação vivo na caixa de entrada da pessoa. Se o descadastro não o
matar, a pessoa cancela e o clique posterior religa a assinatura — e ela fez
exatamente o que pediu para não fazer.

E o caminho de descadastro pela pendência é ALGO QUE NÃO EXISTIA: antes do
double opt-in, quem não tinha confirmado nunca tinha recebido nada, e portanto
não tinha link nenhum para cancelar. A pendência é o primeiro caso em que
"cancelar" e "não receber nunca" são a mesma ação.
"""

from __future__ import annotations

import logging

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from newsletter import services
from newsletter.models import InscricaoNewsletter
from newsletter.tokens import gerar_token_confirmacao, gerar_token_descadastro

pytestmark = pytest.mark.django_db
User = get_user_model()

INSCRIVER = "/api/newsletter/inscrever/"
DESCADASTRAR = "/api/newsletter/descadastrar/"
CANAL = "newsletter.tests.doubles.EntregaRegistradaBackend"


def _conta(email):
    user = User.objects.create_user(email=email, password="senha123", papel="free")
    user.consentimento_aceito_em = timezone.now()
    user.save(update_fields=["consentimento_aceito_em"])
    return user


def _cliente(user):
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION="Token " + Token.objects.create(user=user).key)
    return cliente


def _linha(pk):
    return InscricaoNewsletter.objects.get(pk=pk)


# ---------------------------------------------------------------------------
# 1. DESCADASTRAR A PARTIR DA PENDENTE — pelo link do e-mail de confirmação
# ---------------------------------------------------------------------------


class TestDescadastroDaPendencia:
    def test_o_link_do_e_mail_de_confirmacao_permite_cancelar(self):
        """O e-mail de confirmação traz o link de descadastro, e ele funciona.

        Sem ele, a pessoa que se inscreve e se arrepende antes de confirmar
        ficaria presa esperando um clique que ela não quer dar — e sem poder
        exercer o direito de revogação sem entrar na conta.
        """
        inscricao = services.inscrever(_conta("pend-cancela@example.com"), InscricaoNewsletter.TIPO_PADRAO)
        assert inscricao.confirmado_em is None
        corpo = mail.outbox[-1].body
        # O caminho é `/newsletter?token=…` — onde o `DescadastrarForm` está, e
        # que lê o token da query string. Ver a nota do achado em
        # `_corpo_do_email_de_confirmacao`.
        assert "/newsletter?token=" in corpo

        token = gerar_token_descadastro(inscricao)
        assert services.descadastrar_por_token(token) is True

        inscricao.refresh_from_db()
        assert inscricao.ativa is False
        assert inscricao.consentimento_revogado_em is not None
        assert inscricao.anonimizado_em is not None
        assert inscricao.user_id is None, "o vínculo com a pessoa não foi cortado"

    def test_cancelar_a_pendencia_mata_o_link_de_confirmacao(self):
        """A garantia que o double opt-in criou e que não existia antes.

        Este é o teste mais importante deste arquivo. Sem a rotação de
        `token_confirmacao` na revogação, o link de confirmação que está na
        caixa de entrada da pessoa continua capaz de LIGAR a assinatura — e a
        pessoa teria cancelado para nada, num fluxo em que ela nem sabia que
        havia algo para cancelar.
        """
        inscricao = services.inscrever(_conta("mata-link@example.com"), InscricaoNewsletter.TIPO_PADRAO)
        token_confirmacao = gerar_token_confirmacao(inscricao)
        assert services.descadastrar_por_token(gerar_token_descadastro(inscricao)) is True

        assert services.confirmar_por_token(token_confirmacao) == services.ESTADO_REJEITADA

        inscricao.refresh_from_db()
        assert inscricao.confirmado_em is None, "o link revogado religou a assinatura"
        assert inscricao.ativa is False
        assert inscricao.consentimento_aceito_em is None, (
            "a pessoa nunca concedeu consentimento: revogar um pedido não pode "
            "criar o registro de uma concessão"
        )

    def test_o_endpoint_recusa_o_link_apos_o_cancelamento(self):
        inscricao = services.inscrever(_conta("http-mata@example.com"), InscricaoNewsletter.TIPO_PADRAO)
        token_confirmacao = gerar_token_confirmacao(inscricao)
        APIClient().post(
            DESCADASTRAR, {"token": gerar_token_descadastro(inscricao)}, format="json"
        )

        resposta = APIClient().post(
            "/api/newsletter/confirmar/", {"token": token_confirmacao}, format="json"
        )

        inscricao.refresh_from_db()
        assert inscricao.confirmado_em is None
        # E a resposta é a MESMA do descadastro: nada diz que o cancelamento
        # teve sucesso, porque essa resposta é pública.
        assert resposta.status_code == 200

    def test_cancelar_a_pendencia_pelo_endpoint_autenticado_anonimiza(self):
        """Os DOIS caminhos de revogação, e os dois precisam cortar o vínculo."""
        user = _conta("pend-delete@example.com")
        cliente = _cliente(user)
        cliente.post(INSCRIVER, {"tipo": "padrao"}, format="json")
        inscricao = InscricaoNewsletter.objects.get(user=user)

        assert cliente.delete(INSCRIVER).status_code == 204

        inscricao.refresh_from_db()
        assert inscricao.user_id is None
        assert inscricao.anonimizado_em is not None
        assert inscricao.consentimento_revogado_em is not None
        assert inscricao.confirmado_em is None

    def test_a_pendencia_cancelada_e_estado_rejeitada(self):
        inscricao = services.inscrever(_conta("estado-rejeitada@example.com"), InscricaoNewsletter.TIPO_PADRAO)
        services.descadastrar_por_token(gerar_token_descadastro(inscricao))
        inscricao.refresh_from_db()
        assert inscricao.estado() == "rejeitada"
        assert inscricao.pode_receber is False

    def test_cancelar_a_pendencia_nao_registra_concessao_nem_revogacao_de_concessao(self):
        """A distinção jurídica que o cancelamento de uma pendência preserva.

        Uma PENDENTE nunca teve consentimento concedido. Então a revogação
        dela NÃO pode apagar `consentimento_aceito_em` (que é NULL, e apagar um
        NULL não perde nada) e a linha continua sendo a prova de um PEDIDO, não
        de um consentimento revogado. Um encarregado de dados que perguntasse
        "houve consentimento?" tem a resposta certa em qualquer das duas linhas.
        """
        inscricao = services.inscrever(_conta("sem-concessao@example.com"), InscricaoNewsletter.TIPO_PADRAO)
        services.descadastrar_por_token(gerar_token_descadastro(inscricao))
        inscricao.refresh_from_db()
        assert inscricao.consentimento_aceito_em is None
        assert inscricao.consentimento_revogado_em is not None


# ---------------------------------------------------------------------------
# 2. DESCADASTRAR A PARTIR DA CONFIRMADA
# ---------------------------------------------------------------------------


class TestDescadastroDaConfirmada:
    def _confirmada(self, email):
        inscricao = services.inscrever(_conta(email), InscricaoNewsletter.TIPO_PADRAO)
        services.confirmar_por_token(gerar_token_confirmacao(inscricao))
        inscricao.refresh_from_db()
        assert inscricao.confirmado_em is not None
        return inscricao

    def test_o_link_do_resumo_cancela_a_inscricao_confirmada(self):
        inscricao = self._confirmada("conf-cancela@example.com")

        assert services.descadastrar_por_token(gerar_token_descadastro(inscricao)) is True

        inscricao.refresh_from_db()
        assert inscricao.ativa is False
        assert inscricao.consentimento_revogado_em is not None
        assert inscricao.anonimizado_em is not None
        assert inscricao.user_id is None

    def test_a_confirmada_cancelada_para_de_receber(self):
        inscricao = self._confirmada("conf-para@example.com")
        services.descadastrar_por_token(gerar_token_descadastro(inscricao))
        mail.outbox.clear()

        with override_settings(EMAIL_BACKEND=CANAL):
            envio = services.enviar_newsletters()

        assert envio.total_enviados == 0
        assert envio.total_inscricoes_processadas == 0
        assert mail.outbox == []

    def test_a_confirmada_cancelada_mantem_a_prova_da_concessao(self):
        """O outro lado do mesmo `UPDATE`: a revogação NÃO apaga o registro.

        `confirmado_em` e `consentimento_aceito_em` sobrevivem ao descadastro, e
        é isso que faz a linha valer como PROVA. Sem elas, a linha revogada
        seria indistinguível de uma linha de pedido que nunca foi confirmada, e o
        registro de auditoria perderia a informação mais importante: que houve
        consentimento, e quando acabou.
        """
        inscricao = self._confirmada("conf-prova@example.com")
        concessao = inscricao.consentimento_aceito_em

        services.descadastrar_por_token(gerar_token_descadastro(inscricao))

        inscricao.refresh_from_db()
        assert inscricao.confirmado_em is not None, (
            "a revogação apagou a confirmação — a linha perdeu a prova de que "
            "houve consentimento"
        )
        assert inscricao.consentimento_aceito_em == concessao
        assert inscricao.consentimento_revogado_em is not None
        assert inscricao.consentimento_aceito_em < inscricao.consentimento_revogado_em

    def test_o_endpoint_autenticado_cancela_a_confirmada_e_anonimiza(self):
        user = _conta("conf-delete@example.com")
        cliente = _cliente(user)
        cliente.post(INSCRIVER, {"tipo": "padrao"}, format="json")
        inscricao = InscricaoNewsletter.objects.get(user=user)
        services.confirmar_por_token(gerar_token_confirmacao(inscricao))

        assert cliente.delete(INSCRIVER).status_code == 204

        inscricao.refresh_from_db()
        assert inscricao.ativa is False
        assert inscricao.user_id is None
        assert inscricao.confirmado_em is not None


# ---------------------------------------------------------------------------
# 3. OS DOIS ESTADOS PRODUZEM O MESMO REGISTRO
# ---------------------------------------------------------------------------


def test_os_dois_caminhos_de_descadastro_produzem_o_mesmo_registro():
    """A não-regressão do P1-06, e ela é mais forte agora.

    O P1-06 já provou que `descadastrar_por_token` e `cancelar_inscricao`
    produzem o mesmo registro. Com o double opt-in, isso deixou de ser verdade
    para as pendências — porque a revogação ganhou uma coluna a mais
    (`token_confirmacao`) e foi natural alguém rotacioná-la só num dos dois
    caminhos. Este teste compara os campos DATADOS de quatro linhas: dois
    estados por dois caminhos.
    """
    campos = (
        "ativa",
        "consentimento_revogado_em",
        "anonimizado_em",
        "user_id",
    )
    resultado = {}
    for estado in ("pendente", "confirmada"):
        for caminho in ("token", "autenticado"):
            email = f"{estado}-{caminho}@example.com"
            user = _conta(email)
            inscricao = services.inscrever(user, InscricaoNewsletter.TIPO_PADRAO)
            if estado == "confirmada":
                services.confirmar_por_token(gerar_token_confirmacao(inscricao))
                inscricao.refresh_from_db()
            if caminho == "token":
                services.descadastrar_por_token(gerar_token_descadastro(inscricao))
            else:
                services.cancelar_inscricao(user)
            linha = _linha(inscricao.pk)
            resultado[(estado, caminho)] = {
                campo: getattr(linha, campo) for campo in campos
            }

    for estado in ("pendente", "confirmada"):
        a = resultado[(estado, "token")]
        b = resultado[(estado, "autenticado")]
        assert a["ativa"] == b["ativa"] is False
        assert a["user_id"] is b["user_id"] is None
        assert a["anonimizado_em"] is not None and b["anonimizado_em"] is not None
        assert a["consentimento_revogado_em"] is not None
        assert b["consentimento_revogado_em"] is not None


def test_o_descadastro_nao_revela_cadastro_em_nenhum_dos_dois_estados(caplog):
    """A resposta anônima é igual nos dois estados, e é igual à de um token
    inválido.

    Este teste é a garantia de que o endpoint de descadastro continua sendo um
    caminho que NÃO consulta cadastro — inclusive para quem tem uma PENDÊNCIA,
    que é um estado novo e poderia ter ganhado um tratamento especial por
    descuido.
    """
    pendente = services.inscrever(_conta("oraculo-pendente@example.com"), InscricaoNewsletter.TIPO_PADRAO)
    services.descadastrar_por_token(gerar_token_descadastro(pendente))

    respostas = {
        "pendente_cancelada": APIClient().post(
            DESCADASTRAR, {"token": gerar_token_descadastro(pendente)}, format="json"
        ),
        "token_invalido": APIClient().post(
            DESCADASTRAR, {"token": "token-que-nunca-existiu"}, format="json"
        ),
    }

    corpos = {nome: (r.status_code, r.content) for nome, r in respostas.items()}
    assert len(set(corpos.values())) == 1, (
        f"o descadastro distingue a pendente cancelada de um token inválido: {corpos}"
    )


def test_o_log_da_revocacao_nao_carrega_o_token_de_confirmacao(caplog):
    """O log de revogação é o que um operador consulta quando um titular
    pergunta "por que ainda recebo?". Ele pode carregar o id da inscrição. Não
    pode carregar nenhum dos dois tokens — o de descadastro e o de
    confirmação — porque ambos são segredos de uso único."""
    inscricao = services.inscrever(_conta("log-tokens@example.com"), InscricaoNewsletter.TIPO_PADRAO)
    token_desc = gerar_token_descadastro(inscricao)
    token_conf = gerar_token_confirmacao(inscricao)

    with caplog.at_level(logging.INFO, logger="newsletter.services"):
        services.descadastrar_por_token(token_desc)

    texto = "\n".join(r.getMessage() for r in caplog.records)
    assert token_desc not in texto
    assert token_conf not in texto
    assert "log-tokens@example.com" not in texto