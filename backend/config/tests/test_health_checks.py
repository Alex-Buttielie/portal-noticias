"""Checks de dependência do health: cache, beat, filas, disco e degradação.

Critérios 9, 16 e 17 (implementation-contract.md): cada dependência opcional
precisa de um resultado HONESTO — `not_configured` quando não há o que medir,
`degraded` quando há ponto cego, `error` quando a checagem falhou. Um "ok"
inventado aqui é o falso verde que a run existe para eliminar.
"""

from __future__ import annotations

import os
import time

import pytest
from django.core.cache import cache
from django.test import override_settings

from config import health

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _broker_em_memoria(monkeypatch):
    """`Settings.broker_url` do Celery prefere `os.environ` ao setting; o
    `.env` local aponta para o Redis real."""

    monkeypatch.setenv("CELERY_BROKER_URL", "memory://")
    monkeypatch.setenv("CELERY_BROKER_WRITE_URL", "memory://")
    health.reset_degraded_cache()
    yield
    health.reset_degraded_cache()


# ---------------------------------------------------------------------------
# Cache / Redis
# ---------------------------------------------------------------------------


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
def test_cache_locmem_e_not_configured_e_nao_conta_como_quebra():
    resultado = health.check_cache()

    assert resultado.status == "not_configured"
    assert resultado.required is False


def test_cache_com_round_trip_functionando_e_ok(tmp_path):
    """Backend de arquivo: é um cache de verdade (nem dummy nem locmem), então
    o check tem de exercitar o round-trip completo."""

    with override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
                "LOCATION": str(tmp_path),
            }
        }
    ):
        resultado = health.check_cache()

    assert resultado.status == "ok"
    assert resultado.meta["backend"] == "FileBasedCache"


def test_cache_que_sempre_falha_e_reportado_como_error(monkeypatch):
    """Com `IGNORE_EXCEPTIONS=True` (produção) o erro do Redis é engolido pelo
    backend: é o check que transforma queda silenciosa em sinal visível."""

    class _CacheQuebrado:
        def set(self, *_a, **_k):
            return False

        def get(self, *_a, **_k):
            return None

    monkeypatch.setattr(health, "cache", _CacheQuebrado())
    with override_settings(
        CACHES={"default": {"BACKEND": "django_redis.cache.RedisCache"}}
    ):
        resultado = health.check_cache()

    assert resultado.status == "error"
    assert "round-trip" in resultado.detail


# ---------------------------------------------------------------------------
# Beat
# ---------------------------------------------------------------------------


def test_beat_sem_heartbeat_configurado_nao_fica_verde():
    resultado = health.check_celery_beat()

    assert resultado.status == "not_configured"
    assert "OBSERVABILITY_BEAT_HEARTBEAT_FILE" in resultado.detail


def test_beat_com_heartbeat_recem_escrito_e_ok(tmp_path):
    arquivo = tmp_path / "beat.heartbeat"
    arquivo.write_text("ok")

    with override_settings(OBSERVABILITY_BEAT_HEARTBEAT_FILE=str(arquivo)):
        resultado = health.check_celery_beat()

    assert resultado.status == "ok"
    assert resultado.meta["age_seconds"] < 5


def test_beat_com_heartbeat_parado_e_degraded(tmp_path):
    arquivo = tmp_path / "beat.heartbeat"
    arquivo.write_text("ok")
    antigo = time.time() - 7200
    os.utime(arquivo, (antigo, antigo))

    with override_settings(
        OBSERVABILITY_BEAT_HEARTBEAT_FILE=str(arquivo),
        OBSERVABILITY_BEAT_MAX_AGE_SECONDS=900,
    ):
        resultado = health.check_celery_beat()

    assert resultado.status == "degraded"
    assert resultado.meta["age_seconds"] > 7000


def test_beat_com_arquivo_ausente_e_error(tmp_path):
    with override_settings(
        OBSERVABILITY_BEAT_HEARTBEAT_FILE=str(tmp_path / "nao-existe")
    ):
        resultado = health.check_celery_beat()

    assert resultado.status == "error"


# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------


def test_celery_broker_fora_do_ar_e_degraded_rapido(monkeypatch):
    """Com o broker recusado, `inspect().ping()` sozinho leva ~6 s (retries do
    kombu) numa thread que atende requisição: o portão `ensure_connection` com
    `max_retries=0` reduz para ~20 ms e o estado vira `degraded` (o portal
    serve tráfego sem worker) em vez de erro."""

    from config.celery import app

    class _ConexaoRecusada:
        def ensure_connection(self, **_k):
            raise ConnectionRefusedError("Error 111 connecting to localhost:6379")

        def release(self):
            return None

    monkeypatch.setattr(
        app,
        "connection_for_write",
        lambda **_k: _ConexaoRecusada(),
    )
    inicio = time.perf_counter()
    with override_settings(OBSERVABILITY_CHECK_CELERY=True):
        resultado = health.check_celery()
    duracao = time.perf_counter() - inicio

    assert resultado.status == "degraded"
    assert "broker unreachable" in resultado.detail
    assert resultado.meta["workers"] == 0
    assert duracao < 1.0


def test_celery_sem_worker_respondedor_e_degraded(monkeypatch):
    from config.celery import app

    class _ConexaoViva:
        def ensure_connection(self, **_k):
            return True

        def release(self):
            return None

    class _Inspector:
        def ping(self):
            return []

    monkeypatch.setattr(app, "connection_for_write", lambda **_k: _ConexaoViva())
    monkeypatch.setattr(app.control, "inspect", lambda **_k: _Inspector())

    with override_settings(OBSERVABILITY_CHECK_CELERY=True):
        resultado = health.check_celery()

    assert resultado.status == "degraded"
    assert "worker" in resultado.detail


def test_celery_com_worker_responde_conta_sem_vazar_nome(monkeypatch):
    from config.celery import app

    class _ConexaoViva:
        def ensure_connection(self, **_k):
            return True

        def release(self):
            return None

    class _Inspector:
        def ping(self):
            return [{"celery@host-interno-da-vps": {"ok": "pong"}}]

    monkeypatch.setattr(app, "connection_for_write", lambda **_k: _ConexaoViva())
    monkeypatch.setattr(app.control, "inspect", lambda **_k: _Inspector())

    with override_settings(OBSERVABILITY_CHECK_CELERY=True):
        resultado = health.check_celery()

    assert resultado.status == "ok"
    assert resultado.meta == {"workers": 1}


# ---------------------------------------------------------------------------
# Filas
# ---------------------------------------------------------------------------


def test_filas_sem_leitura_possivel_e_degraded_nao_ok():
    """Declarar passivamente falha tanto para fila ainda não criada quanto
    para broker que não responde: afirmar "ok" seria inventar saúde."""

    resultado = health.check_filas()

    assert resultado.status in {"degraded", "ok"}
    if resultado.status == "degraded":
        assert "unavailable" in resultado.detail


def test_filas_com_broker_fora_do_ar_e_error_sem_estourar_tempo(monkeypatch):
    class _ConexaoQuebrada:
        def __enter__(self):
            raise ConnectionError("broker fora do ar")

        def __exit__(self, *_a):
            return False

    from config.celery import app

    monkeypatch.setattr(app, "connection_for_write", lambda **_k: _ConexaoQuebrada())

    resultado = health.check_filas()

    assert resultado.status == "error"
    assert "broker fora do ar" in resultado.detail


def test_filas_acima_do_limite_e_degraded(monkeypatch):
    class _Canal:
        def queue_declare(self, queue=None, passive=False):
            return queue, 5000, 1

    class _Conexao:
        default_channel = _Canal()

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    from config.celery import app

    monkeypatch.setattr(app, "connection_for_write", lambda **_k: _Conexao())
    METRICS = pytest.importorskip("config.metrics").METRICS
    METRICS.clear()

    with override_settings(OBSERVABILITY_QUEUE_DEPTH_WARN=100):
        resultado = health.check_filas()

    assert resultado.status == "degraded"
    assert resultado.meta["filas"]["celery"] == 5000
    assert 'portal_celery_queue_depth{queue="celery"} 5000' in METRICS.render_prometheus()


# ---------------------------------------------------------------------------
# Filesystem do collector
# ---------------------------------------------------------------------------


def test_filesystem_do_collector_reporta_espaco(tmp_path):
    with override_settings(OBSERVABILITY_COLLECTOR_PATH=str(tmp_path)):
        resultado = health.check_filesystem()

    assert resultado.status == "ok"
    assert resultado.meta["path"] == str(tmp_path)
    assert 0 < resultado.meta["free_ratio"] <= 1


def test_filesystem_cheio_e_degraded(tmp_path):
    with override_settings(
        OBSERVABILITY_COLLECTOR_PATH=str(tmp_path),
        OBSERVABILITY_DISK_MIN_FREE_RATIO=1.1,
    ):
        resultado = health.check_filesystem()

    assert resultado.status == "degraded"
    assert "low on space" in resultado.detail


def test_filesystem_inexistente_e_error():
    with override_settings(OBSERVABILITY_COLLECTOR_PATH="/caminho/que/nao/existe-123"):
        resultado = health.check_filesystem()

    assert resultado.status == "error"


# ---------------------------------------------------------------------------
# Estado agregado e memoização
# ---------------------------------------------------------------------------


def test_snapshot_com_opcionais_agrega_degraded_sem_derrubar_readiness(monkeypatch):
    monkeypatch.setattr(
        health, "check_cache", lambda: health.CheckResult("redis", "error", False, 1.0, "down")
    )
    monkeypatch.setattr(
        health,
        "check_celery",
        lambda: health.CheckResult("celery", "ok", False, 1.0, "", {"workers": 1}),
    )
    monkeypatch.setattr(
        health, "check_celery_beat", lambda: health.CheckResult("celery_beat", "not_configured")
    )
    monkeypatch.setattr(
        health, "check_filesystem", lambda: health.CheckResult("collector_disk", "ok", False, 1.0)
    )

    dados = health.snapshot(include_optional=True, include_queues=False)

    assert dados["ready"] is True
    assert dados["status"] == "degraded"
    assert dados["degraded"] is True


def test_degraded_state_memoiza_e_nao_repete_o_probe(monkeypatch):
    chamadas = []

    def _cache():
        chamadas.append(1)
        return health.CheckResult("redis", "error", False, 1.0, "down")

    monkeypatch.setattr(health, "check_cache", _cache)
    monkeypatch.setattr(
        health, "check_celery", lambda: health.CheckResult("celery", "not_configured")
    )
    monkeypatch.setattr(
        health, "check_celery_beat", lambda: health.CheckResult("celery_beat", "not_configured")
    )
    monkeypatch.setattr(
        health, "check_filesystem", lambda: health.CheckResult("collector_disk", "ok", False, 1.0)
    )

    with override_settings(OBSERVABILITY_DEGRADED_PROBE_INTERVAL_SECONDS=60):
        primeiro = health.degraded_state()
        segundo = health.degraded_state()

    assert primeiro["status"] == "degraded"
    assert primeiro["reasons"] == ("redis:error",)
    assert len(chamadas) == 1
    assert segundo["status"] == "degraded"


def test_degraded_state_forcado_reavalia(monkeypatch):
    estados = [
        health.CheckResult("redis", "error", False, 1.0, "down"),
        health.CheckResult("redis", "ok", False, 1.0),
    ]
    monkeypatch.setattr(health, "check_cache", lambda: estados.pop(0))
    monkeypatch.setattr(
        health, "check_celery", lambda: health.CheckResult("celery", "not_configured")
    )
    monkeypatch.setattr(
        health, "check_celery_beat", lambda: health.CheckResult("celery_beat", "not_configured")
    )
    monkeypatch.setattr(
        health, "check_filesystem", lambda: health.CheckResult("collector_disk", "ok", False, 1.0)
    )

    with override_settings(OBSERVABILITY_DEGRADED_PROBE_INTERVAL_SECONDS=60):
        primeiro = health.degraded_state()
        segundo = health.degraded_state(force=True)

    assert primeiro["status"] == "degraded"
    assert segundo["status"] == "ok"


def test_estado_inicial_desconhecido_nao_marca_degradado():
    """Todo deploy nascer degradado seria ruído: o primeiro estado é
    `unknown` e o middleware só marca quando o probe viu problema."""

    health.reset_degraded_cache()

    with override_settings(OBSERVABILITY_DEGRADED_PROBE_INTERVAL_SECONDS=0):
        estado = health.degraded_state()

    assert estado["status"] in {"ok", "degraded"}


def test_public_snapshot_nao_expoe_check_nem_detalhe():
    dados = health.public_snapshot()

    assert set(dados) == {"status", "ready"}
    assert dados["status"] in {"ready", "unavailable"}


def test_cache_usa_chave_estavel_inspecionavel(tmp_path):
    """A chave do probe precisa ser previsível para o operador conferir no
    Redis (`id(cache)` mudaria a cada processo)."""

    with override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
                "LOCATION": str(tmp_path),
            }
        }
    ):
        health.check_cache()

        assert cache.get("observability:health:ping") == "ok"
