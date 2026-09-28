#!/usr/bin/env python3
"""
Prova de poder discriminante das 14 REGRAS DE ALERTA (P2-01).

Uma regra que não pode disparar é pior que uma regra não testada: ocupa uma
linha no arquivo, aparece no catálogo de alertas e dá a impressão de que o
sinal está coberto. Este script usa o framework de teste UNITÁRIO do
`promtool` (`promtool test rules`), que é a ferramenta canônica para isso.

Para cada regra, dois casos, e os dois importam:

  FIRES  injeta a série que a regra vigia e exige que a expressão vale 1
         (a regra dispara);
  SILENT com a série no estado normal (ou com as séries que develop NÃO expõe,
         no caso das regras de lacuna) exige que a expressão NÃO vale 1
         (a regra não dispara).

Sem o segundo caso não há prova: uma regra que dispara sempre também
"detecta" a condição. E, para as regras de `absent()` — que é o mecanismo do
`not_configured` deste lote — o caso SILENT é o que mostra que elas ESCUTAM o
dado aparecer, e não apenas reclamam da falta dele.

As séries injetadas são as que develop EXPÕE de fato, com os rótulos que o
backend emite (verificado executando `GET /metrics`; a tabela completa está em
`../verificar-correspondencia.py`).

Uso:  python3 infra/observability/proving/provar-regras.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parents[2]
ALERTAS = REPO / "infra" / "observability" / "alerts"
CACHE = Path.home() / ".cache" / "p2-01-provar-regras"

# --------------------------------------------------------------------------
# As séries que develop expõe, prontas para o formato de teste do promtool.
# `cresce` = 20 amostras crescentes (suficiente para qualquer `rate()` de 5 m
# com `evaluation_interval: 1m`).
# --------------------------------------------------------------------------
SERIES = {
    "portal_readyz_ok":
        'portal_readyz_total{ambiente="production",situacao="ok"} 0+30x20',
    "portal_readyz_naopronto":
        'portal_readyz_total{ambiente="production",situacao="nao_pronto"} 0+3x20',
    "portal_readyz_duracao":
        'portal_readyz_duracao_ms{ambiente="production"} 40+0x20',
    "portal_health_detail_ok":
        'portal_health_detail_total{ambiente="production",situacao="ok"} 0+20x20',
    "portal_health_detail_degradado":
        'portal_health_detail_total{ambiente="production",situacao="degradado"} 0+2x20',
    # 30/min = 0,5/s, acima do limiar de 0,1/s de PortalAcessoPrivadoSendoSondado.
    "portal_acesso_negado_metrics":
        'portal_acesso_negado_total{ambiente="production",recurso="metrics"} 0+30x20',
    "portal_config_insegura_email":
        'portal_config_insegura_total{ambiente="production",item="email_backend"} 0+2x20',
    "portal_email_sem_canal":
        'portal_email_entrega_total{ambiente="production",destino="newsletter",'
        'situacao="sem_canal"} 0+2x20',
    "portal_email_falha_provedor":
        'portal_email_falha_provedor_total{ambiente="production",destino="newsletter",'
        'tipo="TimeoutError"} 0+2x20',
    "portal_up_api_1":
        'up{ambiente="production",job="portal-api",instance="127.0.0.1:5103"} 1+0x20',
    "portal_up_api_0":
        'up{ambiente="production",job="portal-api",instance="127.0.0.1:5103"} 0+0x20',
    "portal_up_alloy_1":
        'up{ambiente="production",job="alloy",instance="127.0.0.1:12345"} 1+0x20',
    "portal_uptime_estavel":
        'portal_tempo_de_atividade_segundos{ambiente="production"} 1000+60x20',
    # gauge que CAI três vezes em 30 min: o `changes()` conta quedas
    "portal_uptime_caindo":
        'portal_tempo_de_atividade_segundos{ambiente="production"} '
        '1000+600x4 10+600x4 20+600x4 30+600x4',
    "portal_cardinalidade_alta": None,  # gerado abaixo
    "portal_cardinalidade_baixa": None,
}

# 8 séries distintas: o orçamento de 200 NÃO dispara. 250 séries: dispara.
def _cardinalidade(n: int) -> list[str]:
    return [f'portal_metrica_de_teste_{i}{{ambiente="production"}} 1+0x20' for i in range(n)]


# --------------------------------------------------------------------------
# Casos: (alerta, arquivos de regra, séries do caso FIRES, séries do caso
# SILENT, descrição do que cada caso prova)
# --------------------------------------------------------------------------
CASOS = [
    dict(
        alerta="PortalApiInacessivel",
        desc_fires="API fora do ar: `up{job=portal-api}` = 0",
        fires=["portal_up_api_0"],
        desc_silent="API no ar: `up` = 1",
        silent=["portal_up_api_1"],
    ),
    dict(
        alerta="PortalReadinessFalha",
        desc_fires="readiness respondeu `nao_pronto` (é o que views.py:116 conta)",
        fires=["portal_readyz_ok", "portal_readyz_naopronto"],
        desc_silent="só existem respostas `ok` — a série `nao_pronto` NÃO é emitida "
                    "e a regra não pode distinguir isso de 'não sei' (é o que "
                    "PortalReadinessNaoSondada cobre)",
        silent=["portal_readyz_ok"],
    ),
    dict(
        alerta="PortalReadinessNaoSondada",
        desc_fires="ninguém sondou /readyz no ambiente: nenhum portal_readyz_total",
        fires=[],
        # AS DUAS séries: a regra é `absent(A) or absent(B)`, então injetar só
        # `A` a mantém disparando. Foi a primeira versão deste teste que
        # "reprovou" — e estava certa: a regra é sensível aos dois lados.
        desc_silent="/readyz foi sondado: as DUAS séries existem e a regra resolve",
        silent=["portal_readyz_ok", "portal_readyz_duracao"],
    ),
    dict(
        alerta="PortalColetorIndisponivel",
        desc_fires="não há `up{job=alloy}`: o coletor parou",
        fires=[],
        desc_silent="o coletor está no ar",
        silent=["portal_up_alloy_1"],
    ),
    dict(
        alerta="PortalTelemetriaAusente",
        desc_fires="nenhuma série do ambiente production para o job portal-api",
        fires=[],
        desc_silent="o ambiente production envia telemetria — o que só é verdade "
                    "porque `config.alloy` posta `ambiente` como rótulo EM BANDA "
                    "via `prometheus.relabel`; com só `external_labels` esta "
                    "regra nunca dispararia",
        silent=["portal_up_api_1"],
    ),
    dict(
        alerta="PortalTelemetriaNaoInstrumentada",
        desc_fires="as 16 séries que develop NÃO expõe estão todas ausentes: a "
                   "regra de lacuna dispara. Este é o teste do `not_configured`",
        fires=[],
        desc_silent="develop passou a expor uma daquelas séries: a regra de lacuna "
                    "RESOLVE. Sem esta metade, ela seria só um alarme fixo",
        silent=["portal_http_requests_total_presente"],
    ),
    dict(
        alerta="PortalDependenciaCriticaIndisponivel",
        desc_fires="checagem de dependência falhou (health_detail = degradado)",
        fires=["portal_health_detail_ok", "portal_health_detail_degradado"],
        desc_silent="todas as checagens passaram",
        silent=["portal_health_detail_ok"],
    ),
    dict(
        alerta="PortalFilaDeMonitoracaoAusente",
        desc_fires="nem o scrape da API nem o registro de configuração chegaram: "
                   "o canal pelo qual o Loki enxerga `saude_filas` morreu",
        fires=[],
        desc_silent="a telemetria do ambiente está chegando (é o que sustenta o "
                    "painel de filas pelo canal JSON oficial)",
        silent=["portal_up_api_1", "portal_config_insegura_email"],
    ),
    dict(
        alerta="PortalEmailNaoEntregue",
        desc_fires="alguém tentou entregar e-mail e não havia canal (P1-04)",
        fires=["portal_email_sem_canal"],
        desc_silent="nenhuma tentativa sem canal",
        silent=["portal_config_insegura_email"],  # série existe, mas não a vigiada
    ),
    dict(
        alerta="PortalEmailFalhaProvedor",
        desc_fires="o provedor de e-mail lançou exceção",
        fires=["portal_email_falha_provedor"],
        desc_silent="o provedor não lançou exceção",
        silent=["portal_email_sem_canal"],
    ),
    dict(
        alerta="PortalConfiguracaoInsegura",
        desc_fires="configuração insegura ativa (item email_backend)",
        fires=["portal_config_insegura_email"],
        desc_silent="nenhuma configuração insegura",
        silent=["portal_readyz_ok"],
    ),
    dict(
        alerta="PortalAcessoPrivadoSendoSondado",
        desc_fires="negação constante ao endpoint privado (0,25/s > 0,1/s)",
        fires=["portal_acesso_negado_metrics"],
        desc_silent="sem negação acima do limiar",
        silent=["portal_config_insegura_email"],
    ),
    dict(
        alerta="PortalCardinalidadeAcimaDoOrcamento",
        desc_fires="250 séries `portal_*` no ambiente, acima do orçamento de 200",
        fires=["cardinalidade_alta"],
        desc_silent="8 séries `portal_*`: orçamento respeitado",
        silent=["cardinalidade_baixa"],
    ),
    dict(
        alerta="PortalProcessoReiniciando",
        desc_fires="o uptime caiu três vezes em 30 min (crash loop)",
        fires=["portal_uptime_caindo"],
        desc_silent="uptime subindo monotonicamente (um restart isolated)",
        silent=["portal_uptime_estavel"],
    ),
]


def series_de(nome: str) -> list[str]:
    if nome == "cardinalidade_alta":
        return _cardinalidade(250)
    if nome == "cardinalidade_baixa":
        return _cardinalidade(8)
    if nome == "portal_http_requests_total_presente":
        # Uma das 16 séries da regra de lacuna, agora EXISTINDO. É o que tem de
        # fazer a regra de lacuna resolver.
        return ['portal_http_requests_total{ambiente="production",status="200"} 0+40x20']
    v = SERIES[nome]
    return [v] if v else []


def series_de_all(nomes: list[str]) -> list[str]:
    out: list[str] = []
    for n in nomes:
        out.extend(series_de(n))
    return out


def main() -> int:
    import yaml

    if shutil_missing():
        print("ERRO: shutil indisponível")
        return 2

    regras_por_nome = {}
    for caminho in sorted(ALERTAS.glob("regras-*.yaml")):
        d = yaml.safe_load(caminho.read_text(encoding="utf-8"))
        for g in d.get("groups", []):
            for r in g.get("rules", []):
                if "alert" in r:
                    regras_por_nome[r["alert"]] = r

    faltando = [c["alerta"] for c in CASOS if c["alerta"] not in regras_por_nome]
    if faltando:
        print(f"ERRO: alerta(s) no arquivo de regras que este script não cobre: {faltando}")
        return 2

    # COMPLETUDE: um alerta sem caso aqui é um alerta NÃO PROVADO. Sem esta
    # checagem, alguém que acrescente uma regra nova receberia "SUCCESS" sem
    # que a regra tivesse sido exercitada — que é o falso verde desta prova.
    sem_caso = sorted(set(regras_por_nome) - {c["alerta"] for c in CASOS})
    if sem_caso:
        print(f"ERRO: alerta(s) no arquivo de regras SEM caso de prova: {sem_caso}")
        print("      Toda regra precisa dos dois lados: DISPARA com a série do sinal, "
              "e RESOLVE sem ele.")
        return 2

    CACHE.mkdir(parents=True, exist_ok=True)
    for f in ALERTAS.glob("regras-*.yaml"):
        (CACHE / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")

    # Um `tests:` por caso, cada um com os dois lados (fires/silent).
    blocos = ["# Gerado por infra/observability/proving/provar-regras.py.",
              "evaluation_interval: 1m", "rule_files:",
              "  - regras-disponibilidade.yaml", "  - regras-operacao.yaml", "tests:"]
    rotulos: list[tuple[str, str, bool]] = []
    for c in CASOS:
        expr = regras_por_nome[c["alerta"]]["expr"].strip()
        linha_expr = " ".join(ln.strip() for ln in expr.splitlines())
        for desc, series, quer_1 in (
            (c["desc_fires"], series_de_all(c["fires"]), True),
            (c["desc_silent"], series_de_all(c["silent"]), False),
        ):
            blocos.append("  - interval: 1m")
            if series:
                blocos.append("    input_series:")
                for s in series:
                    nome, valores = s.split(" ", 1)
                    blocos.append(f"      - series: '{nome}'")
                    blocos.append(f"        values: '{valores}'")
            else:
                blocos.append("    input_series: []")
            blocos.append("    promql_expr_test:")
            # `count()` ENVOLVE a expressão de propósito. O `promtool` exige
            # comparar amostras exatas, e uma comparação PromQL devolve o
            # VALOR DO LADO ESQUERDO quando é verdadeira (`changes(...) >= 3`
            # devolve 19, não 1). O que o teste precisa afirmar é a DECISÃO
            # — "dispara" ou "não dispara" —, não o número: `count()` de um
            # vetor vazio é vazio (não 0), então o caso SILENT fica sem
            # `exp_samples` e o promtool exige resultado vazio.
            testada = "count(" + linha_expr + ")"
            blocos.append('      - expr: "' + testada.replace("\\", "\\\\").replace('"', '\\"') + '"')
            blocos.append("        eval_time: 20m")
            if quer_1:
                blocos.append("        exp_samples:")
                blocos.append("          - labels: '{}'")
                blocos.append("            value: 1")
            rotulos.append((c["alerta"], desc, quer_1))

    (CACHE / "testes.yaml").write_text("\n".join(blocos) + "\n", encoding="utf-8")

    r = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "promtool", "-v", f"{CACHE}:/r:ro",
         "prom/prometheus:latest", "test", "rules", "/r/testes.yaml"],
        capture_output=True, text=True,
    )
    saida = r.stdout + r.stderr
    print("=" * 100)
    print("promtool test rules — cada alerta avaliado em DOIS cenários")
    print("=" * 100)
    print(saida.strip() or "(sem saída)")
    print()
    print(f"exit={r.returncode}")
    ok = r.returncode == 0
    print()
    print("VEREDITO:", f"as {len(CASOS)} regras do arquivo demonstram que DISPARAM "
          "com o sinal presente e que RESOLVEM com ele ausente" if ok
          else "HÁ REGRA QUE NÃO DISPARA OU NÃO RESOLVE — ver acima")
    return 0 if ok else 1


def shutil_missing() -> bool:
    try:
        import shutil  # noqa: F401
        return False
    except ImportError:
        return True


if __name__ == "__main__":
    raise SystemExit(main())
