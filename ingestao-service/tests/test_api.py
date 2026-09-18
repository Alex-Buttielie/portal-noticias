"""Testes da API de servico + painel (Frente C).

Usa TestClient com mongo fake via monkeypatch em `app.db.get_collection`
(única costura de persistência usada pelos routers) e token `X-API-Token: test`.
"""
from __future__ import annotations

import os
import uuid

os.environ["INGESTAO_API_TOKEN"] = "test"

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.db as db_module
from app import db as app_db
from app.config import settings

settings.INGESTAO_API_TOKEN = "test"

from app.main import app  # noqa: E402
from app.routers import ingestao as ingestao_router  # noqa: E402

TOKEN = {"X-API-Token": "test"}


# ---------------------------------------------------------------- mongo fake
def _match(doc: dict, filtro: dict | None) -> bool:
    if not filtro:
        return True
    return all(doc.get(k, None) == v for k, v in filtro.items())


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict] = []

    def find(self, filtro: dict | None = None):
        return [d for d in self.docs if _match(d, filtro or {})]

    def find_one(self, filtro: dict | None = None):
        for d in self.docs:
            if _match(d, filtro or {}):
                return d
        return None

    def insert_one(self, doc: dict):
        doc = dict(doc)
        doc.setdefault("_id", str(uuid.uuid4()))
        self.docs.append(doc)
        return SimpleNamespace(inserted_id=doc["_id"])

    def update_one(self, filtro: dict, update: dict):
        for d in self.docs:
            if _match(d, filtro or {}):
                for k, v in (update.get("$set") or {}).items():
                    d[k] = v
                return SimpleNamespace(matched_count=1, modified_count=1)
        return SimpleNamespace(matched_count=0, modified_count=0)

    def delete_one(self, filtro: dict):
        for i, d in enumerate(self.docs):
            if _match(d, filtro or {}):
                del self.docs[i]
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    def count_documents(self, filtro: dict | None = None):
        return len(self.find(filtro))


@pytest.fixture()
def fake_db(monkeypatch):
    from collections import defaultdict

    bancos: dict[str, FakeCollection] = defaultdict(FakeCollection)

    def _get(nome: str):
        return bancos.setdefault(nome, FakeCollection())

    monkeypatch.setattr(db_module, "get_collection", _get)
    monkeypatch.setattr(app_db, "get_collection", _get)
    return bancos


@pytest.fixture()
def client(fake_db):
    return TestClient(app, raise_server_exceptions=False)


def _criar_fonte(client, nome="G1", url="https://g1.globo.com/rss"):
    r = client.post(
        "/api/v1/fontes", json={"nome": nome, "url": url}, headers=TOKEN
    )
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------------------- auth
def test_sem_token_retorna_401(client):
    r = client.get("/api/v1/fontes")
    assert r.status_code == 401
    assert "detail" in r.json()


def test_token_errado_retorna_401(client):
    r = client.get("/api/v1/fontes", headers={"X-API-Token": "errado"})
    assert r.status_code == 401


# ------------------------------------------------------------------ fontes
def test_crud_fontes(client):
    criada = _criar_fonte(client)
    assert criada["nome"] == "G1"
    assert criada["ativo"] is True
    assert criada["categoria_padrao"] == "geral"

    r = client.get("/api/v1/fontes", headers=TOKEN)
    assert r.status_code == 200
    assert any(f["nome"] == "G1" for f in r.json())

    r = client.patch(
        f"/api/v1/fontes/{criada['id']}",
        json={"ativo": False, "categoria_padrao": "politica"},
        headers=TOKEN,
    )
    assert r.status_code == 200
    assert r.json()["ativo"] is False
    assert r.json()["categoria_padrao"] == "politica"

    r = client.delete(f"/api/v1/fontes/{criada['id']}", headers=TOKEN)
    assert r.status_code == 204

    r = client.delete(f"/api/v1/fontes/{criada['id']}", headers=TOKEN)
    assert r.status_code == 404
    assert "detail" in r.json()


def test_criar_fonte_url_invalida_422(client):
    r = client.post(
        "/api/v1/fontes", json={"nome": "X", "url": "ftp://x/y"}, headers=TOKEN
    )
    assert r.status_code == 422
    assert "detail" in r.json()


def test_criar_fonte_duplicada_409(client):
    _criar_fonte(client, nome="G1", url="https://g1.globo.com/rss")
    r = client.post(
        "/api/v1/fontes", json={"nome": "G1", "url": "https://outra.com/rss"}, headers=TOKEN
    )
    assert r.status_code == 409
    r = client.post(
        "/api/v1/fontes",
        json={"nome": "Outra", "url": "https://g1.globo.com/rss"},
        headers=TOKEN,
    )
    assert r.status_code == 409


def test_patch_fonte_inexistente_404(client):
    r = client.patch("/api/v1/fontes/nao-existe", json={"ativo": False}, headers=TOKEN)
    assert r.status_code == 404


def test_sincronizar_upsert(client):
    _criar_fonte(client, nome="G1 antigo", url="https://g1.globo.com/rss")
    r = client.post(
        "/api/v1/fontes/sincronizar",
        json={
            "fontes": [
                {"nome": "G1 novo", "url": "https://g1.globo.com/rss", "ativo": True},
                {"nome": "UOL", "url": "https://uol.com.br/rss", "categoria_padrao": "geral"},
            ]
        },
        headers=TOKEN,
    )
    assert r.status_code == 200
    assert r.json() == {"criadas": 1, "atualizadas": 1, "total": 2}
    r = client.get("/api/v1/fontes", headers=TOKEN)
    nomes = {f["nome"] for f in r.json()}
    assert {"G1 novo", "UOL"} <= nomes


def test_sincronizar_corpo_invalido_422(client):
    r = client.post("/api/v1/fontes/sincronizar", json={"x": 1}, headers=TOKEN)
    assert r.status_code == 422
    r = client.post(
        "/api/v1/fontes/sincronizar", json={"fontes": [{"nome": "SemUrl"}]}, headers=TOKEN
    )
    assert r.status_code == 422


# ---------------------------------------------------------------- ingestao
def test_executar_ingestao_201(client, fake_db, monkeypatch):
    _criar_fonte(client, nome="G1", url="https://g1.globo.com/rss")
    _criar_fonte(client, nome="Inativa", url="https://inativa.com/rss")
    col = fake_db["fontes"]
    inativa = col.find_one({"nome": "Inativa"})
    col.update_one({"_id": inativa["_id"]}, {"$set": {"ativo": False}})

    chamadas = {}

    def fake_executar(fontes=None, config=None):
        chamadas["n_fontes"] = len(fontes or [])
        chamadas["config"] = config
        assert all(f.get("ativo", True) for f in (fontes or []))
        return {
            "itens_por_fonte": {"G1": 3},
            "erros_por_fonte": {},
            "total_itens_ingeridos": 3,
            "total_grupos_formados": 2,
            "total_duplicatas_agrupadas": 1,
            "chamadas_llm": 1,
            "tokens_llm": 100,
            "custo_usd": 0.01,
        }

    monkeypatch.setattr(ingestao_router, "executar_pipeline", fake_executar)
    r = client.post("/api/v1/ingestao/executar", headers=TOKEN)
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["total_itens_ingeridos"] == 3
    assert chamadas["n_fontes"] == 1  # só a fonte ativa
    assert isinstance(chamadas["config"], dict) and "intervalo_minutos" in chamadas["config"]

    r = client.get("/api/v1/ingestao/execucoes", headers=TOKEN)
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_executar_ingestao_falha_catastrofica_500(client, fake_db, monkeypatch):
    def boom(fontes=None, config=None):
        raise RuntimeError("tudo quebrou")

    monkeypatch.setattr(ingestao_router, "executar_pipeline", boom)
    r = client.post("/api/v1/ingestao/executar", headers=TOKEN)
    assert r.status_code == 500
    assert "detail" in r.json()
    assert "Traceback" not in r.text


def test_execucoes_ordenadas_desc(client, fake_db):
    col = fake_db["execucoes"]
    col.insert_one({"_id": "a", "executado_em": "2026-01-01T00:00:00+00:00"})
    col.insert_one({"_id": "b", "executado_em": "2026-02-01T00:00:00+00:00"})
    r = client.get("/api/v1/ingestao/execucoes", headers=TOKEN)
    assert r.status_code == 200
    ids = [e["id"] for e in r.json()]
    assert ids[0] == "b"


# -------------------------------------------------------------------- fila
def _inserir_fila(fake_db, titulo, ts, status_revisao="pendente"):
    col = fake_db["fila"]
    doc = {
        "tipo": "item",
        "titulo": titulo,
        "categoria": "geral",
        "status_revisao": status_revisao,
        "nome_fonte": "G1",
        "url_fonte_original": f"https://x/{titulo}",
        "urgente": False,
        "timestamp_ingestao": ts,
    }
    return col.insert_one(doc).inserted_id


def test_fila_lista_ordenada_e_paginada(client, fake_db):
    _inserir_fila(fake_db, "Antiga", "2026-01-01T00:00:00+00:00")
    _inserir_fila(fake_db, "Nova", "2026-03-01T00:00:00+00:00")
    r = client.get("/api/v1/fila?page=1&page_size=1", headers=TOKEN)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["count"] == 2
    assert corpo["results"][0]["titulo"] == "Nova"


def test_fila_decisao_aprovar_e_404(client, fake_db):
    item_id = _inserir_fila(fake_db, "Para aprovar", "2026-03-01T00:00:00+00:00")
    r = client.post(
        f"/api/v1/fila/{item_id}/decisao", json={"acao": "aprovar"}, headers=TOKEN
    )
    assert r.status_code == 200
    assert r.json()["status_revisao"] == "aprovado"

    r = client.post(
        "/api/v1/fila/inexistente/decisao", json={"acao": "aprovar"}, headers=TOKEN
    )
    assert r.status_code == 404

    r = client.post(
        f"/api/v1/fila/{item_id}/decisao", json={"acao": "publicar"}, headers=TOKEN
    )
    assert r.status_code == 422


# ------------------------------------------------------------------ config
def test_config_default_e_patch(client, fake_db):
    r = client.get("/api/v1/config", headers=TOKEN)
    assert r.status_code == 200
    assert r.json()["intervalo_minutos"] == 15

    r = client.patch("/api/v1/config", json={"intervalo_minutos": 30}, headers=TOKEN)
    assert r.status_code == 200
    assert r.json()["intervalo_minutos"] == 30

    r = client.patch("/api/v1/config", json={"intervalo_minutos": 0}, headers=TOKEN)
    assert r.status_code == 422
    r = client.patch("/api/v1/config", json={"dedup_limiar": 1.5}, headers=TOKEN)
    assert r.status_code == 422
    r = client.patch("/api/v1/config", json={"campo_fantasma": 1}, headers=TOKEN)
    assert r.status_code == 422


# -------------------------------------------------------------------- feed
def _inserir_item(fake_db, colecao, titulo, status_revisao, urgente=False, categoria="geral"):
    col = fake_db[colecao]
    return col.insert_one(
        {
            "tipo": "cluster" if colecao == "clusters" else "item",
            "titulo": titulo,
            "titulo_acontecimento": titulo,
            "resumo": f"resumo de {titulo}",
            "resumo_proprio": f"resumo de {titulo}",
            "categoria": categoria,
            "categoria_dominante": categoria,
            "status_revisao": status_revisao,
            "nome_fonte": "G1",
            "url_fonte_original": f"https://x/{titulo}",
            "urgente": urgente,
            "timestamp_ingestao": "2026-03-01T00:00:00+00:00",
            "timestamp": "2026-03-01T00:00:00+00:00",
        }
    ).inserted_id


def test_feed_so_aprovados(client, fake_db):
    _inserir_item(fake_db, "itens", "Aprovada", "aprovado")
    _inserir_item(fake_db, "itens", "Pendente", "pendente")
    _inserir_item(fake_db, "itens", "Rejeitada", "rejeitado")
    r = client.get("/api/v1/feed", headers=TOKEN)
    assert r.status_code == 200
    corpo = r.json()
    assert set(corpo) == {"count", "next", "previous", "results"}
    titulos = [i["titulo"] for i in corpo["results"]]
    assert titulos == ["Aprovada"]
    assert corpo["count"] == 1


def test_feed_filtros_e_urgentes(client, fake_db):
    _inserir_item(fake_db, "clusters", "Eleição X", "aprovado", urgente=True, categoria="politica")
    _inserir_item(fake_db, "itens", "Jogo Y", "aprovado", categoria="esporte")
    r = client.get("/api/v1/feed?categoria=politica", headers=TOKEN)
    assert [i["titulo"] for i in r.json()["results"]] == ["Eleição X"]
    r = client.get("/api/v1/feed?busca=jogo", headers=TOKEN)
    assert [i["titulo"] for i in r.json()["results"]] == ["Jogo Y"]
    r = client.get("/api/v1/feed/urgentes?limite=5", headers=TOKEN)
    assert r.status_code == 200
    assert [i["titulo"] for i in r.json()["results"]] == ["Eleição X"]


def test_feed_detalhes_e_404_nao_publicavel(client, fake_db):
    item_id = _inserir_item(fake_db, "itens", "Detalhada", "aprovado")
    pend_id = _inserir_item(fake_db, "itens", "Oculta", "pendente")
    r = client.get(f"/api/v1/feed/item/{item_id}", headers=TOKEN)
    assert r.status_code == 200
    assert r.json()["fontes"][0]["nome_fonte"] == "G1"
    r = client.get(f"/api/v1/feed/item/{pend_id}", headers=TOKEN)
    assert r.status_code == 404
    r = client.get("/api/v1/feed/cluster/nao-existe", headers=TOKEN)
    assert r.status_code == 404


# ------------------------------------------------------------------ painel
def test_painel_200_html(client, fake_db, monkeypatch):
    monkeypatch.setattr(db_module, "ping_db", lambda: True)
    _criar_fonte(client)
    r = client.get("/api/v1/painel", headers=TOKEN)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "/docs" in r.text
    assert "Fila pendente" in r.text or "fila" in r.text.lower()
