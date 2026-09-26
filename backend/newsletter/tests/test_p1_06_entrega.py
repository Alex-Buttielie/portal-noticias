"""
P1-06 — ENTREGA: nunca reportar sucesso de envio que não aconteceu.

A REGUA
=======
`contato/` (P0-02c, furo 3) já escreveu a regra neste projeto, e ela está na
docstring de `contato/services.py:33-40` como "NUNCA 2xx SEM ENTREGA". A mesma
frase vale para o caminho periódico, que é o que o `newsletter/` faz — e que
**não** a respeitava.

O QUE ESTAVA ERRADO (medido em d225791)
=======================================
`enviar_newsletters` fazia `send_mail(...)` e somava `total_enviados += 1` sem
perguntar se alguém entregou. Com `EMAIL_BACKEND` em console (o default de
`config/settings.py:616`, e o que está em produção — nenhum workflow define a
variável) o estado gravado era:

    EnvioNewsletter: processadas=1 ENVIADOS=1 falhas=0 | mail.outbox=1

isto é, "1 enviado" com `console.EmailBackend`, que escreve no stdout do
container. Era o furo 3 da P0-02c exatamente no caminho que já estava em
produção.

POR QUE `locmem` TORNA ISSO INCONTESTÁVEL NOS TESTES
====================================================
`django.test.utils.setup_test_environment()` **sobrescreve**
`settings.EMAIL_BACKEND` com `locmem` no início de toda sessão de teste
(`django/test/utils.py:146-147`, comment literal: "setting the email backend to
the locmem email backend"). Nenhum teste deste projeto — nem um — roda por
padrão contra um backend que entrega. Portanto o caminho de "entregou de
verdade" só existe sob `override_settings`, com o dublê de
`newsletter/tests/doubles.py` (que faz zero I/O).

Credencial Resend real é Pendência (chegará do solicitante depois;
`PROD_DECISOES.md` item 2). Nenhum teste aqui toca `RESEND_API_KEY` nem rede.
"""

from __future__ import annotations

import logging

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from newsletter import services
from newsletter.models import InscricaoNewsletter
from newsletter.tests.doubles import (
    CAMINHO_ENTREGA,
    CAMINHO_EXPLODE,
    CAMINHO_RECUSA,
)

pytestmark = pytest.mark.django_db
User = get_user_model()


def _consentido(email):
    user = User.objects.create_user(email=email, password="senha123", papel="free")
    user.consentimento_aceito_em = timezone.now()
    user.save(update_fields=["consentimento_aceito_em"])
    return user


def _inscrito(email):
    return services.inscrever(_consentido(email), InscricaoNewsletter.TIPO_PADRAO)


# ---------------------------------------------------------------------------
# O estado reflete a realidade
# ---------------------------------------------------------------------------


def test_backend_que_nao_entrega_nao_e_contado_como_enviado(caplog):
    """O teste que prova o defeito central do item 5 do backlog.

    Faz este teste falhar: voltar a `total_enviados += 1` sem checar o canal.
    """
    _inscrito("nao-entrega@example.com")
    mail.outbox.clear()

    with override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"):
        with caplog.at_level(logging.ERROR, logger="newsletter.services"):
            envio = services.enviar_newsletters()

    assert envio.total_enviados == 0, (
        "contou como enviado com um backend que não entrega a ninguém"
    )
    assert envio.total_falhas == 1
    assert envio.total_inscricoes_processadas == 1
    assert mail.outbox == [], "nem deve haver tentativa de entrega num canal inexistente"

    # E o operador precisa saber o que configurar, por nome de variável — nunca
    # por valor de credencial.
    erro = "\n".join(r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR)
    assert "DJANGO_EMAIL_BACKEND" in erro
    assert "RESEND_API_KEY" in erro
    assert "console" in erro


def test_locmem_nao_e_contado_como_enviado():
    """`locmem` é o backend que TODOS os testes deste projeto veem, e ele não
    entrega a ninguém."""
    _inscrito("locmem@example.com")
    mail.outbox.clear()
    with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
        envio = services.enviar_newsletters()
    assert envio.total_enviados == 0
    assert envio.total_falhas == 1


@pytest.mark.parametrize(
    "backend",
    [
        "django.core.mail.backends.console.EmailBackend",
        "django.core.mail.backends.locmem.EmailBackend",
        "django.core.mail.backends.dummy.EmailBackend",
        "django.core.mail.backends.filebased.EmailBackend",
    ],
)
def test_nenhum_backend_da_lista_de_nao_entrega_conta_como_enviado(backend):
    _inscrito("lista@example.com")
    with override_settings(EMAIL_BACKEND=backend):
        envio = services.enviar_newsletters()
    assert envio.total_enviados == 0, backend
    assert envio.total_falhas == 1, backend


def test_backend_que_entrega_e_contado_como_enviado():
    """O caminho feliz, que só existe com `override_settings` — ver a docstring
    do módulo sobre `setup_test_environment`."""
    _inscrito("entrega-real@example.com")
    mail.outbox.clear()

    with override_settings(EMAIL_BACKEND=CAMINHO_ENTREGA):
        envio = services.enviar_newsletters()

    assert envio.total_enviados == 1
    assert envio.total_falhas == 0
    assert [m.to for m in mail.outbox] == [["entrega-real@example.com"]]


def test_backend_que_recusa_conta_como_falha_e_nao_como_envio():
    _inscrito("recusa@example.com")
    with override_settings(EMAIL_BACKEND=CAMINHO_RECUSA):
        envio = services.enviar_newsletters()
    assert envio.total_enviados == 0
    assert envio.total_falhas == 1


def test_excecao_do_provedor_e_falha_e_nao_derruba_o_lote(caplog):
    """Uma falha individual não pode parar as demais — nem virar sucesso."""
    _inscrito("estoura-1@example.com")
    _inscrito("estoura-2@example.com")
    mail.outbox.clear()

    with override_settings(EMAIL_BACKEND=CAMINHO_EXPLODE):
        with caplog.at_level(logging.ERROR, logger="newsletter.services"):
            envio = services.enviar_newsletters()

    assert envio.total_enviados == 0
    assert envio.total_falhas == 2
    assert envio.total_inscricoes_processadas == 2
    assert any("OSError" in r.getMessage() for r in caplog.records)


def test_lote_misto_conta_cada_um_pelo_seu_proprio_resultado(monkeypatch):
    """Um que entrega e um que falha: as contagens não se misturam."""
    _inscrito("misto-bom@example.com")
    _inscrito("misto-ruim@example.com")
    mail.outbox.clear()

    chamadas = {"n": 0}
    real = services.send_mail

    def alterna(**kwargs):
        chamadas["n"] += 1
        if "ruim" in kwargs["recipient_list"][0]:
            raise OSError("provedor recusou")
        return real(**kwargs)

    monkeypatch.setattr(services, "send_mail", alterna)
    with override_settings(EMAIL_BACKEND=CAMINHO_ENTREGA):
        envio = services.enviar_newsletters()

    assert envio.total_enviados == 1
    assert envio.total_falhas == 1
    assert envio.total_inscricoes_processadas == 2


def test_sem_inscricoes_nao_ha_envio_nem_erro_de_canal():
    """Não havendo nada a entregar, nem se abre a discussão de canal: um ERROR
    sobre backend sem entrega seria alarme falso."""
    with override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"):
        envio = services.enviar_newsletters()
    assert (envio.total_inscricoes_processadas, envio.total_enviados, envio.total_falhas) == (0, 0, 0)


def test_aviso_de_canal_aparece_uma_vez_por_execucao_nao_uma_por_inscricao(caplog):
    """Cinco inscrições ativas = um ERROR, não cinco. O motivo é o mesmo para
    todas; repetir o mesmo texto enche o log sem acrescentar informação."""
    for i in range(5):
        _inscrito(f"volume-{i}@example.com")

    with override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"):
        with caplog.at_level(logging.ERROR, logger="newsletter.services"):
            envio = services.enviar_newsletters()

    erros = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(erros) == 1
    assert envio.total_falhas == 5
    assert envio.total_enviados == 0


def test_duble_de_entrega_cumpre_o_contrato_de_send_messages():
    """Contrato de `BaseEmailBackend.send_messages`: lote vazio é 0, sem exceção.

    Um dublê que errasse aqui daria um falso positivo de "entregou" nos testes que
    dependem dele — o pior tipo de erro numa suíte de entrega.
    """
    from django.core.mail import EmailMessage

    from newsletter.tests.doubles import BackendQueRecusa, EntregaRegistradaBackend

    assert EntregaRegistradaBackend().send_messages([]) == 0
    assert BackendQueRecusa().send_messages([]) == 0
    assert (
        EntregaRegistradaBackend().send_messages(
            [EmailMessage("assunto", "corpo", "de@exemplo.test", ["para@exemplo.test"])]
        )
        == 1
    )


# ---------------------------------------------------------------------------
# O corpo do e-mail é o que a pessoa recebe de verdade
# ---------------------------------------------------------------------------


def test_corpo_traz_link_de_descadastro_e_fontes_originais():
    inscricao = _inscrito("corpo@example.com")
    corpo = services.montar_corpo_email(inscricao)
    assert "Resumo do Portal de Notícias" in corpo
    assert "/newsletter/descadastrar?token=" in corpo
    assert "/planos" in corpo


def test_envio_nao_inclui_inscricao_inativa_ou_sem_consentimento():
    _inscrito("ativa@example.com")
    inativa = _inscrito("inativa@example.com")
    services.cancelar_inscricao(inativa.user)
    sem = User.objects.create_user(email="sem-c@example.com", password="x", papel="free")
    InscricaoNewsletter.objects.create(user=sem, ativa=True)
    mail.outbox.clear()

    with override_settings(EMAIL_BACKEND=CAMINHO_ENTREGA):
        envio = services.enviar_newsletters()

    assert envio.total_inscricoes_processadas == 1
    assert [m.to for m in mail.outbox] == [["ativa@example.com"]]


def test_periodo_separa_manha_e_noite_sem_entrega_real():
    """Com o caminho de não-entrega, o estado é 'nada foi entregue' e mesmo assim
    o período é respeitado — o filtro de público roda antes do do canal."""
    manha = services.inscrever(
        _consentido("p-manha@example.com"), InscricaoNewsletter.TIPO_PADRAO,
        periodo=InscricaoNewsletter.PERIODO_MANHA,
    )
    services.inscrever(
        _consentido("p-noite@example.com"), InscricaoNewsletter.TIPO_PADRAO,
        periodo=InscricaoNewsletter.PERIODO_NOITE,
    )
    assert manha.periodo == InscricaoNewsletter.PERIODO_MANHA

    with override_settings(EMAIL_BACKEND=CAMINHO_ENTREGA):
        envio = services.enviar_newsletters(periodo=InscricaoNewsletter.PERIODO_NOITE)

    assert envio.total_inscricoes_processadas == 1
    assert envio.total_enviados == 1
    assert [m.to for m in mail.outbox] == [["p-noite@example.com"]]
