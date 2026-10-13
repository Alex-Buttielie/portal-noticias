"""
Middleware de atualização de `User.last_seen` (implementation-contract.md
run 20261013-1048-home-radar-central-ux, Bloco C, C-07 — "ativos agora").

POR QUE É UM MIDDLEWARE DE DJANGO (E NÃO ALGO EM CADA VIEW):
`request.user` de uma `rest_framework.views.APIView` é resolvido durante
`APIView.dispatch()` → `self.initial(request)` → `self.perform_authentication(request)`,
e o `Request.user` setter do DRF grava o valor TAMBÉM no `HttpRequest`
original (`self._request.user = value` — ver `rest_framework/request.py`).
Isso significa que, quando este middleware roda a parte de código DEPOIS de
`self.get_response(request)` (ou seja, depois da view já ter respondido),
`request.user` já é o usuário autenticado de verdade, para QUALQUER view
DRF — sem precisar duplicar a chamada em cada `APIView`. A posição deste
middleware na lista `MIDDLEWARE` não importa para este mecanismo: todos os
middlewares de função única compartilham a MESMA instância de `request`.
"""

from . import services


class AtualizarUltimoAcessoMiddleware:
    """
    Atualiza `last_seen` do usuário autenticado após cada resposta. O
    throttle de verdade (não gravar a cada requisição) é responsabilidade
    de `identidade.services.atualizar_last_seen` — este middleware só
    decide QUANDO chamar (toda requisição autenticada), nunca COMO/QUANDO
    persistir.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        usuario = getattr(request, "user", None)
        if usuario is not None and getattr(usuario, "is_authenticated", False):
            try:
                services.atualizar_last_seen(usuario)
            except Exception:
                # Telemetria nunca pode quebrar uma resposta que já foi
                # processada com sucesso pela view.
                import logging

                logging.getLogger(__name__).exception(
                    "Falha ao atualizar last_seen (ignorada — não afeta a resposta)."
                )
        return response
