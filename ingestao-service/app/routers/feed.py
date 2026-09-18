"""Router /feed — servico do feed curado ao portal (Frente C).

Serve SOMENTE itens/clusters publicaveis (status aprovado/publicado): nada
pendente ou rejeitado vaza para o portal. Agrega as colecoes `clusters`,
`itens` e `fila` (decisoes aprovadas), porque o pipeline (Frente B) pode
persistir o resultado em qualquer uma delas.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app import db
from app.deps import exigir_token
from app.routers._comum import (
    buscar_por_id,
    doc_id_str,
    e_publicavel,
    erro_interno,
    paginar_lista,
    status_revisao_doc,
    timestamp_doc,
    validar_paginacao,
)
from app.schemas import DetalheFeed, FonteDetalhe, ItemServido

router = APIRouter(dependencies=[Depends(exigir_token)])

COLECOES_FEED = ("clusters", "itens", "fila")


def _coletar_publicaveis() -> List[Dict[str, Any]]:
    """Junta documentos publicaveis das colecoes do feed (tolerante a falhas)."""
    saida: List[Dict[str, Any]] = []
    for nome in COLECOES_FEED:
        try:
            docs = list(db.get_collection(nome).find())
        except Exception:
            continue
        for doc in docs:
            doc = dict(doc)
            doc["_origem"] = nome
            if e_publicavel(doc):
                saida.append(doc)
    return saida


def _numero_fontes(doc: Dict[str, Any]) -> int:
    for chave in ("numero_fontes", "numero_fontes_distintas"):
        valor = doc.get(chave)
        if isinstance(valor, int) and valor >= 1:
            return valor
    for chave in ("fontes", "itens"):
        valor = doc.get(chave)
        if isinstance(valor, list) and valor:
            return len(valor)
    return 1


def _para_item_servido(doc: Dict[str, Any]) -> ItemServido:
    origem = doc.get("_origem", "")
    tipo = str(doc.get("tipo", "") or "").lower()
    if tipo not in ("cluster", "item"):
        tipo = "cluster" if (origem == "clusters" or doc.get("titulo_acontecimento")) else "item"
    titulo = str(doc.get("titulo") or doc.get("titulo_acontecimento") or "")
    resumo = str(doc.get("resumo") or doc.get("resumo_proprio") or "")
    categoria = str(
        doc.get("categoria") or doc.get("categoria_dominante") or "geral"
    ) or "geral"
    return ItemServido(
        tipo=tipo,  # type: ignore[arg-type]
        id=doc_id_str(doc),
        titulo=titulo,
        resumo=resumo,
        categoria=categoria,
        urgente=bool(doc.get("urgente", False)),
        numero_fontes=_numero_fontes(doc),
        timestamp=timestamp_doc(doc),
        imagem_url=str(doc.get("imagem_url", "") or ""),
    )


def _aplicar_filtros(
    docs: List[Dict[str, Any]],
    categoria: Optional[str],
    busca: Optional[str],
) -> List[Dict[str, Any]]:
    if categoria:
        alvo = categoria.strip().lower()
        docs = [
            d
            for d in docs
            if str(d.get("categoria") or d.get("categoria_dominante") or "").lower() == alvo
        ]
    if busca:
        termo = busca.strip().lower()
        docs = [
            d
            for d in docs
            if termo
            in f"{d.get('titulo', '') or d.get('titulo_acontecimento', '')} "
            f"{d.get('resumo', '') or d.get('resumo_proprio', '')}".lower()
        ]
    docs.sort(key=timestamp_doc, reverse=True)
    return docs


def _pagina_url(
    base: str, page: int | None, page_size: int, categoria: Optional[str], busca: Optional[str]
) -> str | None:
    if page is None:
        return None
    params: Dict[str, Any] = {"page": page, "page_size": page_size}
    if categoria:
        params["categoria"] = categoria
    if busca:
        params["busca"] = busca
    return f"{base}?{urlencode(params)}"


@router.get(
    "/feed",
    summary="Obter feed curado (só aprovados)",
    description=(
        "Feed paginado de itens e clusters APROVADOS, no formato `ItemServido`, "
        "ordenados do mais recente para o mais antigo. Filtros opcionais: "
        "`categoria` (igualdade exata) e `busca` (trecho do título/resumo). "
        "Resposta no envelope `{count, next, previous, results}`. "
        "Requer header `X-API-Token`."
    ),
    response_description="Envelope paginado do feed.",
)
def obter_feed(
    categoria: Optional[str] = Query(default=None, description="Filtrar por categoria exata"),
    busca: Optional[str] = Query(default=None, description="Trecho do título/resumo"),
    page: int = Query(default=1, ge=1, description="Página (a partir de 1)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Itens por página (máx. 100)"),
) -> Dict[str, Any]:
    page, page_size = validar_paginacao(page, page_size)
    try:
        docs = _aplicar_filtros(_coletar_publicaveis(), categoria, busca)
    except HTTPException:
        raise
    except Exception:
        raise erro_interno("Não foi possível montar o feed no momento")
    fatia, total = paginar_lista(docs, page, page_size)
    total_pages = max(1, -(-total // page_size))
    proxima = page + 1 if page < total_pages else None
    anterior = page - 1 if page > 1 else None
    return {
        "count": total,
        "next": _pagina_url("/api/v1/feed", proxima, page_size, categoria, busca),
        "previous": _pagina_url("/api/v1/feed", anterior, page_size, categoria, busca),
        "results": [_para_item_servido(d).model_dump() for d in fatia],
    }


@router.get(
    "/feed/urgentes",
    summary="Obter notícias urgentes",
    description=(
        "Atalho do feed com apenas itens/clusters aprovados marcados como "
        "`urgente=true`, ordenados do mais recente primeiro. `limite` padrão 10 "
        "(máximo 100). Requer header `X-API-Token`."
    ),
    response_description="Envelope {count, results} de urgentes.",
)
def obter_urgentes(
    limite: int = Query(default=10, ge=1, description="Máximo de itens (1–100)"),
) -> Dict[str, Any]:
    if limite < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Parâmetro 'limite' inválido: deve ser maior ou igual a 1",
        )
    limite = min(limite, 100)
    try:
        docs = [d for d in _coletar_publicaveis() if bool(d.get("urgente", False))]
        docs.sort(key=timestamp_doc, reverse=True)
    except Exception:
        raise erro_interno("Não foi possível montar a lista de urgentes no momento")
    fatia = docs[:limite]
    return {"count": len(fatia), "results": [_para_item_servido(d).model_dump() for d in fatia]}


def _buscar_publicavel(doc_id: str, tipos: tuple[str, ...]) -> Optional[Dict[str, Any]]:
    """Busca por id nas colecoes do feed, exigindo tipo e status publicavel."""
    for nome in COLECOES_FEED:
        try:
            doc = buscar_por_id(db.get_collection(nome), doc_id)
        except Exception:
            continue
        if doc is None:
            continue
        doc = dict(doc)
        doc["_origem"] = nome
        tipo = str(doc.get("tipo", "") or "").lower()
        if not tipo:
            tipo = "cluster" if (nome == "clusters" or doc.get("titulo_acontecimento")) else "item"
        if tipos and tipo not in tipos:
            continue
        if not e_publicavel(doc):
            return None
        doc["tipo"] = tipo
        return doc
    return None


def _fonte_detalhe_de(doc: Dict[str, Any]) -> FonteDetalhe:
    return FonteDetalhe(
        nome_fonte=str(doc.get("nome_fonte", "") or ""),
        url_fonte_original=str(doc.get("url_fonte_original", "") or ""),
        resumo=str(doc.get("resumo") or doc.get("resumo_proprio") or ""),
        imagem_url=str(doc.get("imagem_url", "") or ""),
        conteudo=str(doc.get("conteudo", "") or ""),
    )


def _membros_do_cluster(cluster_id: str) -> List[Dict[str, Any]]:
    membros: List[Dict[str, Any]] = []
    for nome in ("itens", "fila"):
        try:
            docs = list(db.get_collection(nome).find())
        except Exception:
            continue
        for doc in docs:
            if str(doc.get("cluster", "") or "") == cluster_id and e_publicavel(doc):
                membros.append(doc)
    membros.sort(key=timestamp_doc, reverse=True)
    return membros


def _detalhe(doc: Dict[str, Any]) -> DetalheFeed:
    tipo = str(doc.get("tipo", "item"))
    doc_id = doc_id_str(doc)
    if tipo == "cluster":
        membros = _membros_do_cluster(doc_id)
        fontes: List[FonteDetalhe] = []
        if membros:
            fontes = [_fonte_detalhe_de(m) for m in membros]
        elif isinstance(doc.get("fontes"), list) and doc["fontes"]:
            for f in doc["fontes"]:
                if isinstance(f, dict):
                    fontes.append(
                        FonteDetalhe(
                            nome_fonte=str(f.get("nome_fonte", "") or ""),
                            url_fonte_original=str(f.get("url_fonte_original", "") or ""),
                            resumo=str(f.get("resumo", "") or ""),
                            imagem_url=str(f.get("imagem_url", "") or ""),
                            conteudo=str(f.get("conteudo", "") or ""),
                        )
                    )
        else:
            fontes = [_fonte_detalhe_de(doc)]
        titulo = str(doc.get("titulo") or doc.get("titulo_acontecimento") or "")
    else:
        fontes = [_fonte_detalhe_de(doc)]
        titulo = str(doc.get("titulo", "") or "")
    categoria = str(doc.get("categoria") or doc.get("categoria_dominante") or "geral") or "geral"
    return DetalheFeed(
        tipo=tipo,
        id=doc_id,
        titulo=titulo,
        categoria=categoria,
        urgente=bool(doc.get("urgente", False)),
        timestamp=timestamp_doc(doc),
        fontes=fontes,
    )


@router.get(
    "/feed/cluster/{cluster_id}",
    summary="Detalhar cluster aprovado",
    description=(
        "Detalhe de um cluster (`DetalheFeed`) com as fontes agrupadas. "
        "Retorna 404 se o cluster não existir ou não estiver publicado "
        "(pendente/rejeitado nunca aparece aqui). Requer header `X-API-Token`."
    ),
    response_description="Detalhe do cluster.",
)
def obter_cluster(cluster_id: str) -> Dict[str, Any]:
    try:
        doc = _buscar_publicavel(cluster_id, ("cluster",))
    except Exception:
        raise erro_interno("Não foi possível carregar o cluster no momento")
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster não encontrado ou ainda não publicado",
        )
    return _detalhe(doc).model_dump()


@router.get(
    "/feed/item/{item_id}",
    summary="Detalhar item aprovado",
    description=(
        "Detalhe de um item (`DetalheFeed`) com a fonte original rastreável. "
        "Retorna 404 se o item não existir ou não estiver publicado. "
        "Requer header `X-API-Token`."
    ),
    response_description="Detalhe do item.",
)
def obter_item(item_id: str) -> Dict[str, Any]:
    try:
        doc = _buscar_publicavel(item_id, ("item",))
    except Exception:
        raise erro_interno("Não foi possível carregar o item no momento")
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item não encontrado ou ainda não publicado",
        )
    return _detalhe(doc).model_dump()

