"""
CACHE ISOLADO POR TENANT B2B (backlog P1-13, workstream WS-12).

O painel cacheia a coisa mais cara do app: uma varredura de `NewsItem` por
critério ativo, materializada em memória. Cachear sem namespace de tenant
seria o vazamento mais silencioso dos três eixos, porque nada no código de
negócio denunciaria: a resposta da empresa A simplesmente apareceria no
painel da empresa B.

Estes testes atacam essa hipótese de três maneiras, porque as três dão
falso-verde em testes diferentes:

1. **Estrutural** — a chave é montada por uma função que exige a organização
   como argumento posicional; não existe caminho para uma chave sem
   `org:<id>`.
2. **Empirical** — duas empresas com conteúdo idêntico, a segunda acessando
   em cache MISS: o nome da organização e os ids dos critérios do payload
   têm que ser os DELE, e não os da outra. Conteúdo igual de propósito: só o
   namespace da chave decide.
3. **Contagem de queries** — o cache é real (locmem) e prova que a segunda
   leitura NÃO toca o banco, senão um cache que não cacheia também "passa"
   no teste 2.

O cache da suíte geral é `DummyCache` (ver `config/settings_test.py`); aqui
ele é religado com `override_settings`, mesmo padrão de
`feed/tests/test_p1_feed_cache_indices.py`.
"""

from __future__ import annotations

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from rest_framework.test import APIClient

from b2b import cache as cache_b2b
from b2b import services
from b2b.models import Organizacao
from catalogo_noticias.models import NewsItem

pytestmark = pytest.mark.django_db

CACHE_LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "p1-13-b2b-cache",
    }
}


@pytest.fixture
def cache_locmem():
    with override_settings(CACHES=CACHE_LOCMEM):
        cache.clear()
        yield cache
        cache.clear()


def _usuario(email):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(email=email, password="senha123", papel="free")


def _noticia(titulo, url):
    return NewsItem.objects.create(
        titulo=titulo,
        resumo_proprio="Resumo.",
        conteudo_bruto="Conteudo bruto longo o bastante para o modelo de resumo.",
        url_fonte_original=url,
        nome_fonte="G1",
        categoria="economia",
        status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
    )


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ---------------------------------------------------------------------------
# 1. Estrutural: nenhuma chave sem o namespace do tenant
# ---------------------------------------------------------------------------


def test_chave_exige_organizacao_persistida(cache_locmem):
    """
    `chave_organizacao` não tem como produzir chave sem `org:<id>`: a
    organização é posicional, e uma instância sem `pk` (não persistida) é
    recusada em vez de gerar `org:None` — que seria uma chave COMPARTILHADA
    por todas as organizações não persistidas.
    """
    with pytest.raises(ValueError):
        cache_b2b.chave_organizacao(Organizacao(nome="x"), "itens-monitorados", 30)

    org = services.criar_organizacao("Empresa Alfa", Organizacao.PLANO_ENTERPRISE)
    chave = cache_b2b.chave_organizacao(org, "itens-monitorados", 30)
    assert chave == f"b2b:v1:org:{org.pk}:itens-monitorados:30"


def test_toda_chave_do_app_carrega_o_id_da_organizacao(cache_locmem):
    """
    Varredura por construção, não por convenção: para as duas organizações,
    todas as combinações de recurso/janela que o app usa, a chave contém
    `org:<id da própria org>` e NENHUM outro id de organização.
    """
    org_a = services.criar_organizacao("Alfa", Organizacao.PLANO_ENTERPRISE)
    org_b = services.criar_organizacao("Beta", Organizacao.PLANO_ENTERPRISE)

    chaves_a = [
        cache_b2b.chave_organizacao(org_a, recurso, dias)
        for recurso in (cache_b2b.RECURSO_ITENS_MONITORADOS, cache_b2b.RECURSO_RESUMO_EXECUTIVO)
        for dias in (7, 30, 90)
    ]
    chaves_b = [
        cache_b2b.chave_organizacao(org_b, recurso, dias)
        for recurso in (cache_b2b.RECURSO_ITENS_MONITORADOS, cache_b2b.RECURSO_RESUMO_EXECUTIVO)
        for dias in (7, 30, 90)
    ]

    assert chaves_a and not set(chaves_a) & set(chaves_b)
    for chave in chaves_a:
        assert f"org:{org_a.pk}" in chave
        assert f"org:{org_b.pk}" not in chave
    for chave in chaves_b:
        assert f"org:{org_b.pk}" in chave
        assert f"org:{org_a.pk}" not in chave


def test_invalidar_organizacao_nao_apaga_o_cache_da_outra(cache_locmem):
    org_a = services.criar_organizacao("Alfa", Organizacao.PLANO_ENTERPRISE)
    org_b = services.criar_organizacao("Beta", Organizacao.PLANO_ENTERPRISE)
    cache_b2b.gravar(org_a, cache_b2b.RECURSO_RESUMO_EXECUTIVO, {"organizacao": "Alfa"}, 30)
    cache_b2b.gravar(org_b, cache_b2b.RECURSO_RESUMO_EXECUTIVO, {"organizacao": "Beta"}, 30)

    cache_b2b.invalidar_organizacao(org_a)

    assert cache_b2b.ler(org_a, cache_b2b.RECURSO_RESUMO_EXECUTIVO, 30) is None
    assert cache_b2b.ler(org_b, cache_b2b.RECURSO_RESUMO_EXECUTIVO, 30) == {"organizacao": "Beta"}


# ---------------------------------------------------------------------------
# 2 + 3. Empírico: o payload de B nunca é o de A, e o cache funciona mesmo
# ---------------------------------------------------------------------------


def test_painel_de_b_nao_serve_o_payload_cacheado_de_a(cache_locmem):
    """
    Alfa e Beta têm o MESMO critério ("acordo") e as MESMAS notícias. Alfa
    abre o painel primeiro (populando o cache). Beta abre depois: se a chave não
    carregasse o tenant, Beta receberia o dicionário com a chave do critério
    de Alfa e veria o nome da empresa Alfa.
    """
    admin_a = _usuario("cache-admin-a@example.com")
    admin_b = _usuario("cache-admin-b@example.com")
    org_a = services.criar_organizacao_com_admin("Empresa Alfa", admin_a, Organizacao.PLANO_ENTERPRISE)
    org_b = services.criar_organizacao_com_admin("Empresa Beta", admin_b, Organizacao.PLANO_ENTERPRISE)
    criterio_a = services.criar_criterio(org_a, "palavra_chave", "acordo")
    criterio_b = services.criar_criterio(org_b, "palavra_chave", "acordo")
    _noticia("Acordo assinado", "https://g1/cache-acordo-1")

    # Alfa primeiro: popula o cache.
    resumo_a = _client(admin_a).get("/api/b2b/resumo-executivo/").json()
    assert resumo_a["organizacao"] == "Empresa Alfa"

    # Beta: tem que ser MISS e vir do próprio banco.
    itens_b = _client(admin_b).get("/api/b2b/itens-monitorados/").json()
    assert set(itens_b.keys()) == {str(criterio_b.id)}
    assert str(criterio_a.id) not in itens_b

    resumo_b = _client(admin_b).get("/api/b2b/resumo-executivo/").json()
    assert resumo_b["organizacao"] == "Empresa Beta"
    assert "Empresa Alfa" not in str(resumo_b)


def test_segunda_leitura_nao_toca_o_banco_e_cache_por_organizacao(cache_locmem):
    """O cache é real: prova por contagem de queries, senão o teste acima é vazio."""
    admin_a = _usuario("cache2-admin-a@example.com")
    admin_b = _usuario("cache2-admin-b@example.com")
    org_a = services.criar_organizacao_com_admin("Empresa Alfa", admin_a, Organizacao.PLANO_ENTERPRISE)
    org_b = services.criar_organizacao_com_admin("Empresa Beta", admin_b, Organizacao.PLANO_ENTERPRISE)
    services.criar_criterio(org_a, "palavra_chave", "acordo")
    services.criar_criterio(org_b, "palavra_chave", "acordo")
    _noticia("Acordo assinado", "https://g1/cache2-acordo-1")

    client_a, client_b = _client(admin_a), _client(admin_b)

    def _queries_de_painel(capturadas):
        """Só as consultas que o painel dispara: NewsItem e critérios.

        A resolução do tenant por request (`organizacao_do_usuario` +
        `permissions.pode`) é contabilizada à parte, e é o motivo de não
        afirmar "zero queries" — o que interessa é que a varredura cara, a
        que o cache existe para evitar, não ocorra.
        """
        return [
            q
            for q in capturadas
            if "catalogo_noticias_newsitem" in q["sql"] or "b2b_criteriomonitoramento" in q["sql"]
        ]

    # Fria: Alfa varre o acervo.
    with CaptureQueriesContext(connection) as frias_a:
        client_a.get("/api/b2b/resumo-executivo/")
    assert _queries_de_painel(frias_a.captured_queries), "a leitura fria deveria varrer o painel"

    # Quente: Alfa não varre.
    with CaptureQueriesContext(connection) as quentes_a:
        client_a.get("/api/b2b/resumo-executivo/")
    assert _queries_de_painel(quentes_a.captured_queries) == []

    # Beta é outra chave: a PRIMEIRA leitura dela ainda varre, mesmo com o
    # cache de Alfa quente. É esta asserção que morre se o id da organização
    # sair da chave.
    with CaptureQueriesContext(connection) as frias_b:
        client_b.get("/api/b2b/resumo-executivo/")
    assert _queries_de_painel(frias_b.captured_queries), (
        "a leitura de Beta não deveria aproveitar o cache de Alfa"
    )


def test_cache_guarda_e_devolve_o_contrato_em_python_com_chave_inteira(cache_locmem):
    """
    O dicionário de `itens_monitorados` é indexado por id INTEIRO no contrato
    em Python (o JSON entrega string). A conversão acontece na fronteira do
    cache; sem ela, `resultado[criterio.id]` deixaria de funcionar para quem
    consome o serviço — que é o que o contrato já fazia.
    """
    admin = _usuario("cache3-admin@example.com")
    org = services.criar_organizacao_com_admin("Empresa Alfa", admin, Organizacao.PLANO_ENTERPRISE)
    criterio = services.criar_criterio(org, "palavra_chave", "acordo")
    _noticia("Acordo assinado", "https://g1/cache3-acordo-1")

    frio = services.itens_monitorados(org)
    quente = services.itens_monitorados(org)  # agora vem do cache

    assert set(quente.keys()) == {criterio.id}
    assert all(isinstance(chave, int) for chave in quente.keys())
    assert quente[criterio.id]["total_itens"] == frio[criterio.id]["total_itens"]
    assert quente[criterio.id]["itens"] == frio[criterio.id]["itens"]


# ---------------------------------------------------------------------------
# 4. Invalidação: escrita da organização descarta o próprio painel
# ---------------------------------------------------------------------------


def test_criar_criterio_invalida_o_painel_da_organizacao(cache_locmem):
    admin = _usuario("cache4-admin-a@example.com")
    outra = _usuario("cache4-admin-b@example.com")
    org = services.criar_organizacao_com_admin("Empresa Alfa", admin, Organizacao.PLANO_ENTERPRISE)
    org_outra = services.criar_organizacao_com_admin("Empresa Beta", outra, Organizacao.PLANO_ENTERPRISE)

    services.itens_monitorados(org)
    services.itens_monitorados(org_outra)

    services.criar_criterio(org, "palavra_chave", "energia")

    # A entrada de Alfa some (foi invalidada); a de Beta permanece.
    assert cache_b2b.ler(org, cache_b2b.RECURSO_ITENS_MONITORADOS, 30) is None
    assert cache_b2b.ler(org_outra, cache_b2b.RECURSO_ITENS_MONITORADOS, 30) is not None


def test_excluir_criterio_pela_api_invalida_o_painel(cache_locmem):
    from b2b.models import CriterioMonitoramento

    admin = _usuario("cache5-admin@example.com")
    org = services.criar_organizacao_com_admin("Empresa Alfa", admin, Organizacao.PLANO_ENTERPRISE)
    criterio = services.criar_criterio(org, "palavra_chave", "acordo")
    _client(admin).get("/api/b2b/resumo-executivo/")
    assert cache_b2b.ler(org, cache_b2b.RECURSO_RESUMO_EXECUTIVO, 30) is not None

    resposta = _client(admin).delete(f"/api/b2b/criterios/{criterio.id}/")

    assert resposta.status_code == 204
    assert cache_b2b.ler(org, cache_b2b.RECURSO_RESUMO_EXECUTIVO, 30) is None
    assert CriterioMonitoramento.objects.filter(pk=criterio.pk).exists() is False


# ---------------------------------------------------------------------------
# 5. Fail-open: cache quebrado não é erro nem vazamento
# ---------------------------------------------------------------------------


def test_cache_quebrado_cai_para_o_banco_sem_erro(cache_locmem, monkeypatch):
    """
    Backend de cache fora do ar (Redis caiu) não pode virar 500 nem resposta
    vazia. O caminho do banco é o mesmo da organizations, então o resultado
    continua correto.
    """
    admin = _usuario("cache6-admin@example.com")
    org = services.criar_organizacao_com_admin("Empresa Alfa", admin, Organizacao.PLANO_ENTERPRISE)
    services.criar_criterio(org, "palavra_chave", "acordo")

    def _quebrado(*_args, **_kwargs):
        raise ConnectionError("redis fora")

    monkeypatch.setattr(cache_b2b.cache, "get", _quebrado)
    monkeypatch.setattr(cache_b2b.cache, "set", _quebrado)

    resumo = _client(admin).get("/api/b2b/resumo-executivo/")

    assert resumo.status_code == 200
    assert resumo.json()["organizacao"] == "Empresa Alfa"
