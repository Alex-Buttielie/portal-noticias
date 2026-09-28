#!/usr/bin/env python3
"""
Verificador de correspondência da malha de observabilidade (P2-01).

Duas funções, e as duas importam:

1. `promtool check rules` valida a SINTAXE e os TEMPLATES de cada expressão
   PromQL extraída dos 4 painéis e das 2 regras de alerta. Uma expressão que
   não compila é um painel em branco com erro escondido.

2. A checagem de CORRESPONDÊNCIA extrai os nomes de métria de toda expressão e
   confronta com a exposição REAL de `develop`. Duas classes de problema são
   reprovadas:
     * métrica pedida que o backend não expõe e que NÃO está dentro de um
       `absent(...)` — porque `absent()` é o jeito DECLARADO de denunciar a
       lacuna, e uma métrica fora de `absent()` é painel quebrado;
     * métrica exposta que nenhum painel nem regra usa — informação disponível
       que ninguém está olhando.

O verificador tem uma lista de métricas conhecidas de `develop` com
`arquivo:linha`, extraída executando `/metrics` contra o código real. Para
re-gerar essa lista depois de uma mudança no backend, rode:

    backend/manage.py shell -c "<o mesmo trecho de /home/alex-buttielie/scratch/on2/metricas_expostas.py>"
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Ground truth: o que `develop` (1dec732) expõe, com arquivo:linha.
# MEDIDO executando GET /metrics — não estimado.
# ---------------------------------------------------------------------------
EXPOSTO_EM_DEVELOP = {
    "portal_tempo_de_atividade_segundos": "backend/config/health.py:459-461",
    "portal_healthz_total": "backend/config/views.py:83",
    "portal_livez_total": "backend/config/views.py:97",
    "portal_readyz_total": "backend/config/views.py:116",
    "portal_readyz_duracao_ms": "backend/config/views.py:117",
    "portal_health_detail_total": "backend/config/views.py:142",
    "portal_acesso_negado_total": "backend/config/views.py:138,215",
    "portal_config_insegura_total": "backend/config/views.py:160,183",
    "portal_metrics_total": "backend/config/views.py:218",
    "portal_email_entrega_total": "backend/config/email_entrega.py:184-186",
    "portal_email_falha_provedor_total": "backend/config/email_entrega.py:210-212",
}

# Séries que NÃO vêm do backend e sim do coletor (existem se o Alloy rodar).
EXPOSTO_PELO_COLETOR = {
    "up": "infra/observability/alloy/config.alloy (prometheus.scrape)",
    "scrape_samples_scraped": "coletor",
    "scrape_duration_seconds": "coletor",
    "prometheus_remote_storage_samples_failed_total": "remote_write do coletor",
    "prometheus_remote_storage_samples_total": "remote_write do coletor",
    "prometheus_remote_storage_samples_retried_total": "remote_write do coletor",
    "prometheus_remote_storage_shards": "remote_write do coletor",
    "prometheus_remote_storage_queues": "remote_write do coletor",
    "prometheus_rule_evaluation_failures_total": "coletor",
    "loki_write_dropped_entries_total": "Loki write do coletor",
}

# Funções e construções da linguagem — não são nomes de métrica.
RESERVADO = {
    "absent", "and", "or", "unless", "by", "without", "on", "ignoring", "group_left",
    "group_right", "offset", "bool", "sum", "avg", "min", "max", "count", "topk",
    "bottomk", "quantile", "count_values", "stddev", "stdvar", "rate", "irate",
    "increase", "delta", "idelta", "deriv", "predict_linear", "changes", "resets",
    "histogram_quantile", "label_replace", "label_join", "vector", "time", "abs",
    "ceil", "floor", "exp", "ln", "log2", "log10", "sqrt", "clamp", "clamp_max",
    "clamp_min", "round", "scalar", "sort", "sort_desc", "day_of_month",
    "day_of_week", "days_in_month", "hour", "minute", "month", "year",
    "timestamp", "last_over_time", "present_over_time", "holt_winters",
    # meta-rótulos e construções
    "__name__", "job", "instance", "le", "quantile", "ambiente", "situacao",
    "recurso", "item", "destino", "status", "route", "task", "result", "queue",
    "dependency", "reason", "target", "check", "environment", "malha",
}

NOME_METRICA = re.compile(r"\b([a-z_][a-z0-9_]*)\b")


# Variáveis de template do GRAFANA (não do PromQL). Têm de sair antes da
# extração de nomes, senão `$__rate_interval` e `${ambiente:raw}` viram
# "métricas" inexistentes e o verificador acusa 46 falsos positivos.
TEMPLATE_GRAFANA = re.compile(
    r"\$\{[^}]*\}"          # ${ambiente:raw}
    r"|\$[A-Za-z_][A-Za-z0-9_]*"  # $__rate_interval, $labels, $value
)


def metricas_de(expr: str) -> set[str]:
    """Nomes de métrica referenciados por uma expressão PromQL."""
    # 1) remove templates do Grafana ($__rate_interval, ${ambiente:raw}, …)
    sem_template = TEMPLATE_GRAFANA.sub(" ", expr)
    # 2) remove literais de string: nenhum nome dentro de "..." é métrica.
    sem_strings = re.sub(r'"[^"]*"', ' ', sem_template)
    # 3) remove comentários de linha.
    sem_strings = re.sub(r"#.*", ' ', sem_strings)
    brutos = set(NOME_METRICA.findall(sem_strings))
    return {n for n in brutos if n not in RESERVADO}


def dentro_de_absent(expr: str) -> set[str]:
    """Nomes citados dentro de um `absent(...)` — declarada como lacuna."""
    encontrados: set[str] = set()
    for m in re.finditer(r"absent\s*\(", expr):
        nivel = 1
        i = m.end()
        while i < len(expr) and nivel:
            if expr[i] == "(":
                nivel += 1
            elif expr[i] == ")":
                nivel -= 1
            i += 1
        encontrados |= metricas_de(expr[m.end():i - 1])
    return encontrados


def _para_promtool(expr: str) -> str:
    """Substitui templates do Grafana por valores literais válidos em PromQL.

    Sem isto o `promtool` reprovaria por `sum by (ambiente)` onde o Grafana
    escreveria `sum by (${ambiente:raw})` — o que é um problema do VALIDADOR,
    não da expressão.
    """
    expr = re.sub(r"\$\{ambiente(:raw|:regex)?\}", "production", expr)
    expr = re.sub(r"\$\{ambiente\}", "production", expr)
    expr = expr.replace("$__rate_interval", "5m").replace("$__range", "1h")
    expr = TEMPLATE_GRAFANA.sub("x", expr)
    return expr


def expressoes_dos_paineis(raiz: Path):
    """(arquivo, painel_id, título, expr) para cada alvo de painel."""
    for caminho in sorted(raiz.glob("*.json")):
        d = json.loads(caminho.read_text(encoding="utf-8"))
        for p in d.get("panels", []):
            for t in p.get("targets", []) or []:
                e = t.get("expr")
                if e and (t.get("datasource") or {}).get("type") == "prometheus":
                    yield caminho.name, p.get("id"), p.get("title"), e


def expressoes_das_regras(raiz: Path):
    import yaml
    for caminho in sorted(raiz.glob("*.yaml")):
        d = yaml.safe_load(caminho.read_text(encoding="utf-8"))
        for g in d.get("groups", []):
            for r in g.get("rules", []):
                if "expr" in r:
                    yield caminho.name, r["alert"], r["alert"], r["expr"]


def main() -> int:
    raiz = Path(sys.argv[1] if len(sys.argv) > 1 else "infra/observability")
    paineis = raiz / "grafana" / "dashboards"
    alertas = raiz / "alerts"

    print("=" * 100)
    print("1) SINTAXE E TEMPLATES — promtool check rules sobre TUDO que tem PromQL")
    print("=" * 100)
    # O promtool só valida `expr` dentro de blocos `alert:`/`record:`. Para os
    # painéis, cada `expr` vira uma regra de alerta descartável — é assim que se
    # obtém a validação de parser PromQL e de template Go que existe.
    # O diretório temporário NÃO pode ser o /tmp do host: o daemon do Docker
    # não enxerga esse tmpfs (o volume é recusado com "mounts denied"), e o
    # /tmp é tmpfs com limite apertado. Usa o diretório de cache do usuário.
    cache_dir = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    os.makedirs(cache_dir, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache_dir) as td:
        arquivos = []
        for nome, _pid, _titulo, expr in expressoes_dos_paineis(paineis):
            corpo = (
                "groups:\n  - name: painel\n    rules:\n"
                "      - alert: ValidaExprDoPainel\n"
                "        expr: |\n"
                + "".join("          " + ln + "\n" for ln in _para_promtool(expr).splitlines())
                + "        labels:\n          severity: info\n"
                "        annotations:\n          summary: \"{{ $labels.ambiente }}\"\n"
            )
            p = Path(td) / f"{nome.replace('.json','')}_{len(arquivos)}.yaml"
            p.write_text(corpo, encoding="utf-8")
            arquivos.append(p)
        for nome, _al, _t, expr in expressoes_das_regras(alertas):
            corpo = (
                "groups:\n  - name: regra\n    rules:\n"
                "      - alert: ValidaExprDaRegra\n"
                "        expr: |\n"
                + "".join("          " + ln + "\n" for ln in expr.strip().splitlines())
                + "        labels:\n          severity: info\n"
                "        annotations:\n          summary: \"{{ $labels.ambiente }}\"\n"
            )
            p = Path(td) / f"{nome.replace('.yaml','')}_{len(arquivos)}.yaml"
            p.write_text(corpo, encoding="utf-8")
            arquivos.append(p)

        r = subprocess.run(
            ["docker", "run", "--rm", "--entrypoint", "promtool", "-v", f"{td}:/r:ro",
             "prom/prometheus:latest", "check", "rules", "--lint=all"]
            + [f"/r/{p.name}" for p in arquivos],
            capture_output=True, text=True,
        )
        ok_sintaxe = r.returncode == 0
        falhas = [l for l in (r.stdout + r.stderr).splitlines() if "FAILED" in l or "Error" in l]
        print(f"  expressões validadas: {len(arquivos)}")
        print(f"  promtool exit: {r.returncode}  ->  {'TODAS COMPILAM' if ok_sintaxe else 'REPROVOU'}")
        for f in falhas:
            print("   ", f)
        if ok_sintaxe:
            print("   ", [l for l in r.stdout.splitlines() if "SUCCESS" in l][:2])

    print()
    print("=" * 100)
    print("2) CORRESPONDÊNCIA — métrica pedida × exposta em develop")
    print("=" * 100)
    conhecidos = set(EXPOSTO_EM_DEVELOP) | set(EXPOSTO_PELO_COLETOR)
    usadas: dict[str, list[str]] = {}
    problemas: list[str] = []
    lacunas_declaradas: dict[str, list[str]] = {}

    for arquivo, pid, titulo, expr in list(expressoes_dos_paineis(paineis)) + list(
            expressoes_das_regras(alertas)):
        ausentes = dentro_de_absent(expr)
        for m in sorted(metricas_de(expr)):
            origem = f"{arquivo}#{pid}"
            if m in conhecidos:
                usadas.setdefault(m, []).append(origem)
                continue
            if m in ausentes:
                lacunas_declaradas.setdefault(m, []).append(origem)
                continue
            problemas.append(
                f"  QUEBRADO   {origem} [{titulo}] pede `{m}`, que develop não expõe "
                f"E não está declarado dentro de absent()"
            )

    total_expr = len(list(expressoes_dos_paineis(paineis))) + len(
        list(expressoes_das_regras(alertas)))
    print(f"  expressões analisadas: {total_expr}")
    print(f"  métricas de develop referenciadas fora de absent(): "
          f"{len([m for m in usadas if m in EXPOSTO_EM_DEVELOP])} de {len(EXPOSTO_EM_DEVELOP)}")
    print(f"  séries do coletor referenciadas: "
          f"{len([m for m in usadas if m in EXPOSTO_PELO_COLETOR])} de {len(EXPOSTO_PELO_COLETOR)}")
    print(f"  lacunas declaradas em absent(): {len(lacunas_declaradas)} séries")
    print()
    if problemas:
        print("  REFERÊNCIAS QUEBRADAS (reprovam o lote):")
        for p in problemas:
            print(p)
    else:
        print("  Nenhuma referência quebrada: toda métrica pedida fora de absent() existe em develop.")
    print()
    print("  developing exposto e NUNCA usado por painel ou regra:")
    nao_usado = [m for m in EXPOSTO_EM_DEVELOP if m not in usadas]
    if nao_usado:
        for m in nao_usado:
            print(f"    - {m}  ({EXPOSTO_EM_DEVELOP[m]})")
    else:
        print("    (nenhum: as 11 métricas de develop são usadas por pelo menos um painel ou regra)")

    print()
    print("=" * 100)
    print("VEREDITO")
    print("=" * 100)
    if ok_sintaxe and not problemas and not nao_usado:
        print("  APROVADO: todas as expressões compilam e toda referência existe em develop.")
        return 0
    if not ok_sintaxe:
        print("  REPROVADO por sintaxe/template.")
    if problemas:
        print(f"  REPROVADO por {len(problemas)} referência(s) quebrada(s).")
    if nao_usado:
        print(f"  AVISO: {len(nao_usado)} métrica(s) de develop sem nenhum painel ou regra.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
