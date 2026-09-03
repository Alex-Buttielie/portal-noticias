from __future__ import annotations

from django.utils import timezone
import pytest
from django.contrib.auth import get_user_model
from django.core import mail

from catalogo_noticias.models import NewsItem
from gating.models import FeatureLimit
from newsletter import services
from newsletter.models import InscricaoNewsletter

pytestmark = pytest.mark.django_db

User = get_user_model()


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


def test_inscricao_personalizada_funciona_para_premium():
    usuario_premium = _usuario_consentido("premium-news@example.com", papel="premium")
    FeatureLimit.objects.update_or_create(
        chave="newsletter_personalizada", plano="premium", defaults={"valor": "true"}
    )

    inscricao = services.inscrever(usuario_premium, InscricaoNewsletter.TIPO_PERSONALIZADA)
    assert inscricao.ativa is True


def test_descadastro_por_token_desativa_inscricao():
    usuario = _usuario_consentido("desc@example.com")
    inscricao = services.inscrever(usuario, InscricaoNewsletter.TIPO_PADRAO)

    resultado = services.descadastrar_por_token(inscricao.token_descadastro)

    inscricao.refresh_from_db()
    assert resultado is True
    assert inscricao.ativa is False


def test_enviar_newsletters_respeita_consentimento_e_inscricao_ativa():
    _item("Noticia 1", "https://g1/news-1")
    consentido = _usuario_consentido("envio1@example.com")
    services.inscrever(consentido, InscricaoNewsletter.TIPO_PADRAO)

    sem_consentimento = User.objects.create_user(email="semconsent@example.com", password="senha123", papel="free")
    services.inscrever(sem_consentimento, InscricaoNewsletter.TIPO_PADRAO)

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
