"""Endpoints de observabilidade: liveness, readiness, detalhe e métricas.

Separação deliberada (implementation-contract.md, critérios 7-9 e 17):

``/livez``
    O PROCESSO responde. Não toca banco, cache, Celery nem filesystem. Um
    banco fora do ar não pode fazer o orquestrador reiniciar um Python que
    está vivo — isso causaria o pior incidente possível: reinício em cascata
    de todos os workers exatamente quando o Postgres é o problema.

``/readyz``
    Dependências OBRIGATÓRIAS (PostgreSQL + migrations aplicadas). Público e
    genérico: devolve ``{"status", "ready"}`` e nada mais. Sem `str(exc)`, sem
    traceback, sem nome de check que falhou, sem host — a causa vive no
    endpoint privado.

``/health-detail``
    Diagnóstico completo (Redis, worker/beat Celery, filas, disco do
    collector), com a CAUSA redigida. Privado.

``/metrics``
    Exposição Prometheus das métricas técnicas. Loopback ou bearer token.

Autorização (por quê não é "só staff"): o coletor (Alloy/Prometheus), o
Better Stack e o `curl` do operador chegam por token ou pela rede interna, e
ninguém deles tem sessão Django. E por que não é "qualquer IP privado": atrás
de Docker/Nginx o `REMOTE_ADDR` do tráfego público é um IP privado da rede de
containers — tratar "privado" como "de confiança" publicaria o diagnóstico
para a internet. A confiança é sempre loopback explícito, ou uma lista
operacional de redes de proxy (`OBSERVABILITY_TRUSTED_PROXY_NETWORKS`), ou
token, ou staff.

`X-Forwarded-For` NÃO é usado para decidir autorização: é controlado pelo
cliente final e o Nginx não o sobrescreve por padrão, então confiá-lo seria
uma autenticação por `curl -H`.
"""

from __future__ import annotations

import logging
import secrets

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache

from . import health
from .metrics import METRICS
from .observability import environment, release, service
from .proxies import endereco_remoto, redes_confiaveis

logger = logging.getLogger("config.observability")

PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def _setting(nome: str, padrao: str = "") -> str:
    return str(getattr(settings, nome, padrao) or "").strip()


def eh_loopback(request) -> bool:
    """True para loopback real ou para um proxy explicitamente declarado.

    `X-Forwarded-For` é ignorado de propósito (ver docstring do módulo). A
    lista de redes vem de `config/proxies.py` — a mesma implementação que decide
    a identidade do cliente no rate limit, para que "quem é confiável" não
    tenha duas versões capable de divergir.
    """

    endereco = endereco_remoto(request)
    if endereco is None:
        return False
    if endereco.is_loopback:
        return True
    return any(endereco in rede for rede in redes_confiaveis())


def _token_autoriza(request, nome_setting: str) -> bool:
    """Compara o bearer token em BYTES, nunca em `str`.

    `secrets.compare_digest` só aceita `str` ASCII: com um header não-ASCII
    (`Authorization: Bearer çéé`) ele levanta `TypeError` e o 404 silencioso do
    endpoint privado virava **500** — ruído de 5xx e evento de Sentry gerados
    por qualquer cliente anônimo com um único header (achado MINOR-3). Em bytes a
    comparação continua constante e não existe `TypeError` possível.
    """

    esperado = _setting(nome_setting)
    if not esperado:
        return False
    header = request.headers.get("Authorization", "")
    prefixo, _, valor = header.partition(" ")
    if prefixo.lower() != "bearer" or not valor:
        return False
    return secrets.compare_digest(valor.strip().encode("utf-8"), esperado.encode("utf-8"))


def _eh_staff(request) -> bool:
    try:
        usuario = getattr(request, "user", None)
        if usuario is None or not getattr(usuario, "is_authenticated", False):
            return False
        return bool(getattr(usuario, "is_staff", False) or getattr(usuario, "is_superuser", False))
    except Exception:  # noqa: BLE001 - resolver o usuário exige o banco/sessão
        # Fail-closed: sem banco para validar a sessão, o acesso privado é
        # negado (o loopback e o token continuam funcionando).
        return False


def _negado(request, motivo: str) -> HttpResponse:
    """Resposta de acesso negado SEM revelar que o endpoint existe.

    404 (e não 403) para tudo que não é autorizado: um 403 confirma a
    existência do diagnóstico — e o conteúdo desse diagnóstico é justamente o
    que não pode vazar. Um monitor externo consegue distinguir "rota não
    existe" de "sem permissão" apenas pelo corpo/header, que é idêntico aqui.
    """

    METRICS.inc("portal_observability_access_denied_total", target=motivo[:32])
    resposta = JsonResponse({"detail": "Not found."}, status=404)
    resposta["Cache-Control"] = "no-store"
    return resposta


def _no_store(resposta: HttpResponse) -> HttpResponse:
    resposta["Cache-Control"] = "no-store, max-age=0"
    return resposta


@never_cache
def livez(request):
    """Liveness do processo. Payload mínimo e sem dependência alguma."""

    METRICS.inc("portal_livez_total")
    resposta = JsonResponse({"status": "alive"})
    return _no_store(resposta)


@never_cache
def readyz(request):
    """Readiness: banco + migrations. Público, genérico e sem `str(exc)`."""

    METRICS.inc("portal_readyz_total")
    dados = health.public_snapshot()
    status = 200 if dados["ready"] else 503
    if not dados["ready"]:
        # O motivo fica no log técnico (com request_id), nunca no corpo: o
        # corpo é público e o nome do host/tabela é informação de operação.
        logger.warning(
            "readiness indisponível: dependência obrigatória fora do ar "
            "(detalhe em /health-detail)"
        )
    METRICS.gauge("portal_ready", 1 if dados["ready"] else 0)
    return _no_store(JsonResponse(dados, status=status))


@never_cache
def health_detail(request):
    """Diagnóstico completo. Loopback, staff/admin ou bearer token."""

    autorizado = (
        eh_loopback(request)
        or _token_autoriza(request, "OBSERVABILITY_HEALTH_TOKEN")
        or _eh_staff(request)
    )
    if not autorizado:
        return _negado(request, "health-detail")

    dados = health.snapshot(include_optional=True, include_queues=True)
    dados["collector"] = {
        "service": service(),
        "environment": environment(),
        "release": release(),
    }
    METRICS.gauge("portal_ready", 1 if dados["ready"] else 0)
    if dados.get("degraded"):
        METRICS.inc("portal_health_degraded_total")
    resposta = JsonResponse(dados, status=200 if dados["ready"] else 503)
    return _no_store(resposta)


@never_cache
def metrics_view(request):
    """Exposição Prometheus. Loopback (ou proxy declarado) ou bearer token."""

    autorizado = (
        eh_loopback(request)
        or _token_autoriza(request, "OBSERVABILITY_METRICS_TOKEN")
    )
    if not autorizado:
        return _negado(request, "metrics")

    METRICS.inc("portal_metrics_scrapes_total")
    # O scrape é um dos momentos em que o operador precisa da telemetria de job,
    # e este processo pode não ter atendido requisição nenhuma desde o último
    # scrape (site com tráfego baixo, probes que só batem em `/readyz`).
    # Publicar aqui garante que as séries existam mesmo sem probe anterior.
    try:
        from .job_state import publicar_metricas

        publicar_metricas()
    except Exception:  # noqa: BLE001 - canal de job nunca derruba o scrape
        pass
    corpo = METRICS.render_prometheus()
    resposta = HttpResponse(corpo, content_type=PROMETHEUS_CONTENT_TYPE)
    return _no_store(resposta)


__all__ = [
    "PROMETHEUS_CONTENT_TYPE",
    "eh_loopback",
    "health_detail",
    "livez",
    "metrics_view",
    "readyz",
]
