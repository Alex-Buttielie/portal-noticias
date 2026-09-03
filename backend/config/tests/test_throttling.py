"""
Suite do `tester` — cobre o critério de aceite 5 de
`implementation-contract.md` (run 20260903-1134-seo-lgpd-design-system,
escopo C: rate limiting): "Dado mais de N requisições anônimas ao endpoint
de cadastro/lista de espera em um intervalo curto, quando o limite
configurado é excedido, então a API responde HTTP 429."

O executor implementou `config.throttling.EscritaPublicaAnonThrottle`
(aplicada em `identidade.views.CadastroView`, `landing.views.ListaEsperaView`
e `comunidade.views.PublicacoesListCreateView`, só em POST) mas registrou
explicitamente em `implementation-history.md` que não exercitou o
comportamento com um teste real de carga (throttle depende de cache — cache
default do projeto é Redis com `IGNORE_EXCEPTIONS=True`, então sem um Redis
rodando localmente o throttle nunca de fato ativa; ver nota abaixo).

Isolamento de cache: cada teste usa a fixture `settings` do pytest-django
(que dispara corretamente o sinal `setting_changed` do Django, recriando o
`CacheHandler`) para trocar `CACHES` para `LocMemCache` (backend em memória
do próprio processo) só durante a duração do teste, e limpa explicitamente
antes de cada sequência de requisições (`cache.clear()`). Isso evita dois
problemas:
  1. Se o ambiente não tiver Redis local (como este), o backend "redis"
     padrão do projeto (`config/settings.py`, `IGNORE_EXCEPTIONS=True`)
     silenciosamente ignora erros de conexão e o throttle NUNCA bloqueia
     nada — um teste que rodasse com o cache padrão passaria "por acidente"
     sem testar nada de verdade (falso positivo).
  2. `LocMemCache` guarda estado em um dicionário global por `location` do
     processo (não por instância de config) — sem isolar/limpar, contagens
     de um teste vazariam para o próximo e poderiam causar 429 espúrio em
     outros testes da suíte completa que usam os MESMOS endpoints throttled
     (`identidade.CadastroView`, `landing.ListaEsperaView`,
     `comunidade.PublicacoesListCreateView`). Trocar `CACHES` só dentro do
     teste (via fixture `settings`, que reverte automaticamente ao final de
     cada teste) limita o efeito a este arquivo, não afetando o resto da
     suíte quando rodada em conjunto.

NOTA (rodando a suíte completa): mesmo isolado por teste, o efeito colateral
de fato ativar o throttle aqui é local a este módulo — os outros apps não
usam a fixture `settings` para CACHES, então continuam rodando com o cache
"redis com IGNORE_EXCEPTIONS" default (throttle inerte), exatamente como na
iteração anterior do executor. Isso é intencional: o objetivo aqui é validar
o comportamento de throttling, não introduzir instabilidade nos outros ~190
testes da suíte.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from config.settings import REST_FRAMEWORK

pytestmark = pytest.mark.django_db

_LOCMEM_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-throttling-locmem",
    }
}


def _limite_configurado() -> int:
    """Lê o número inteiro de `DEFAULT_THROTTLE_RATES['escrita_publica']`
    (formato "N/min" ou "N/hour" etc — ver `rest_framework.throttling`),
    para não hardcodar o valor do limite no teste (ele é configurável via
    env `THROTTLE_ESCRITA_PUBLICA_RATE`, ver `config/settings.py`)."""
    rate = REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["escrita_publica"]
    num, _, _period = rate.partition("/")
    return int(num)


@pytest.fixture
def cache_locmem_isolado(settings):
    """Troca CACHES para um LocMemCache isolado só durante o teste (fixture
    `settings` do pytest-django reverte automaticamente ao final, disparando
    o sinal `setting_changed` que o `django.core.cache` escuta para
    recriar o `CacheHandler`)."""
    settings.CACHES = _LOCMEM_CACHES
    cache.clear()
    yield
    cache.clear()


class TestAC5RateLimitingListaEspera:
    """Endpoint `POST /api/landing/lista-espera/` (AllowAny, anônimo)."""

    def test_excede_limite_configurado_responde_429(self, cache_locmem_isolado):
        limite = _limite_configurado()
        client = APIClient()

        respostas = []
        for i in range(limite):
            resposta = client.post(
                "/api/landing/lista-espera/",
                {
                    "nome": f"Usuario {i}",
                    "email": f"throttle-lista-{i}@example.com",
                    "aceite_comunicacao": True,
                },
                format="json",
            )
            respostas.append(resposta.status_code)

        # Nenhuma das N requisições dentro do limite deve ter sido barrada
        # por throttling (podem existir 201 ou, em tese, 400 por outro
        # motivo de validação — mas nunca 429 antes de exceder o limite).
        assert 429 not in respostas, (
            f"Requisição barrada por throttling antes de atingir o limite "
            f"configurado ({limite}): respostas={respostas}"
        )

        # A requisição N+1 deve ser barrada.
        resposta_excedente = client.post(
            "/api/landing/lista-espera/",
            {
                "nome": "Usuario excedente",
                "email": "throttle-lista-excedente@example.com",
                "aceite_comunicacao": True,
            },
            format="json",
        )
        assert resposta_excedente.status_code == 429, (
            f"Esperado 429 após exceder o limite de {limite} requisições "
            f"anônimas, obtido {resposta_excedente.status_code}: "
            f"{resposta_excedente.data}"
        )
        # DRF inclui Retry-After no cabeçalho de uma resposta throttled.
        assert "Retry-After" in resposta_excedente.headers

        # Confirma que o registro que gerou o 429 NÃO foi persistido (o
        # throttle bloqueou antes do handler da view rodar).
        from landing.models import InscricaoListaEspera

        assert not InscricaoListaEspera.objects.filter(
            email="throttle-lista-excedente@example.com"
        ).exists()


class TestAC5RateLimitingCadastro:
    """Endpoint `POST /api/auth/cadastro/` (AllowAny, anônimo) — segundo
    endpoint citado explicitamente no critério de aceite 5 ("cadastro/lista
    de espera")."""

    def test_excede_limite_configurado_responde_429(self, cache_locmem_isolado):
        limite = _limite_configurado()
        client = APIClient()

        respostas = []
        for i in range(limite):
            resposta = client.post(
                "/api/auth/cadastro/",
                {
                    "email": f"throttle-cadastro-{i}@example.com",
                    "nome": f"Usuario {i}",
                    "senha": "SenhaForte123",
                    "aceite_termos": True,
                },
                format="json",
            )
            respostas.append(resposta.status_code)

        assert 429 not in respostas, (
            f"Requisição barrada por throttling antes de atingir o limite "
            f"configurado ({limite}): respostas={respostas}"
        )

        resposta_excedente = client.post(
            "/api/auth/cadastro/",
            {
                "email": "throttle-cadastro-excedente@example.com",
                "nome": "Excedente",
                "senha": "SenhaForte123",
                "aceite_termos": True,
            },
            format="json",
        )
        assert resposta_excedente.status_code == 429, (
            f"Esperado 429 após exceder o limite de {limite} requisições "
            f"anônimas, obtido {resposta_excedente.status_code}: "
            f"{resposta_excedente.data}"
        )

        User = get_user_model()
        assert not User.objects.filter(email="throttle-cadastro-excedente@example.com").exists()


class TestAC5RateLimitingNaoAfetaUsuarioAutenticado:
    """`AnonRateThrottle` só deve contar/bloquear requisições NÃO
    autenticadas — documentado em `config/throttling.py`. Este teste garante
    que o comportamento documentado é real: um usuário autenticado
    continua conseguindo usar o endpoint de escrita pública (comunidade)
    mesmo depois de o "balde" anônimo estar cheio, porque ele usa uma chave
    de cache diferente (por usuário, não por IP)."""

    def test_usuario_autenticado_nao_e_bloqueado_pelo_throttle_anonimo(self, cache_locmem_isolado):
        User = get_user_model()
        limite = _limite_configurado()

        # Esgota o limite anônimo em landing/lista-espera (endpoint só
        # anônimo, sem alternativa autenticada, serve só para encher o
        # balde do IP do APIClient de teste).
        anon_client = APIClient()
        for i in range(limite):
            anon_client.post(
                "/api/landing/lista-espera/",
                {
                    "nome": f"Usuario {i}",
                    "email": f"throttle-isolamento-{i}@example.com",
                    "aceite_comunicacao": True,
                },
                format="json",
            )
        resposta_bloqueada = anon_client.post(
            "/api/landing/lista-espera/",
            {
                "nome": "Bloqueado",
                "email": "throttle-isolamento-bloqueado@example.com",
                "aceite_comunicacao": True,
            },
            format="json",
        )
        assert resposta_bloqueada.status_code == 429

        # Um usuário autenticado batendo em outro endpoint com o mesmo
        # throttle (comunidade, POST) não deve ser afetado pelo balde
        # anônimo acima esgotado (chave de cache diferente).
        user = User.objects.create_user(
            email="autenticado@example.com", nome="Autenticado", password="SenhaForte123"
        )
        token, _ = Token.objects.get_or_create(user=user)
        auth_client = APIClient()
        auth_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        resposta_autenticada = auth_client.post(
            "/api/comunidade/publicacoes/",
            {
                "titulo": "Publicação de teste",
                "conteudo": "Conteúdo de teste do usuário autenticado.",
                "tipo": "opiniao",
            },
            format="json",
        )
        # 403 é esperado (usuário não é jornalista credenciado — fora do
        # escopo deste teste) — o que importa é que NÃO seja 429: a
        # requisição passou pelo throttle e chegou até a lógica de negócio.
        assert resposta_autenticada.status_code != 429, (
            f"Usuário autenticado foi bloqueado pelo throttle anônimo "
            f"(esperado: chave de cache separada por usuário, não por IP): "
            f"{resposta_autenticada.status_code} {resposta_autenticada.data}"
        )
