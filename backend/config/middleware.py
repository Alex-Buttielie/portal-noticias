"""Middleware X-Request-ID — observabilidade P0 item 10.

Gera/propaga X-Request-ID (uuid4 se não vier na requisição) e ecoa no
response header. Também expõe em request.META para logs.
"""

from __future__ import annotations

import uuid


class RequestIdMiddleware:
    """Propaga X-Request-ID: reaproveita se cliente/nginx já enviou, senão gera."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get("HTTP_X_REQUEST_ID") or str(uuid.uuid4())
        # Normaliza: garante que request.META tenha o valor final
        request.META["HTTP_X_REQUEST_ID"] = request_id
        # Opcional: expõe como atributo direto
        request.request_id = request_id  # type: ignore[attr-defined]
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response
