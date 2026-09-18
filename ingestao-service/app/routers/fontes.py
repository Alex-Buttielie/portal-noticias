"""Router /fontes — CRUD + sincronizacao via portal (Frente C).

As fontes cadastradas aqui alimentam o ciclo de ingestao: apenas fontes com
`ativo=true` sao usadas em `POST /ingestao/executar`. O portal (admin)
espelha sua lista de fontes via `POST /fontes/sincronizar` (upsert por url).
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app import db
from app.deps import exigir_token
from app.routers._comum import agora_iso, buscar_por_id, doc_id_str, erro_interno, filtro_id

router = APIRouter(dependencies=[Depends(exigir_token)])

COL_FONTES = "fontes"
CAMPOS_PERMITIDOS = ("nome", "url", "ativo", "categoria_padrao")


def _validar_url(url: Any) -> str:
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="URL inválida: deve começar com http:// ou https://",
        )
    return url.strip()


def _serializar(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc_id_str(doc),
        "nome": doc.get("nome", ""),
        "url": doc.get("url", ""),
        "ativo": bool(doc.get("ativo", True)),
        "categoria_padrao": doc.get("categoria_padrao", "geral") or "geral",
    }


def _conflito(col, campo: str, valor: str, ignorar_doc: Dict[str, Any] | None = None) -> bool:
    try:
        existente = col.find_one({campo: valor})
    except Exception:
        existente = None
    if existente is None:
        return False
    if ignorar_doc is not None and doc_id_str(existente) == doc_id_str(ignorar_doc):
        return False
    return True


@router.get(
    "/fontes",
    summary="Listar fontes de notícias",
    description=(
        "Lista todas as fontes RSS/API cadastradas no serviço, ordenadas por nome. "
        "Cada fonte possui nome, url, flag `ativo` (só fontes ativas entram no ciclo "
        "de ingestão) e `categoria_padrao`. Requer header `X-API-Token`."
    ),
    response_description="Lista de fontes cadastradas.",
)
def listar_fontes() -> List[Dict[str, Any]]:
    try:
        docs = list(db.get_collection(COL_FONTES).find())
    except Exception:
        raise erro_interno("Não foi possível listar as fontes no momento")
    docs.sort(key=lambda d: str(d.get("nome", "")).lower())
    return [_serializar(d) for d in docs]


@router.post(
    "/fontes/sincronizar",
    summary="Sincronizar fontes vindas do portal (upsert por url)",
    description=(
        "Recebe a lista de fontes informada no portal (admin) no formato "
        "`{\"fontes\": [{\"nome\", \"url\", \"ativo\", \"categoria_padrao\"}]}` e faz "
        "upsert pela `url`: fontes com url nova são criadas, fontes com url já "
        "cadastrada são atualizadas. Retorna a contagem de criadas, atualizadas e total. "
        "É assim que as fontes do portal alimentam este serviço. Requer `X-API-Token`."
    ),
    response_description="Contadores {criadas, atualizadas, total}.",
)
def sincronizar_fontes(payload: dict) -> Dict[str, int]:
    if not isinstance(payload, dict) or not isinstance(payload.get("fontes"), list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Corpo inválido: esperado um objeto com a chave 'fontes' contendo uma lista",
        )
    try:
        col = db.get_collection(COL_FONTES)
    except Exception:
        raise erro_interno("Não foi possível sincronizar as fontes no momento")
    criadas = 0
    atualizadas = 0
    for i, entrada in enumerate(payload["fontes"]):
        if not isinstance(entrada, dict) or not entrada.get("nome") or not entrada.get("url"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Fonte inválida na posição {i}: 'nome' e 'url' são obrigatórios",
            )
        nome = str(entrada["nome"]).strip()
        if not nome:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Fonte inválida na posição {i}: 'nome' não pode ser vazio",
            )
        url = _validar_url(entrada["url"])
        ativo = bool(entrada.get("ativo", True))
        categoria = str(entrada.get("categoria_padrao", "geral") or "geral").strip() or "geral"
        try:
            existente = col.find_one({"url": url})
            if existente is None:
                col.insert_one(
                    {
                        "nome": nome,
                        "url": url,
                        "ativo": ativo,
                        "categoria_padrao": categoria,
                        "criado_em": agora_iso(),
                    }
                )
                criadas += 1
            else:
                col.update_one(
                    filtro_id(existente),
                    {"$set": {"nome": nome, "ativo": ativo, "categoria_padrao": categoria}},
                )
                atualizadas += 1
        except HTTPException:
            raise
        except Exception:
            raise erro_interno("Não foi possível sincronizar as fontes no momento")
    return {"criadas": criadas, "atualizadas": atualizadas, "total": criadas + atualizadas}


@router.post(
    "/fontes",
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar nova fonte",
    description=(
        "Cadastra uma fonte RSS/API com `{nome, url, ativo?, categoria_padrao?}`. "
        "A `url` precisa começar com http:// ou https://. Retorna 409 se já existir "
        "fonte com o mesmo nome ou a mesma url. Requer header `X-API-Token`."
    ),
    response_description="Fonte criada.",
)
def criar_fonte(payload: dict) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Corpo inválido: esperado um objeto com 'nome' e 'url'",
        )
    nome = payload.get("nome")
    url = payload.get("url")
    if not nome or not str(nome).strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Campo 'nome' é obrigatório e não pode ser vazio",
        )
    if not url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Campo 'url' é obrigatório",
        )
    nome = str(nome).strip()
    url = _validar_url(url)
    ativo = bool(payload.get("ativo", True))
    categoria = str(payload.get("categoria_padrao", "geral") or "geral").strip() or "geral"
    try:
        col = db.get_collection(COL_FONTES)
        if _conflito(col, "nome", nome):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Fonte já cadastrada com este nome",
            )
        if _conflito(col, "url", url):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Fonte já cadastrada com esta url",
            )
        resultado = col.insert_one(
            {
                "nome": nome,
                "url": url,
                "ativo": ativo,
                "categoria_padrao": categoria,
                "criado_em": agora_iso(),
            }
        )
    except HTTPException:
        raise
    except Exception:
        raise erro_interno("Não foi possível criar a fonte no momento")
    return {
        "id": str(getattr(resultado, "inserted_id", "")),
        "nome": nome,
        "url": url,
        "ativo": ativo,
        "categoria_padrao": categoria,
    }


@router.patch(
    "/fontes/{fonte_id}",
    summary="Atualizar fonte (parcial)",
    description=(
        "Atualiza parcialmente uma fonte: qualquer subconjunto de "
        "`{nome, url, ativo, categoria_padrao}`. Valida a url (http/https) e "
        "retorna 409 se o novo nome/url colidir com outra fonte. "
        "Retorna 404 se a fonte não existir. Requer header `X-API-Token`."
    ),
    response_description="Fonte atualizada.",
)
def atualizar_fonte(fonte_id: str, payload: dict) -> Dict[str, Any]:
    if not isinstance(payload, dict) or not payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Corpo inválido: informe ao menos um campo para atualizar",
        )
    try:
        col = db.get_collection(COL_FONTES)
        doc = buscar_por_id(col, fonte_id)
    except HTTPException:
        raise
    except Exception:
        raise erro_interno("Não foi possível atualizar a fonte no momento")
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fonte não encontrada"
        )
    atualizacoes: Dict[str, Any] = {}
    if "nome" in payload:
        nome = str(payload["nome"] or "").strip()
        if not nome:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Campo 'nome' não pode ser vazio",
            )
        if _conflito(col, "nome", nome, ignorar_doc=doc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Fonte já cadastrada com este nome",
            )
        atualizacoes["nome"] = nome
    if "url" in payload:
        url = _validar_url(payload["url"])
        if _conflito(col, "url", url, ignorar_doc=doc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Fonte já cadastrada com esta url",
            )
        atualizacoes["url"] = url
    if "ativo" in payload:
        atualizacoes["ativo"] = bool(payload["ativo"])
    if "categoria_padrao" in payload:
        atualizacoes["categoria_padrao"] = (
            str(payload["categoria_padrao"] or "geral").strip() or "geral"
        )
    if not atualizacoes:
        return _serializar(doc)
    try:
        col.update_one(filtro_id(doc), {"$set": atualizacoes})
        atualizado = buscar_por_id(col, fonte_id) or {**doc, **atualizacoes}
    except Exception:
        raise erro_interno("Não foi possível atualizar a fonte no momento")
    return _serializar(atualizado)


@router.delete(
    "/fontes/{fonte_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover fonte",
    description=(
        "Remove uma fonte pelo id. Retorna 204 sem corpo em caso de sucesso e "
        "404 se a fonte não existir. Requer header `X-API-Token`."
    ),
    response_description="Removida (sem corpo).",
)
def remover_fonte(fonte_id: str) -> Response:
    try:
        col = db.get_collection(COL_FONTES)
        doc = buscar_por_id(col, fonte_id)
    except Exception:
        raise erro_interno("Não foi possível remover a fonte no momento")
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fonte não encontrada"
        )
    try:
        col.delete_one(filtro_id(doc))
    except Exception:
        raise erro_interno("Não foi possível remover a fonte no momento")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

