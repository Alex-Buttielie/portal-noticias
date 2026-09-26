from __future__ import annotations

from django.test import override_settings
from django.utils import timezone
import pytest
from django.contrib.auth import get_user_model
from django.core import mail

from catalogo_noticias.models import NewsItem
from gating.models import ConfiguracaoSistema, FeatureLimit
from newsletter import services
from newsletter.models import InscricaoNewsletter
from newsletter.tests.doubles import CAMINHO_ENTREGA
from newsletter.tokens import gerar_token_descadastro

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture(autouse=True)
def _premium_ativo_para_gating():
    """O teste de gating abaixo exige a flag LIGADA (com ela desligada,
    todo mundo navega como Premium)."""
    ConfiguracaoSistema.objects.update_or_create(pk=1, defaults={"premium_ativo": True})


def _usuario_consentido(email, papel="free"):
    usuario = User.objects.create_user(email=email, password="senha123", papel=papel)
    usuario.consentimento_aceito_em = timezone.now()
    usuario.save(update_fields=["consentimento_aceito_em"])
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


def test_inscricao_personalizada_exige_premium():
    usuario_free = _usuario_consentido("free-news@example.com")
    with pytest.raises(services.RecursoGatedError):
        services.inscrever(usuario_free, InscricaoNewsletter.TIPO_PERSONALIZADA)


def test_inscricao_personalizada_funciona_para_premium(fabrica_usuario_premium):
    # P1-08: Premium de verdade (assinatura paga), não `papel="premium"` solto.
    usuario_premium = fabrica_usuario_premium(email="premium-news@example.com")
    usuario_premium.consentimento_aceito_em = timezone.now()
    usuario_premium.save(update_fields=["consentimento_aceito_em"])
    FeatureLimit.objects.update_or_create(
        chave="newsletter_personalizada", plano="premium", defaults={"valor": "true"}
    )

    inscricao = services.inscrever(usuario_premium, InscricaoNewsletter.TIPO_PERSONALIZADA)
    assert inscricao.ativa is True


def test_descadastro_por_token_desativa_inscricao():
    """P1-06: o valor aceito é o token ASSINADO do link, não o segredo cru do
    banco. Antes desta correção o teste passava o segredo e ele era exatamente o
    que ia na URL — o que expunha o segredo de estado e nunca expirava."""
    usuario = _usuario_consentido("desc@example.com")
    inscricao = services.inscrever(usuario, InscricaoNewsletter.TIPO_PADRAO)

    resultado = services.descadastrar_por_token(gerar_token_descadastro(inscricao))

    inscricao.refresh_from_db()
    assert resultado is True
    assert inscricao.ativa is False


def test_enviar_newsletters_respeita_consentimento_e_inscricao_ativa():
    """P1-06 mudou as duas últimas asserções deste teste, e é um ponto do item.

    ANTES (código de d225791) o teste afirmava `total_enviados == 1` e
    `len(mail.outbox) == 1` sem olhar o canal. Rodando na suíte, o backend é
    `locmem` — `django/test/utils.py:146-147` sobrescreve
    `settings.EMAIL_BACKEND` com locmem no início de toda sessão de teste — e
    locmem não entrega a ninguém. Ou seja: a asserção registrava "1 enviado"
    para um e-mail que foi só para um dicionário em memória. Era o furo 3 da
    P0-02c no caminho que já estava em produção.

    Agora o backend que "entrega" é o dublê de `tests/doubles.py` (zero I/O),
    declarado explicitamente.
    """
    _item("Noticia 1", "https://g1/news-1")
    consentido = _usuario_consentido("envio1@example.com")
    services.inscrever(consentido, InscricaoNewsletter.TIPO_PADRAO)

    # Quem não consentiu nem chega a ter inscrição: a trava é no caminho de
    # escrita (`services.inscrever_com_status`). Antes desta correção o teste
    # criava a inscrição sem consentimento e só confiava no filtro do envio.
    sem_consentimento = User.objects.create_user(email="semconsent@example.com", password="senha123", papel="free")
    with pytest.raises(services.ConsentimentoAusenteError):
        services.inscrever(sem_consentimento, InscricaoNewsletter.TIPO_PADRAO)

    with override_settings(EMAIL_BACKEND=CAMINHO_ENTREGA):
        envio = services.enviar_newsletters()

    assert envio.total_enviados == 1
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["envio1@example.com"]


# ---------------------------------------------------------------------------
# BRD seção 27 — "Resumo da manhã"/"Resumo da noite" precisam ser envios de
# fato distintos por período, e a newsletter precisa incluir o Radar de
# tendências. Gaps reais encontrados na análise do BRD.
# ---------------------------------------------------------------------------


def test_inscricao_padrao_usa_periodo_manha_por_default():
    usuario = _usuario_consentido("periodo-default@example.com")
    inscricao = services.inscrever(usuario, InscricaoNewsletter.TIPO_PADRAO)
    assert inscricao.periodo == InscricaoNewsletter.PERIODO_MANHA


def test_inscricao_pode_escolher_periodo_noite():
    usuario = _usuario_consentido("periodo-noite@example.com")
    inscricao = services.inscrever(usuario, InscricaoNewsletter.TIPO_PADRAO, periodo=InscricaoNewsletter.PERIODO_NOITE)
    assert inscricao.periodo == InscricaoNewsletter.PERIODO_NOITE


def test_enviar_newsletters_com_periodo_so_alcanca_inscricoes_daquele_periodo():
    _item("Noticia periodo", "https://g1/news-periodo")
    usuario_manha = _usuario_consentido("periodo-m@example.com")
    services.inscrever(usuario_manha, InscricaoNewsletter.TIPO_PADRAO, periodo=InscricaoNewsletter.PERIODO_MANHA)
    usuario_noite = _usuario_consentido("periodo-n@example.com")
    services.inscrever(usuario_noite, InscricaoNewsletter.TIPO_PADRAO, periodo=InscricaoNewsletter.PERIODO_NOITE)

    # P1-06: o backend precisa entregar para o total decir "1 enviado" — ver a
    # justificativa em `test_enviar_newsletters_respeita_consentimento_e_inscricao_ativa`.
    with override_settings(EMAIL_BACKEND=CAMINHO_ENTREGA):
        envio = services.enviar_newsletters(periodo=InscricaoNewsletter.PERIODO_MANHA)

    assert envio.total_enviados == 1
    assert mail.outbox[0].to == ["periodo-m@example.com"]


def test_corpo_do_email_inclui_radar_de_tendencias_quando_ha_assuntos_em_alta():
    _item("Noticia A", "https://g1/radar-news-a")
    _item("Noticia B", "https://g1/radar-news-b")
    usuario = _usuario_consentido("radar-newsletter@example.com")
    inscricao = services.inscrever(usuario, InscricaoNewsletter.TIPO_PADRAO)

    corpo = services.montar_corpo_email(inscricao)

    assert "Radar de tendências" in corpo
    assert "geral" in corpo  # categoria usada por _item() acima
