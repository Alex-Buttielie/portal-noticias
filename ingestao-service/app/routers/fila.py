"""Router /fila — revisao humana (Frente C).

Itens que o pipeline considera sensiveis, de alta relevancia ou sem resumo
confiavel caem aqui com `status_revisao=pendente`. O operador aprova ou
rejeita via `POST /fila/{id}/decisao`; se a Frente B prover
`curadoria.decidir_status`, ele e usado como validacao best-effort.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app import db
from app.deps import exigir_token
from app.routers._comum import (
    agora_iso,
    buscar_por_id,
    doc_id_str,
    erro_interno,
    filtro_id,
    paginar_lista,
    status_revisao_doc,
    timestamp_doc,
    validar_paginacao,
)
from app.schemas import FilaItem

router = APIRouter(dependencies=[Depends(exigir_token)])

COL_FILA = "fila"
COL_ITENS_FALLBACK = "itens"


def _para_fila_item(doc: Dict[str, Any]) -> FilaItem:
    cluster = doc.get("cluster")
    return FilaItem(
        tipo=str(doc.get("tipo", "item") or "item"),
        id=doc_id_str(doc),
        titulo=str(doc.get("titulo", "") or ""),
        categoria=str(doc.get("categoria", doc.get("categoria_dominante", "geral")) or "geral"),
        status_revisao=status_revisao_doc(doc),
        nome_fonte=str(doc.get("nome_fonte", "") or ""),
        url_fonte_original=str(doc.get("url_fonte_original", "") or ""),
        urgente=bool(doc.get("urgente", False)),
        cluster=str(cluster) if cluster not in (None, "") else None,
        cluster_titulo=str(doc.get("cluster_titulo", "") or ""),
        timestamp_ingestao=timestamp_doc(doc),
    )


def _buscar_na_fila(item_id: str) -> tuple[Optional[Dict[str, Any]], Any]:
    """Procura na `fila` e, em fallback, em `itens`. Devolve (doc, colecao)."""
    col = db.get_collection(COL_FILA)
    doc = buscar_por_id(col, item_id)
    if doc is not None:
        return doc, col
    try:
        col2 = db.get_collection(COL_ITENS_FALLBACK)
    except Exception:
        return None, col
    doc2 = buscar_por_id(col2, item_id)
    if doc2 is not None:
        return doc2, col2
    return None, col


@router.get(
    "/fila",
    summary="Listar fila de revisão humana",
    description=(
        "Lista itens aguardando decisão editorial, ordenados pela ingestão mais "
        "recente primeiro. Filtre por `status` (`pendente` por padrão; use "
        "`aprovado`/`rejeitado` para auditoria). Paginação com `page`/`page_size` "
        "(padrão 20, máximo 100). Requer header `X-API-Token`."
    ),
    response_description="Envelope {count, page, page_size, results}.",
)
def listar_fila(
    status: str = Query(default="pendente", description="Status de revisão a listar"),
    page: int = Query(default=1, ge=1, description="Página (a partir de 1)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Itens por página (máx. 100)"),
) -> Dict[str, Any]:
    page, page_size = validar_paginacao(page, page_size)
    alvo = str(status or "pendente").lower()
    try:
        docs = list(db.get_collection(COL_FILA).find())
    except Exception:
        raise erro_interno("Não foi possível listar a fila no momento")
    filtrados = [d for d in docs if status_revisao_doc(d) == alvo]
    filtrados.sort(key=timestamp_doc, reverse=True)
    fatia, total = paginar_lista(filtrados, page, page_size)
    return {
        "count": total,
        "page": page,
        "page_size": page_size,
        "results": [_para_fila_item(d).model_dump() for d in fatia],
    }


@router.post(
    "/fila/{item_id}/decisao",
    summary="Decidir item da fila (aprovar/rejeitar)",
    description=(
        "Registra a decisão editorial sobre um item: corpo "
        "`{\"acao\": \"aprovar\" | \"rejeitar\"}`. `aprovar` publica o item no feed; "
        "`rejeitar` o descarta. Retorna 404 se o item não existir e 422 para ação "
        "inválida. Requer header `X-API-Token`."
    ),
    response_description="Item atualizado.",
)
def decidir_item(item_id: str, payload: dict) -> Dict[str, Any]:
    acao = ""
    if isinstance(payload, dict):
        acao = str(payload.get("acao", "") or "").strip().lower()
    if acao not in ("aprovar", "rejeitar"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Ação inválida: use 'aprovar' ou 'rejeitar'",
        )
    try:
        doc, col = _buscar_na_fila(item_id)
    except Exception:
        raise erro_interno("Não foi possível registrar a decisão no momento")
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado na fila"
        )
    novo_status = "aprovado" if acao == "aprovar" else "rejeitado"
    try:  # Hook opcional da Frente B: valida a transicao sem quebrar a rota
        from app.pipeline.curadoria import decidir_status as _decidir  # type: ignore

        try:
            _decidir(doc, novo_status)
        except Exception:
            pass
    except Exception:
        pass
    try:
        col.update_one(
            filtro_id(doc),
            {"$set": {"status_revisao": novo_status, "decidido_em": agora_iso()}},
        )
        atualizado = buscar_por_id(col, item_id) or {**doc, "status_revisao": novo_status}
    except Exception:
        raise erro_interno("Não foi possível registrar a decisão no momento")
    return _para_fila_item(atualizado).model_dump()


# Export para reuso/testes sem duplicar logica.
__all__ = ["router", "decidir_item", "listar_fila"]

