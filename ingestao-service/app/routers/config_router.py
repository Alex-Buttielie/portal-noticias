"""Router /config — configuracao singleton do robo (Frente C).

`GET /config` cria o documento padrão na primeira leitura (valores espelham
`app.schemas.Config`). `PATCH /config` aceita atualização parcial com
validações de faixa em pt-BR (intervalo 1–1440 min, limiares 0–1, etc.).
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from app import db
from app.deps import exigir_token
from app.routers._comum import erro_interno
from app.schemas import Config

router = APIRouter(dependencies=[Depends(exigir_token)])

COL_CONFIG = "config"


def _ler_doc() -> Dict[str, Any] | None:
    try:
        return db.get_collection(COL_CONFIG).find_one()
    except Exception:
        raise erro_interno("Não foi possível ler a configuração no momento")


def _para_config(doc: Dict[str, Any] | None) -> Config:
    if not doc:
        return Config()
    dados = {k: v for k, v in dict(doc).items() if k in Config.model_fields}
    try:
        return Config(**dados)
    except ValidationError:
        return Config()


def _validar_patch(atual: Config, patch: Dict[str, Any]) -> Dict[str, Any]:
    desconhecidos = sorted(set(patch) - set(Config.model_fields))
    if desconhecidos:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Campos de configuração desconhecidos: {', '.join(desconhecidos)}",
        )
    base = atual.model_dump()
    for campo, valor in patch.items():
        if isinstance(valor, bool) and campo not in ("ativo", "cluster_sempre_revisao"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Campo '{campo}' inválido: esperado número ou texto, não booleano",
            )
        if campo == "intervalo_minutos":
            if not isinstance(valor, int) or isinstance(valor, bool) or not 1 <= valor <= 1440:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Campo 'intervalo_minutos' inválido: deve ser inteiro entre 1 e 1440",
                )
        elif campo in ("dedup_limiar", "resumo_sim_max", "resumo_trecho_max"):
            if (
                not isinstance(valor, (int, float))
                or isinstance(valor, bool)
                or not 0 <= float(valor) <= 1
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Campo '{campo}' inválido: deve ser um número entre 0 e 1",
                )
        elif campo == "dedup_janela_horas":
            if (
                not isinstance(valor, (int, float))
                or isinstance(valor, bool)
                or float(valor) <= 0
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Campo 'dedup_janela_horas' inválido: deve ser um número maior que 0",
                )
        elif campo in (
            "limiar_fontes_alta_relevancia",
            "dedup_max_itens",
            "llm_lote",
            "llm_max_tokens",
            "llm_timeout",
        ):
            if not isinstance(valor, int) or isinstance(valor, bool) or valor < 1:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Campo '{campo}' inválido: deve ser um inteiro maior ou igual a 1",
                )
        elif campo in ("llm_teto_usd", "llm_preco_1k"):
            if (
                not isinstance(valor, (int, float))
                or isinstance(valor, bool)
                or float(valor) < 0
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Campo '{campo}' inválido: deve ser um número maior ou igual a 0",
                )
        elif campo in ("ativo", "cluster_sempre_revisao"):
            if not isinstance(valor, bool):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Campo '{campo}' inválido: deve ser verdadeiro ou falso",
                )
        elif campo in ("categorias_sensiveis", "llm_model", "llm_base_url"):
            if not isinstance(valor, str):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Campo '{campo}' inválido: deve ser um texto",
                )
        base[campo] = valor
    try:
        return Config(**base).model_dump()
    except ValidationError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Combinação de configuração inválida",
        )


@router.get(
    "/config",
    response_model=Config,
    summary="Obter configuração do robô",
    description=(
        "Retorna a configuração singleton do serviço (intervalo de ingestão, "
        "limiares de dedup/resumo, parâmetros do LLM, categorias sensíveis). "
        "Se ainda não existir, o documento padrão é criado na hora. "
        "Requer header `X-API-Token`."
    ),
    response_description="Configuração vigente.",
)
def obter_config() -> Config:
    doc = _ler_doc()
    if doc is None:
        cfg = Config()
        try:
            db.get_collection(COL_CONFIG).insert_one({**cfg.model_dump(), "_id": "singleton"})
        except Exception:
            pass
        return cfg
    return _para_config(doc)


@router.patch(
    "/config",
    response_model=Config,
    summary="Atualizar configuração (parcial)",
    description=(
        "Atualiza parcialmente a configuração singleton. Validações: "
        "`intervalo_minutos` entre 1 e 1440; `dedup_limiar`, `resumo_sim_max` e "
        "`resumo_trecho_max` entre 0 e 1; contadores/lotes inteiros ≥ 1; "
        "tetos de custo ≥ 0. Campos desconhecidos retornam 422. "
        "Requer header `X-API-Token`."
    ),
    response_description="Configuração atualizada.",
)
def atualizar_config(payload: dict) -> Config:
    if not isinstance(payload, dict) or not payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Corpo inválido: informe ao menos um campo de configuração",
        )
    atual = _para_config(_ler_doc())
    novos = _validar_patch(atual, payload)
    try:
        col = db.get_collection(COL_CONFIG)
        if col.find_one() is None:
            col.insert_one({**novos, "_id": "singleton"})
        else:
            col.update_one({}, {"$set": novos})
    except HTTPException:
        raise
    except Exception:
        raise erro_interno("Não foi possível atualizar a configuração no momento")
    return Config(**novos)

