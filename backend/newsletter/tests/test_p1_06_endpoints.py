"""
P1-06 — CONTRATO HTTP dos endpoints de newsletter.

Antes deste item, `newsletter/views.py` estava a **48% de cobertura**
(`14-21`, `27-28`, `37-40` sem execução): nenhum teste batia nos endpoints que
o frontend chama em produção. `NewsletterForm.tsx:132` chama
`POST /api/newsletter/inscrever/` e `api.ts:959` chama
`POST /api/newsletter/descadastrar/` — ou seja, exatamente o que não era testado.

Este arquivo fecha isso: o contrato observável de cada endpoint, incluindo o
rate limit, que **não existia** em nenhuma das duas views (medido: 60 POSTs
seguidos no `descadastrar/` → 60 × 400, zero 429).
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from newsletter import services
from newsletter.models import InscricaoNewsletter
from newsletter.tokens import gerar_token_descadastro

pytestmark = pytest.mark.django_db
User = get_user_model()

INSCRIVER = "/api/newsletter/inscrever/"
DESCADASTRAR = "/api/newsletter/descadastrar/"


def _consentido(email, papel="free"):
    user = User.objects.create_user(email=email, password="senha123", papel=papel)
    user.consentimento_aceito_em = timezone.now()
    user.save(update_fields=["consentimento_aceito_em"])
    return user


def _cliente(user):
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION="Token " + Token.objects.create(user=user).key)
    return cliente


def _limite_configurado() -> int:
    from config.settings import REST_FRAMEWORK

    taxa = REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["escrita_publica"]
    return int(taxa.partition("/")[0])


# Cache isolado em locmem, pelo mesmo motivo de `config/tests/test_throttling.py`:
# a suíte usa DummyCache (`settings_test.CACHES`), com o qual o throttle nunca
# ativa — um teste que rodasse com o cache padrão passaria sem testar nada.
_LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-p1-06-throttle",
    }
}


@pytest.fixture
def cache_para_throttle(settings):
    settings.CACHES = _LOCMEM
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------------------
# /inscrever/ — autenticação
# ---------------------------------------------------------------------------


def test_inscrever_exige_autenticacao():
    assert APIClient().post(INSCRIVER, {"tipo": "padrao"}, format="json").status_code == 401


def test_inscrever_com_token_invalido_responde_401():
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION="Token token-que-nao-existe")
    assert cliente.post(INSCRIVER, {"tipo": "padrao"}, format="json").status_code == 401


def test_delete_exige_autenticacao():
    assert APIClient().delete(INSCRIVER).status_code == 401


# ---------------------------------------------------------------------------
# /inscrever/ — contrato de sucesso e re-inscrição
# ---------------------------------------------------------------------------


def test_inscricao_criada_responde_201_com_o_estado():
    user = _consentido("novo@example.com")
    resposta = _cliente(user).post(INSCRIVER, {"tipo": "padrao"}, format="json")

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["tipo"] == "padrao"
    assert corpo["periodo"] == "manha"
    assert corpo["ativa"] is True
    assert InscricaoNewsletter.objects.filter(user=user).count() == 1


def test_segunda_inscricao_responde_200_e_nao_duplica():
    """O frontend (`NewsletterForm.tsx:132`) manda o formulário inteiro de novo
    sempre que a pessoa clica. O efeito no banco é o mesmo; o que muda é o status.

    Anunciar 201 na segunda vez diz ao cliente que existe um recurso novo — e não
    existe. `landing/` já respondia 200 na repetição (`landing/views.py:34-35`).
    """
    user = _consentido("reinscreve@example.com")
    cliente = _cliente(user)

    primeira = cliente.post(INSCRIVER, {"tipo": "padrao"}, format="json")
    segunda = cliente.post(INSCRIVER, {"tipo": "padrao"}, format="json")

    assert primeira.status_code == 201
    assert segunda.status_code == 200
    assert InscricaoNewsletter.objects.filter(user=user).count() == 1
    assert "atualizada" in segunda.json()["detail"].lower()
    # O conteúdo do estado continua igual — só muda a honestidade do status.
    for campo in ("tipo", "periodo", "ativa"):
        assert segunda.json()[campo] == primeira.json()[campo]


def test_reinscricao_atualiza_as_escolhas_sem_criar_linha():
    user = _consentido("muda@example.com")
    cliente = _cliente(user)
    cliente.post(INSCRIVER, {"tipo": "padrao", "periodo": "manha"}, format="json")
    resposta = cliente.post(
        INSCRIVER,
        {"tipo": "categoria", "categorias": ["geral"], "periodo": "noite"},
        format="json",
    )

    inscricao = InscricaoNewsletter.objects.get(user=user)
    assert resposta.status_code == 200
    assert inscricao.tipo == "categoria"
    assert inscricao.categorias == ["geral"]
    assert inscricao.periodo == "noite"
    assert InscricaoNewsletter.objects.filter(user=user).count() == 1


def test_reinscrever_reativa_uma_inscricao_desativada():
    """Cenário real: a pessoa se descadastrou e depois se inscreve de novo pelo
    formulário. Uma linha, `ativa=True` de novo."""
    user = _consentido("volta@example.com")
    cliente = _cliente(user)
    cliente.post(INSCRIVER, {"tipo": "padrao"}, format="json")
    services.cancelar_inscricao(user)
    assert not InscricaoNewsletter.objects.get(user=user).ativa

    resposta = cliente.post(INSCRIVER, {"tipo": "padrao"}, format="json")

    inscricao = InscricaoNewsletter.objects.get(user=user)
    assert inscricao.ativa is True
    assert resposta.status_code == 200
    assert resposta.json()["ativa"] is True
    assert InscricaoNewsletter.objects.filter(user=user).count() == 1


def test_periodo_e_tipo_passao_pelo_endpoint():
    user = _consentido("escolhas@example.com")
    resposta = _cliente(user).post(
        INSCRIVER, {"tipo": "categoria", "categorias": ["geral"], "periodo": "noite"},
        format="json",
    )
    inscricao = InscricaoNewsletter.objects.get(user=user)
    assert inscricao.periodo == "noite"
    assert inscricao.tipo == "categoria"
    assert resposta.json()["periodo"] == "noite"


def test_tipo_personalizada_sem_premium_responde_403():
    from gating.models import ConfiguracaoSistema

    ConfiguracaoSistema.objects.update_or_create(pk=1, defaults={"premium_ativo": True})
    user = _consentido("free-gated@example.com")
    resposta = _cliente(user).post(
        INSCRIVER, {"tipo": "personalizada"}, format="json"
    )
    assert resposta.status_code == 403
    assert "premium" in resposta.json()["detail"].lower()
    assert not InscricaoNewsletter.objects.filter(user=user).exists()


def test_tipo_personalizada_com_premium_responde_201(fabrica_usuario_premium):
    from gating.models import ConfiguracaoSistema, FeatureLimit

    ConfiguracaoSistema.objects.update_or_create(pk=1, defaults={"premium_ativo": True})
    FeatureLimit.objects.update_or_create(
        chave="newsletter_personalizada", plano="premium", defaults={"valor": "true"}
    )
    # P1-08: Premium de verdade (assinatura paga pela porta pública
    # `assinar_plano`), e não `papel="premium"` escrito à mão. A versão
    # anterior fixava como verdade a premissa de que o campo `papel` sozinho
    # libera o recurso — premissa que o P1-08 tratou como NÃO premium, e que
    # aqui permitiria a uma conta sem assinatura nenhuma assinar a newsletter
    # personalizada. O `papel` continua sendo um snapshot: o que dá direito é a
    # assinatura (`gating.services._assinatura_autoriza_premium`).
    user = fabrica_usuario_premium(email="premium@example.com")
    user.consentimento_aceito_em = timezone.now()
    user.save(update_fields=["consentimento_aceito_em"])
    resposta = _cliente(user).post(INSCRIVER, {"tipo": "personalizada"}, format="json")
    assert resposta.status_code == 201
    assert InscricaoNewsletter.objects.get(user=user).tipo == "personalizada"


def test_delete_desativa_a_inscricao_e_responde_204():
    user = _consentido("cancela@example.com")
    cliente = _cliente(user)
    cliente.post(INSCRIVER, {"tipo": "padrao"}, format="json")

    resposta = cliente.delete(INSCRIVER)

    assert resposta.status_code == 204
    assert resposta.content == b""
    assert InscricaoNewsletter.objects.get(user=user).ativa is False


def test_delete_de_quem_nao_tem_inscricao_responde_204():
    """Idempotente: não ter inscrição não é erro, e a resposta não diz se havia
    uma (esta resposta é só para o próprio titular autenticado, mas a
    consistência é a mesma do descadastro por token)."""
    user = _consentido("sem-inscricao@example.com")
    assert _cliente(user).delete(INSCRIVER).status_code == 204


# ---------------------------------------------------------------------------
# Rate limit — escopo `escrita_publica`
# ---------------------------------------------------------------------------


def test_descadastrar_respeita_o_limite_de_escrita_publica(cache_para_throttle):
    """O endpoint `AllowAny` que valida um segredo é o que o limite protege de
    verdade. Faz este teste falhar: remover `throttle_classes` das views."""
    limite = _limite_configurado()
    cliente = APIClient()

    respostas = [
        cliente.post(DESCADASTRAR, {"token": f"chute-{i}"}, format="json")
        for i in range(limite + 5)
    ]
    codigos = [r.status_code for r in respostas]

    assert 429 in codigos, f"nenhum 429 em {limite + 5} requisições: sem rate limit"
    assert codigos[:limite] == [200] * limite, (
        f"o limite só valeu depois de {limite + 1} requisições: {codigos}"
    )
    barrado = next(r for r in respostas if r.status_code == 429)
    assert barrado["Retry-After"], "429 sem Retry-After: o cliente não sabe quando voltar"


def test_limite_do_descadastrar_e_o_mesmo_da_lista_de_espera(cache_para_throttle):
    """Mesma classe, mesmo escopo, mesma taxa: um único regulador para toda a
    escrita pública anônima, como `landing/` e `contato/`."""
    from landing.views import ListaEsperaView
    from newsletter.views import DescadastrarView

    assert DescadastrarView.throttle_classes == ListaEsperaView.throttle_classes
    assert DescadastrarView.throttle_classes[0].scope == "escrita_publica"


def test_limite_tambem_esta_declarado_na_inscricao():
    """Declarado nas DUAS views, pelo mesmo motivo dos outros pontos de escrita
    pública do projeto: `EscritaPublicaAnonThrottle` só conta cliente anônimo, e
    o dia em que `/inscrever/` virar pública (o que o próprio frontend prevê) o
    limite precisa já estar lá."""
    from newsletter.views import InscreverView

    assert InscreverView.throttle_classes[0].scope == "escrita_publica"


def test_login_nao_e_afetado_pelo_limite_de_escrita_publica(cache_para_throttle):
    """Honestidade sobre o alcance: `AnonRateThrottle` não conta usuário
    autenticado, então quem tem conta não é barrado por este limite. O teste
    registra esse fato para ninguém concluir depois que o `/inscrever/` está
    limitado por IP."""
    user = _consentido("muitos@example.com")
    cliente = _cliente(user)
    limite = _limite_configurado()
    codigos = [
        cliente.post(INSCRIVER, {"tipo": "padrao"}, format="json").status_code
        for _ in range(limite + 5)
    ]
    assert 429 not in codigos, "usuário autenticado foi barrado por um throttle de anônimo"
    assert set(codigos) == {201, 200}


def test_descadastrar_anonimo_continua_200_abaixo_do_limite(cache_para_throttle):
    """O limite não pode estragar o caso legítimo."""
    inscricao = services.inscrever(
        _consentido("abaixo-limite@example.com"), InscricaoNewsletter.TIPO_PADRAO
    )
    resposta = APIClient().post(
        DESCADASTRAR, {"token": gerar_token_descadastro(inscricao)}, format="json"
    )
    assert resposta.status_code == 200
    inscricao.refresh_from_db()
    assert inscricao.ativa is False


# ---------------------------------------------------------------------------
# A rota é a que o frontend chama
# ---------------------------------------------------------------------------


def test_rotas_expostas():
    from django.urls import resolve

    assert resolve("/api/newsletter/inscrever/").url_name == "inscrever"
    assert resolve("/api/newsletter/descadastrar/").url_name == "descadastrar"


def test_view_de_descadastrar_e_publica_e_a_de_inscrever_nao():
    """`frontend/app/newsletter/NewsletterForm.tsx:23-31` registra que o caminho
    público é a lista de espera, porque `/inscrever/` exige token. A trava não
    pode afrouxar sem o frontend acompanhar."""
    from newsletter.views import DescadastrarView, InscreverView
    from rest_framework.permissions import AllowAny, IsAuthenticated

    assert InscreverView.permission_classes == [IsAuthenticated]
    assert DescadastrarView.permission_classes == [AllowAny]
