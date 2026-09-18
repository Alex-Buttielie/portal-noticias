"""Cliente MongoDB lazy (pymongo) — Frente A esqueleto."""
from __future__ import annotations

from typing import Optional

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from app.config import settings

_client: Optional[MongoClient] = None


def get_client() -> MongoClient:
    """Retorna o cliente global, criando sob demanda (lazy)."""
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGO_URL, serverSelectionTimeoutMS=3000)
    return _client


def get_db() -> Database:
    return get_client()[settings.DB_NAME]


def get_collection(nome: str) -> Collection:
    """TODO(Frente B): definir nomes canonicos de collections (fontes, itens, fila, execucoes, config)."""
    return get_db()[nome]


def ping_db() -> bool:
    """Ping real no Mongo; retorna False em vez de levantar."""
    try:
        get_client().admin.command("ping")
        return True
    except Exception:
        return False


def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
