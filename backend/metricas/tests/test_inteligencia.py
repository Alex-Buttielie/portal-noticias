"""FRENTE 6 — Central de Inteligência: ingestão, painel e overrides."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from catalogo_noticias.models import NewsItem
from feed.models import DestaqueEditorial, EventoBusca, InteracaoNoticia
from metricas.models import EventoSite
from painel_admin.models import RegraCuradoria

pytestmark = pytest.mark.django_db

User = get_user_model()


def _admin():
    return User.objects.create_user(email="admin-intel@example.com", password="s", papel="admin")


def _free():
    return User.objects.create_user(email="free-intel@example.com", password="s", papel="free")


def _noticia(**kw):
    base = {
        "titulo": "Notícia de teste",
        "nome_fonte": "G1",
        "url_fonte_original": "https://exemplo.com/n1",
        "categoria": "economia",
        "status_revisao": NewsItem.STATUS_APROVADO,
    }
    base.update(kw)
    return NewsItem.objects.create(**base)


# --- ingestão ---------------------------------------------------------------


def test_evento_site_publico_anonimo_ok():
    client = APIClient()
    r = client.post(
        "/api/metricas/eventos/",
        {"tipo": "page_view", "path": "/", "sessao": "s1", "origem": "direto", "dispositivo": "mobile"},
        format="json",
    )
    assert r.status_code == 201
    assert EventoSite.objects.filter(tipo="page_view", sessao="s1").count() == 1


def test_evento_tipo_desconhecido_400():
    r = APIClient().post("/api/metricas/eventos/", {"tipo": "invasao_alien"}, format="json")
    assert r.status_code == 400


def test_evento_news_view_roteado_para_feed_sem_duplicar():
    item = _noticia()
    r = APIClient().post(
        "/api/metricas/eventos/",
        {"tipo": "news_view", "entry_tipo": "item", "entry_id": item.id, "sessao": "s2"},
        format="json",
    )
    assert r.status_code == 201
    assert InteracaoNoticia.objects.filter(tipo="view", item=item).count() == 1
    # Fonte única: nada vai para EventoSite.
    assert EventoSite.objects.count() == 0


def test_evento_search_roteado_para_eventobusca():
    r = APIClient().post(
        "/api/metricas/eventos/",
        {"tipo": "search", "termo": "agronegócio", "resultados": 4, "sessao": "s3"},
        format="json",
    )
    assert r.status_code == 201
    assert EventoBusca.objects.filter(query_normalizada="agronegócio").count() == 1


def test_evento_alvo_inexistente_nao_quebra():
    r = APIClient().post(
        "/api/metricas/eventos/",
        {"tipo": "news_view", "entry_tipo": "item", "entry_id": 999999, "sessao": "sx"},
        format="json",
    )
    assert r.status_code == 201
    assert r.data["registrado"] is False


# --- central -----------------------------------------------------------------


def test_inteligencia_exige_admin():
    client = APIClient()
    client.force_authenticate(user=_free())
    assert client.get("/api/metricas/inteligencia/?periodo=7d").status_code == 403


def test_inteligencia_agrega_dados_reais_e_compara():
    client = APIClient()
    EventoSite.objects.create(tipo="page_view", path="/", sessao="a", origem="direto")
    EventoSite.objects.create(tipo="page_view", path="/economia", sessao="a", origem="direto")
    EventoSite.objects.create(tipo="category_view", categoria="economia", sessao="a")
    EventoSite.objects.create(tipo="radar_view", sessao="a")
    EventoSite.objects.create(
        tipo="location_selected", sessao="a", estado="GO", cidade="Goiânia", pais="Brasil"
    )
    item = _noticia(titulo="Safra recorde", categoria="agronegócio",
                    url_fonte_original="https://exemplo.com/safra")
    for _ in range(6):
        InteracaoNoticia.objects.create(tipo="view", entry_tipo="item", item=item, categoria="agronegócio")
    InteracaoNoticia.objects.create(tipo="share", entry_tipo="item", item=item, categoria="agronegócio")
    for _ in range(4):
        EventoBusca.objects.create(query="agronegócio", query_normalizada="agronegócio", resultados=2)

    client.force_authenticate(user=_admin())
    r = client.get("/api/metricas/inteligencia/?periodo=7d")
    assert r.status_code == 200
    corpo = r.data
    assert corpo["audiencia"]["visitas"] == 2
    assert corpo["audiencia"]["sessoes"] == 1
    assert corpo["comportamento"]["radar_views"] == 1
    assert corpo["localizacao"]["estados"][0]["label"] == "GO"
    assert any(t["termo"] == "agronegócio" for t in corpo["conteudo"]["mais_pesquisadas"])
    assert corpo["conteudo"]["mais_acessadas"][0]["titulo"] == "Safra recorde"
    assert corpo["conteudo"]["mais_compartilhadas"][0]["total"] == 1
    assert len(corpo["series"]["visitas"]) == 7
    assert "delta_pct" in corpo["comparativo"]["visitas"]
    # Insights vêm de dados reais (categoria emergente agronegócio).
    assert corpo["inteligencia"]["sem_dados"] is False
    tipos = {i["tipo"] for i in corpo["inteligencia"]["itens"]}
    assert "categoria_emergente" in tipos or "busca_emergente" in tipos


def test_inteligencia_sem_dados_nao_inventa():
    client = APIClient()
    client.force_authenticate(user=_admin())
    r = client.get("/api/metricas/inteligencia/?periodo=custom&inicio=2001-01-01&fim=2001-01-02")
    assert r.status_code == 200
    assert r.data["audiencia"]["visitas"] == 0
    assert r.data["inteligencia"]["sem_dados"] is True


# --- overrides admin ----------------------------------------------------------


def test_destaque_crud_admin_e_respeitado_na_recomendacao():
    from feed import recomendacao

    item = _noticia()
    client = APIClient()
    client.force_authenticate(user=_admin())
    r = client.post(
        "/api/admin/editoriais/",
        {"tipo": "bloqueio", "entry_tipo": "item", "entry_id": item.id, "motivo": "teste"},
        format="json",
    )
    assert r.status_code == 201
    destaque_id = r.data["id"]

    _, bloqueios, _ = recomendacao.overrides_vigentes()
    assert ("item", item.id) in bloqueios

    r = client.get("/api/admin/editoriais/")
    assert r.status_code == 200
    assert any(d["id"] == destaque_id for d in r.data)

    assert client.patch(f"/api/admin/editoriais/{destaque_id}/", {"ativo": False}, format="json").status_code == 200
    _, bloqueios2, _ = recomendacao.overrides_vigentes()
    assert ("item", item.id) not in bloqueios2

    assert client.delete(f"/api/admin/editoriais/{destaque_id}/").status_code == 204
    assert not DestaqueEditorial.objects.filter(pk=destaque_id).exists()


def test_destaque_exige_alvo_real():
    client = APIClient()
    client.force_authenticate(user=_admin())
    r = client.post(
        "/api/admin/editoriais/",
        {"tipo": "manchete", "entry_tipo": "item", "entry_id": 424242},
        format="json",
    )
    assert r.status_code == 400


def test_regra_curadoria_bloqueio_e_ordem_no_feed():
    _noticia(titulo="Política A", categoria="política", url_fonte_original="https://exemplo.com/pa")
    _noticia(titulo="Esporte B", categoria="esportes", url_fonte_original="https://exemplo.com/eb")
    RegraCuradoria.objects.create(tipo="bloqueio_categoria", alvo="política")
    RegraCuradoria.objects.create(tipo="ordem_categorias", alvo="esportes, economia")

    r = APIClient().get("/api/feed/")
    assert r.status_code == 200
    titulos = [e["titulo"] for e in r.data["results"]]
    assert "Política A" not in titulos
    assert "Esporte B" in titulos


def test_regra_curadoria_boost_e_selo():
    item = _noticia(titulo="Boosted", categoria="cultura", url_fonte_original="https://exemplo.com/b1")
    _noticia(titulo="Outra", categoria="cultura", url_fonte_original="https://exemplo.com/b2")
    RegraCuradoria.objects.create(tipo="boost_entrada", entry_tipo="item", entry_id=item.id)
    RegraCuradoria.objects.create(
        tipo="selo_forcado", entry_tipo="item", entry_id=item.id, alvo="Exclusivo"
    )
    r = APIClient().get("/api/feed/")
    assert r.status_code == 200
    primeiro = r.data["results"][0]
    assert primeiro["titulo"] == "Boosted"
    assert primeiro["selo_editorial"] == "Exclusivo"


def test_regras_exigem_admin():
    client = APIClient()
    client.force_authenticate(user=_free())
    assert client.get("/api/admin/regras/").status_code == 404
    assert client.get("/api/admin/editoriais/").status_code == 404
