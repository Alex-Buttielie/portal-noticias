"""Router /ingestao — disparo do ciclo + historico de execucoes (Frente C).

`POST /ingestao/executar` delega o trabalho pesado (RSS -> dedup -> cluster ->
LLM -> fila) a `app.pipeline.execucao::executar_ingestao` (Frente B),
passando as fontes ativas e a configuracao persistida no banco. O isolamento
de falhas por fonte vive no pipeline; aqui, apenas falhas catastroficas
(pipeline indisponivel ou excecao nao tratada) viram 500 — sempre com `detail`
em pt-BR e sem vazar stack trace.
"""
from __future__ import annotations

import uuid
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app import db
from app.deps import exigir_token
from app.routers._comum import agora_iso, doc_id_str, erro_interno, timestamp_doc
from app.schemas import Config, Execucao

router = APIRouter(dependencies=[Depends(exigir_token)])

COL_EXECUCOES = "execucoes"
COL_FONTES = "fontes"
COL_CONFIG = "config"

# Seam de injecao: os testes (e a Frente B, se preferir) podem fixar a funcao
# do pipeline aqui sem importar o modulo real.
executar_pipeline: Optional[Callable[..., Any]] = None


def _obter_funcao_pipeline() -> Optional[Callable[..., Any]]:
    if executar_pipeline is not None:
        return executar_pipeline
    try:
        from app.pipeline.execucao import executar_ingestao as fn  # Frente B

        return fn
    except Exception:
        return None


def _fontes_ativas() -> List[Dict[str, Any]]:
    try:
        docs = list(db.get_collection(COL_FONTES).find())
    except Exception:
        raise erro_interno("Não foi possível carregar as fontes para a ingestão")
    return [d for d in docs if bool(d.get("ativo", True))]


def _config_dict() -> Dict[str, Any]:
    try:
        doc = db.get_collection(COL_CONFIG).find_one()
    except Exception:
        raise erro_interno("Não foi possível carregar a configuração para a ingestão")
    if not doc:
        return Config().model_dump()
    dados = {k: v for k, v in dict(doc).items() if k in Config.model_fields}
    try:
        return Config(**dados).model_dump()
    except Exception:
        return Config().model_dump()


def _num(valor: Any, padrao: Any = 0) -> Any:
    try:
        if isinstance(valor, bool):
            return valor
        if isinstance(valor, (int, float)):
            return valor
        if valor is None:
            return padrao
        return valor
    except Exception:
        return padrao


def normalizar_execucao(resultado: Any) -> Execucao:
    """Converte o retorno do pipeline (dict, Execucao ou objeto) em `Execucao`."""
    if isinstance(resultado, Execucao):
        return resultado
    if isinstance(resultado, dict):
        dados: Dict[str, Any] = dict(resultado)
    elif resultado is None:
        dados = {}
    else:
        g = lambda *nomes, padrao=None: next(
            (getattr(resultado, n) for n in nomes if getattr(resultado, n, None) is not None),
            padrao,
        )
        dados = {
            "id": str(g("id", padrao="") or ""),
            "executado_em": str(g("executado_em", padrao="") or ""),
            "itens_por_fonte": g("itens_por_fonte", padrao={}) or {},
            "erros_por_fonte": g("erros_por_fonte", padrao={}) or {},
            "total_itens_ingeridos": g("total_itens_ingeridos", padrao=0) or 0,
            "total_grupos_formados": g("total_grupos_formados", padrao=0) or 0,
            "total_duplicatas_agrupadas": g("total_duplicatas_agrupadas", padrao=0) or 0,
            "chamadas_llm": g(
                "chamadas_llm",
                "chamadas_summarization_provider",
                "chamadas_summarization",
                padrao=0,
            )
            or 0,
            "tokens_llm": g(
                "tokens_llm", "tokens_utilizados_summarization", "tokens_utilizados", padrao=0
            )
            or 0,
            "custo_usd": g(
                "custo_usd",
                "custo_estimado_summarization_usd",
                "custo_estimado_usd",
                padrao=0.0,
            )
            or 0.0,
        }
    if not dados.get("id"):
        dados["id"] = str(uuid.uuid4())
    if not dados.get("executado_em"):
        dados["executado_em"] = agora_iso()
    dados.setdefault("itens_por_fonte", {})
    dados.setdefault("erros_por_fonte", {})
    try:
        return Execucao(**dados)
    except Exception:
        raise erro_interno("O pipeline devolveu um resultado de execução inválido")


def _doc_para_execucao(doc: Dict[str, Any]) -> Execucao:
    dados: Dict[str, Any] = {k: v for k, v in dict(doc).items() if k != "_id"}
    dados.setdefault("id", doc_id_str(doc))
    return normalizar_execucao(dados)


@router.post(
    "/ingestao/executar",
    status_code=status.HTTP_201_CREATED,
    response_model=Execucao,
    summary="Executar ciclo de ingestão",
    description=(
        "Dispara um ciclo completo de ingestão (coleta RSS/API das fontes ativas, "
        "deduplicação, agrupamento, resumo/classificação via LLM e triagem para a "
        "fila de revisão). Erros isolados por fonte são registrados em "
        "`erros_por_fonte` sem derrubar a execução — 500 só em falha catastrófica "
        "(pipeline indisponível ou erro não tratado), sempre com `detail` em pt-BR. "
        "A execução é persistida e aparece em `GET /ingestao/execucoes`. "
        "Requer header `X-API-Token`."
    ),
    response_description="Registro da execução (201).",
)
def executar_ciclo() -> Execucao:
    fn = _obter_funcao_pipeline()
    if fn is None:
        raise erro_interno("Pipeline de ingestão indisponível no momento")
    fontes = _fontes_ativas()
    config = _config_dict()
    try:
        try:
            resultado = fn(fontes=fontes, config=config)
        except TypeError:
            try:
                resultado = fn(fontes, config)
            except TypeError:
                resultado = fn()
    except HTTPException:
        raise
    except Exception:
        raise erro_interno("Falha catastrófica ao executar a ingestão")
    execucao = normalizar_execucao(resultado)
    try:
        doc = execucao.model_dump()
        doc["_id"] = execucao.id
        db.get_collection(COL_EXECUCOES).insert_one(doc)
    except Exception:
        raise erro_interno("Ingestão concluída, mas não foi possível registrar a execução")
    return execucao


@router.get(
    "/ingestao/execucoes",
    summary="Listar últimas execuções",
    description=(
        "Lista as últimas 50 execuções do pipeline, da mais recente para a mais "
        "antiga, com totais por fonte, erros por fonte e custo/uso de LLM. "
        "Requer header `X-API-Token`."
    ),
    response_description="Últimas execuções (máx. 50).",
)
def listar_execucoes() -> List[Execucao]:
    try:
        docs = list(db.get_collection(COL_EXECUCOES).find())
    except Exception:
        raise erro_interno("Não foi possível listar as execuções no momento")
    docs.sort(key=timestamp_doc, reverse=True)
    return [_doc_para_execucao(d) for d in docs[:50]]

