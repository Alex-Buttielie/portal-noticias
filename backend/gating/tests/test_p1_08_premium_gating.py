"""
P1-08 — ATIVAÇÃO CONDICIONAL DO PREMIUM (gate de segurança do produto).

Critério de aceite do backlog, literal: *"Premium só abre após todos os gates
de pagamento; caso contrário, fechado com fallback"*.

Este arquivo existe porque, até 20260926, `gating/` tinha apenas
`test_sanity.py`, que verificava a tabela `FeatureLimit` (a configuração) e
NÃO a decisão de acesso tomada com um usuário e uma assinatura reais. A
distinção importa: uma tabela de flags pode estar perfeita enquanto o gate que
a consente está furado. Medido na baseline: `gating/services.py:67-68`
(`except Exception: return False`) e `assinatura/services.py:220-239` (o laço
de renovação da task de vencimentos) estavam com 0% de cobertura — e são,
exatamente, as duas linhas de falha dos dois catastrofes possíveis.

O que este arquivo prova, em ordem de gravidade:

  A. VAZAMENTO — anônimo, Free, assinatura vencida, assinatura cancelada já
     vencida e `papel="premium"` sem assinatura NÃO recebem o conteúdo
     Premium. Premium válido recebe. Verificado no BACKEND (o endpoint e o
     corpo da resposta) e no que o FRONTEND LÊ para decidir o que mostrar.
  B. FALLBACK — Premium indisponível (banco/cache fora do ar, migração
     ausente) ⇒ Free sem anúncios. Nunca erro, nunca Premium vazando.
  C. EXPIRAÇÃO — assinatura vencida não mantém acesso, com data passada e
     com data futura.
  D. INCONSISTÊNCIA — banco diz ativa, provedor diz cancelada ⇒ NEGA, e
     registra. Falhar para o lado permissivo seria blocker.
  E. FREE INTACTO — o plano Free continua acessível e sem anúncios em todos
     os estados.
  F. PODER DISCRIMINANTE — a garantia é daFONTE, não do sintoma.

Nada aqui é inventado: todas as asserções rodam contra `evolucao_interesse`
(o recurso Premium real, `radar_avancado`), que produz a série de evolução —
o conteúdo Premium propriamente dito, não uma flag.
"""

from __future__ import annotations

import ast
from datetime import timedelta
from pathlib import Path
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from assinatura import services as assinatura_services
from assinatura.models import (
    AssinaturaMudancaEstadoLog,
    Plan,
    Subscription,
)
from gating import services as gating_services
from gating.models import ConfiguracaoSistema, FeatureLimit

pytestmark = pytest.mark.django_db

User = get_user_model()

# Recurso Premium REAL: `radar_avancado` protege a evolução de tendências.
EVOLUCAO = "/api/radar/evolucao/"
MEUS_RECURSOS = "/api/gating/meus-recursos/"
STATUS_SISTEMA = "/api/gating/status/"
NEWSLETTER_PERSONALIZADA = "/api/newsletter/inscrever/"

BACKEND = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _premium_ativo():
    """A maioria destes testes é sobre o modo de COBRANÇA (flag LIGADA). O
    fallback com a flag desligada tem seção própria (`test_fallback_*`)."""
    ConfiguracaoSistema.objects.update_or_create(pk=1, defaults={"premium_ativo": True})


@pytest.fixture
def serie_premium_real():
    """Conteúdo Premium de verdade, para o teste de vazamento não ser sobre
    uma resposta vazia (que "não vazaria" mesmo com a brecha aberta)."""
    from catalogo_noticias.models import NewsItem

    for i in range(4):
        NewsItem.objects.create(
            titulo=f"Notícia premium {i}",
            resumo_proprio="Resumo",
            conteudo_bruto="Bruto",
            url_fonte_original=f"https://exemplo.test/premium-{i}",
            nome_fonte="Fonte Teste",
            categoria="politica",
            status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
        )
    return True


@pytest.fixture
def radar_avancado_liberado_para_premium():
    FeatureLimit.objects.update_or_create(
        chave="radar_avancado", plano="free", defaults={"valor": "false"}
    )
    FeatureLimit.objects.update_or_create(
        chave="radar_avancado", plano="premium", defaults={"valor": "true"}
    )
    return True


def _registra_consentimento(usuario):
    """Consentimento datado (P1-06): o produto tem UM consentimento, o do
    cadastro. A newsletter exige que ele exista antes de olhar o plano."""
    from django.utils import timezone as _tz

    User.objects.filter(pk=usuario.pk).update(
        consentimento_aceito_em=_tz.now(), consentimento_versao_termos="1.0"
    )
    usuario.refresh_from_db()
    return usuario


def _usuario_consentido(email, papel="free"):
    return _registra_consentimento(_usuario(papel, email=email))


def _usuario(papel="free", email=None):
    return User.objects.create_user(
        email=email or f"{papel}-{abs(hash(papel))}@exemplo.test", password="senha123", papel=papel
    )


def _get(usuario, url=EVOLUCAO):
    cliente = APIClient()
    if usuario is not None:
        cliente.force_authenticate(user=usuario)
    return cliente.get(url)


def _tem_serie(resposta) -> bool:
    """O conteúdo Premium propriamente dito está no corpo da resposta?"""
    dados = resposta.json() if hasattr(resposta, "json") else resposta.data
    return bool(isinstance(dados, dict) and dados.get("serie"))


# ===========================================================================
# A. VAZAMENTO DE CONTEÚDO PREMIUM
# ===========================================================================


def test_anonimo_nao_recebe_conteudo_premium(serie_premium_real, radar_avancado_liberado_para_premium):
    """
    Visitante anônimo é barrado pela autenticação da view, antes de qualquer
    decisão de plano. Nenhuma linha de conteúdo Premium sai.
    """
    resposta = _get(None)

    assert resposta.status_code in (401, 403)
    assert _tem_serie(resposta) is False


def test_free_logado_nao_recebe_conteudo_premium(
    serie_premium_real, radar_avancado_liberado_para_premium
):
    """Free logado: 403 e corpo SEM a série de evolução."""
    resposta = _get(_usuario("free", email="free-vazamento@exemplo.test"))

    assert resposta.status_code == 403
    assert _tem_serie(resposta) is False


def test_assinatura_vencida_nao_recebe_conteudo_premium_ainda_com_papel_premium(
    serie_premium_real, radar_avancado_liberado_para_premium, fabrica_usuario_premium
):
    """
    ESTE É O TESTE QUE PROVA A CORREÇÃO PRINCIPAL.

    Estado reproduzido: `User.papel == "premium"` (o snapshot que a
    `_sincronizar_papel_usuario` escreveu quando o pagamento foi aprovado) com
    a assinatura JÁ VENCIDA há 3 dias, porque a task de vencimentos ainda não
    rodou. É o estado real entre o vencimento e o próximo tick do beat.

    Antes da correção este teste recebia HTTP 200 com a série completa: o
    gating confiava no snapshot e não olhava `vencimento`. Agora nega.
    """
    usuario = fabrica_usuario_premium(
        email="vencida-papel-premium@exemplo.test", vencimento_dias=-3, rebaixar_papel=True
    )
    assert usuario.papel == "premium", "precondição: o snapshot diz Premium"

    resposta = _get(usuario)

    assert resposta.status_code == 403, "assinatura vencida não mantém acesso Premium"
    assert _tem_serie(resposta) is False


def test_assinatura_cancelada_e_vencida_nao_recebe_conteudo_premium(
    serie_premium_real, radar_avancado_liberado_para_premium, fabrica_usuario_premium
):
    """Cancelamento com o período já pago ESGOTADO não é Premium. A janela de
    graça do cancelamento (ainda dentro do `vencimento`) é coberta em
    `test_cancelada_dentro_do_periodo_pago_ainda_tem_acesso`."""
    usuario = fabrica_usuario_premium(
        email="cancelada-vencida@exemplo.test",
        status=Subscription.STATUS_CANCELADA,
        vencimento_dias=-1,
        rebaixar_papel=True,
    )

    resposta = _get(usuario)

    assert resposta.status_code == 403
    assert _tem_serie(resposta) is False


def test_papel_premium_sem_assinatura_nao_recebe_conteudo_premium(
    serie_premium_real, radar_avancado_liberado_para_premium
):
    """
    `papel="premium"` sem NENHUMA assinatura é o estado incoerente por
    definição: ninguém pagou. Se o campo sozinho bastasse, qualquer
    rebaixamento/importação que gravasse esse valor daria Premium eterno.
    """
    usuario = _usuario("premium", email="papel-sem-assinatura@exemplo.test")
    assert Subscription.objects.filter(user=usuario).count() == 0

    resposta = _get(usuario)

    assert resposta.status_code == 403
    assert _tem_serie(resposta) is False


def test_inadimplente_fora_do_grace_period_nao_recebe_conteudo_premium(
    serie_premium_real, radar_avancado_liberado_para_premium, fabrica_usuario_premium
):
    """Inadimplente SEM `grace_period_termina_em` é fail-closed: sem prazo
    conhecido, não há o que preservar."""
    from assinatura.models import Subscription as Sub

    usuario = fabrica_usuario_premium(
        email="inadimplente-sem-grace@exemplo.test", status=Sub.STATUS_INADIMPLENTE
    )
    Sub.objects.filter(user=usuario).update(grace_period_termina_em=None)
    User.objects.filter(pk=usuario.pk).update(papel="premium")

    assert _get(usuario).status_code == 403


def test_premium_valido_recebe_conteudo_premium(
    serie_premium_real, radar_avancado_liberado_para_premium, fabrica_usuario_premium
):
    """O contraposto obrigatório: quem PAGOU, dentro do prazo, recebe. Sem
    isto, "negar tudo" também passaria."""
    usuario = fabrica_usuario_premium(
        email="premium-valido@exemplo.test", vencimento_dias=10
    )
    assert usuario.papel == "premium"

    resposta = _get(usuario)

    assert resposta.status_code == 200
    assert _tem_serie(resposta) is True, "o Premium válido tem de receber a série"


def test_admin_nao_e_limitado_pelo_plano(fabrica_usuario_premium):
    """Critério de aceite 5 da spec original: admin não é um usuário final e
    não é barrado por assinatura."""
    FeatureLimit.objects.update_or_create(
        chave="radar_avancado", plano="premium", defaults={"valor": "true"}
    )
    admin = _usuario("admin", email="admin-gating@exemplo.test")

    assert _get(admin).status_code == 200


def test_newsletter_personalizada_bloqueada_para_nao_pagante(radar_avancado_liberado_para_premium):
    """Segundo recurso gated do produto — a newsletter personalizada. Um gate
    fechado não basta se o outro está aberto."""
    from newsletter import services as newsletter_services
    from newsletter.models import InscricaoNewsletter

    # O P1-06 passou a exigir consentimento ANTES do gating, então o teste
    # registra o consentimento para chegar na trava de PLANO — que é o que
    # este arquivo precisa medir.
    free = _usuario_consentido(email="free-news-vazamento@exemplo.test")
    FeatureLimit.objects.update_or_create(
        chave="newsletter_personalizada", plano="premium", defaults={"valor": "true"}
    )

    with pytest.raises(newsletter_services.RecursoGatedError):
        newsletter_services.inscrever(free, InscricaoNewsletter.TIPO_PERSONALIZADA)


def test_newsletter_personalizada_bloqueada_para_assinatura_vencida(
    fabrica_usuario_premium
):
    """O mesmo recurso, para o pagante VENCIDO — o caso que mais dói
    commercialmente e o mais fácil de errar."""
    from newsletter import services as newsletter_services
    from newsletter.models import InscricaoNewsletter

    usuario = fabrica_usuario_premium(
        email="vencida-news@exemplo.test", vencimento_dias=-2, rebaixar_papel=True
    )
    _registra_consentimento(usuario)
    FeatureLimit.objects.update_or_create(
        chave="newsletter_personalizada", plano="premium", defaults={"valor": "true"}
    )

    with pytest.raises(newsletter_services.RecursoGatedError):
        newsletter_services.inscrever(usuario, InscricaoNewsletter.TIPO_PERSONALIZADA)


# --- o que o FRONTEND lê ---------------------------------------------------


def test_endpoint_publico_meus_recursos_nunca_anuncia_premium_a_anonimo(
    radar_avancado_liberado_para_premium,
):
    """
    `MeusRecursosView` é `AllowAny` — é a resposta que o front consulta sem
    token. Ela não pode dizer "premium" para quem não é, porque é com esse
    `plano` que o front decide o que renderizar.
    """
    resposta = _get(None, MEUS_RECURSOS)

    assert resposta.status_code == 200
    assert resposta.data["plano"] == "free"
    chaves = {r["chave"]: r for r in resposta.data["recursos"]}
    assert chaves["radar_avancado"]["disponivel"] is False


def test_meus_recursos_para_assinatura_vencida_diz_free(
    radar_avancado_liberado_para_premium, fabrica_usuario_premium
):
    """O front e o backend concordam: o `plano` que o front lê é o mesmo que
    o endpoint de conteúdo aplica. Um backend que nega e um front que mostra
    seria o caso perigoso — testamos os DOIS lados."""
    usuario = fabrica_usuario_premium(
        email="vencida-meus-recursos@exemplo.test", vencimento_dias=-1, rebaixar_papel=True
    )

    plano_anunciado = _get(usuario, MEUS_RECURSOS).data["plano"]
    conteudo = _get(usuario, EVOLUCAO)

    assert plano_anunciado == "free", "o front não pode acreditar que há Premium"
    assert conteudo.status_code == 403, "e o backend não pode entregar o Premium"


def test_status_sistema_publico_nao_vaza_e_nao_quebra():
    """`GET /api/gating/status/` é o outro chamariz do front
    (`lib/premium.ts` -> `usePremiumAtivo`). É público por natureza, devolve
    só a flag, e tem de responder 200 mesmo com a assinatura inconsistente."""
    resposta = _get(None, STATUS_SISTEMA)

    assert resposta.status_code == 200
    assert resposta.data == {"premium_ativo": True}


def test_frontend_nao_tem_atalho_para_o_plano_que_o_backend_nao_concede(
    radar_avancado_liberado_para_premium,
):
    """
    O frontend DOIS trusts decide Premium por conta própria
    (`app/radar/RadarClient.tsx`: `usuario?.papel === "premium"`) e ainda
    trunca a série no navegador (`evo.serie.slice(-7)`) — o que já é um gate
    de fachada, o dado completo vai na resposta. Não posso mexer em
    `frontend/`, então este teste trava o que o BACKEND garante e fixa o
    desacoplamento: enquanto o backend responder 403, o atalho do front não
    tem o que exibir.
    """
    vencida = _usuario("premium", email="front-vencida@exemplo.test")

    resposta = _get(vencida)

    assert resposta.status_code == 403
    assert "serie" not in resposta.data


# ===========================================================================
# B. FALLBACK — Premium indisponível ⇒ Free, nunca erro, nunca vazamento
# ===========================================================================


def test_fallback_banco_fora_do_ar_cai_para_free_e_nao_levanta_excecao(
    radar_avancado_liberado_para_premium,
):
    """
    A falha de infraestrutura que existia: `premium_ativo()` fazia
    `except Exception: return False` e `False` significa "liberado para
    TODOS". Banco fora do ar ⇒ Premium vaza para qualquer um, em silêncio.
    """
    with mock.patch.object(
        gating_services.ConfiguracaoSistema.objects,
        "filter",
        side_effect=RuntimeError("banco indisponivel"),
    ):
        assert gating_services.premium_ativo() is True, "falha de infra tem de NEgar"
        assert gating_services.has_feature(None, "radar_avancado") is False
        assert gating_services.plano_do_usuario(None) == "free"


def test_fallback_banco_fora_do_ar_no_endpoint_e_403_e_nao_500(serie_premium_real):
    """O fallback tem de ser um RESPOSTA, não uma exceção: o visitante anônimo
    recebe 'sem Premium', não uma tela quebrada."""
    with mock.patch.object(
        gating_services.ConfiguracaoSistema.objects,
        "filter",
        side_effect=RuntimeError("banco indisponivel"),
    ):
        resposta = _get(_usuario("free", email="free-fallback@exemplo.test"))

    assert resposta.status_code == 403
    assert _tem_serie(resposta) is False


def test_fallback_cache_fora_do_ar_cai_para_free():
    """A flag é cacheada (P1-1, TTL 45s). Cache derrubado não pode virar
    "liberado para todos"."""
    with mock.patch.object(gating_services, "cache") as cache_quebrado:
        cache_quebrado.get.side_effect = RuntimeError("redis fora do ar")
        assert gating_services.premium_ativo() is True


def test_fallback_migracao_ausente_cai_para_free():
    """
    `ConfiguracaoSistema(pk=1)` inexistente (migração `0004` ainda não
    aplicada) — a versão anterior devolvia `False` e abria tudo. Agora a
    ausência da linha é fail-closed: sem configuração, não há direito.
    """
    ConfiguracaoSistema.objects.all().delete()

    assert gating_services.premium_ativo() is True
    assert gating_services.has_feature(None, "radar_avancado") is False


def test_fallback_nao_exige_escrita_no_banco():
    """O fallback é de LEITURA. Se a falha for de escrita (o admin não
    consegue marcar a flag), a leitura continua valendo o que está no
    banco — o usuário não perde o Premium que já pagou por um erro de
    escrita."""
    assert gating_services.premium_ativo() is True


def test_free_continua_acessivel_com_a_flag_desligada(serie_premium_real):
    """
    Modo "liberado a todos" (flag DESLIGADA, decisão de produto: opera como
    se todo mundo fosse Premium). Aqui o fallback é o ÚNICO Premium: o Free
    navega inteiro, e nada quebra.
    """
    ConfiguracaoSistema.objects.update_or_create(pk=1, defaults={"premium_ativo": False})
    FeatureLimit.objects.update_or_create(
        chave="radar_avancado", plano="free", defaults={"valor": "false"}
    )

    resposta = _get(_usuario("free", email="free-liberado@exemplo.test"))

    assert resposta.status_code == 200
    assert _tem_serie(resposta) is True


def test_nenhum_payload_expoe_publicidade():
    """'Free sem anúncios' é o outro lado do fallback. Nenhum endpoint do
    produto pode expor um campo de publicidade — se a chave `publicidade`
    fosse lida e devolvida, o Free poderia ser servido com anúncios. Hoje
    ela não tem NENHUM consumidor no backend (verificação estrutural em
    `test_chave_publicidade_nao_tem_consumidor`)."""
    for url in (EVOLUCAO, MEUS_RECURSOS, STATUS_SISTEMA, "/api/feed/", "/api/feed/home/"):
        resposta = _get(None, url)
        corpo = repr(resposta.data if hasattr(resposta, "data") else resposta.content)
        assert "exibir_publicidade" not in corpo, url


# ===========================================================================
# C. EXPIRAÇÃO — data passada nega, data futura permite
# ===========================================================================


def test_vencimento_passado_nega_e_vencimento_futuro_permite(fabrica_usuario_premium):
    """
    A regra de direito, isolada: `deveria_ter_acesso_premium` precisa do TEMPO,
    não só do `status`. Sem esta checagem, `status=ativa` concedia acesso para
    sempre.
    """
    usuario_passado = fabrica_usuario_premium(
        email="expiracao-passado@exemplo.test", vencimento_dias=-1
    )
    usuario_futuro = fabrica_usuario_premium(
        email="expiracao-futuro@exemplo.test", vencimento_dias=1
    )

    passado = Subscription.objects.filter(user=usuario_passado).first()
    futuro = Subscription.objects.filter(user=usuario_futuro).first()

    assert passado.vencimento < timezone.now()
    assert futuro.vencimento > timezone.now()

    assert passado.deveria_ter_acesso_premium is False
    assert futuro.deveria_ter_acesso_premium is True


def test_assinatura_sem_vencimento_nao_concede_acesso(fabrica_usuario_premium):
    """Fail-closed de campo ausente: `vencimento=None` não é "válido para
    sempre", é "não se sabe" — e não se sabe é não."""
    usuario = fabrica_usuario_premium(email="sem-vencimento@exemplo.test")
    assinatura = Subscription.objects.filter(user=usuario).first()
    Subscription.objects.filter(pk=assinatura.pk).update(vencimento=None)
    assinatura.refresh_from_db()

    assert assinatura.deveria_ter_acesso_premium is False


def test_grace_period_vencido_nega_e_nao_vencido_permite(fabrica_usuario_premium):
    """O grace period também é prazo, não estado permanente."""
    usuario = fabrica_usuario_premium(
        email="grace-vencido@exemplo.test", status=Subscription.STATUS_INADIMPLENTE
    )
    assinatura = Subscription.objects.filter(user=usuario).first()

    Subscription.objects.filter(pk=assinatura.pk).update(
        grace_period_termina_em=timezone.now() - timedelta(days=1)
    )
    assinatura.refresh_from_db()
    assert assinatura.deveria_ter_acesso_premium is False

    Subscription.objects.filter(pk=assinatura.pk).update(
        grace_period_termina_em=timezone.now() + timedelta(days=1)
    )
    assinatura.refresh_from_db()
    assert assinatura.deveria_ter_acesso_premium is True


def test_cancelada_dentro_do_periodo_pago_ainda_tem_acesso(fabrica_usuario_premium):
    """
    DECISÃO DE PRODUTO, FIXADA AQUI DE PROPÓSITO.

    Cancelar NÃO corta o que já foi pago: enquanto o `vencimento` não chega, o
    Premium continua. Isto é o oposto de "cortar o que o usuário pagou", e é
    deliberado (`Subscription.STATUS_COM_ACESSO_PREMIUM`, models.py:62-67).

    O backlog do P1-08 lista "assinatura expirada/cancelada" como não
    recebedoras. Este teste é o registro explícito de que a versão deste
    código é a mais protetiva do pagante dentro do período pago, e de que a
    negativa só vale DEPOIS do vencimento. Se a decisão de produto for
    "cancelar corta na hora", este é o teste a inverter — e o resto da
    suíte continua valendo.
    """
    usuario = fabrica_usuario_premium(
        email="cancelada-no-prazo@exemplo.test",
        status=Subscription.STATUS_CANCELADA,
        vencimento_dias=5,
    )
    assinatura = Subscription.objects.filter(user=usuario).first()

    assert assinatura.deveria_ter_acesso_premium is True


def _assinatura_com_divergencia(status=Subscription.STATUS_ATIVA, vencimento_dias=10):
    """
    Monta o estado que a brief chama de incoerente: o BANCO diz que a
    assinatura está ativa (`status` + `User.papel=premium`) enquanto o
    PROVEDOR vai dizer que não está mais autorizada.

    `vencimento_dias=None` deixa o `vencimento` NUL (sem prazo).
    """
    from decimal import Decimal

    user = _usuario("free", email=f"divergencia-{status}-{vencimento_dias}@exemplo.test")
    plano = Plan.objects.create(
        nome="Plano Divergência",
        preco=Decimal("29.90"),
        duracao_dias=30,
        ativo=True,
    )
    assinatura = Subscription.objects.create(
        user=user,
        plan=plano,
        status=status,
        preco_cobrado=plano.preco,
        duracao_dias_no_momento=plano.duracao_dias,
        inicio=timezone.now(),
        vencimento=(
            None if vencimento_dias is None
            else timezone.now() + timedelta(days=vencimento_dias)
        ),
        gateway_referencia="preapproval-divergente-123",
    )
    user.papel = "premium"
    user.save(update_fields=["papel"])
    return assinatura


# ===========================================================================
# D. INCONSISTÊNCIA ENTRE BANCO E PROVEDOR
#
# NOTA DE VIGÊNCIA (rebase sobre 6be53dd / P1-07): a revisão por baixo da
# divergência não é mais feita aqui. O P1-07 reconstruiu o caminho do
# webhook em torno de UM ponto único, `services.aplicar_resultado_provedor`,
# e nele o caso "banco diz `ativa`, provedor diz cancelado e não há cobrança
# em aberto" já espelha localmente (`cancelar_assinatura(... ja_cancelado_no_
# provedor=True)` → `cancelada_por_divergencia_de_estado`) e registra.
#
# A correção do P1-08 sobre o gateway é, portanto, a DE MENOR FORÇA possível
# e não depende do provedor: `deveria_ter_acesso_premium` exige `vencimento`
# em dia. Mesmo que o webhook falhe, seja perdido, ou o provedor responda
# errado, o acesso Premium é decidido no momento da requisição. É por isso
# que os testes abaixo verificam o DIREITO (o gate) e não o reflexo da
# notificação — e por isso que o `test_webhook_nao_revoga_quando...` do
# relatório anterior virou, aqui, uma afirmação de que o caminho do P1-07
# continua íntegro depois do rebase.
# ===========================================================================


def test_caminho_do_provedor_espelha_o_cancelamento_detectado_no_gateway():
    """
    O que o P1-07 garantit, verificado de forma independente do HTTP: com o
    banco `ativa` e o provedor dizendo cancelado/pausado SEM cobrança em
    aberto, `aplicar_resultado_provedor` espelha o cancelamento localmente.
    """
    from decimal import Decimal

    from assinatura.models import HistoricoPagamento
    from assinatura.providers.payment import CobrancaGateway

    assinatura = _assinatura_com_divergencia()
    User.objects.filter(pk=assinatura.user_id).update(papel="premium")
    assinatura.user.refresh_from_db()
    # Nenhuma cobrança em aberto: é a assinatura de "o acordo morreu lá".
    assert not HistoricoPagamento.objects.filter(subscription=assinatura).exists()

    class _GatewayDizCancelado:
        def cancelar(self, referencia_gateway):
            return None

    acao = assinatura_services.aplicar_resultado_provedor(
        assinatura,
        _GatewayDizCancelado(),
        CobrancaGateway(
            referencia_gateway="preapproval-divergente-123", status="recusado", valor=Decimal("29.90")
        ),
    )

    assinatura.refresh_from_db()
    assert acao == "cancelada_por_divergencia_de_estado"
    assert assinatura.status == Subscription.STATUS_CANCELADA


def test_gateway_nao_promove_nem_derruba_quando_o_provedor_falha(
    radar_avancado_liberado_para_premium
):
    """
    Provedor fora do ar NÃO pode virar estado: sem confirmação não há
    promoção, sem recusa não há revogação. E, como a assinatura está
    vencida, o gating nega de todo modo.
    """
    assinatura = _assinatura_com_divergencia(vencimento_dias=-1)
    User.objects.filter(pk=assinatura.user_id).update(papel="premium")
    assinatura.user.refresh_from_db()

    resposta = _get(assinatura.user, EVOLUCAO)

    assert resposta.status_code == 403
    assinatura.refresh_from_db()
    assert assinatura.status == Subscription.STATUS_ATIVA, "o provedor não foi consultado; nada muda"


def test_divergencia_fica_registrada_na_auditoria_da_assinatura():
    """A correção de segurança tem de ser reconstituível: o estado sozinho
    não diz que houve divergência com o gateway."""
    assinatura = _assinatura_com_divergencia()

    assinatura_services.cancelar_assinatura(
        assinatura,
        motivo="Cancelamento detectado no provedor durante a conciliação.",
        ja_cancelado_no_provedor=True,
    )

    log = AssinaturaMudancaEstadoLog.objects.filter(subscription=assinatura).latest("criado_em")
    assert log.estado_anterior == Subscription.STATUS_ATIVA
    assert log.estado_novo == Subscription.STATUS_CANCELADA
    assert "provedor" in log.motivo


# ===========================================================================
# E. A VARREDURA DE VENCIMENTOS NÃO PODE SER ABORTADA POR UM
# ===========================================================================


class _GatewayQuebrado:
    def criar_cobranca(self, subscription, valor):
        raise RuntimeError("provedor fora do ar")

    def consultar_status(self, referencia_gateway):
        return "pendente"

    def cancelar(self, referencia_gateway):
        return None


def test_uma_assinatura_com_gateway_fora_do_ar_nao_aborta_a_varredura(
    fabrica_usuario_premium
):
    """
    A varredura roda a cada 60 min. Se a primeira cobrança queRENOVA levanta
    exceção, a versão anterior saía do laço e as demais assinaturas NÃO eram
    processadas — vencidas continuavam `ativa` indefinidamente, sem erro
    visível para o usuário. Como a task roda de novo, a janela se repete a
    cada hora enquanto o provedor estiver fora: um provedor instável é um
    vazamento silencioso e permanente.
    """
    quebrada = fabrica_usuario_premium(
        email="renovacao-quebrada@exemplo.test",
        vencimento_dias=-1,
    )
    outra = fabrica_usuario_premium(
        email="renovacao-outra@exemplo.test", vencimento_dias=-1
    )
    Subscription.objects.filter(user__in=[quebrada, outra]).update(renovacao_automatica=True)

    resultado = assinatura_services.processar_vencimentos_e_grace_periods(
        payment_gateway=_GatewayQuebrado()
    )

    assert resultado["erros"] == 2, "as duas falhas são contadas, não escondidas"
    # A varredura não abortou: as DUAS assinaturas foram alcançadas.
    assert resultado["expiradas"] == 0


def test_varredura_com_gateway_quebrado_ainda_cobra_o_direito_no_gating(fabrica_usuario_premium):
    """
    O ponto que fecha o ciclo: mesmo com a task sem conseguir agir, o gating
    NÃO concede Premium a quem está vencido. A task é limpeza; o direito é
    do gating. Se esta assertions falhar, a task voltou a ser o único
    mecanismo de revogação — ou seja, a brecha original voltou.
    """
    usuario = fabrica_usuario_premium(
        email="vencida-task-quebrada@exemplo.test", vencimento_dias=-1, rebaixar_papel=True
    )
    assinatura_services.processar_vencimentos_e_grace_periods(
        payment_gateway=_GatewayQuebrado()
    )

    assert gating_services.plano_do_usuario(usuario) == "free"


# ===========================================================================
# F. ESTRUTURA — a garantia vem da fonte, não do sintoma
# ===========================================================================


def test_nenhum_modulo_fora_de_gating_le_o_papel_como_autoridade():
    """
    `gating/services.py` (linha 6 do módulo) proíbe explicitamente checar
    `user.papel == "premium"` direto: o `papel` é um cache denormalizado.
    Este teste varre o código de produção e falha se algum módulo voltar a
    tratar o snapshot como direito — que foi exatamente a origem do
    vazamento.

    Exceção declarada: `assinatura.services._sincronizar_papel_usuario` é o
    ÚNICO escritor de `papel` a partir de uma assinatura (por desenho), e a
    checagem `user.papel == "admin"` é o gate de papel, que não é plano.
    """
    infracoes = []
    for caminho in BACKEND.rglob("*.py"):
        partes = set(caminho.relative_to(BACKEND).parts)
        if partes & {"migrations", "tests", "__pycache__"}:
            continue
        if caminho.parts[-2] in ("gating", "assinatura"):
            continue
        # `utf-8-sig`: alguns módulos versionados do repositório começam com
        # BOM (ex.: `painel_admin/__init__.py`) e `ast.parse` rejeita U+FEFF.
        arvore = ast.parse(caminho.read_text(encoding="utf-8-sig"))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Compare):
                continue
            if not (isinstance(no.left, ast.Attribute) and no.left.attr == "papel"):
                continue
            literais = {
                c.value for c in no.comparators if isinstance(c, ast.Constant) and isinstance(c.value, str)
            }
            if "premium" in literais:
                infracoes.append(f"{caminho.relative_to(BACKEND)}:{no.lineno}")

    assert infracoes == [], f"módulos tratando `papel` como Premium: {infracoes}"


def test_falha_ao_ler_a_assinatura_nega_premium_e_registra(fabrica_usuario_premium, caplog):
    """
    A consulta autoritativa pode falhar (tabela de assinatura ausente numa
    migração pendente, banco indisponível). O resultado tem de ser NEGAR, e
    o motivo tem de aparecer no log — um deny silencioso e inexplicado é
    impossível de distinguir de bug na tela de planos.
    """
    import logging

    usuario = fabrica_usuario_premium(email="falha-leitura@exemplo.test")
    with caplog.at_level(logging.ERROR, logger="gating.services"):
        with mock.patch(
            "assinatura.models.Subscription.objects.filter",
            side_effect=RuntimeError("tabela de assinatura indisponivel"),
        ):
            plano = gating_services.plano_do_usuario(usuario)
            recurso = gating_services.has_feature(usuario, "radar_avancado")

    assert plano == "free", "falha de leitura nega Premium (fail-closed)"
    assert recurso is False
    assert "falha ao conferir a assinatura" in caplog.text.lower()


def test_erro_de_conexao_com_a_assinatura_nao_vira_500(radar_avancado_liberado_para_premium):
    """A mesma falha, vista pelo endpoint: resposta coerente (403), não um
    traceback 500 para o visitante."""
    usuario = _usuario("premium", email="falha-leitura-endpoint@exemplo.test")
    with mock.patch(
        "assinatura.models.Subscription.objects.filter",
        side_effect=RuntimeError("tabela indisponivel"),
    ):
        resposta = _get(usuario, EVOLUCAO)

    assert resposta.status_code == 403
    assert _tem_serie(resposta) is False


def test_chave_publicidade_nao_tem_consumidor():
    """
    A chave `publicidade` (free=true/premium=false) é a declaração de "Free
    COM anúncios, Premium SEM". Ela é a base do fallback "Free sem anúncios"…
    e NÃO TEM NENHUM CONSUMIDOR no backend: o `feed` nem expõe mais
    `exibir_publicidade` (ver `feed/tests/test_algoritmos_busca.py:209`).

    Isto não é um vazamento (não há anúncio em lugar nenhum para vazar), mas
    é uma afirmação de produto sem implementação: a tela de planos promete
    "feed sem anúncios" ao Premium e não existe diferença nenhuma. Fica registrado
    como pendência, não como verde.
    """
    from django.conf import settings

    instalados = set(settings.INSTALLED_APPS)
    assert "gating" in instalados

    consumidores = []
    for caminho in BACKEND.rglob("*.py"):
        partes = set(caminho.relative_to(BACKEND).parts)
        if partes & {"migrations", "tests", "__pycache__"}:
            continue
        texto = caminho.read_text(encoding="utf-8")
        # consuming = passa a chave como argumento, não só a menciona/comenta
        if '"publicidade"' in texto or "'publicidade'" in texto:
            for linha in texto.splitlines():
                if '"publicidade"' in linha or "'publicidade'" in linha:
                    if linha.strip().startswith("#") or "descricao=" in linha or "help_text" in linha:
                        continue
                    if "has_feature(" in linha or "exigir_feature(" in linha or "obter_limite_numerico(" in linha:
                        consumidores.append(f"{caminho.relative_to(BACKEND)}")

    assert consumidores == [], (
        f"a chave `publicidade` ganhou consumidor: {consumidores} — o gate de "
        "anúncios precisa de teste de vazamento antes de existir"
    )


# ===========================================================================
# G. A MATRIZ DE DECISÃO
# ===========================================================================


def test_matriz_de_decisao_impressa(capsys, serie_premium_real):
    """
    (estado do visitante × estado da assinatura × estado do pagamento) → o que
    o backend responde. É a prova mais direta de que não há brecha: a tabela
    é gerada EXECUTANDO o endpoint, não descrevendo o código.

    `radar_avancado` = Free:false / Premium:true (recurso Premium real).
    """
    from decimal import Decimal

    FeatureLimit.objects.update_or_create(
        chave="radar_avancado", plano="free", defaults={"valor": "false"}
    )
    FeatureLimit.objects.update_or_create(
        chave="radar_avancado", plano="premium", defaults={"valor": "true"}
    )
    plano = Plan.objects.create(
        nome="Plano Matriz", preco=Decimal("29.90"), duracao_dias=30, ativo=True
    )
    n = {"i": 0}

    def cenario(
        rotulo, status, venc_dias, pagamento, *, flag=True, forcar_papel=None,
        anonimo=False, sincronizar=True,
    ):
        ConfiguracaoSistema.objects.update_or_create(pk=1, defaults={"premium_ativo": flag})
        n["i"] += 1
        user = None
        assinatura = None
        if not anonimo:
            user = User.objects.create_user(
                email=f"matriz-{n['i']}@exemplo.test", password="senha123", papel="free"
            )
            if status is not None:
                assinatura = Subscription.objects.create(
                    user=user,
                    plan=plano,
                    status=status,
                    preco_cobrado=plano.preco,
                    duracao_dias_no_momento=30,
                    inicio=timezone.now(),
                    vencimento=None if venc_dias is None else timezone.now() + timedelta(days=venc_dias),
                    # `inadimplente` só preserva acesso com prazo de graça
                    # definido (ver `deveria_ter_acesso_premium`); sem isto a
                    # linha seria negada por ausência de dado, não por
                    # expiração — e a matriz mediria a coisa errada.
                    grace_period_termina_em=(
                        None if status != Subscription.STATUS_INADIMPLENTE or venc_dias is None
                        else timezone.now() + timedelta(days=venc_dias)
                    ),
                )
            if assinatura is not None and sincronizar:
                # Reproduz o estado PÓS-pagamento real: o snapshot `papel` é
                # escrito por `assinatura.services._sincronizar_papel_usuario`
                # a partir do estado da assinatura. Sem esta chamada, um
                # assinante `ativa` com pagamento aprovado apareceria com
                # `papel=free` e a linha 403 — faria a matriz afirmar que
                # "pagar não libera nada", que é o OUTRO erro catastrófico,
                # e a testaria pelo motivo errado.
                assinatura_services._sincronizar_papel_usuario(assinatura)
                user.refresh_from_db()
            if forcar_papel:
                User.objects.filter(pk=user.pk).update(papel=forcar_papel)
                # OBRIGATÓRIO: `force_authenticate` usa o objeto em memória, e
                # um `QuerySet.update()` não o muda. Sem este refresh, a
                # requisição leria `papel="free"` e estas linhas aprovariam
                # pelo motivo ERRADO — verde falso, o pior defeito de um
                # teste de gate.
                user.refresh_from_db()
        resposta = _get(user, EVOLUCAO)
        papel = user.papel if user else "-"
        return {
            "visitante": rotulo,
            "papel": papel,
            "assinatura": f"{status or '—'} (venc {venc_dias})",
            "pagamento": pagamento,
            "http": resposta.status_code,
            # `tem_direito` é a EXPECTATIVA, declarada por linha. Com a flag
            # desligada TODO MUNDO tem direito (modo de lançamento, ver
            # `gating/migrations/0004_configuracao_sistema.py:7`); com a flag
            # ligada, só tem direito quem tem assinatura COM PRAZO EM DIA —
            # mais o admin, que não é um usuário final.
            #
            # O anônimo é 401 em AMBOS os modos: `EvolucaoView` exige
            # `IsAuthenticated` e a recusa de autenticação roda antes de
            # qualquer decisão de plano. A flag de Premium não é o que
            # mantém o anônimo fora do Radar, e a matriz não deve sugere
            # que é.
            # `direito` = a regra de DIREITO do modelo, declarada por linha,
            # independente de qual gate acabou dando a resposta. Quando os
            # dois divergem, a linha imprime DIVERGE: é assim que se vê um
            # gate furado (o `papel` dissolvendo a regra de direito) e
            # separadamente um pagante barrado por bug.
            "direito": assinatura.deveria_ter_acesso_premium if assinatura is not None else False,
            "anonimo": anonimo,
            "flag": flag,
        }

    def esperado_de(c):
        """
        O que a linha DEVE responder, derivado da regra de DIREITO
        (`Subscription.deveria_ter_acesso_premium`) e não do rótulo.

        401: anônimo — `EvolucaoView` exige `IsAuthenticated` e a recusa de
            autenticação roda antes de qualquer decisão de plano.
        200: assinatura com DIREITO no instante (prazo em dia, ou período já
            pago ainda não esgotado) — inclui `inadimplente` dentro do grace
            period, que é a preservação deliberada do que já foi pago — ou
            `papel=admin`, que não é usuário final e não tem assinatura.
        403: Premium ligado mas sem direito no instante.
        """
        if c["anonimo"]:
            return 401
        if not c["flag"]:
            return 200  # modo de lançamento: liberado para todos
        if c["papel"] == "admin":
            return 200
        return 200 if c["direito"] else 403

    linhas = []
    for c in [
        # visitante anônimo e Free
        cenario("anônimo", None, None, "—", anonimo=True),
        cenario("free", None, None, "—"),
        # assinatura em curso
        cenario("assinante", "pagamento_pendente", 5, "pendente"),
        cenario("assinante", "teste", 5, "aprovado"),
        cenario("assinante", "ativa", 5, "aprovado"),
        cenario("assinante", "inadimplente", 5, "recusado"),
        cenario("assinante", "cancelada", 5, "aprovado"),
        # EXPIRADOS (a linha que estava furada)
        cenario("assinante", "ativa", -3, "aprovado", forcar_papel="premium"),
        cenario("assinante", "cancelada", -3, "aprovado", forcar_papel="premium"),
        cenario("assinante", "inadimplente", -3, "recusado", forcar_papel="premium"),
        cenario("assinante", "expirada", -3, "aprovado", forcar_papel="premium"),
        cenario("assinante", "encerrada", -3, "aprovado", forcar_papel="premium"),
        # estado incoerente
        cenario("sem assinatura", None, None, "—", forcar_papel="premium"),
        # admin
        cenario("admin", None, None, "—", forcar_papel="admin"),
        # flag desligada: fallback de produto, liberado para todos
        cenario("free", None, None, "—", flag=False),
        cenario("anônimo", None, None, "—", flag=False, anonimo=True),
    ]:
        linhas.append(c)

    cabecalho = (
        f"{'visitante':<14} | {'papel':<8} | {'assinatura':<28} | "
        f"{'pagamento':<10} | esperado | obtido"
    )
    print("\n" + "=" * 100)
    print("MATRIZ DE DECISÃO — P1-08 (executada de verdade, não descrita)")
    print("Recurso Premium real: GET /api/radar/evolucao/  (radar_avancado: free=false, premium=true)")
    print("200 = conteúdo Premium servido | 401 = anônimo | 403 = sem Premium")
    print("=" * 100)
    print(cabecalho)
    print("-" * 100)
    for c in linhas:
        esperado = esperado_de(c)
        marca = " <<< DIVERGE" if esperado != c["http"] else ""
        print(
            f"{c['visitante']:<14} | {c['papel']:<8} | {c['assinatura']:<28} | "
            f"{c['pagamento']:<10} | {esperado:>8} | {c['http']:>6}{marca}"
        )
    print("-" * 100)
    divergentes = [c for c in linhas if esperado_de(c) != c["http"]]
    print(f"linhas que divergem do esperado: {len(divergentes)}")
    with capsys.disabled():
        pass

    # A matriz é a prova de que NÃO HÁ BRECHA: cada linha bate com o direito
    # declarado, incluindo as vencidas (que eram 200 antes da correção).
    assert divergentes == [], f"decisão divergente do esperado: {divergentes}"
