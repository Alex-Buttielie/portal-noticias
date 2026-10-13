from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from catalogo_noticias.models import NewsItem
from gating.models import ConfiguracaoSistema, FeatureLimit
from radar import services

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture(autouse=True)
def _premium_ativo_para_gating():
    """O teste de gating abaixo exige a flag LIGADA (com ela desligada,
    todo mundo navega como Premium)."""
    ConfiguracaoSistema.objects.update_or_create(pk=1, defaults={"premium_ativo": True})


def _item(titulo, categoria, cidade="", estado="", pais="", url=None):
    return NewsItem.objects.create(
        titulo=titulo,
        resumo_proprio="Resumo",
        conteudo_bruto="Bruto",
        url_fonte_original=url or f"https://g1/{titulo}",
        nome_fonte="G1",
        categoria=categoria,
        pais=pais,
        estado=estado,
        cidade=cidade,
        status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
    )


def test_tendencias_sem_filtro_agrega_por_categoria():
    _item("A", "esportes")
    _item("B", "esportes")
    _item("C", "politica")

    resultado = services.tendencias()

    assuntos = {a["categoria"]: a["numero_noticias"] for a in resultado["assuntos_em_alta"]}
    assert assuntos["esportes"] == 2
    assert assuntos["politica"] == 1
    assert "COBERTURA jornalística" in resultado["aviso_metodologia"]


def test_tendencias_filtra_por_estado():
    # R-02: `cidade` nunca é populada pela ingestão real — o filtro
    # geográfico que de fato funciona é por `estado` (UF).
    _item("A", "esportes", estado="SP")
    _item("B", "esportes", estado="RJ")

    resultado = services.tendencias(estado="SP")

    total = sum(a["numero_noticias"] for a in resultado["assuntos_em_alta"])
    assert total == 1
    assert resultado["localidade"]["estado"] == "SP"


def test_tendencias_resolve_estado_por_nome_de_cidade(monkeypatch):
    # "Trindade" (cidade de GO) resolvida via enderecos.resolver_uf —
    # mockado aqui porque a resolução real depende de rede (testada em
    # enderecos/tests/test_enderecos.py).
    from enderecos import services as enderecos_services

    monkeypatch.setattr(enderecos_services, "resolver_uf", lambda texto: "GO" if texto == "Trindade" else None)
    _item("A", "esportes", estado="GO")
    _item("B", "esportes", estado="SP")

    resultado = services.tendencias(estado="Trindade")

    total = sum(a["numero_noticias"] for a in resultado["assuntos_em_alta"])
    assert total == 1
    assert resultado["localidade"]["estado"] == "GO"


def test_tendencias_estado_nao_resolvivel_devolve_vazio_sem_erro(monkeypatch):
    # Nunca 500, nunca estado inventado — vazio com `erro_localidade`.
    # `resolver_uf` mockado para não depender de rede (o caso real de
    # geocodificação falhando é testado em enderecos/tests/test_enderecos.py).
    from enderecos import services as enderecos_services

    monkeypatch.setattr(enderecos_services, "resolver_uf", lambda texto: None)
    resultado = services.tendencias(estado="Localidade Que Não Existe De Verdade Nenhuma")

    assert resultado["assuntos_em_alta"] == []
    assert "erro_localidade" in resultado and resultado["erro_localidade"]


def test_tendencias_ordena_por_distancia_quando_ha_coordenada(monkeypatch):
    # Sem filtro de estado (recorte nacional): cada categoria tem itens em
    # UFs diferentes — com lat/lon do usuário, a categoria cuja UF
    # representante está mais próxima vem primeiro, mesmo tendo menos
    # notícias/score do que a outra.
    _item("A", "esportes", estado="SP")  # perto de SP
    for i in range(3):
        _item(f"B{i}", "politica", estado="AM")  # Manaus, longe de SP

    lat_sp, lon_sp = -23.5505, -46.6333
    resultado = services.tendencias(lat=lat_sp, lon=lon_sp)

    categorias = [a["categoria"] for a in resultado["assuntos_em_alta"]]
    assert categorias[0] == "esportes"
    assert resultado["assuntos_em_alta"][0]["distancia_km"] is not None
    assert resultado["assuntos_em_alta"][0]["distancia_km"] < resultado["assuntos_em_alta"][1]["distancia_km"]


def test_tendencias_sem_coordenada_mantem_ordenacao_por_score():
    _item("A", "esportes", estado="SP")
    for i in range(3):
        _item(f"B{i}", "politica", estado="AM")

    resultado = services.tendencias()

    # Sem lat/lon, não há `distancia_km` nos resultados (comportamento
    # atual preservado).
    assert all("distancia_km" not in a for a in resultado["assuntos_em_alta"])


def test_evolucao_interesse_filtra_por_estado():
    _item("A", "esportes", estado="SP")
    _item("B", "esportes", estado="RJ")

    resultado = services.evolucao_interesse(estado="SP")

    assert sum(p["numero_noticias"] for p in resultado["serie"]) == 1


def test_evolucao_interesse_estado_nao_resolvivel_devolve_serie_vazia(monkeypatch):
    from enderecos import services as enderecos_services

    monkeypatch.setattr(enderecos_services, "resolver_uf", lambda texto: None)
    resultado = services.evolucao_interesse(estado="Localidade Que Não Existe De Verdade Nenhuma")
    assert resultado["serie"] == []
    assert resultado.get("erro_localidade")


def test_noticias_regionais_filtra_por_estado_real():
    _item("Notícia de SP", "esportes", estado="SP")
    _item("Notícia do RJ", "esportes", estado="RJ")

    resultado = services.noticias_regionais(estado="SP")

    assert len(resultado["itens"]) == 1
    assert resultado["itens"][0]["estado"] == "SP"
    assert resultado["ordenado_por"] == "recencia"


def test_noticias_regionais_busca_textual():
    _item("Governo anuncia pacote econômico", "economia", estado="SP")
    _item("Time vence partida decisiva", "esportes", estado="SP")

    resultado = services.noticias_regionais(estado="SP", busca="pacote")

    assert len(resultado["itens"]) == 1
    assert "pacote" in resultado["itens"][0]["titulo"].lower()


def test_noticias_regionais_ordena_por_distancia_com_coordenada():
    _item("Notícia perto", "geral", estado="SP")
    _item("Notícia longe", "geral", estado="AM")

    lat_sp, lon_sp = -23.5505, -46.6333
    resultado = services.noticias_regionais(lat=lat_sp, lon=lon_sp)

    assert resultado["ordenado_por"] == "distancia"
    assert resultado["itens"][0]["estado"] == "SP"
    assert resultado["itens"][0]["distancia_km"] < resultado["itens"][1]["distancia_km"]


def test_noticias_regionais_estado_nao_resolvivel_devolve_vazio_sem_erro(monkeypatch):
    from enderecos import services as enderecos_services

    monkeypatch.setattr(enderecos_services, "resolver_uf", lambda texto: None)
    resultado = services.noticias_regionais(estado="Localidade Que Não Existe De Verdade Nenhuma")
    assert resultado["itens"] == []
    assert resultado.get("erro_localidade")


def test_item_pendente_nao_conta_no_radar():
    NewsItem.objects.create(
        titulo="Pendente",
        resumo_proprio="R",
        conteudo_bruto="B",
        url_fonte_original="https://g1/pendente-radar",
        nome_fonte="G1",
        categoria="esportes",
        status_revisao=NewsItem.STATUS_PENDENTE,
    )
    resultado = services.tendencias()
    assert resultado["assuntos_em_alta"] == []


def test_salvar_localidade_e_idempotente():
    usuario = User.objects.create_user(email="radar@example.com", password="senha123", papel="free")
    services.salvar_localidade(usuario, cidade="São Paulo")
    services.salvar_localidade(usuario, cidade="São Paulo")
    assert services.localidades_salvas(usuario).count() == 1


def test_radar_avancado_gated_para_free(fabrica_usuario_premium):
    from gating.services import has_feature

    usuario_free = User.objects.create_user(email="free-radar@example.com", password="senha123", papel="free")
    # P1-08: Premium de verdade (assinatura paga), não `papel="premium"` solto.
    usuario_premium = fabrica_usuario_premium(email="premium-radar@example.com")
    FeatureLimit.objects.update_or_create(chave="radar_avancado", plano="free", defaults={"valor": "false"})
    FeatureLimit.objects.update_or_create(chave="radar_avancado", plano="premium", defaults={"valor": "true"})

    assert has_feature(usuario_free, "radar_avancado") is False
    assert has_feature(usuario_premium, "radar_avancado") is True
