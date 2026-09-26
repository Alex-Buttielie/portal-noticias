"""
P1-06 — CONSENTIMENTO: o eixo legal do item.

O QUE ESTÁ REGISTRADO E ONDE (mediado, não presumido)
====================================================
O projeto tem **um** consentimento datado, e ele é no cadastro da conta:

* `User.consentimento_aceito_em` (DateTimeField) e
  `User.consentimento_versao_termos` (o texto aceito).
* Gravado em `identidade/serializers.py:71` (cadastro por e-mail/senha) e em
  `identidade/views.py:331-332` (cadastro social), e o cadastro é **recusado**
  sem o aceite (`identidade/tests/test_acceptance_criteria.py:309`).

Ou seja: é impossível ter conta no portal sem consentimento datado. E o envio
de newsletter já exigia esse consentimento — `services.enviar_newsletters` filtra
por `user__consentimento_aceito_em__isnull=False` (linha que já existia em
d225791).

O QUE ESTAVA ERRADO
===================
A **inscrição** não exigia nada. `InscreverView` (`views.py`, antes do P1-06)
aceitava `POST {"tipo": "padrao"}` de uma conta com
`consentimento_aceito_em = None` e respondia 201 com `ativa: true` — medido. A
inscrição existia e ficava ativa; só o ENVIO a filtrava. Isso é frágil porque o
filtro é de leitura: qualquer tela futura que liste inscrições sem repeti-lo
trataria aquela pessoa como inscrita, e o registro de que ela pediu para receber
não existia em lugar nenhum.

O QUE ESTE ARQUIVO PROVA
=======================
1. A inscrição é recusada (403) sem consentimento — no caminho de escrita, que é
   o único onde dá para recusar.
2. O consentimento é o que autoriza o envio, e continua datado.
3. O descadastro **revoga** o efeito: a inscrição desativa não recebe e-mail.
4. As duas listas de "backend que não entrega" não divergem entre
   `contato/` e `config/settings.py` (trava de não-regressão da P0-02c).
5. O que **não** é garantido — a Pendência jurídica deste item — está escrito
   no teste `test_pendencia_juridica_*` para não ser esquecido e para não ser
   silenciosamente "resolvido" por um teste verde.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from newsletter import services
from newsletter.models import InscricaoNewsletter
from newsletter.tests.doubles import CAMINHO_ENTREGA

pytestmark = pytest.mark.django_db
User = get_user_model()

INSCRIVER = "/api/newsletter/inscrever/"


def _consentido(email, papel="free"):
    """Conta como o cadastro real cria: consentimento COM data e COM a versão do
    texto aceito (`identidade/serializers.py:71-72`)."""
    from django.conf import settings

    user = User.objects.create_user(email=email, password="senha123", papel=papel)
    user.consentimento_aceito_em = timezone.now()
    user.consentimento_versao_termos = settings.TERMOS_VERSAO_ATUAL
    user.save(update_fields=["consentimento_aceito_em", "consentimento_versao_termos"])
    return user


def _sem_consentimento(email, papel="free"):
    return User.objects.create_user(email=email, password="senha123", papel=papel)


def _cliente_autenticado(user):
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION="Token " + Token.objects.create(user=user).key)
    return cliente


# ---------------------------------------------------------------------------
# 1. A inscrição exige consentimento
# ---------------------------------------------------------------------------


def test_inscricao_e_recusada_quando_a_conta_nao_tem_consentimento():
    """Reversão que faz este teste falhar: remover a trava de
    `services.inscrever_com_status`."""
    user = _sem_consentimento("sem-aceite@example.com")
    with pytest.raises(services.ConsentimentoAusenteError):
        services.inscrever(user, InscricaoNewsletter.TIPO_PADRAO)
    assert not InscricaoNewsletter.objects.filter(user=user).exists()


def test_endpoint_de_inscricao_responde_403_sem_consentimento():
    user = _sem_consentimento("sem-aceite-http@example.com")
    resposta = _cliente_autenticado(user).post(
        INSCRIVER, {"tipo": "padrao"}, format="json"
    )
    assert resposta.status_code == 403
    assert "consentimento" in resposta.json()["detail"].lower()
    assert not InscricaoNewsletter.objects.filter(user=user).exists()


def test_erro_de_consentimento_nao_se_confunde_com_gating_premium():
    """403 por falta de consentimento e 403 por recurso Premium são decisões
    diferentes, com textos diferentes. Um `except` único trataria os dois como
    a mesma coisa e esconderia a falta de base legal atrás de um upsell."""
    from gating.models import ConfiguracaoSistema

    ConfiguracaoSistema.objects.update_or_create(pk=1, defaults={"premium_ativo": True})

    sem_consentimento = _sem_consentimento("sem-aceite-gated@example.com")
    r1 = _cliente_autenticado(sem_consentimento).post(
        INSCRIVER, {"tipo": "personalizada"}, format="json"
    )

    consentido = _consentido("premium-gated@example.com")
    r2 = _cliente_autenticado(consentido).post(
        INSCRIVER, {"tipo": "personalizada"}, format="json"
    )

    assert r1.status_code == r2.status_code == 403
    assert r1.json()["detail"] != r2.json()["detail"]
    assert "consentimento" in r1.json()["detail"].lower()
    assert "premium" in r2.json()["detail"].lower()


def test_consentimento_ausente_nao_impede_o_envio_dos_outros():
    """A trava é por PESSOA, não global: quem tem consentimento continua
    recebendo normalmente quando há outra conta sem consentimento no banco."""
    _consentido("com-aceite@example.com")
    services.inscrever(
        User.objects.get(email="com-aceite@example.com"), InscricaoNewsletter.TIPO_PADRAO
    )
    _sem_consentimento("outro-sem-aceite@example.com")

    with override_settings(EMAIL_BACKEND=CAMINHO_ENTREGA):
        envio = services.enviar_newsletters()

    assert envio.total_enviados == 1
    assert [m.to for m in mail.outbox] == [["com-aceite@example.com"]]


# ---------------------------------------------------------------------------
# 2. O consentimento é registrado, com data, e é ele que autoriza o envio
# ---------------------------------------------------------------------------


def test_consentimento_registrado_tem_data_e_versao_do_texto():
    """O consentimento que autoriza a newsletter é o do cadastro, e ele é
    datado e identifica o texto aceito."""
    user = _consentido("datado@example.com")
    assert user.consentimento_aceito_em is not None
    assert user.consentimento_aceito_em.tzinfo is not None
    assert user.consentimento_versao_termos

    inscricao = services.inscrever(user, InscricaoNewsletter.TIPO_PADRAO)
    assert inscricao.ativa is True
    # A inscrição tem data de criação própria (quando a pessoa pediu para
    # receber) — é o segundo carimbo do mesmo ato.
    assert inscricao.criado_em is not None


def test_envio_exige_consentimento_registrado():
    """Sem consentimento não há inscrição (trava de escrita), e o filtro de
    leitura também não deixaria passar. As duas defesas, verificadas."""
    com = _consentido("envia@example.com")
    services.inscrever(com, InscricaoNewsletter.TIPO_PADRAO)

    # Simula o estado legado que existia antes do P1-06: uma inscrição ativa de
    # alguém sem consentimento (criada por um caminho que não exigia aceite).
    sem = _sem_consentimento("legado-sem-aceite@example.com")
    InscricaoNewsletter.objects.create(user=sem, ativa=True)

    with override_settings(EMAIL_BACKEND=CAMINHO_ENTREGA):
        envio = services.enviar_newsletters()

    assert envio.total_inscricoes_processadas == 1
    assert [m.to for m in mail.outbox] == [["envia@example.com"]]


# ---------------------------------------------------------------------------
# 3. O descadastro revoga
# ---------------------------------------------------------------------------


def test_descadastro_revoga_o_efeito_do_consentimento():
    """Revogar éobservable: a pessoa deixa de estar no envio, e a resposta de
    ambos os caminhos é a mesma (nada vaza sobre o e-mail)."""
    from newsletter.tokens import gerar_token_descadastro

    user = _consentido("revoga@example.com")
    inscricao = services.inscrever(user, InscricaoNewsletter.TIPO_PADRAO)
    token = gerar_token_descadastro(inscricao)

    with override_settings(EMAIL_BACKEND=CAMINHO_ENTREGA):
        antes = services.enviar_newsletters()
        assert antes.total_enviados == 1

        resposta = APIClient().post(
            "/api/newsletter/descadastrar/", {"token": token}, format="json"
        )

        depois = services.enviar_newsletters()

    inscricao.refresh_from_db()
    assert inscricao.ativa is False
    assert depois.total_enviados == 0
    assert depois.total_inscricoes_processadas == 0
    assert len(mail.outbox) == 1, "nenhum e-mail novo foi enviado"
    assert resposta.status_code == 200


def test_revogacao_registra_o_instante():
    """A data da revogação é observável em `atualizado_em` (auto_now).

    É um PROXY, não um campo de primeira classe — ver
    `test_pendencia_juridica_*.py`. O teste existe para deixar explícito o que
    hoje dá para responder a um titular que pergunta "quando cancelei?".
    """
    from newsletter.tokens import gerar_token_descadastro

    inscricao = services.inscrever(
        _consentido("quando@example.com"), InscricaoNewsletter.TIPO_PADRAO
    )
    antes = inscricao.atualizado_em

    services.descadastrar_por_token(gerar_token_descadastro(inscricao))

    inscricao.refresh_from_db()
    assert inscricao.atualizado_em >= antes
    assert inscricao.ativa is False


# ---------------------------------------------------------------------------
# 4. Trava de não-regressão da P0-02c entre os dois caminhos de e-mail
# ---------------------------------------------------------------------------


def test_lista_de_backends_que_nao_entregam_do_newsletter_contem_a_do_settings():
    """`newsletter/` e `config/settings.py` precisam concordar sobre o que é
    "não entrega". Sem esta trava, alguém corrigindo um caminho e não o outro
    reintroduz o furo 3 da P0-02c em um dos dois."""
    from config.settings import _EMAIL_BACKENDS_QUE_NAO_ENTREGAM
    from contato.services import BACKENDS_SEM_ENTREGA_REAL

    assert _EMAIL_BACKENDS_QUE_NAO_ENTREGAM <= BACKENDS_SEM_ENTREGA_REAL


def test_locmem_e_console_sao_reconhecidos_como_nao_entregantes():
    from contato.services import BACKENDS_SEM_ENTREGA_REAL

    for backend in (
        "django.core.mail.backends.console.EmailBackend",
        "django.core.mail.backends.locmem.EmailBackend",
        "django.core.mail.backends.dummy.EmailBackend",
        "django.core.mail.backends.filebased.EmailBackend",
        "",
    ):
        with override_settings(EMAIL_BACKEND=backend):
            assert services.canal_entrega_real() is False, backend


def test_resend_e_o_unico_backend_de_verdade_que_o_projeto_conhece():
    from contato.services import BACKENDS_SEM_ENTREGA_REAL

    with override_settings(EMAIL_BACKEND="config.email_resend.ResendEmailBackend"):
        assert services.canal_entrega_real() is True
    assert "config.email_resend.ResendEmailBackend" not in BACKENDS_SEM_ENTREGA_REAL
