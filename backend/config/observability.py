"""Primitivas de observabilidade do backend.

Este módulo é deliberadamente pequeno e sem dependências de UI.  Ele fornece:

* contexto de correlação (request/task) propagado por middleware e sinais
  Celery;
* redaction defensiva para logs e eventos Sentry;
* metadados de ambiente/release usados por todos os serviços;
* uma Before-Send do Sentry que nunca envia cookies, Authorization, query
  strings ou payloads de usuário.

As funções não inicializam integrações externas.  Assim podem ser importadas
pelo formatter de logging, por commands de management e por testes sem DSN,
Redis ou Sentry configurados.

Duas fontes de verdade convivem aqui de propósito, e a ordem importa:

1. os valores por variável de ambiente (`ENVIRONMENT`/`RELEASE`/`SERVICE_NAME`),
   calculados no import, que funcionam mesmo sem o Django carregado;
2. os settings do Django (`OBSERVABILITY_ENVIRONMENT`, ...), que são a
   configuração de fato do projeto e sabe cair em ``"production"`` quando
   ``DEBUG`` é False (o bloco abaixo só lê do ambiente, então sem esta
   precedência o header ``X-Environment`` mentiria em produção).
"""

from __future__ import annotations

import copy
import datetime as dt
import logging
import os
import re
from contextvars import ContextVar
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit, urlunsplit

try:  # python-json-logger é runtime, mas não é necessário para importar o módulo.
    from pythonjsonlogger.jsonlogger import JsonFormatter
except ImportError:  # pragma: no cover - fallback para ambientes mínimos
    JsonFormatter = None  # type: ignore[assignment,misc]

SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "portal-api").strip() or "portal-api"
ENVIRONMENT = (
    os.environ.get("SENTRY_ENVIRONMENT")
    or os.environ.get("DJANGO_ENVIRONMENT")
    or os.environ.get("APP_ENV")
    or "development"
).strip() or "development"
RELEASE = (
    os.environ.get("SENTRY_RELEASE")
    or os.environ.get("GIT_SHA")
    or os.environ.get("RELEASE_SHA")
    or "local"
).strip() or "local"

REDACTED = "[REDACTED]"
MAX_LOG_TEXT = 4_000
MAX_REDACT_DEPTH = 6
MAX_REDACT_ITEMS = 100

_task_id_ctx: ContextVar[str] = ContextVar("observability_task_id", default="-")
_technical_consent_ctx: ContextVar[bool] = ContextVar(
    "observability_technical_consent", default=False
)

# Nomes que nunca devem aparecer em telemetria. A comparação é feita por
# TOKEN (início/fim de palavra ou separador `_`/`-`), não por sub-string: a
# versão por sub-string redigia campos inocente como `description`
# ("descrip-tion" contém "ip") e `clip`, o que esconde diagnóstico real sem
# adicionar proteção. Compostos de IP (`client_ip`, `x_forwarded_for`, ...)
# entram explicitamente porque não têm separador.
_SENSITIVE_KEY = re.compile(
    r"(?:^|[^a-z0-9])(?:"
    r"authorization|proxy-authorization|cookie|set-cookie|password|passwd|secret|"
    r"token|api[-_]?key|access[-_]?key|private[-_]?key|credential|session|"
    r"sessionid|csrf|xsrf|email|e-mail|telefone|phone|documento|document|"
    r"endereco|address|user[-_]?agent|cookieconsent|query|senha|chave|segredo|"
    r"cpf|cnpj"
    r")(?:[^a-z0-9]|$)"
    r"|(?:^|[^a-z0-9])(?:ip|clientip|remoteip|ipaddress|ips|xforwardedfor)(?:[^a-z0-9]|$)"
    r"|(?:client|remote|source|user|origin)[-_]?ip(?:[^a-z0-9]|$)"
    r"|(?:x[-_]?forwarded[-_]?for)(?:[^a-z0-9]|$)",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
# Esquema de autenticação com credencial: `Bearer <jwt>`, `Basic <base64>`,
# `Token <chave>`. Só `Bearer` estava coberto (achado MINOR-1): o regex
# genérico de atribuição abaixo parava no PRIMEIRO espaço, então em
# `Authorization: Basic ZGV2OnNlcmV0YQ==` ele consumia "Basic" como valor e a
# credencial base64 ficava de fora — visível no log e no evento do Sentry.
_AUTH_SCHEME = re.compile(r"\b(Bearer|Basic|Token)\s+[A-Za-z0-9._~+/=-]{2,}", re.IGNORECASE)
# JWT sem rótulo (`eyJ...`), comum em log de exceção/header cru.
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{4,}")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(authorization|proxy-authorization|cookie|set-cookie|token|auth|"
    r"api[_-]?key|access[_-]?key|secret|client[_-]?secret|passwd|password|pass|"
    r"pwd|senha|chave|segredo|cpf|cnpj|session|sessionid|session[_-]?id|"
    r"access[_-]?token|refresh[_-]?token|"
    r"id[_-]?token|private[_-]?key)\s*[:=]\s*[^\s,;&]+"
)
# Os QUATRO headers cujo valor precisa ser consumido até o fim da linha. São
# exceções deliberadas a `[^\s,;&]+`: o valor de um header não termina no
# primeiro espaço nem no primeiro `;`, e é justamente aí que a segunda
# credencial sobrevivia (`Cookie: sessao=abc123 csrf=def456` -> o segundo par
# ficava de fora, porque `csrf` também não é um nome sensível). O custo é
# perder o resto da linha quando um texto menciona "cookie:" como palavra —
# falso positivo aceitável para telemetria, vazamento não.
_HEADER_VALUE = re.compile(
    r"(?i)\b(authorization|proxy-authorization|cookie|set-cookie)\s*[:=]\s*[^\r\n]+"
)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# CR/LF/TAB viram escapes visíveis. Onde isso é aplicado (`redact_single_line`,
# formatter de texto) não existe estrutura de dados que isole a linha: um `\n`
# num `request.path` viraria uma LINHA DE LOG FORJADA, com `levelname`,
# `request_id` e release do atacante. O modo JSON não precisa disso (o
# `json.dumps` neutraliza) e o traceback preserva as quebras de linha de
# propósito — são elas que tornam o log legível.
_LINE_BREAK = re.compile(r"[\r\n\t]")
# Identidade vai para HEADER (`X-Release`, `X-Environment`, tag do Sentry), então
# aqui não pode sobrar NENHUM caractere de controle nem espaço: CR/LF num
# header é injeção de resposta (o `settings.py` deriva release de `GIT_SHA`/
# ambiente, e um valor mal configurado não pode virar um segundo header).
_CONTROL_HEADER = re.compile(r"[\s\x00-\x1f\x7f]")

_TRUE_VALUES = {"1", "true", "yes", "on"}


def _settings_value(nome: str, padrao: str) -> str:
    """Lê um setting do Django quando ele já está configurado.

    Antes do `django.setup()` (ou durante o próprio import de
    `config.settings`) `settings` não está pronto: nesse caso devolvemos o
    fallback calculado do ambiente, sem nunca forçar o setup prematuramente
    (fazer isso produziria um objeto `Settings` com o módulo pela metade).
    """

    try:
        from django.conf import settings as django_settings

        if not django_settings.configured:
            return padrao
        valor = getattr(django_settings, nome, None)
    except Exception:  # noqa: BLE001 - observabilidade nunca derruba o processo
        return padrao
    if valor in (None, ""):
        return padrao
    return str(valor)


def current_task_id() -> str:
    """ID da task Celery corrente ou ``-`` fora de uma task."""

    return _task_id_ctx.get()


def set_task_id(task_id: object | None):
    """Define o contexto de task e devolve o token para ``reset``."""

    value = str(task_id or "-").strip() or "-"
    return _task_id_ctx.set(value[:128])


def reset_task_id(token) -> None:
    _task_id_ctx.reset(token)


def set_technical_consent(value: bool):
    """ContextVar de consentimento técnico para filtros Sentry/logs."""

    return _technical_consent_ctx.set(bool(value))


def reset_technical_consent(token) -> None:
    _technical_consent_ctx.reset(token)


def technical_consent() -> bool:
    return _technical_consent_ctx.get()


def release() -> str:
    """Release efetiva, sem aceitar-control/injection do ambiente."""

    value = _CONTROL_HEADER.sub("", _settings_value("OBSERVABILITY_RELEASE", RELEASE))
    return value[:200] or "local"


def environment() -> str:
    """Ambiente efetivo (development/homolog/production) para logs e headers."""

    value = _CONTROL_HEADER.sub("", _settings_value("OBSERVABILITY_ENVIRONMENT", ENVIRONMENT))
    return value[:80] or "development"


def service() -> str:
    value = _CONTROL_HEADER.sub("", _settings_value("OBSERVABILITY_SERVICE_NAME", SERVICE_NAME))
    return value[:80] or "portal-api"


def is_sensitive_key(key: object) -> bool:
    return bool(_SENSITIVE_KEY.search(str(key)))


def redact_text(value: object, *, limit: int = MAX_LOG_TEXT) -> str:
    """Reduz texto a uma forma segura para log/Sentry.

    A função é conservadora: mesmo um valor que não seja um segredo pode ser
    mascarado.  False positives são aceitáveis para telemetria; vazar um token
    ou query string não é.
    """

    text = "" if value is None else str(value)
    text = _CONTROL.sub("", text)
    text = _AUTH_SCHEME.sub(lambda m: f"{m.group(1)} {REDACTED}", text)
    text = _JWT.sub(REDACTED, text)
    text = _EMAIL.sub("[REDACTED_EMAIL]", text)
    # Header com credencial: o valor vai até o fim da linha (ver `_HEADER_VALUE`).
    text = _HEADER_VALUE.sub(lambda m: f"{m.group(1)}={REDACTED}", text)
    text = _SECRET_ASSIGNMENT.sub(lambda m: f"{m.group(1)}={REDACTED}", text)
    # Não preservar query strings em URLs que apareçam em mensagens de log.
    text = re.sub(
        r"(https?://[^\s?]+)\?[^\s#]+",
        lambda m: f"{m.group(1)}?{REDACTED}",
        text,
    )
    if len(text) > max(0, limit):
        return text[: max(0, limit - 1)] + "…"
    return text


def redact_single_line(value: object, *, limit: int = MAX_LOG_TEXT) -> str:
    """`redact_text` + CR/LF/TAB virados em escape visível.

    Onde não existe estrutura de dados segurando o valor (uma linha de log em
    modo texto, um rótulo de métrica, o `request.path` de um 500), uma quebra de
    linha é uma LINHA FORJADA: o atacante escolhe o `levelname` e o
    `request_id` que o operador vai ler. `redact_text` sozinha não resolve
    porque preserva `\n`/`\r` de propósito — traceback sem quebra de linha é
    ilegível.
    """

    texto = _LINE_BREAK.sub(lambda m: {chr(10): "\\n", chr(13): "\\r", chr(9): "\\t"}[m.group(0)], redact_text(value, limit=limit))
    return texto


def safe_path(value: object, *, limit: int = 500) -> str:
    """Path sem query/fragment, preservando apenas o que é útil no diagnóstico."""

    raw = "" if value is None else str(value)
    try:
        parts = urlsplit(raw)
        # Só trata como URL absoluta o que realmente é http(s): um path como
        # "api:feed/x" seria interpretado como esquema "api" e remontado
        # errado, corrompendo o rótulo de rota das métricas.
        if parts.netloc or parts.scheme in {"http", "https"}:
            return redact_text(
                urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")),
                limit=limit,
            )
        # urlsplit trata um path comum como path; query/fragment são removidos.
        if parts.scheme:
            return redact_text(raw.split("?", 1)[0].split("#", 1)[0], limit=limit)
        return redact_text(parts.path or raw, limit=limit)
    except Exception:
        return redact_text(raw.split("?", 1)[0].split("#", 1)[0], limit=limit)


def redact_payload(value: Any, *, _depth: int = 0, _key: object | None = None) -> Any:
    """Reduz estruturas recursivamente, com limites de CPU/tamanho.

    Listas e dicionários são limitados para que um payload de erro malicioso não
    vire um log gigante.  unknown objects viram apenas seu tipo/nome seguro.
    """

    if _key is not None and is_sensitive_key(_key):
        return REDACTED
    if _depth >= MAX_REDACT_DEPTH:
        return "[TRUNCATED_DEPTH]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, bytes):
        return f"[BYTES:{len(value)}]"
    # Tipos que o JsonEncoder do python-json-logger saberia formatar: mantemos
    # a informação (ISO/número) em vez de degradar tudo para "[datetime]",
    # senão todo campo de tempo do log vira inútil.
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, dt.timedelta):
        return value.total_seconds()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_REDACT_ITEMS:
                output["_truncated"] = True
                break
            key_text = redact_text(key, limit=120)
            output[key_text] = redact_payload(item, _depth=_depth + 1, _key=key)
        return output
    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)[:MAX_REDACT_ITEMS]
        result = [redact_payload(item, _depth=_depth + 1) for item in items]
        if len(value) > MAX_REDACT_ITEMS:
            result.append("[TRUNCATED_ITEMS]")
        return result
    if isinstance(value, BaseException):
        return safe_exception(value)
    return f"[{type(value).__name__}]"


def safe_exception(exc: BaseException | None) -> str:
    """Mensagem de exceção sem traceback, credenciais ou payload."""

    if exc is None:
        return ""
    return redact_text(f"{type(exc).__name__}: {exc}")


def _technical_consent_default() -> bool:
    """Consentimento técnico padrão, configurável por setting ou ambiente.

    Fail-closed: sem consentimento explícito (header `X-Technical-Consent` ou
    o default do operador) o Sentry não recebe nada.  O default é lido do
    setting `SENTRY_TECHNICAL_CONSENT_DEFAULT` para que a decisão fique no
    mesmo lugar que o resto da configuração (e seja testável com
    `override_settings`); o ambiente é apenas o fallback para uso fora do
    Django.
    """

    try:
        from django.conf import settings as django_settings

        if django_settings.configured and hasattr(
            django_settings, "SENTRY_TECHNICAL_CONSENT_DEFAULT"
        ):
            return bool(getattr(django_settings, "SENTRY_TECHNICAL_CONSENT_DEFAULT"))
    except Exception:  # noqa: BLE001
        pass
    return str(os.environ.get("SENTRY_TECHNICAL_CONSENT_DEFAULT", "false")).strip().lower() in _TRUE_VALUES


def _contestao_envio(motivo: str) -> None:
    """Contabiliza o evento retido, para o descarte não virar falso verde.

    Sem isto, um `SENTRY_TECHNICAL_CONSENT_DEFAULT` mal configurado seria
    indistinguível de "não houve erro": o alerta de zero erros continuaria
    verde enquanto o Sentry descartaria tudo.
    """

    try:
        from .metrics import METRICS

        METRICS.inc("portal_sentry_events_dropped_total", reason=str(motivo)[:32])
    except Exception:  # noqa: BLE001
        pass


def reportar_falha_de_init_sentry(exc: BaseException) -> None:
    """Sinaliza que o APM NÃO subiu, sem derrubar o processo.

    O `sentry_sdk.init` roda dentro de um `try/except Exception` em
    `config/settings.py` (falha de observabilidade não pode impedir o portal de
    subir) e o `pass` original sumia em silêncio: DSN com typo, integração
    ausente ou argumento inválido deixavam o operador com a sensação de APM
    ativo e nenhum evento. O único sinal posterior
    (`portal_sentry_events_dropped_total`) nem subia, porque não houve init.

    O aviso leva só o TIPO da exceção: DSN e traceback podem carregar segredo e
    host, e o log é justamente a superfície que precisa ser limpa.
    """

    tipo = type(exc).__name__[:32] or "Exception"
    logging.getLogger("config.settings").warning(
        "Sentry nao inicializado (falha=%s): sem APM, sem evento.", tipo
    )
    try:
        from .metrics import METRICS

        METRICS.inc("portal_sentry_init_failed_total", error=tipo)
    except Exception:  # noqa: BLE001 - o sinal é acessório; a falha não sobe
        pass


def sentry_before_send(event: dict, hint: dict | None = None) -> dict | None:
    """Filtro Sentry fail-closed para PII e segredos.

    ``before_send`` também é o ponto de controle para o consentimento técnico
    quando o SDK está em contexto de browser/servidor.  O servidor pode
    configurar ``SENTRY_TECHNICAL_CONSENT_DEFAULT=true`` para eventos
    operacionais; o padrão é não enviar eventos quando não há contexto de
    consentimento.  O pipeline de produto continua separado.
    """

    if not _technical_consent_default() and not technical_consent():
        _contestao_envio("no_technical_consent")
        return None
    if not isinstance(event, dict):
        return None
    safe = redact_payload(copy.deepcopy(event))
    if not isinstance(safe, dict):
        return None
    safe["environment"] = environment()
    safe["release"] = release()
    tags = safe.setdefault("tags", {})
    if isinstance(tags, dict):
        tags.setdefault("service", service())
        tags.setdefault("environment", environment())
        tags.setdefault("release", release())
        task_id = current_task_id()
        if task_id != "-":
            tags.setdefault("task_id", task_id)
    # Sentry integrations podem colocar estes campos no event mesmo com
    # send_default_pii=False. Removê-los é uma segunda barreira explícita.
    safe.pop("user", None)
    request_data = safe.get("request")
    if isinstance(request_data, dict):
        request_data.pop("cookies", None)
        request_data.pop("headers", None)
        request_data.pop("query_string", None)
        request_data.pop("data", None)
        if "url" in request_data:
            request_data["url"] = safe_path(request_data["url"], limit=1_000)
    extra = safe.get("extra")
    if isinstance(extra, dict):
        safe["extra"] = redact_payload(extra)
    return safe


def sentry_before_send_transaction(event: dict, hint: dict | None = None) -> dict | None:
    """Aplica o mesmo controle de consentimento a transações."""

    return sentry_before_send(event, hint)


def configure_sentry_tags(**values: object) -> None:
    """Define tags sem transformar a inicialização do Sentry em dependência."""

    try:
        import sentry_sdk
    except ImportError:
        return
    for key, value in values.items():
        if value not in (None, "", "-"):
            try:
                sentry_sdk.set_tag(str(key), str(value)[:200])
            except Exception:
                return


def _request_id_do_contexto() -> str:
    """Request ID do ContextVar do middleware, sem ciclo de import no topo."""

    try:
        from .middleware import get_current_request_id

        return get_current_request_id()
    except Exception:  # noqa: BLE001
        return "-"


class RedactingJsonFormatter(JsonFormatter if JsonFormatter is not None else object):  # type: ignore[misc]
    """JSON logger que aplica os mesmos limites do redactor do Sentry."""

    def format(self, record):  # noqa: D102
        # Não mutamos o LogRecord original: outros handlers podem precisar do
        # traceback original dentro do mesmo processo.
        local = copy.copy(record)
        msg = getattr(local, "msg", "")
        # `logger.info({...})` é a forma de log estruturado que o
        # python-json-logger entende (dict vira campo, não texto): passar por
        # `redact_text` transformaria o payload em string e perderia a
        # estrutura. Aqui ele é redigido como estrutura.
        local.msg = redact_payload(msg) if isinstance(msg, dict) else redact_text(msg)
        args = getattr(local, "args", None)
        if args:
            # `logging` guarda um dict de args como dict (não tupla) quando o
            # log usa `logger.info("%(k)s", {"k": v})`; iterar esse dict
            # devolveria as CHAVES e quebraria o `msg % args` na saída.
            local.args = (
                redact_payload(args) if isinstance(args, dict)
                else tuple(redact_payload(arg) for arg in args)
            )
        local.request_id = getattr(local, "request_id", None) or _request_id_do_contexto() or "-"
        local.service = getattr(local, "service", None) or service()
        local.environment = getattr(local, "environment", None) or environment()
        local.release = getattr(local, "release", None) or release()
        local.task_id = getattr(local, "task_id", None) or current_task_id()
        return super().format(local)

    def add_fields(self, log_record, record, message_dict):  # noqa: D102
        # `super().add_fields` monta o JSON final (format string + `extra=`).
        # Redigir aqui é a única barreira para campo injetado por
        # `logger.info(..., extra={"email": ...})`: o python-json-logger copia
        # qualquer atributo do record para a saída sem filtro.
        super().add_fields(log_record, record, message_dict)
        seguro = redact_payload(log_record)
        if isinstance(seguro, dict):
            log_record.clear()
            log_record.update(seguro)

    def formatException(self, ei):  # noqa: N802,D102
        return redact_text(super().formatException(ei))


class RedactingTextFormatter(logging.Formatter):
    """Formatter de texto (`DJANGO_LOG_JSON=false`) com a mesma redação do JSON.

    Antes o modo `verbose` era um `logging.Formatter` puro: a redação — declarada
    no módulo como "última barreira" — não existia nesse caminho, e um `\n` num
    `request.path` virava uma segunda linha de log com `levelname`/`request_id`
    controlados por quem fez a requisição (achado MINOR-2).

    Só a MENSAGEM é redigida e achatada em uma linha. O traceback continua
    multilinha: quebrá-lo destruiria a legibilidade que é a razão de existir do
    modo texto, e ele não contém entrada do cliente nas suas primeiras linhas
    (a `redact_text` do `formatException` continua valendo).
    """

    def formatMessage(self, record) -> str:  # noqa: N802,D102
        return redact_single_line(super().formatMessage(record))

    def formatException(self, ei):  # noqa: N802,D102
        # O traceback é anexado DEPOIS de `formatMessage` pelo `logging`, então
        # redigir só a mensagem deixaria a exceção crua na linha de log — e a
        # mensagem de exceção é onde vive a query string com token.
        return redact_text(super().formatException(ei))


__all__ = [
    "ENVIRONMENT",
    "RELEASE",
    "SERVICE_NAME",
    "RedactingJsonFormatter",
    "RedactingTextFormatter",
    "configure_sentry_tags",
    "current_task_id",
    "environment",
    "is_sensitive_key",
    "redact_payload",
    "redact_single_line",
    "redact_text",
    "release",
    "reportar_falha_de_init_sentry",
    "reset_task_id",
    "reset_technical_consent",
    "safe_exception",
    "safe_path",
    "sentry_before_send",
    "sentry_before_send_transaction",
    "service",
    "set_task_id",
    "set_technical_consent",
    "technical_consent",
]
