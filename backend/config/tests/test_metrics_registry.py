"""Registro de métricas técnicas: exposição, limites e robustez.

Critérios 14 e 17 (implementation-contract.md) e a robustez do registry contra
cardinalidade alimentada por tráfego público.
"""

from __future__ import annotations

import math

from config.metrics import (
    DESCARTE_OUTRAS,
    MAX_SERIES,
    MAX_SERIES_DESCARTE,
    MAX_SERIES_POR_METRICA,
    METRICS,
    SERIES_DROPPED,
    MetricsRegistry,
    normalizar_metodo,
    normalizar_rota,
    normalizar_status,
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


def test_histograma_acumula_buckets_e_nao_guarda_observacoes():
    """Os buckets são acumulados na observação, não recalculados no scrape.

    A versão anterior guardava até 10 000 floats por série e recontava tudo a
    cada exposição: 200 séries × 10 000 observações custavam 0,89 s e 33 MB de
    cópia por scrape, com o lock do registry segurado. Aqui o custo por
    observação é O(#buckets) e o render só lê contadores prontos.
    """

    registry = MetricsRegistry()
    for _ in range(3):
        registry.observe("portal_teste", 0.3)
    registry.observe("portal_teste", 30.0)

    stats = registry.snapshot()["histograms"][("portal_teste", ())]

    # Só os contadores: nenhuma lista de observações sobrevive.
    assert stats["counts"][0] == 0  # `le=0.005` não recebia nenhum 0.3
    assert stats["total"] == 4
    assert math.isclose(stats["soma"], 30.9)
    linhas = _render(registry).splitlines()
    assert 'portal_teste_bucket{le="0.5"} 3' in linhas
    assert 'portal_teste_bucket{le="+Inf"} 4' in linhas
    assert "portal_teste_count 4" in linhas


def test_buckets_acumulados_preservam_a_semantica_cumulativa():
    """Bucket é cumulativo: `le` maior inclui os valores dos `le` menores."""

    registry = MetricsRegistry()
    for valor in (0.004, 0.02, 0.4, 3.0, 90.0):
        registry.observe("portal_cumulativo", valor)

    linhas = _render(registry).splitlines()

    def _count(le: str) -> int:
        alvo = f'portal_cumulativo_bucket{{le="{le}"}}'
        return int(next(linha for linha in linhas if linha.startswith(alvo)).rsplit(" ", 1)[1])

    assert _count("0.005") == 1
    assert _count("0.025") == 2
    assert _count("0.5") == 3
    assert _count("5") == 4
    assert _count("+Inf") == 5


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

    # `rota` é o rótulo de entrada direto (`inc` não normaliza: a normalização
    # do vocabulário é de `record_http`/middleware), então aqui a família
    # estoura primeiro o TETO POR FAMÍLIA, e não o global. O global continua
    # sendo a rede de segurança para quem espalha por várias famílias.
    assert len(series) == MAX_SERIES_POR_METRICA
    assert f'{SERIES_DROPPED}{{metric="portal_http_requests_total"}} 500' in _render(registry)


def test_familia_farta_nao_derruba_metricas_de_sistema():
    """Achado MAJOR-2: com só o teto global, uma família que estourou 5 000
    séries (o `method` controlado pelo cliente fazia exatamente isso) levava
    `portal_http_requests_total`, `portal_ready` e a profundidade de uma fila
    nova embora sumirem do `/metrics` em silêncio. O teto por família impede
    que a família barulhenta coma o orçamento inteiro."""

    registry = MetricsRegistry()
    for indice in range(MAX_SERIES + 100):
        registry.inc("portal_http_requests_total", method=f"ZZZ{indice}")
    registry.inc("portal_ready")
    registry.gauge("portal_celery_queue_depth", 3, queue="celery")

    texto = _render(registry)

    assert "portal_ready 1" in texto
    assert 'portal_celery_queue_depth{queue="celery"} 3' in texto
    # E o que já existia continua íntegro: a família barulhenta não apaga
    # ninguém, só recusa o que é novo.
    assert 'portal_http_requests_total{method="ZZZ0"} 1' in texto
    series = [
        chave
        for chave in registry.snapshot()["counters"]
        if chave[0] == "portal_http_requests_total"
    ]
    assert len(series) == MAX_SERIES_POR_METRICA


def test_teto_global_continua_valendo_entre_familias():
    registry = MetricsRegistry()
    for indice in range(MAX_SERIES + 10):
        registry.inc(f"portal_familia_{indice}")

    series = [k for k in registry.snapshot()["counters"] if k[0].startswith("portal_familia_")]
    assert len(series) == MAX_SERIES
    assert f'{SERIES_DROPPED}{{metric="portal_familia_' in _render(registry)


def test_descarte_nao_cria_serie_nova_para_cada_nome_de_metrica():
    """O contador do descarte é imune ao teto GLOBAL, então ele próprio tem
    teto: sem isso, "criar uma família por vez" trocava o problema de família."""

    registry = MetricsRegistry()
    for indice in range(MAX_SERIES + MAX_SERIES_DESCARTE + 50):
        registry.inc(f"portal_familia_{indice}")

    rotulos = [
        chave[1] for chave in registry.snapshot()["counters"] if chave[0] == SERIES_DROPPED
    ]

    assert len(rotulos) <= MAX_SERIES_DESCARTE + 1  # + o agregado "__outras__"
    assert any(("metric", DESCARTE_OUTRAS) in rotulo for rotulo in rotulos)


def test_teto_nao_bloqueia_a_metrica_que_conta_o_descarte():
    registry = MetricsRegistry()
    for indice in range(MAX_SERIES_POR_METRICA + 10):
        registry.inc("portal_http_requests_total", rota=f"/r/{indice}")

    # Um `inc` da própria métrica de descarte continua funcionando mesmo com o
    # registry cheio (senão contaria o descarte recursivamente).
    registry.inc(SERIES_DROPPED)
    assert f"{SERIES_DROPPED} " in _render(registry)


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


# ---------------------------------------------------------------------------
# Rótulo controlado pelo cliente (achado MAJOR-2)
# ---------------------------------------------------------------------------


def test_method_forjado_vira_other_e_nao_cria_serie_nova():
    """`request.method` é texto do cliente e o parser HTTP aceita qualquer
    token. Sem allowlist, cada scanner criava DUAS séries por requisição
    (counter + histograma) e envenenava o rótulo que o operador filtra."""

    METRICS.clear()
    for indice in range(50):
        record_http(f"ZZZ{indice}", "/api/feed/", 200, 0.01)

    texto = METRICS.render_prometheus()
    linhas_http = [linha for linha in texto.splitlines() if linha.startswith("portal_http_requests_total{")]

    assert len(linhas_http) == 1
    assert 'method="other",route="/api/feed/",status="200"' in linhas_http[0]
    assert "ZZZ" not in texto


def test_metodos_http_reais_passam_pela_allowlist():
    for metodo in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"):
        assert normalizar_metodo(metodo) == metodo
    # Case é normalizada para maiúsculas antes do confronto: o token HTTP é
    # case-sensitive, mas um `get` minúsculo é o mesmo método — dobrá-lo em
    # `GET` mantém a cardinalidade em 1 e ainda mostra o que aconteceu.
    assert normalizar_metodo("get") == "GET"
    assert normalizar_metodo("") == "other"
    assert normalizar_metodo(None) == "other"
    assert normalizar_metodo("PROPFIND") == "other"
    assert normalizar_metodo("ZZZ123") == "other"


def test_status_forjado_vira_other():
    assert normalizar_status(200) == "200"
    assert normalizar_status("404") == "404"
    assert normalizar_status("200 OK") == "other"
    assert normalizar_status(0) == "other"
    assert normalizar_status(None) == "other"


def test_status_que_nao_e_codigo_http_nao_cria_serie_no_caminho_normal():
    """Prova pelo caminho de produção (`record_http`): é lá que o rótulo entra
    no `/metrics`."""

    METRICS.clear()
    record_http("GET", "/api/x/", "200 OK injected", 0.01)
    record_http("GET", "/api/x/", 200, 0.02)

    texto = METRICS.render_prometheus()
    assert 'status="other"' in texto
    assert 'status="200"' in texto
    assert "injected" not in texto


def test_rota_e_truncada_e_nunca_vazia():
    assert normalizar_rota(None) == "unknown"
    assert normalizar_rota("") == "unknown"
    assert len(normalizar_rota("/x" * 500)) == 200


def test_scrape_nao_custa_mais_que_as_series_existentes():
    """O trabalho caro saiu do lock: o render lê contadores acumulados.

    Antes, `render_prometheus` copiava e reordenava TODAS as observações
    retidas dentro do lock a cada scrape. Aqui o custo é limitado às séries que
    existem e não cresce com o número de observações já registradas.
    """

    registry = MetricsRegistry()
    for _ in range(20_000):
        registry.observe("portal_bulk", 0.42, task="t")
    primeira = _render(registry)

    assert 'portal_bulk_count{task="t"} 20000' in primeira
    # Nenhuma observação sobreviveu no registry (só contadores).
    stats = registry.snapshot()["histograms"][("portal_bulk", (("task", "t"),))]
    assert set(stats) == {"limits", "counts", "total", "soma"}
