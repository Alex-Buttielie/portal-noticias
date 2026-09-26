"""
COTA E LIMITES DE ALERTA B2B (backlog P1-13, workstream WS-12).

Alerta que "sempre dispara" é ruído e é ignorado; alerta que "nunca dispara" é
um botão morto. Por isso cada limite é testado nos DOIS lados: dispara no
limite, não dispara abaixo dele, e o placar diz qual limite segurou.

Os quatro mecanismos, e o que cada um impede:

- **cota de critérios por plano** (`b2b/limites.py`) — cada critério ativo é
  uma varredura de `NewsItem` por execução do job. Sem teto, uma conta cria
  critérios sem limite e o job periódico vira laço.
- **teto por execução** — N organizações x M critérios podia virar N x M
  e-mails numa tacada só.
- **teto por organização** — uma organização concentrada esmaga as demais.
- **cooldown por organização** — sem ele, novidade a cada hora vira um
  e-mail por hora, por organização.

E o sinal de anomalia de tenant, testado com o mesmo cuidado: cada tipo
dispara acima do limiar e fica calado abaixo.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from b2b import services
from b2b.limites import CotaDeCriteriosExcedidaError, cota_de_criterios, remanescente
from b2b.models import CriterioMonitoramento, Organizacao

pytestmark = pytest.mark.django_db

User = get_user_model()


def _usuario(email):
    return User.objects.create_user(email=email, password="senha123", papel="free")


def _noticia(titulo, url, mins=0):
    """Notícia com `timestamp_ingestao` deslocado do agora (ratchet/cooldown)."""
    from datetime import datetime, timezone as dt_timezone

    from catalogo_noticias.models import NewsItem

    item = NewsItem.objects.create(
        titulo=titulo,
        resumo_proprio="Resumo.",
        conteudo_bruto="Conteudo bruto longo o bastante para o modelo de resumo.",
        url_fonte_original=url,
        nome_fonte="G1",
        categoria="economia",
        status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
    )
    if mins:
        momento = datetime.now(dt_timezone.utc) - timedelta(minutes=mins)
        NewsItem.objects.filter(pk=item.pk).update(timestamp_ingestao=momento)
        item.refresh_from_db()
    return item


def _org(nome, plano=Organizacao.PLANO_ENTERPRISE, email=None):
    email = email or f"{nome.lower().replace(' ', '-')}@example.com"
    admin = _usuario(email)
    org = services.criar_organizacao_com_admin(nome, admin, plano)
    return org, admin


def _tipos(anomalias):
    return sorted(a["tipo"] for a in anomalias)


# ---------------------------------------------------------------------------
# 1. Cota de critérios por plano
# ---------------------------------------------------------------------------


@override_settings(B2B_COTA_CRITERIOS_BASIC=2, B2B_COTA_CRITERIOS_PRO=4, B2B_COTA_CRITERIOS_ENTERPRISE=9)
def test_cota_bloqueia_ao_atingir_o_teto_do_plano():
    org, _ = _org("Empresa Cota", Organizacao.PLANO_BASIC)
    services.criar_criterio(org, "palavra_chave", "um")
    services.criar_criterio(org, "palavra_chave", "dois")

    with pytest.raises(CotaDeCriteriosExcedidaError) as erro:
        services.criar_criterio(org, "palavra_chave", "tres")

    # A mensagem é acionável: plano, teto e a saída.
    assert "basic" in str(erro.value)
    assert "2/2" in str(erro.value)
    assert CriterioMonitoramento.objects.filter(organizacao=org).count() == 2


@override_settings(B2B_COTA_CRITERIOS_BASIC=2, B2B_COTA_CRITERIOS_PRO=4, B2B_COTA_CRITERIOS_ENTERPRISE=9)
def test_cota_da_api_responde_403_com_a_instrucao_da_saida():
    org, admin = _org("Empresa Cota Api", Organizacao.PLANO_BASIC)
    client = APIClient()
    client.force_authenticate(user=admin)
    for valor in ("um", "dois"):
        assert (
            client.post("/api/b2b/criterios/", {"tipo": "palavra_chave", "valor": valor}, format="json").status_code
            == 201
        )

    resposta = client.post(
        "/api/b2b/criterios/", {"tipo": "palavra_chave", "valor": "tres"}, format="json"
    )

    assert resposta.status_code == 403
    corpo = resposta.json()
    assert corpo["cota_criterios"] == 2
    assert corpo["criterios_ativos"] == 2
    assert corpo["criterios_remanescentes"] == 0
    assert "Exclua um critério" in corpo["detail"]


def test_cota_por_plano_e_distinta_e_nao_vaza_entre_organizacoes():
    """O teto vem do plano DA organização, e a contagem é escopada nela."""
    basic, _ = _org("Empresa Basic", Organizacao.PLANO_BASIC, "cota-basic@example.com")
    pro, _ = _org("Empresa Pro", Organizacao.PLANO_PRO, "cota-pro@example.com")
    # Enche a basic até o teto default (5).
    for i in range(5):
        services.criar_criterio(basic, "palavra_chave", f"b{i}")

    with pytest.raises(CotaDeCriteriosExcedidaError):
        services.criar_criterio(basic, "palavra_chave", "b6")
    # A pro tem folga: a contagem da basic não contaminou a pro.
    assert remanescente(pro) == settings.B2B_COTA_CRITERIOS_PRO
    services.criar_criterio(pro, "palavra_chave", "p0")


def test_criterio_desativado_nao_consome_cota():
    """Só critério ATIVO custa varredura no job; desativado libera espaço."""
    org, _ = _org("Empresa Inativa", Organizacao.PLANO_BASIC)
    for i in range(5):
        services.criar_criterio(org, "palavra_chave", f"c{i}")
    with pytest.raises(CotaDeCriteriosExcedidaError):
        services.criar_criterio(org, "palavra_chave", "c5")

    CriterioMonitoramento.objects.filter(organizacao=org, valor="c0").update(ativo=False)

    assert remanescente(org) == 1
    services.criar_criterio(org, "palavra_chave", "c5")  # agora passa


# ---------------------------------------------------------------------------
# 2. Teto por execução (storm global)
# ---------------------------------------------------------------------------


@override_settings(B2B_ALERTA_MAX_POR_EXECUCAO=2, B2B_ALERTA_COOLDOWN_MINUTOS=0)
def test_teto_por_execucao_segura_o_envio():
    org, admin = _org("Empresa Storm", email="storm@example.com")
    for i in range(5):
        services.criar_criterio(org, "palavra_chave", "tempestade")
    _noticia("Tempestade em São Paulo", "https://g1/storm-1")

    mail.outbox.clear()
    resultado = services.verificar_e_enviar_alertas()

    assert resultado["total_alertas_enviados"] == 2
    assert len(mail.outbox) == 2
    assert resultado["total_suprimidos_por_limite_execucao"] == 3


@override_settings(B2B_ALERTA_MAX_POR_EXECUCAO=2, B2B_ALERTA_COOLDOWN_MINUTOS=0)
def test_o_que_o_teto_suprimiu_sai_na_execucao_seguinte():
    """
    O que o teto segura NÃO é perdido: o ratchet de `ultimo_alerta_em` só
    anda quando o e-mail sai, então o que ficou para trás entra na execução
    seguinte. Sem isto, o teto seria descarte silencioso de alerta.
    """
    org, admin = _org("Empresa Storm Seguinte", email="storm2@example.com")
    for i in range(5):
        services.criar_criterio(org, "palavra_chave", "tempestade")
    _noticia("Tempestade em Salvador", "https://g1/storm2-1")

    primeira = services.verificar_e_enviar_alertas()
    segunda = services.verificar_e_enviar_alertas()

    assert primeira["total_alertas_enviados"] == 2
    assert segunda["total_alertas_enviados"] == 2
    # Um dos 5 critérios só foi notificado agora.
    notificados = CriterioMonitoramento.objects.filter(
        organizacao=org, ultimo_alerta_em__isnull=False
    ).count()
    assert notificados == 4


# ---------------------------------------------------------------------------
# 3. Teto por organização
# ---------------------------------------------------------------------------


@override_settings(B2B_ALERTA_MAX_POR_ORGANIZACAO=1, B2B_ALERTA_MAX_POR_EXECUCAO=50, B2B_ALERTA_COOLDOWN_MINUTOS=0)
def test_teto_por_organizacao_nao_deixa_uma_esmagar_as_outras():
    concentrada, _ = _org("Empresa Concentrada", email="concentrada@example.com")
    discreta, _ = _org("Empresa Discreta", email="discreta@example.com")
    for i in range(4):
        services.criar_criterio(concentrada, "palavra_chave", "tempestade")
    for i in range(4):
        services.criar_criterio(discreta, "palavra_chave", "tempestade")
    _noticia("Tempestade no Nordeste", "https://g1/org-1")

    mail.outbox.clear()
    resultado = services.verificar_e_enviar_alertas()

    assert resultado["total_alertas_enviados"] == 2  # 1 de cada
    assert resultado["total_suprimidos_por_limite_organizacao"] == 6
    # A organização discreta recebeu o dela — o teto é por tenant, não global.
    enviadores = {msg.to[0] for msg in mail.outbox}
    assert enviadores == {"concentrada@example.com", "discreta@example.com"}


# ---------------------------------------------------------------------------
# 4. Cooldown — adia, não cancela
# ---------------------------------------------------------------------------


@override_settings(B2B_ALERTA_COOLDOWN_MINUTOS=240, B2B_ALERTA_MAX_POR_EXECUCAO=50)
def test_cooldown_nao_deixa_chover_e_mail_por_hora():
    org, admin = _org("Empresa Cooldown", email="cooldown@example.com")
    criterio = services.criar_criterio(org, "palavra_chave", "mercado")
    _noticia("Mercado abre em alta", "https://g1/cd-1")

    primeira = services.verificar_e_enviar_alertas()
    assert primeira["total_alertas_enviados"] == 1

    # Novidade 30 min depois: o ratchet deixaria passar; o cooldown segura.
    _noticia("Mercado fecha em baixa", "https://g1/cd-2", mins=30)
    mail.outbox.clear()
    segunda = services.verificar_e_enviar_alertas()

    assert segunda["total_alertas_enviados"] == 0
    assert mail.outbox == []
    assert segunda["total_suprimidos_por_cooldown"] == 1


@override_settings(B2B_ALERTA_COOLDOWN_MINUTOS=240, B2B_ALERTA_MAX_POR_EXECUCAO=50)
def test_passado_o_cooldown_o_que_entrou_sai_integral():
    """
    O cooldown adia, não cancela: passados os 240 min, tudo que entrou desde
    o último alerta (aqui, 3 itens) sai de uma vez. Um limite que só empurrasse
    o envio para o infinito seria pior que não ter limite.
    """
    org, admin = _org("Empresa Cooldown2", email="cooldown2@example.com")
    services.criar_criterio(org, "palavra_chave", "mercado")
    _noticia("Primeira do mercado", "https://g1/cd2-1")
    services.verificar_e_enviar_alertas()

    # Envelhece o último alerta em 5 horas e cria 3 novidades.
    CriterioMonitoramento.objects.filter(organizacao=org).update(
        ultimo_alerta_em=timezone.now() - timedelta(hours=5)
    )
    for i in range(3):
        _noticia(f"Novidade do mercado {i}", f"https://g1/cd2-n{i}")

    mail.outbox.clear()
    resultado = services.verificar_e_enviar_alertas()

    assert resultado["total_alertas_enviados"] == 1
    assert resultado["total_suprimidos_por_cooldown"] == 0
    assert len(mail.outbox) == 1
    corpo = mail.outbox[0].body
    for i in range(3):
        assert f"Novidade do mercado {i}" in corpo


@override_settings(B2B_ALERTA_COOLDOWN_MINUTOS=240, B2B_ALERTA_MAX_POR_EXECUCAO=50, B2B_ALERTA_MAX_POR_ORGANIZACAO=50)
def test_cooldown_e_por_criterio_nao_derruba_o_resto_da_organizacao():
    """
    O cooldown é por CRITÉRIO, na dimensão do tempo. Uma organização com 3
    critérios casando a MESMA novidade recebe 3 e-mails nesta execução — o
    que segura o volume é o teto por organização, não o relógio. Nenhum
    cliente perde a novidade do próprio critério por estar dividindo a janela
    com os outros dois.
    """
    org, admin = _org("Empresa Multi", email="multi@example.com")
    for i in range(3):
        services.criar_criterio(org, "palavra_chave", "energia")
    _noticia("Energia sobe 5%", "https://g1/multi-1")

    mail.outbox.clear()
    resultado = services.verificar_e_enviar_alertas()

    assert resultado["total_alertas_enviados"] == 3
    assert resultado["total_suprimidos_por_cooldown"] == 0

    # Segunda execução: os 3 acabaram de alertar, e agora o cooldown segura.
    seguinte = services.verificar_e_enviar_alertas()
    assert seguinte["total_alertas_enviados"] == 0
    assert seguinte["total_suprimidos_por_cooldown"] == 3


# ---------------------------------------------------------------------------
# 5. Anomalia de tenant — dispara acima do limiar, calada abaixo
# ---------------------------------------------------------------------------


@override_settings(B2B_COTA_CRITERIOS_BASIC=2)
def test_anomalia_cota_atingida_dispara_no_teto_e_cala_abaixo_dele(caplog):
    org, admin = _org("Empresa No Teto", Organizacao.PLANO_BASIC, "anom-cota@example.com")
    services.criar_criterio(org, "palavra_chave", "um")
    services.criar_criterio(org, "palavra_chave", "dois")

    with caplog.at_level(logging.WARNING, logger="b2b.services"):
        resultado = services.verificar_e_enviar_alertas()

    assert "cota_atingida" in _tipos(resultado["anomalias"])
    anomalia = next(a for a in resultado["anomalias"] if a["tipo"] == "cota_atingida")
    # Acionável: identifica a organização, o plano e diz o que fazer.
    assert anomalia["organizacao_id"] == org.pk
    assert anomalia["organizacao"] == "Empresa No Teto"
    assert anomalia["plano"] == Organizacao.PLANO_BASIC
    assert "2/2" in anomalia["detalhe"]
    assert any("cota_atingida" in r.message for r in caplog.records)

    # Um abaixo do teto: cala.
    CriterioMonitoramento.objects.filter(organizacao=org, valor="dois").update(ativo=False)
    abaixo = services.verificar_e_enviar_alertas()
    assert "cota_atingida" not in _tipos(abaixo["anomalias"])


def test_anomalia_sem_destinatario_dispara_e_cala_quando_ha_membro(caplog):
    """
    Organização com critérios ativos e nenhum membro com e-mail: o envio era
    pulado em silêncio e o cliente achava que estava sendo monitorado. Agora
    vira sinal, com a ação sugerida.
    """
    org, admin = _org("Empresa Orfa", email="anom-orfa@example.com")
    services.criar_criterio(org, "palavra_chave", "mercado")

    # Sem e-mail no usuário: a lista de destinatários sai vazia.
    User.objects.filter(pk=admin.pk).update(email="")
    mail.outbox.clear()

    with caplog.at_level(logging.WARNING, logger="b2b.services"):
        resultado = services.verificar_e_enviar_alertas()

    assert resultado["total_alertas_enviados"] == 0
    assert "sem_destinatario" in _tipos(resultado["anomalias"])
    anomalia = next(a for a in resultado["anomalias"] if a["tipo"] == "sem_destinatario")
    assert "nenhum membro com e-mail" in anomalia["detalhe"]
    assert any("sem_destinatario" in r.message for r in caplog.records)

    # Com membro com e-mail: cala.
    User.objects.filter(pk=admin.pk).update(email="anom-orfa@example.com")
    com_membro = services.verificar_e_enviar_alertas()
    assert "sem_destinatario" not in _tipos(com_membro["anomalias"])


def test_anomalia_organizacao_inativa_com_criterios_dispara(caplog):
    """
    Organização desativada com critérios ativos: a varredura pula em silêncio
    (`organizacao__ativo=True`) e a varredura morta continua custando. É
    higiene de dados, e só o operador resolve.
    """
    org, admin = _org("Empresa Inativa", email="anom-inativa@example.com")
    services.criar_criterio(org, "palavra_chave", "mercado")
    Organizacao.objects.filter(pk=org.pk).update(ativo=False)

    with caplog.at_level(logging.WARNING, logger="b2b.services"):
        resultado = services.verificar_e_enviar_alertas()

    assert "organizacao_inativa_com_criterios" in _tipos(resultado["anomalias"])
    assert any("organizacao_inativa_com_criterios" in r.message for r in caplog.records)
    # A organização inativa não gera envio, mesmo com novidade.
    assert resultado["total_alertas_enviados"] == 0


def test_anomalia_falha_ao_enviar_identifica_a_organizacao(monkeypatch):
    org, admin = _org("Empresa Falha", email="anom-falha@example.com")
    services.criar_criterio(org, "palavra_chave", "mercado")
    _noticia("Mercado em alta", "https://g1/falha-1")

    def _explode(*_args, **_kwargs):
        raise OSError("smtp fora do ar")

    monkeypatch.setattr(services, "send_mail", _explode)
    resultado = services.verificar_e_enviar_alertas()

    assert resultado["total_alertas_enviados"] == 0
    assert resultado["total_falhas"] == 1
    assert "falha_ao_enviar" in _tipos(resultado["anomalias"])
    anomalia = next(a for a in resultado["anomalias"] if a["tipo"] == "falha_ao_enviar")
    assert anomalia["organizacao_id"] == org.pk


def test_execucao_saudavel_nao_reporta_anomalia():
    """
    O contraponto do "sempre dispara": uma operação normal — organização
    ativa, com membros, longe da cota — não produz sinal nenhum. Um alerta de
    anomalia que dispara em toda execução deixa de ser lido em duas semanas.
    """
    org, admin = _org("Empresa Saudavel", Organizacao.PLANO_ENTERPRISE, "anom-ok@example.com")
    services.criar_criterio(org, "palavra_chave", "mercado")
    _noticia("Mercado em alta", "https://g1/ok-1")

    resultado = services.verificar_e_enviar_alertas()

    assert resultado["total_alertas_enviados"] == 1
    assert resultado["anomalias"] == []
    assert resultado["total_suprimidos_por_limite_execucao"] == 0
    assert resultado["total_suprimidos_por_limite_organizacao"] == 0
    assert resultado["total_suprimidos_por_cooldown"] == 0


def test_plano_desconhecido_cai_no_teto_mais_permissivo():
    """
    Linha antiga com `plano` nulo (ou plano novo no catálogo) não pode
    trancar o cliente que já pagou: o fallback é o maior teto, não o menor.
    """
    org = Organizacao.objects.create(nome="Empresa Legada", plano="")
    maior = max(
        settings.B2B_COTA_CRITERIOS_BASIC,
        settings.B2B_COTA_CRITERIOS_PRO,
        settings.B2B_COTA_CRITERIOS_ENTERPRISE,
    )
    assert cota_de_criterios(org) == maior
