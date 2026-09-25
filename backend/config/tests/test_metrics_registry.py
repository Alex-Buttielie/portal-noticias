"""Registro de métricas técnicas: exposição, limites e robustez.

Critérios 14 e 17 (implementation-contract.md) e a robustez do registry contra
cardinalidade alimentada por tráfego público.
"""

from __future__ import annotations

import math

from config.metrics import (
    MAX_OBSERVATIONS,
    MAX_SERIES,
    METRICS,
    SERIES_DROPPED,
    MetricsRegistry,
    record_celery,
    record_degradacao,
    record_dependency,
    record_http,
)


def _render(registry: MetricsRegistry) -> str:
    return registry.render_prometheus()


# ---------------------------------------------------------------------------
# Exposição Prometheus
# ---------------------------------------------------------------------------


def test_registry_vazio_nao_emit_linha_quebrada():
    assert _render(MetricsRegistry()) == ""


def test_counter_e_histograma_com_help_e_type():
    registry = MetricsRegistry()
    registry.inc("portal_teste_total", valor="a")
    registry.observe("portal_teste_segundos", 0.3)

    linhas = _render(registry).splitlines()

    assert "# HELP portal_teste_total portal teste total" in linhas
    assert "# TYPE portal_teste_total counter" in linhas
    assert 'portal_teste_total{valor="a"} 1' in linhas
    assert "# TYPE portal_teste_segundos histogram" in linhas
    assert 'portal_teste_segundos_bucket{le="0.25"} 0' in linhas
    assert 'portal_teste_segundos_bucket{le="0.5"} 1' in linhas
    assert 'portal_teste_segundos_bucket{le="+Inf"} 1' in linhas
    assert "portal_teste_segundos_count 1" in linhas
    assert "portal_teste_segundos_sum 0.3" in linhas


def test_histograma_respeita_buckets_customizados():
    registry = MetricsRegistry()
    registry.observe("portal_custom", 5.0, buckets=(1, 10))

    linhas = _render(registry).splitlines()

    assert 'portal_custom_bucket{le="1"} 0' in linhas
    assert 'portal_custom_bucket{le="10"} 1' in linhas
    # Não pode leaking o bucket default: mentiria sobre o recorte pedido.
    assert 'portal_custom_bucket{le="2.5"}' not in "\n".join(linhas)


def test_gauge_mantem_o_ultimo_valor():
    registry = MetricsRegistry()
    registry.gauge("portal_fila", 12)
    registry.gauge("portal_fila", 3)

    linhas = _render(registry).splitlines()

    assert "# TYPE portal_fila gauge" in linhas
    assert "portal_fila 3" in linhas
    assert "portal_fila 12" not in "\n".join(linhas)


def test_labels_escapam_aspas_e_novas_linhas():
    registry = MetricsRegistry()
    registry.inc("portal_teste_total", rota='a"b\nc\\d')

    assert 'rota="a\\"b\\nc\\\\d"' in _render(registry)


def test_valores_nao_finitos_sao_descartados():
    registry = MetricsRegistry()
    registry.observe("portal_teste", float("nan"))
    registry.observe("portal_teste", float("inf"))
    registry.gauge("portal_gauge", float("-inf"))

    assert "portal_teste" not in _render(registry)
    assert "portal_gauge" not in _render(registry)


def test_observacoes_sao_limitadas_por_serie():
    registry = MetricsRegistry()
    for _ in range(MAX_OBSERVATIONS + 50):
        registry.observe("portal_teste", 1.0)

    total = len(registry.snapshot()["observations"][("portal_teste", ())])

    assert total == MAX_OBSERVATIONS


# ---------------------------------------------------------------------------
# Cardinalidade
# ---------------------------------------------------------------------------


def test_teto_de_cardinalidade_nao_deixa_o_registry_crescer_sem_limite():
    """Um 404 por path aleatório criaria uma série por requisição: o dict
    cresceria para sempre (OOM) e o Grafana receberia `instance` inútil."""

    registry = MetricsRegistry()
    for indice in range(MAX_SERIES + 500):
        registry.inc("portal_http_requests_total", rota=f"/scanner/{indice}")

    series = [k for k in registry.snapshot()["counters"] if k[0] == "portal_http_requests_total"]

    assert len(series) == MAX_SERIES
    # O descarte é visível: o teto não pode esconder cardinalidade excessiva.
    assert f"{SERIES_DROPPED} 500" in _render(registry)


def test_teto_nao_bloqueia_a_metrica_que_conta_o_descarte():
    registry = MetricsRegistry()
    for indice in range(MAX_SERIES + 10):
        registry.inc("portal_http_requests_total", rota=f"/r/{indice}")

    # Um `inc` da própria métrica de descarte continua funcionando mesmo com o
    # registry cheio (senão contaria o descarte recursivamente).
    registry.inc(SERIES_DROPPED)
    assert f"{SERIES_DROPPED} 11" in _render(registry)


def test_helpers_publicos_nao_esticam_cardinalidade_dos_labels():
    METRICS.clear()
    for _ in range(3):
        record_http("GET", "/api/feed/", 200, 0.01)
        record_dependency("postgresql", True, 0.002)
        record_celery("feed.tasks.registrar_evento_busca", "SUCCESS", 0.5)
        record_degradacao("optional-dependency")

    texto = METRICS.render_prometheus()

    assert 'method="GET",route="/api/feed/",status="200"' in texto
    # Rótulos saem em ordem alfabética (canônico do registry).
    assert 'result="SUCCESS",task="feed.tasks.registrar_evento_busca"' in texto
    assert 'reason="optional-dependency"' in texto
    assert math.isclose(
        sum(
            float(linha.rsplit(" ", 1)[1])
            for linha in texto.splitlines()
            if linha.startswith("portal_http_requests_total{")
        ),
        3.0,
    )
