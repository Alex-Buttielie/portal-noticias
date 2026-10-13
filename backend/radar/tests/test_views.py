"""Testes das views do Radar (R-02/R-03, run 20261013-1048-home-radar-central-ux).

Cobrem o transporte HTTP (status, parsing de `lat`/`lon`, gating) que os
testes de `services` em `test_sanity.py` não exercitam — o módulo de
serviço já é coberto diretamente ali.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from catalogo_noticias.models import NewsItem
from config.settings import REST_FRAMEWORK
from config.throttling import EnderecosAnonThrottle
from gating.models import ConfiguracaoSistema, FeatureLimit
from radar.views import NoticiasView, TendenciasView

pytestmark = pytest.mark.django_db

User = get_user_model()

# code-review-contract.md (Finding 1, major): `TendenciasView`/`NoticiasView`
# são AllowAny e resolvem `estado` como texto livre via egress real ao
# Nominatim (`enderecos.services.resolver_uf`) sem nenhum throttle —
# verificação de que o mitigante do projeto (`EnderecosAnonThrottle`, já
# usado por todo `enderecos/views.py` pelo mesmo motivo) foi aplicado.
_LOCMEM_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-radar-throttling-locmem",
    }
}


def _limite_configurado() -> int:
    num, _, _periodo = REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["enderecos"].partition("/")
    return int(num)


@pytest.fixture
def cache_locmem_isolado(settings):
    # Mesma técnica de `contato/tests/test_throttle.py` — isola o balde do
    # throttle num LocMemCache só para este teste, sem depender de Redis
    # estar rodando no ambiente (o cache default do projeto ignora falhas
    # de conexão, o que tornaria o throttle silenciosamente inerte).
    settings.CACHES = _LOCMEM_CACHES
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _premium_ativo_para_gating():
    ConfiguracaoSistema.objects.update_or_create(pk=1, defaults={"premium_ativo": True})


def _item(titulo, categoria="geral", estado="", pais=""):
    return NewsItem.objects.create(
        titulo=titulo,
        resumo_proprio="Resumo",
        conteudo_bruto="Bruto",
        url_fonte_original=f"https://g1/{titulo}",
        nome_fonte="G1",
        categoria=categoria,
        pais=pais,
        estado=estado,
        status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
    )


def test_tendencias_view_sem_filtro():
    _item("A", "esportes", estado="SP")
    client = APIClient()
    resp = client.get("/api/radar/tendencias/")
    assert resp.status_code == 200
    assert resp.json()["assuntos_em_alta"]


def test_tendencias_view_filtra_por_estado_e_ignora_lat_lon_invalidos():
    _item("A", "esportes", estado="SP")
    _item("B", "esportes", estado="RJ")
    client = APIClient()
    resp = client.get("/api/radar/tendencias/?estado=SP&lat=not-a-number&lon=")
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["localidade"]["estado"] == "SP"
    total = sum(a["numero_noticias"] for a in dados["assuntos_em_alta"])
    assert total == 1


def test_tendencias_view_estado_nao_resolvivel_devolve_200_vazio(monkeypatch):
    from enderecos import services as enderecos_services

    monkeypatch.setattr(enderecos_services, "resolver_uf", lambda texto: None)
    client = APIClient()
    resp = client.get("/api/radar/tendencias/?estado=Localidade+Inexistente")
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["assuntos_em_alta"] == []
    assert dados["erro_localidade"]


def test_tendencias_view_com_coordenada_ordena_por_distancia():
    _item("A", "esportes", estado="SP")
    for i in range(3):
        _item(f"B{i}", "politica", estado="AM")
    client = APIClient()
    resp = client.get("/api/radar/tendencias/?lat=-23.5505&lon=-46.6333")
    assert resp.status_code == 200
    categorias = [a["categoria"] for a in resp.json()["assuntos_em_alta"]]
    assert categorias[0] == "esportes"


def test_evolucao_view_exige_autenticacao():
    client = APIClient()
    resp = client.get("/api/radar/evolucao/")
    assert resp.status_code == 401


def test_evolucao_view_gated_para_free():
    usuario_free = User.objects.create_user(email="free-radar-view@example.com", password="senha123", papel="free")
    FeatureLimit.objects.update_or_create(chave="radar_avancado", plano="free", defaults={"valor": "false"})
    client = APIClient()
    client.force_authenticate(user=usuario_free)
    resp = client.get("/api/radar/evolucao/")
    assert resp.status_code == 403


def test_evolucao_view_libera_para_premium(fabrica_usuario_premium):
    usuario_premium = fabrica_usuario_premium(email="premium-radar-view@example.com")
    FeatureLimit.objects.update_or_create(chave="radar_avancado", plano="premium", defaults={"valor": "true"})
    _item("A", "esportes", estado="SP")
    client = APIClient()
    client.force_authenticate(user=usuario_premium)
    resp = client.get("/api/radar/evolucao/?estado=SP")
    assert resp.status_code == 200
    assert "serie" in resp.json()


def test_evolucao_view_estado_nao_resolvivel_devolve_200_vazio(monkeypatch, fabrica_usuario_premium):
    from enderecos import services as enderecos_services

    monkeypatch.setattr(enderecos_services, "resolver_uf", lambda texto: None)
    usuario_premium = fabrica_usuario_premium(email="premium-radar-view2@example.com")
    FeatureLimit.objects.update_or_create(chave="radar_avancado", plano="premium", defaults={"valor": "true"})
    client = APIClient()
    client.force_authenticate(user=usuario_premium)
    resp = client.get("/api/radar/evolucao/?estado=Localidade+Inexistente")
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["serie"] == []
    assert dados["erro_localidade"]


def test_noticias_view_filtra_e_pagina():
    _item("Notícia de SP", "esportes", estado="SP")
    _item("Notícia do RJ", "esportes", estado="RJ")
    client = APIClient()
    resp = client.get("/api/radar/noticias/?estado=SP&limite=5&periodo_dias=10")
    assert resp.status_code == 200
    dados = resp.json()
    assert len(dados["itens"]) == 1
    assert dados["itens"][0]["estado"] == "SP"
    assert dados["ordenado_por"] == "recencia"


def test_noticias_view_com_coordenada_ordena_por_distancia():
    _item("Notícia perto", "geral", estado="SP")
    _item("Notícia longe", "geral", estado="AM")
    client = APIClient()
    resp = client.get("/api/radar/noticias/?lat=-23.5505&lon=-46.6333")
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["ordenado_por"] == "distancia"
    assert dados["itens"][0]["estado"] == "SP"


def test_noticias_view_limite_e_periodo_invalidos_caem_no_default():
    _item("A", "geral", estado="SP")
    client = APIClient()
    resp = client.get("/api/radar/noticias/?limite=abc&periodo_dias=xyz")
    assert resp.status_code == 200


def test_localidades_salvas_view_crud():
    usuario = User.objects.create_user(email="localidades-view@example.com", password="senha123", papel="free")
    client = APIClient()
    client.force_authenticate(user=usuario)

    resp = client.post("/api/radar/localidades-salvas/", {"estado": "GO", "cidade": "Trindade"}, format="json")
    assert resp.status_code == 201

    resp = client.get("/api/radar/localidades-salvas/")
    assert resp.status_code == 200
    assert any(loc["estado"] == "GO" for loc in resp.json())

    resp = client.delete("/api/radar/localidades-salvas/", {"estado": "GO", "cidade": "Trindade"}, format="json")
    assert resp.status_code == 204


def test_para_voce_regional_view():
    _item("A", "esportes", estado="SP")
    client = APIClient()
    resp = client.get("/api/radar/para-voce/?estado=SP")
    assert resp.status_code == 200
    assert "secoes" in resp.json()


# ---------------------------------------------------------------------------
# code-review-contract.md Finding 1 (major) — throttle das views públicas
# que resolvem `estado` em texto livre via egress externo (Nominatim).
# ---------------------------------------------------------------------------


@pytest.fixture
def sem_egress_real_ao_nominatim(monkeypatch):
    """Os testes de throttle abaixo simulam exatamente o cenário do
    finding (string de `estado` variando a cada chamada, nunca resolvível
    por sigla/nome conhecido) — sem isso, cada requisição bateria de
    verdade no Nominatim e o teste mediria o rate limit DELES, não o
    throttle da nossa aplicação (foi o que aconteceu na primeira versão
    deste teste: `enderecos.services:resolver-uf HTTP 429` vinha do
    upstream real, mascarando se o nosso `EnderecosAnonThrottle` estava
    funcionando). O throttle do DRF age ANTES do `.get()` da view
    executar, então mockar a resolução não interfere no que está sendo
    testado aqui.
    """
    from enderecos import services as enderecos_services

    monkeypatch.setattr(enderecos_services, "resolver_uf", lambda texto: None)


def test_tendencias_e_noticias_view_declaram_o_throttle_de_enderecos():
    """A classe aplicada é a MESMA já usada em `enderecos/views.py` para o
    mesmo risco (upstream externo) — sem inventar um throttle novo/paralelo.
    """
    assert TendenciasView.throttle_classes == [EnderecosAnonThrottle]
    assert NoticiasView.throttle_classes == [EnderecosAnonThrottle]
    assert EnderecosAnonThrottle.scope == "enderecos"


def test_tendencias_view_com_estado_variando_ainda_dispara_429(cache_locmem_isolado, sem_egress_real_ao_nominatim):
    """Cenário de falha descrito no finding: um cliente varia a string de
    `estado` a cada chamada (o cache de resolução é por texto exato, então
    strings diferentes nunca compartilham cache) — mesmo assim, o throttle
    por IP deve contar as requisições e bloquear a partir do limite
    configurado, já que a identidade do balde é por IP, não pelo texto de
    `estado`.
    """
    limite = _limite_configurado()
    client = APIClient()

    respostas = [
        client.get(f"/api/radar/tendencias/?estado=Localidade+Aleatoria+{i}").status_code
        for i in range(limite)
    ]
    assert 429 not in respostas, respostas

    excedente = client.get("/api/radar/tendencias/?estado=Localidade+Aleatoria+excedente")
    assert excedente.status_code == 429, excedente.data
    assert "Retry-After" in excedente.headers


def test_noticias_view_com_estado_variando_ainda_dispara_429(cache_locmem_isolado, sem_egress_real_ao_nominatim):
    limite = _limite_configurado()
    client = APIClient()

    respostas = [
        client.get(f"/api/radar/noticias/?estado=Localidade+Aleatoria+{i}").status_code
        for i in range(limite)
    ]
    assert 429 not in respostas, respostas

    excedente = client.get("/api/radar/noticias/?estado=Localidade+Aleatoria+excedente")
    assert excedente.status_code == 429, excedente.data


def test_throttle_de_radar_e_por_ip_nao_global(cache_locmem_isolado, sem_egress_real_ao_nominatim):
    """Outro IP tem o próprio balde — confirma que o throttle não derruba
    tráfego legítimo de um IP diferente (mesma garantia já coberta para
    `enderecos`/`contato`, verificada aqui para o novo uso em `radar`).
    """
    limite = _limite_configurado()
    primeiro = APIClient()
    for i in range(limite):
        primeiro.get(f"/api/radar/tendencias/?estado=X{i}", REMOTE_ADDR="10.0.1.1")
    barrado = primeiro.get("/api/radar/tendencias/?estado=Xbarrado", REMOTE_ADDR="10.0.1.1")
    assert barrado.status_code == 429

    segundo = APIClient()
    livre = segundo.get("/api/radar/tendencias/?estado=Y", REMOTE_ADDR="10.0.1.2")
    assert livre.status_code == 200
