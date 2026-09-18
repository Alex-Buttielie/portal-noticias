"""Schemas Pydantic v2 — CONTRATOS CONGELADOS (Frente A).

Outras 3 frentes implementam contra estes nomes/paths. NAO renomear
campos, modelos ou paths sem acordo entre frentes.
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class Fonte(BaseModel):
    id: str
    nome: str
    url: str
    ativo: bool = True
    categoria_padrao: str = "geral"


class ItemServido(BaseModel):
    tipo: Literal["cluster", "item"]
    id: str
    titulo: str
    resumo: str = ""
    categoria: str = "geral"
    urgente: bool = False
    numero_fontes: int = 1
    timestamp: str = ""
    imagem_url: str = ""


class FonteDetalhe(BaseModel):
    nome_fonte: str
    url_fonte_original: str
    resumo: str = ""
    imagem_url: str = ""
    conteudo: str = ""


class DetalheFeed(BaseModel):
    tipo: str
    id: str
    titulo: str
    categoria: str = "geral"
    urgente: bool = False
    timestamp: str = ""
    fontes: List[FonteDetalhe] = Field(default_factory=list)


class FilaItem(BaseModel):
    tipo: str
    id: str
    titulo: str
    categoria: str = "geral"
    status_revisao: str = "pendente"
    nome_fonte: str = ""
    url_fonte_original: str = ""
    urgente: bool = False
    cluster: Optional[str] = None
    cluster_titulo: str = ""
    timestamp_ingestao: str = ""


class Execucao(BaseModel):
    id: str
    executado_em: str
    itens_por_fonte: Dict[str, int] = Field(default_factory=dict)
    erros_por_fonte: Dict[str, str] = Field(default_factory=dict)
    total_itens_ingeridos: int = 0
    total_grupos_formados: int = 0
    total_duplicatas_agrupadas: int = 0
    chamadas_llm: int = 0
    tokens_llm: int = 0
    custo_usd: float = 0.0


class Config(BaseModel):
    """Defaults espelham as regras de negocio vindas do portal (ver README)."""

    intervalo_minutos: int = 15
    ativo: bool = True
    categorias_sensiveis: str = "politica,crime,saude,eleicoes"
    limiar_fontes_alta_relevancia: int = 3
    dedup_limiar: float = 0.55
    dedup_janela_horas: float = 24.0
    dedup_max_itens: int = 300
    resumo_sim_max: float = 0.6
    resumo_trecho_max: float = 0.6
    cluster_sempre_revisao: bool = True
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""
    llm_lote: int = 10
    llm_max_tokens: int = 220
    llm_teto_usd: float = 5.0
    llm_preco_1k: float = 0.15
    llm_timeout: int = 30
