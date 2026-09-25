"""Primitivas de contexto: task_id, consentimento técnico, identidade e tags.

Critérios 18, 19 e 27 (implementation-contract.md). A correlação de log de task
(sinal do Celery em `config/celery.py`) só vale se `current_task_id()` reflecting
o contexto da task — é isso que é testado aqui.
"""

from __future__ import annotations

import logging
import sys
import types

import pytest
from django.test import override_settings

from config.observability import (
    configure_sentry_tags,
    current_task_id,
    environment,
    release,
    reportar_falha_de_init_sentry,
    reset_task_id,
    reset_technical_consent,
    service,
    set_task_id,
    set_technical_consent,
    technical_consent,
)


# ---------------------------------------------------------------------------
# Identidade (settings > ambiente)
# ---------------------------------------------------------------------------


@override_settings(
    OBSERVABILITY_SERVICE_NAME="portal-api",
    OBSERVABILITY_ENVIRONMENT="production",
    OBSERVABILITY_RELEASE="sha-9999",
)
def test_identidade_vem_do_settings_quando_configurada():
    assert service() == "portal-api"
    assert environment() == "production"
    assert release() == "sha-9999"


def test_identidade_tem_fallback_sem_settings_configurados(monkeypatch):
    """`config.observability` precisa responder mesmo antes de o Django estar
    pronto (formatter de log, commands, testes), sem nunca forçar um setup
    prematuro do settings (que leria o módulo pela metade)."""

    import config.observability as observability
    from django.conf import empty

    monkeypatch.setattr(observability, "SERVICE_NAME", "svc-env")
    monkeypatch.setattr(observability, "ENVIRONMENT", "homolog")
    monkeypatch.setattr(observability, "RELEASE", "sha-env")
    monkeypatch.setattr("django.conf.settings._wrapped", empty)

    assert service() == "svc-env"
    assert environment() == "homolog"
    assert release() == "sha-env"
    # Sem Django pronto, quem passa a constante do módulo é quem chama
    # (`release()` etc.); a função crua devolve o default recebido.
    assert observability._settings_value("OBSERVABILITY_RELEASE", "padrao") == "padrao"


@override_settings(OBSERVABILITY_RELEASE="sha-com-controle\n-injection")
def test_release_remove_caractere_de_controle():
    assert "\n" not in release()
    assert release().startswith("sha-com-controle")


# ---------------------------------------------------------------------------
# Task ID
# ---------------------------------------------------------------------------


def test_task_id_tem_ciclo_com_reset():
    assert current_task_id() == "-"

    token = set_task_id("task-123")
    try:
        assert current_task_id() == "task-123"
    finally:
        reset_task_id(token)

    assert current_task_id() == "-"


def test_task_id_trunca_e_normaliza_valor_vazio():
    token = set_task_id("t" * 500)
    try:
        assert len(current_task_id()) == 128
    finally:
        reset_task_id(token)

    token = set_task_id(None)
    try:
        assert current_task_id() == "-"
    finally:
        reset_task_id(token)


# ---------------------------------------------------------------------------
# Consentimento técnico
# ---------------------------------------------------------------------------


def test_consentimento_tecnico_por_default_e_falso():
    assert technical_consent() is False

    token = set_technical_consent(True)
    try:
        assert technical_consent() is True
    finally:
        reset_technical_consent(token)

    assert technical_consent() is False


# ---------------------------------------------------------------------------
# Tags do Sentry
# ---------------------------------------------------------------------------


def test_configure_sentry_tags_nao_quebra_sem_sdk(monkeypatch):
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)

    configure_sentry_tags(request_id="req-1")  # não deve levantar


def test_configure_sentry_tags_ignora_valor_vazio_e_trunca(monkeypatch):
    chamadas = []
    fake = types.SimpleNamespace(set_tag=lambda k, v: chamadas.append((k, v)))
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake)

    configure_sentry_tags(
        request_id="req-2", release="r" * 500, environment="production", ignorado="-", vazio=None
    )

    dicionario = dict(chamadas)
    assert dicionario["request_id"] == "req-2"
    assert dicionario["environment"] == "production"
    assert len(dicionario["release"]) == 200
    assert "-" not in dicionario
    assert None not in dicionario.values()


def test_configure_sentry_tags_absorve_falha_do_sdk(monkeypatch):
    def _explode(*_a, **_k):
        raise RuntimeError("sdk fora do ar")

    monkeypatch.setitem(sys.modules, "sentry_sdk", types.SimpleNamespace(set_tag=_explode))

    configure_sentry_tags(request_id="req-3")  # não deve levantar


def test_task_id_do_celery_entra_no_evento_do_sentry():
    from config.observability import sentry_before_send

    token = set_task_id("task-sentry-9")
    try:
        with override_settings(SENTRY_TECHNICAL_CONSENT_DEFAULT=True):
            evento = sentry_before_send({"message": "erro"})
    finally:
        reset_task_id(token)

    assert evento["tags"]["task_id"] == "task-sentry-9"
    assert evento["tags"]["service"]
    assert evento["tags"]["release"]
    assert evento["environment"] == environment()
    assert evento["release"] == release()


# ---------------------------------------------------------------------------
# Falha de init do Sentry (achado MINOR-9)
# ---------------------------------------------------------------------------


def test_falha_de_init_do_sentry_avisa_e_conta_sem_vazar_dsn(caplog):
    """O `except` do `settings.py` não pode falhar em silêncio: sem sinal, o
    operador acredita ter APM e não tem. O aviso leva só o TIPO da exceção — o
    DSN pode estar na mensagem."""

    from config.metrics import METRICS

    METRICS.clear()
    caplog.set_level(logging.WARNING, logger="config.settings")

    reportar_falha_de_init_sentry(
        ValueError("https://chave:segredo@sentry.invalid/123 — formato invalido")
    )

    aviso = next(r for r in caplog.records if "Sentry nao inicializado" in r.getMessage())
    assert "ValueError" in aviso.getMessage()
    assert "segredo" not in aviso.getMessage()
    assert 'portal_sentry_init_failed_total{error="ValueError"} 1' in METRICS.render_prometheus()
