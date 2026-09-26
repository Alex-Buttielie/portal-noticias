"""Rate limit de `POST /api/contato/` — o mesmo padrão do resto do projeto.

`contato` reusa `EscritaPublicaAnonThrottle` (`config/throttling.py:24-34`), o
mesmo escopo `escrita_publica` (20/min por padrão, `config/settings.py:371`)
usado por cadastro, lista de espera e criação de publicação. Este arquivo
verifica as duas metades dessa afirmação:

  1. a VEZ que a classe é aplicada (`test_contato_reusa_o_escopo_do_projeto`);
  2. o COMPORTAMENTO de 429 (classe anônima, por IP, com `Retry-After`).

Isolamento de cache: mesma técnica de `config/tests/test_throttling.py` — o
cache default do projeto é Redis com `IGNORE_EXCEPTIONS=True`, que sem Redis
rodando tornaria o throttle INERTE e o teste passaria sem provar nada. Aqui o
cache é trocado por `LocMemCache` isolado só durante o teste, via a fixture
`settings` do pytest-django (que reverte ao final).
"""

from __future__ import annotations

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from config.settings import REST_FRAMEWORK
from config.throttling import EscritaPublicaAnonThrottle
from contato.tests.backends import EntregaSimuladaBackend, caminho_de
from contato.views import ContatoView

pytestmark = pytest.mark.django_db

URL = "/api/contato/"
DESTINO = "redacao@exemplo.org"
BACKEND_QUE_ENTREGA = caminho_de(EntregaSimuladaBackend)

_LOCMEM_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-contato-throttling-locmem",
    }
}


def _limite_configurado() -> int:
    """Lê `DEFAULT_THROTTLE_RATES['escrita_publica']` (20/min por padrão)."""
    num, _, _periodo = REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["escrita_publica"].partition("/")
    return int(num)


@pytest.fixture(autouse=True)
def _limpa_registro_de_entregas():
    EntregaSimuladaBackend.entregues.clear()
    yield
    EntregaSimuladaBackend.entregues.clear()


@pytest.fixture
def cache_locmem_isolado(settings):
    settings.CACHES = _LOCMEM_CACHES
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def canal_entregando(settings):
    settings.EMAIL_BACKEND = BACKEND_QUE_ENTREGA
    settings.CONTATO_DESTINO = DESTINO
    return settings


def test_contato_reusa_o_escopo_do_projeto():
    """Sem escopo novo: um regulador só, e a taxa já documentada do projeto."""
    assert ContatoView.throttle_classes == [EscritaPublicaAnonThrottle]
    assert EscritaPublicaAnonThrottle.scope == "escrita_publica"
    # A taxa segue a mesma chave já usada por cadastro/lista de espera, então
    # `THROTTLE_ESCRITA_PUBLICA_RATE` continua sendo o único ajuste possível.
    assert "escrita_publica" in REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]


class TestRateLimitPorIp:
    def test_excede_limite_configurado_responde_429(self, canal_entregando, cache_locmem_isolado):
        limite = _limite_configurado()
        client = APIClient()

        dentro_do_limite = [
            client.post(URL, {"nome": f"Leitor {i}", "email": f"l{i}@exemplo.com", "mensagem": "Mensagem dentro do limite."}, format="json").status_code
            for i in range(limite)
        ]

        assert 429 not in dentro_do_limite, dentro_do_limite
        assert all(codigo == 200 for codigo in dentro_do_limite)

        excedente = client.post(
            URL,
            {"nome": "Excedente", "email": "excedente@exemplo.com", "mensagem": "Mensagem que passa do limite."},
            format="json",
        )

        assert excedente.status_code == 429, excedente.data
        assert "Retry-After" in excedente.headers
        # O bloqueio acontece ANTES do envio: nenhuma mensagem a mais foi
        # entregue ao provedor.
        assert len(EntregaSimuladaBackend.entregues) == limite

    def test_limite_e_por_ip(self, canal_entregando, cache_locmem_isolado):
        """Outro IP tem o próprio balde — o limite não é global."""
        limite = _limite_configurado()
        primeiro = APIClient()
        primeiro.post(URL, {"nome": "A", "email": "a@exemplo.com", "mensagem": "Mensagem do primeiro IP."}, format="json", REMOTE_ADDR="10.0.0.1")
        for i in range(limite - 1):
            primeiro.post(URL, {"nome": f"A{i}", "email": f"a{i}@exemplo.com", "mensagem": "Mensagem do primeiro IP."}, format="json", REMOTE_ADDR="10.0.0.1")
        barrado = primeiro.post(URL, {"nome": "A", "email": "a2@exemplo.com", "mensagem": "Mensagem do primeiro IP."}, format="json", REMOTE_ADDR="10.0.0.1")
        assert barrado.status_code == 429

        segundo = APIClient()
        livre = segundo.post(URL, {"nome": "B", "email": "b@exemplo.com", "mensagem": "Mensagem do segundo IP."}, format="json", REMOTE_ADDR="10.0.0.2")

        assert livre.status_code == 200
