"""Utilidades compartilhadas dos routers da API (Frente C).

Centraliza conversao de ids (ObjectId x string), paginacao, timestamps e
mapeamentos tolerantes de documentos do Mongo para os schemas congelados.
Nao toca em config/db/schemas/observability — apenas le via `app.db`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status

try:  # bson vem com o pymongo; ausencia nao pode derrubar a API
    from bson import ObjectId
    from bson.errors import InvalidId
except Exception:  # pragma: no cover - ambiente sem pymongo
    ObjectId = None  # type: ignore[assignment]

    class InvalidId(Exception):  # type: ignore[no-redef]
        pass


# Status que tornam um item/cluster visivel no feed publico.
STATUS_PUBLICAVEIS = frozenset(
    {"aprovado", "aprovada", "aprovados", "nao_aplicavel", "publicado", "publicada"}
)
STATUS_PENDENTE = "pendente"


def agora_iso() -> str:
    """Timestamp atual em ISO-8601 (UTC)."""
    return datetime.now(timezone.utc).isoformat()


def doc_id_str(doc: Dict[str, Any]) -> str:
    """Id publico (string) de um documento do Mongo."""
    return str(doc.get("_id", doc.get("id", "")))


def buscar_por_id(col, id_str: str) -> Optional[Dict[str, Any]]:
    """Busca tolerante por id: ObjectId, string em `_id` ou campo `id`."""
    if ObjectId is not None:
        try:
            doc = col.find_one({"_id": ObjectId(id_str)})
        except Exception:
            doc = None
        if doc is not None:
            return doc
    try:
        doc = col.find_one({"_id": id_str})
    except Exception:
        doc = None
    if doc is not None:
        return doc
    try:
        return col.find_one({"id": id_str})
    except Exception:
        return None


def filtro_id(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Filtro de escrita para o documento (preserva o `_id` real)."""
    if "_id" in doc:
        return {"_id": doc["_id"]}
    return {"id": doc.get("id")}


def validar_paginacao(page: int, page_size: int, maximo: int = 100) -> Tuple[int, int]:
    """Valida `page`/`page_size`; erros em pt-BR, sem vazar stack."""
    if page is None or page < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Parâmetro 'page' inválido: deve ser um inteiro maior ou igual a 1",
        )
    if page_size is None or page_size < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Parâmetro 'page_size' inválido: deve ser um inteiro maior ou igual a 1",
        )
    if page_size > maximo:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Parâmetro 'page_size' inválido: máximo permitido é {maximo}",
        )
    return page, page_size


def paginar_lista(lista: List[Any], page: int, page_size: int) -> Tuple[List[Any], int]:
    """Fatia `lista` (já ordenada) e devolve (fatia, total)."""
    total = len(lista)
    inicio = (page - 1) * page_size
    return lista[inicio : inicio + page_size], total


def timestamp_doc(doc: Dict[str, Any]) -> str:
    """Extrai o timestamp mais relevante do documento (string ISO)."""
    for chave in ("timestamp_ingestao", "timestamp", "executado_em", "criado_em"):
        valor = doc.get(chave)
        if valor:
            return str(valor)
    return ""


def status_revisao_doc(doc: Dict[str, Any], padrao: str = STATUS_PENDENTE) -> str:
    """Status de revisao normalizado (minusculo)."""
    return str(doc.get("status_revisao", doc.get("status", padrao)) or padrao).lower()


def e_publicavel(doc: Dict[str, Any]) -> bool:
    """Diz se o documento pode aparecer no feed (aprovado/publicado)."""
    return status_revisao_doc(doc, padrao="aprovado") in STATUS_PUBLICAVEIS


def erro_interno(mensagem: str) -> HTTPException:
    """500 generico em pt-BR (nunca vaza stack trace)."""
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=mensagem)

