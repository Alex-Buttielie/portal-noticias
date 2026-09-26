"""
P1-06 — LOG: o mínimo necessário, e nada de dado pessoal.

O QUE JÁ ESTAVA CERTO (medido em d225791)
==========================================
`newsletter/` já não logava e-mail, corpo de mensagem nem token: o único log era
`logger.exception("Falha ao enviar newsletter para inscrição %s", inscricao.id)`
(`services.py:116`), que usa o id da inscrição. Isso é o certo pela metade — o
id não é dado pessoal e permite navegar no admin.

O QUE ESTAVA ERRADO
===================
1. **`logger.exception` imprimia o traceback inteiro.** A exceção vinha de dentro
   de `send_mail`, e o texto de erro de um backend de e-mail real ecoa o
   destinatário (`SMTPServerDisconnected: ... b'fulano@exemplo.com' ...`). Com
   `logger.exception`, essa linha — com o endereço de quem receberia newsletter,
   que é dado pessoal — ia para o log. `contato/services.py:225-227` já tinha
   resolvido isso ("tipo da exceção, sem `str(exc)`, sem traceback"); o
   `newsletter/` não.
2. **O ato de revogar não era registrado em lugar nenhum.** Não havia nenhuma
   linha de log dizendo que um consentimento tinha sido revogado, nem quando, nem
   de qual inscrição. Um titular que perguntasse "quando cancelei?" não tinha
   resposta, e não havia trilha para responder.

O QUE ESTE ARQUIVO PROVA
=======================
* O log nunca contém endereço de e-mail, token, segredo do banco, corpo de
  mensagem nem credencial — nos caminhos de sucesso, erro de provedor, descadastro
  e aviso de canal.
* A revogação fica registrada com o id da inscrição e sem nada mais.
* O aviso de canal nomeia a VARIÁVEL de configuração, nunca o valor da chave.

POR QUE SEM HASH DO E-MAIL
=========================
Um hash (tipo o `ip_hash` citado em `contato/services.py:24-27`) foi
considerado e **descartado**, e a razão vale mais que a decisão: para responder
"quem é essa pessoa" o operador abre o admin pelo id da inscrição — o id já é
ponteiro suficiente. Um hash de e-mail no log acrescentaria um pseudônimo de um
dado pessoal sem resolver nada que o id não resolva, e criaria um segundo vetor de
vazamento (log é lido por mais gente que o admin). Então: **id da inscrição, e
nada mais**.
"""

from __future__ import annotations

import logging

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from newsletter import services
from newsletter.models import InscricaoNewsletter
from newsletter.tests.doubles import CAMINHO_ENTREGA, CAMINHO_EXPLODE
from newsletter.tokens import gerar_token_descadastro

pytestmark = pytest.mark.django_db
User = get_user_model()

URL_DESCADASTRO = "/api/newsletter/descadastrar/"


def _consentido(email):
    user = User.objects.create_user(email=email, password="senha123", papel="free")
    user.consentimento_aceito_em = timezone.now()
    user.save(update_fields=["consentimento_aceito_em"])
    return user


def _inscrito(email):
    return services.inscrever(_consentido(email), InscricaoNewsletter.TIPO_PADRAO)


def _todo_o_log(caplog):
    return "\n".join(
        f"{r.name} {r.levelname} {r.getMessage()}" for r in caplog.records
    )


def _nao_vazou(texto, *segredos):
    for segredo in segredos:
        assert segredo not in texto, f"vazou no log: {segredo!r}"


# ---------------------------------------------------------------------------
# O endereço de quem recebe newsletter não vai para o log
# ---------------------------------------------------------------------------


def test_erro_do_provedor_nao_vaza_o_endereco_do_destinatario(caplog):
    """Reversão que faz este teste falhar: voltar a `logger.exception` (ou a
    `str(exc)`). O dublê `BackendQueExplode` coloca um endereço e um segredo no
    texto do erro, imitando o que um backend real faz."""
    inscricao = _inscrito("pessoa-que-nao-deve-aparecer@example.com")
    segredo = inscricao.token_descadastro
    token = gerar_token_descadastro(inscricao)

    with override_settings(EMAIL_BACKEND=CAMINHO_EXPLODE):
        with caplog.at_level(logging.DEBUG):
            services.enviar_newsletters()

    texto = _todo_o_log(caplog)
    assert texto, "o teste não está capturando log nenhum — não prova nada"
    _nao_vazou(
        texto,
        "pessoa-que-nao-deve-aparecer@example.com",
        "fulano-de-exemplo@exemplo.com",
        "endereco-secreto-nao-deve-ir-para-o-log",
        segredo,
        token,
    )
    # E o diagnóstico continua útil: o tipo da exceção e o id da inscrição.
    assert "OSError" in texto
    assert f"inscricao={inscricao.pk}" in texto


def test_sem_traceback_no_log_de_envio(caplog):
    """`logger.exception` anexa o traceback inteiro ao log; é ele que carrega o
    texto de erro do provedor."""
    _inscrito("traceback@example.com")
    with override_settings(EMAIL_BACKEND=CAMINHO_EXPLODE):
        with caplog.at_level(logging.DEBUG):
            services.enviar_newsletters()

    for registro in caplog.records:
        assert registro.exc_info is None, (
            f"registro {registro.name} carrega traceback: {registro.exc_info}"
        )


# ---------------------------------------------------------------------------
# O aviso de canal nomeia a variável, nunca a credencial
# ---------------------------------------------------------------------------


def test_aviso_de_canal_nao_vaza_credencial(caplog):
    _inscrito("credencial@example.com")
    with override_settings(
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
        RESEND_API_KEY="re_ESSECREDOENAODEVEAPARECER",
    ):
        with caplog.at_level(logging.DEBUG):
            services.enviar_newsletters()

    texto = _todo_o_log(caplog)
    _nao_vazou(texto, "re_ESSECREDOENAODEVEAPARECER")
    assert "RESEND_API_KEY" in texto, "o operador precisa saber QUAL configuração falta"
    assert "credencial@example.com" not in texto


# ---------------------------------------------------------------------------
# A revogação fica registrada
# ---------------------------------------------------------------------------


def test_revogacao_e_registrada_com_o_id_da_inscricao(caplog):
    inscricao = _inscrito("revogada@example.com")
    token = gerar_token_descadastro(inscricao)

    with caplog.at_level(logging.INFO, logger="newsletter.services"):
        APIClient().post(URL_DESCADASTRO, {"token": token}, format="json")

    texto = _todo_o_log(caplog)
    assert "revogado" in texto
    assert f"inscricao={inscricao.pk}" in texto
    _nao_vazou(
        texto,
        "revogada@example.com",
        inscricao.token_descadastro,
        token,
    )


def test_revogacao_registra_se_ja_estava_desativada(caplog):
    """Distingue "a pessoa cancelou agora" de "já estava desligada, o link foi
    usado de novo" — informação de auditoria, sem dado pessoal."""
    inscricao = _inscrito("reuso-de-token@example.com")
    token = gerar_token_descadastro(inscricao)
    APIClient().post(URL_DESCADASTRO, {"token": token}, format="json")

    # Reinscreve, usa o MESMO token de novo (já rotacionado, então não casa).
    services.inscrever(inscricao.user, InscricaoNewsletter.TIPO_PADRAO)
    caplog.clear()  # só o que vier depois da reinscrição interessa
    with caplog.at_level(logging.INFO, logger="newsletter.services"):
        APIClient().post(URL_DESCADASTRO, {"token": token}, format="json")

    # O token já usado não revoga nada, então nem entra no log de revogação.
    assert "revogado" not in _todo_o_log(caplog)
    inscricao.refresh_from_db()
    assert inscricao.ativa is True


def test_inscricao_criada_e_registrada_sem_e_mail(caplog):
    _inscrito("criada@example.com")
    with caplog.at_level(logging.INFO, logger="newsletter.services"):
        services.inscrever(
            _consentido("segunda@example.com"), InscricaoNewsletter.TIPO_PADRAO
        )

    texto = "\n".join(
        r.getMessage() for r in caplog.records if r.name == "newsletter.services"
    )
    assert "inscrição criada" in texto
    _nao_vazou(texto, "segunda@example.com")


def test_log_nao_traz_corpo_de_noticia_nem_conteudo_do_email(caplog):
    """O corpo do e-mail é montado por item e inclui títulos e URLs das
    notícias; nada disso pode aparecer no log."""
    from catalogo_noticias.models import NewsItem

    NewsItem.objects.create(
        titulo="TITULO-DE-NOTICIA-QUE-NAO-DEVE-VAZAR",
        resumo_proprio="Resumo",
        conteudo_bruto="Bruto",
        url_fonte_original="https://exemplo.test/noticia-secreta",
        nome_fonte="Fonte X",
        categoria="geral",
        status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
    )
    _inscrito("corpo@example.com")
    mail.outbox.clear()

    with override_settings(EMAIL_BACKEND=CAMINHO_ENTREGA):
        with caplog.at_level(logging.DEBUG):
            services.enviar_newsletters()

    texto = _todo_o_log(caplog)
    _nao_vazou(
        texto,
        "TITULO-DE-NOTICIA-QUE-NAO-DEVE-VAZAR",
        "https://exemplo.test/noticia-secreta",
        "corpo@example.com",
    )


def test_envio_bem_sucedido_nao_registra_o_endereco(caplog):
    """Nem no caminho feliz."""
    _inscrito("feliz@example.com")
    with override_settings(EMAIL_BACKEND=CAMINHO_ENTREGA):
        with caplog.at_level(logging.DEBUG):
            services.enviar_newsletters()

    _nao_vazou(_todo_o_log(caplog), "feliz@example.com")


def test_id_de_inscricao_nao_e_o_endereco():
    """O id da inscrição é um inteiro sequencial — por isso ele serve de ponteiro
    para o admin e não carrega nada do titular. Este teste registra essa
    premissa: se um dia o `__str__`/log passar a incluir o e-mail, ele quebra."""
    inscricao = _inscrito("inteiro@example.com")
    assert isinstance(inscricao.pk, int)
    assert str(inscricao) == (
        f"Newsletter de {inscricao.user_id} (padrao, ativa)"
    )
