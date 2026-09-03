"""
Healthcheck (ARCHITECTURE.md — nova arquitetura de infra, 2026-09-03).

Usado por três consumidores externos que não devem ter acesso a nenhuma
rota autenticada: o `HEALTHCHECK` do Docker Compose (reinicia o container
`web` se parar de responder), o proxy reverso Caddy (só encaminha tráfego
para um upstream saudável) e um monitor de uptime externo (ex.: UptimeRobot).
Por isso é uma view function simples, sem DRF/autenticação/permissão — não
deve depender de nada que possa estar fora do ar por um motivo que não seja
"a aplicação está quebrada" (ex.: token de auth expirado).
"""

from django.db import connection
from django.http import JsonResponse


def healthz(request):
    """Verifica conectividade real com o banco (não só "o processo subiu"),
    já que a garantia de persistência é o requisito não-funcional mais
    crítico desta arquitetura — um container que responde 200 mas não
    consegue falar com o Postgres é tão inútil quanto um que caiu."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as exc:  # noqa: BLE001 — healthcheck deve reportar qualquer falha, não filtrar tipos
        return JsonResponse({"status": "erro", "detalhe": str(exc)}, status=503)
    return JsonResponse({"status": "ok"})
