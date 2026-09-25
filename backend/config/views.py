"""
Healthcheck legado (ARCHITECTURE.md — nova arquitetura de infra, 2026-09-03).

Usado por três consumidores externos que não devem ter acesso a nenhuma
rota autenticada: o `HEALTHCHECK` do Docker Compose (reinicia o container
`web` se parar de responder), o proxy reverso (só encaminha tráfego para um
upstream saudável) e um monitor de uptime externo.

LEGADO (run 20260925-1020-observabilidade, critério 7 e 28). O par canônico de
saúde é `/livez` (o processo responde) + `/readyz` (dependências obrigatórias
disponíveis). `/healthz` continua existindo porque migrar os consumidores é
trabalho do bloco de infra — `docker-compose.yml`, `Dockerfile`, Nginx e PM2
ainda apontam para cá, e trocar o contrato sem migrar quem chama derrubaria o
orquestrador inteiro. Por isso a correção aqui é só de vazamento: a resposta
PÚBLICA virou genérica e o detalhe da falha foi para o log técnico, com
`request_id` para correlação. `portal_healthz_legacy_total` conta as chamadas
para que o operador veja, em dado, quando sobrar quem usa o endpoint legado.

Por que não pode depender de nada além do app: um healthcheck que falha por
token expirado, cache frio ou sessão derramada reinicia/rebaixa o container
errado — o sintoma passa a ser a causa.
"""

import logging

from django.http import JsonResponse

from . import health
from .metrics import METRICS
from .observability import safe_exception

logger = logging.getLogger("config.healthz")


def healthz(request):
    """200/503 útil ao healthcheck, com resposta pública GENÉRICA.

    Mantém a semântica que o Docker/PM2/Nginx esperam (200 = pode receber
    tráfego, 503 = não pode) e remove o que não pode ser público: a mensagem da
    exceção do banco, o traceback e o nome do host. A causa continua visível —
    no log técnico, que tem `request_id`, `environment` e `release`.
    """
    try:
        resultado = health.check_database()
    except Exception as exc:  # noqa: BLE001 — healthcheck não filtra tipos de falha
        # `check_database` já captura tudo internamente; esta guarda existe para
        # o caso de a própria checagem quebrar (ex.: import circular), que
        # viraria 500 e o orquestrador leria como "saúde desconhecida".
        METRICS.inc("portal_healthz_legacy_total", result="unavailable")
        logger.error(
            "healthz legado: falha inesperada na checagem (%s)", safe_exception(exc)
        )
        return JsonResponse({"status": "erro"}, status=503)
    if resultado.status != "ok":
        METRICS.inc("portal_healthz_legacy_total", result="unavailable")
        # `resultado.detail` já vem redigido por `config.health._timed`
        # (`safe_exception`): a mensagem original do driver pode conter host,
        # porta e usuário, e o corpo HTTP é público.
        logger.warning(
            "healthz legado: conectividade indisponível (detalhe=%s detalhe_em=/health-detail)",
            resultado.detail or "-",
        )
        return JsonResponse({"status": "erro"}, status=503)
    METRICS.inc("portal_healthz_legacy_total", result="ok")
    return JsonResponse({"status": "ok"})
