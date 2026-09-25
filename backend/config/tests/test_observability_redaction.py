"""Redaction: o que pode e o que não pode sair no log e no evento do Sentry.

Critérios 19, 25, 26 e 28 (implementation-contract.md). O teste central usa um
payload com e-mail, header `Authorization`, token, cookie de sessão, query
string sensível e um JWT sem rótulo — e exige que NENHUMA dessas cadeias
apareça nem no log JSON nem no evento enviado ao Sentry.
"""

from __future__ import annotations

import json
import logging

import pytest
from django.test import override_settings

from config.observability import (
    REDACTED,
    RedactingJsonFormatter,
    is_sensitive_key,
    redact_payload,
    redact_text,
    safe_path,
    sentry_before_send,
    sentry_before_send_transaction,
    set_technical_consent,
)

EMAIL = "leitor.exemplo@dominio.invalid"
SENHA = "senha-super-secreta-123"
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.c2lnbmF0dXJlLWhlcmU"

# Um payload realista de erro de backend com tudo que não pode vazar.
PAYLOAD_SENSIVEL = {
    "email": EMAIL,
    "user_email": EMAIL,
    "Authorization": f"Bearer {JWT}",
    "authorization": f"Token {SENHA}",
    "sessionid": SENHA,
    "api_key": "ak-live-0123456789",
    "senha": SENHA,
    "cpf": "12345678909",
    "query": "termo muito pessoal",
    "user_agent": "Mozilla/5.0 (X11; Linux x86_64)",
    "client_ip": "203.0.113.77",
    "url": f"https://portal.invalid/api/feed/busca/?q={EMAIL}&token={SENHA}",
    "descricao": "campo inocente que contem a sub-string ip e nao pode ser redigido",
    "rotulo": "principal",
    "clip": "resumo",
    "observacao": f"falhou ao enviar para {EMAIL} com Authorization: Bearer {JWT}",
}


def _log(msg: str = "mensagem de teste", **extra) -> str:
    """Formata um LogRecord pelo formatter real e devolve a linha JSON."""

    formatter = RedactingJsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(environment)s %(service)s "
        "%(release)s %(request_id)s %(task_id)s %(message)s"
    )
    record = logging.LogRecord(
        "config.test", logging.ERROR, __file__, 1, msg, (), None
    )
    record.request_id = "req-redaction-1"
    record.task_id = "task-redaction-1"
    for chave, valor in extra.items():
        setattr(record, chave, valor)
    return formatter.format(record)


# ---------------------------------------------------------------------------
# Log
# ---------------------------------------------------------------------------


def test_log_nao_contem_email_authorization_token_ou_query_sensive():
    linha = _log(
        f"falhou para {EMAIL} | Authorization: Bearer {JWT} | api_key=ak-live-0123456789 "
        f"| cpf=12345678909 | https://portal.invalid/api?email={EMAIL}&token={SENHA}"
    )

    for segredo in (EMAIL, SENHA, JWT, "ak-live-0123456789", "12345678909"):
        assert segredo not in linha
    # Nem o rótulo do header sobrevive: `Authorization: Bearer x` cai na regra
    # de atribuição e vira `Authorization=[REDACTED]`.
    assert REDACTED in linha
    assert linha.count(REDACTED) >= 4


def test_log_redige_campos_injetados_via_extra():
    """`logger.info(..., extra={...})` também passa pelo redactor: o
    python-json-logger copia qualquer atributo do record para a saída."""

    linha = _log(user_email=EMAIL, authorization=f"Bearer {JWT}", trace_id="abc-123")

    assert EMAIL not in linha
    assert JWT not in linha
    # campo inocente preservado: redaction excessiva esconde diagnóstico real
    assert "abc-123" in linha


def test_log_preserva_campos_inocentes_com_substring_de_palavra_sensivel():
    """`description`/`principal`/`clip` contêm "ip" como sub-string: por
    sub-string, seriam redigidos sem necessidade (falso positivo que esconde
    diagnóstico)."""

    linha = _log(
        descricao=PAYLOAD_SENSIVEL["descricao"],
        rotulo="principal",
        clip="resumo",
    )
    dados = json.loads(linha)

    assert dados["descricao"].startswith("campo inocente")
    assert dados["rotulo"] == "principal"
    assert dados["clip"] == "resumo"


def test_log_com_args_de_dict_nao_quebra_e_redige():
    """`logger.info("%(k)s", {...})` guarda um dict em `record.args`; iterar
    esse dict devolveria as CHAVES e o `msg % args` quebraria na saída."""

    formatter = RedactingJsonFormatter("%(message)s")
    record = logging.LogRecord(
        "config.test", logging.INFO, __file__, 1, "contexto=%(contexto)s", None, None
    )
    record.args = {"contexto": {"user_email": EMAIL, "token": SENHA, "ok": "1"}}
    record.request_id = "req"
    record.task_id = "-"

    linha = formatter.format(record)
    dados = json.loads(linha)

    assert EMAIL not in linha
    assert SENHA not in linha
    assert "ok" in dados["message"]


def test_log_com_msg_dict_preserva_campos_e_redige_valores():
    formatter = RedactingJsonFormatter("%(message)s")
    record = logging.LogRecord(
        "config.test", logging.INFO, __file__, 1, {"evento": "x", "email": EMAIL}, (), None
    )
    record.request_id = "req"
    record.task_id = "-"

    dados = json.loads(formatter.format(record))

    assert dados["email"] == REDACTED
    assert dados["evento"] == "x"


def test_traceback_no_log_nao_carrega_segredo_da_excecao():
    formatter = RedactingJsonFormatter("%(message)s")
    try:
        raise ValueError(f"falhou para {EMAIL} com token={SENHA}")
    except ValueError:
        record = logging.LogRecord(
            "config.test", logging.ERROR, __file__, 1, "erro", (), __import__("sys").exc_info()
        )
    record.request_id = "req"
    record.task_id = "-"

    linha = formatter.format(record)

    assert EMAIL not in linha
    assert SENHA not in linha
    assert "ValueError" in linha


# ---------------------------------------------------------------------------
# Sentry
# ---------------------------------------------------------------------------


@override_settings(SENTRY_TECHNICAL_CONSENT_DEFAULT=True)
def test_sentry_redige_payload_completo_e_preserva_o_diagnostico():
    evento = sentry_before_send(
        {
            "message": f"falhou para {EMAIL}",
            "user": {"id": "7", "email": EMAIL, "ip_address": "203.0.113.77"},
            "request": {
                "url": f"https://portal.invalid/api/feed/busca/?q={EMAIL}",
                "query_string": f"q={EMAIL}&token={SENHA}",
                "headers": {"Authorization": f"Bearer {JWT}", "Cookie": f"sessionid={SENHA}"},
                "cookies": {"sessionid": SENHA},
                "data": {"email": EMAIL, "senha": SENHA},
            },
            "extra": dict(PAYLOAD_SENSIVEL),
            "tags": {"transaction": "GET /api/feed"},
        }
    )

    assert evento is not None
    bruto = json.dumps(evento, default=str)
    for segredo in (EMAIL, SENHA, JWT, "ak-live-0123456789", "12345678909"):
        assert segredo not in bruto
    # O que o operador precisa continua lá.
    assert evento["message"].startswith("falhou para")
    assert evento["request"]["url"].startswith("https://portal.invalid/api/feed/busca")
    assert "q=" not in evento["request"]["url"]
    assert evento["tags"]["transaction"] == "GET /api/feed"
    assert evento["environment"] and evento["release"]


@override_settings(SENTRY_TECHNICAL_CONSENT_DEFAULT=True)
def test_sentry_nao_altera_o_evento_original():
    evento = {"extra": {"email": EMAIL}}

    sentry_before_send(evento)

    assert evento["extra"]["email"] == EMAIL


@override_settings(SENTRY_TECHNICAL_CONSENT_DEFAULT=False)
def test_sentry_e_fail_closed_sem_consentimento_tecnico():
    assert sentry_before_send({"message": "erro"}) is None
    assert sentry_before_send_transaction({"message": "erro"}) is None


@override_settings(SENTRY_TECHNICAL_CONSENT_DEFAULT=True)
def test_sentry_usa_consentimento_por_request_acima_do_default():
    token = set_technical_consent(True)
    try:
        assert sentry_before_send({"message": "erro"}) is not None
    finally:
        from config.observability import reset_technical_consent

        reset_technical_consent(token)

    assert sentry_before_send({"message": "erro"}) is not None


# ---------------------------------------------------------------------------
# Funções de redaction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "chave, sensivel",
    [
        ("Authorization", True),
        ("x-api-key", True),
        ("user_email", True),
        ("email", True),
        ("senha", True),
        ("chave_api", True),
        ("cpf", True),
        ("client_ip", True),
        ("x-forwarded-for", True),
        ("query", True),
        ("sessionid", True),
        ("description", False),
        ("clip", False),
        ("principal", False),
        ("request_id", False),
        ("status", False),
    ],
)
def test_is_sensitive_key_por_token(chave, sensivel):
    assert is_sensitive_key(chave) is sensivel


def test_redact_text_cobre_bearer_jwt_e_query_string():
    texto = redact_text(
        f"GET /api?email={EMAIL} Authorization: Bearer {JWT} senha={SENHA} "
        f"chave={SENHA} url=https://x.invalid/a?token=abc"
    )

    for segredo in (EMAIL, JWT, SENHA, "token=abc"):
        assert segredo not in texto
    assert "https://x.invalid/a?" in texto


def test_safe_path_remove_query_e_fragmento():
    assert safe_path(f"/api/feed/busca/?q={EMAIL}#top") == "/api/feed/busca/"
    assert safe_path(f"https://portal.invalid/api?x={EMAIL}") == "https://portal.invalid/api"


def test_redact_payload_limita_profundidade_e_tamanho():
    profundo = {"a": {"b": {"c": {"d": {"e": {"f": {"g": "1"}}}}}}}
    lista = list(range(500))

    assert "TRUNCATED_DEPTH" in json.dumps(redact_payload(profundo), default=str)
    saida = redact_payload({"itens": lista})
    assert len(saida["itens"]) == 101  # 100 + marcador de truncamento


def test_redact_payload_preserva_tempo_e_decimal():
    import datetime as dt
    from decimal import Decimal

    saida = redact_payload(
        {"quando": dt.datetime(2026, 9, 25, 10, 20, tzinfo=dt.timezone.utc), "custo": Decimal("1.5")}
    )

    assert saida["quando"].startswith("2026-09-25T10:20")
    assert saida["custo"] == "1.5"
