"""Painel de controle HTML do microservico (Frente C).

`GET /painel`: pagina simples, sem framework JS, que permite operar o servico
sem o portal — mostra saude do Mongo, fontes ativas, ultima execucao, custo
de hoje, fila pendente e links para o Swagger e os endpoints principais.
"""
from __future__ import annotations

import html
from datetime import date
from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app import db
from app.deps import exigir_token
from app.observability import snapshot
from app.routers._comum import doc_id_str, status_revisao_doc, timestamp_doc

router = APIRouter(dependencies=[Depends(exigir_token)])


def coletar_status() -> Dict[str, Any]:
    """Agrega o estado operacional; cada bloco e tolerante a falha isolada."""
    dados: Dict[str, Any] = {}
    try:
        dados["mongo_ok"] = bool(db.ping_db())
    except Exception:
        dados["mongo_ok"] = False
    try:
        fontes = list(db.get_collection("fontes").find())
        dados["fontes_total"] = len(fontes)
        dados["fontes_ativas"] = sum(1 for f in fontes if bool(f.get("ativo", True)))
    except Exception:
        dados["fontes_total"] = "indisponível"
        dados["fontes_ativas"] = "indisponível"
    try:
        execs = list(db.get_collection("execucoes").find())
        execs.sort(key=timestamp_doc, reverse=True)
        ultima = execs[0] if execs else None
        dados["ultima_execucao"] = timestamp_doc(ultima) if ultima else "nunca"
        dados["ultima_itens"] = (ultima or {}).get("total_itens_ingeridos", "-")
        dados["ultima_custo"] = (ultima or {}).get("custo_usd", "-")
        hoje = date.today().isoformat()
        dados["custo_hoje"] = round(
            sum(
                float(e.get("custo_usd") or 0)
                for e in execs
                if timestamp_doc(e).startswith(hoje)
            ),
            4,
        )
    except Exception:
        dados["ultima_execucao"] = "indisponível"
        dados["ultima_itens"] = "-"
        dados["ultima_custo"] = "-"
        dados["custo_hoje"] = "indisponível"
    try:
        fila = list(db.get_collection("fila").find())
        dados["fila_pendente"] = sum(
            1 for d in fila if status_revisao_doc(d) == "pendente"
        )
    except Exception:
        dados["fila_pendente"] = "indisponível"
    try:
        dados["metricas"] = snapshot()
    except Exception:
        dados["metricas"] = {}
    return dados


def construir_html(dados: Dict[str, Any]) -> str:
    """Monta o HTML do painel (sem framework, so CSS inline)."""
    esc = html.escape
    mongo_txt = "OK" if dados.get("mongo_ok") else "FALHA"
    mongo_cor = "#137333" if dados.get("mongo_ok") else "#b3261e"
    metricas = dados.get("metricas") or {}
    linhas_metricas = "".join(
        f"<tr><td>{esc(str(k))}</td><td>{esc(str(v))}</td></tr>"
        for k, v in sorted(metricas.items())
    ) or "<tr><td colspan='2'>sem métricas</td></tr>"
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Painel — Serviço de Ingestão</title>
<style>
body{{font-family:system-ui,Arial,sans-serif;margin:0;background:#f6f7f9;color:#1a1a1a}}
.wrap{{max-width:900px;margin:0 auto;padding:24px}}
.card{{background:#fff;border:1px solid #e2e2e2;border-radius:10px;padding:16px 20px;margin:12px 0}}
table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #e2e2e2;padding:8px;text-align:left}}
.badge{{display:inline-block;padding:2px 10px;border-radius:999px;color:#fff;background:{mongo_cor}}}
code{{background:#eee;padding:2px 6px;border-radius:6px}}
a{{color:#0b57d0}}
</style>
</head>
<body><div class="wrap">
<h1>Painel — Serviço de Ingestão</h1>
<p>Opere o microserviço sem o portal: acompanhe a saúde abaixo e use os
<a href="/docs">Swagger (/docs)</a> para testar cada endpoint.</p>
<div class="card"><h2>Estado atual</h2>
<table>
<tr><th>Indicador</th><th>Valor</th></tr>
<tr><td>MongoDB</td><td><span class="badge">{mongo_txt}</span></td></tr>
<tr><td>Fontes ativas (total)</td><td>{esc(str(dados.get('fontes_ativas')))} ({esc(str(dados.get('fontes_total')))})</td></tr>
<tr><td>Última execução</td><td>{esc(str(dados.get('ultima_execucao')))} — itens: {esc(str(dados.get('ultima_itens')))}, custo USD: {esc(str(dados.get('ultima_custo')))}</td></tr>
<tr><td>Custo LLM hoje (USD)</td><td>{esc(str(dados.get('custo_hoje')))}</td></tr>
<tr><td>Fila pendente</td><td>{esc(str(dados.get('fila_pendente')))}</td></tr>
</table></div>
<div class="card"><h2>Métricas em memória</h2>
<table><tr><th>Contador</th><th>Valor</th></tr>{linhas_metricas}</table></div>
<div class="card"><h2>Endpoints</h2>
<ul>
<li><a href="/docs">/docs</a> — Swagger interativo (use o header <code>X-API-Token</code>)</li>
<li><a href="/openapi.json">/openapi.json</a> — contrato OpenAPI</li>
<li><a href="/healthz">/healthz</a> — saúde (sem auth) · <code>/api/v1/healthz</code> com auth</li>
<li><a href="/metrics">/metrics</a> — contadores (sem auth na raiz)</li>
<li><code>GET /api/v1/fontes</code> — listar fontes</li>
<li><code>POST /api/v1/fontes/sincronizar</code> — espelhar fontes do portal (<code>{{"fontes":[...]}}</code>)</li>
<li><code>POST /api/v1/ingestao/executar</code> — disparar ciclo de ingestão</li>
<li><code>GET /api/v1/ingestao/execucoes</code> — últimas 50 execuções</li>
<li><code>GET /api/v1/fila?status=pendente</code> — fila de revisão</li>
<li><code>GET /api/v1/config</code> — configuração do robô</li>
<li><code>GET /api/v1/feed</code> — feed curado (só aprovados)</li>
</ul>
<p>Operação típica: 1) sincronize as fontes do portal; 2) dispare
<code>POST /ingestao/executar</code>; 3) revise a fila
(<code>POST /fila/{{id}}/decisao</code> com <code>{{"acao":"aprovar"}}</code>);
4) confira o <code>/feed</code>.</p>
</div>
</div></body></html>"""


@router.get(
    "/painel",
    response_class=HTMLResponse,
    summary="Painel de controle (HTML)",
    description=(
        "Página HTML simples, sem framework, com o estado operacional do serviço "
        "(Mongo, fontes ativas, última execução, custo de hoje, fila pendente) e "
        "links para o Swagger e os endpoints. Permite operar sem o portal. "
        "Requer header `X-API-Token` nesta versão autenticada; a raiz `/painel` "
        "expõe a mesma página sem auth para acesso via navegador."
    ),
    response_description="Página HTML do painel.",
)
def painel() -> HTMLResponse:
    return HTMLResponse(construir_html(coletar_status()))

