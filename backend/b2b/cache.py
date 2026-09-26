"""
Cache do painel B2B com namespace de tenant obrigatório (backlog P1-13 —
"papéis, isolamento e alertas testados"; workstream WS-12).

Por que este módulo existe
--------------------------
`itens_monitorados`/`resumo_executivo` são as únicas consultas caras do app
B2B: uma varredura de `NewsItem` por critério ativo, materializada em memória
a cada request. Cachear é o certo; cachear **sem namespace de tenant** seria
um vazamento cross-tenant: a resposta da empresa A — nome da organização,
critérios e itens — seria servida para o painel da empresa B.

Regra estrutural, não convenção
--------------------------------
A chave é montada por `chave_organizacao()`, cuja assinatura exige a
`Organizacao` como argumento POSICIONAL. Não existe caminho neste módulo que
produza uma chave sem `org:<id>`: quem chama sem organização não compila.
O formato é `b2b:v1:org:<id>:<recurso>[:<parte>]`, com o prefixo `b2b:v1`
para permitir rotação de formato sem colisão com o cache antigo.

O cache é fail-open como em `gating/services.py` e `feed/views.py`: qualquer
exceção do backend de cache cai no cálculo a partir do banco, nunca em erro
500 e nunca em dado de outra organização.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Prefixo de versão do formato das chaves. Não remover versions antigas sem
# um `cache.clear()` ou um TTL que as expire: a troca de formato sozinha não
# invalida nada.
PREFIXO = "b2b:v1"

# Recursos cacheados. `resumo-executivo` deriva de `itens-monitorados`; são
# entradas distintas porque têm TTL/custo distintos e porque o painel da
# empresa consome as duas.
RECURSO_ITENS_MONITORADOS = "itens-monitorados"
RECURSO_RESUMO_EXECUTIVO = "resumo-executivo"


def chave_organizacao(organizacao, recurso: str, *partes) -> str:
    """
    Monta a chave de cache do painel de UMA organização.

    `organizacao` é posicional e obrigatório de propósito: é a única forma de
    garantir que nenhuma chave de payload B2B exista sem o tenant no
    namespace. `partes` (janela em dias, etc.) entram depois do recurso, para
    que variantes do mesmo recurso não se sobrescrevam.
    """
    if getattr(organizacao, "pk", None) is None:
        raise ValueError("chave_organizacao exige uma Organizacao persistida (com pk).")
    sufixo = ":".join(str(parte) for parte in partes)
    base = f"{PREFIXO}:org:{organizacao.pk}:{recurso}"
    return f"{base}:{sufixo}" if sufixo else base


def _ttl() -> int:
    try:
        return max(1, int(getattr(settings, "B2B_CACHE_TTL_SEGUNDOS", 45)))
    except (TypeError, ValueError):
        return 45


def ler(organizacao, recurso: str, *partes):
    """Lê a chave namespaced da organização. `None` em cache miss ou falha."""
    try:
        return cache.get(chave_organizacao(organizacao, recurso, *partes))
    except Exception:  # pragma: no cover - defesa; testado via monkeypatch
        logger.exception("Falha ao ler o cache B2B (%s) — seguindo para o banco.", recurso)
        return None


def gravar(organizacao, recurso: str, valor, *partes) -> None:
    """Grava na chave namespaced da organização. Falha de cache é silenciosa."""
    try:
        cache.set(chave_organizacao(organizacao, recurso, *partes), valor, _ttl())
    except Exception:  # pragma: no cover - defesa; testado via monkeypatch
        logger.exception("Falha ao gravar o cache B2B (%s) — resposta segue do banco.", recurso)


def invalidar_organizacao(organizacao) -> None:
    """
    Descarta tudo que o painel da organização derivou do banco.

    Chamado em toda escrita que muda a resposta do painel (criar/excluir
    critério). Não há `delete_pattern` no Django, então a invalidação é por
    conhecimento das chaves conhecidas — o conjunto é fechado e pequeno
    (dois recursos x uma janela), e o TTL cobre qualquer chave futura.
    """
    try:
        chaves = []
        for recurso in (RECURSO_ITENS_MONITORADOS, RECURSO_RESUMO_EXECUTIVO):
            for dias in _janelas_conhecidas():
                chaves.append(chave_organizacao(organizacao, recurso, dias))
        cache.delete_many(chaves)
    except Exception:  # pragma: no cover - defesa
        logger.exception("Falha ao invalidar o cache B2B da organização %s.", getattr(organizacao, "pk", None))


def _janelas_conhecidas():
    """Janelas (dias) usadas como parte da chave pelo código do app."""
    return (28, 29, 30, 31, 7, 90)
