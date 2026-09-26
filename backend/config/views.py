"""
Endpoints de saúde e prontidão (P0-10, eixo 4).

TRÊS CONTRATOS DIFERENTES, DE PROPÓSITO
=========================================
Misturar "o processo está vivo" com "o serviço pode receber tráfego" é a
causa raiz de dois desvios de operação opostos e igualmente ruins:
reiniciar o container quando o banco está lento (o orquestrador deveria
tirá-lo de rotação, não matá-lo), e continuar mandando tráfego para um
serviço cujas dependências caíram (porque o healthcheck estava atrás de um
proxy que respondia 200).

  GET /livez          Liveness. Só o PROCESSO. Sem tocar em dependência:
                      se o Postgres está lento, o container deve CONTINUAR
                      vivo para poder ser inspecionado e drenado.
  GET /readyz         Readiness. Dependências essenciais com checagem REAL
                      e TIMEOUT. 503 com detalhe quando não está pronto.
  GET /healthz        Genérico, público e ESTÁVEL, para Docker
                      HEALTHCHECK, proxy e monitor externo de uptime.
                      NUNCA inclui mensagem de driver, host, porta ou nome
                      de usuário — era o vazamento de `origin/develop`.

Dois endpoints RESTRITOS, nunca públicos:

  GET /health-detail  Detalhe por dependência. Staff OU token.
  GET /metrics        Exposição Prometheus. Staff OU token.

Autenticação dos restritos
==========================
- `Authorization: Bearer <token>` ou `X-Observability-Token: <token>`,
  comparado com `hmac.compare_digest`.
- OU sessão autenticada com `is_staff`.
- Se `HEALTH_DETAIL_TOKEN` não estiver configurado, o caminho por token é
  DESABILITADO (fail-closed). Um deploy que esqueceu o segredo não pode
  acabar com detalhe de saúde e métricas abertos para a internet.
- Anônimo NUNCA recebe 200 nestes dois, mesmo sem token configurado: o
  status é 401.
"""

from __future__ import annotations

import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from .health import (
    METRICAS,
    autorizado_para_detalhe,
    verificar_prontidao,
)

logger = logging.getLogger(__name__)

#: Payload de `/healthz`. Contrato FIXO: chave e valor não mudam com o
#: estado real, para que o monitor externo nunca interprete um campo como
#: ausente ou vazio. O estado real vive em `/readyz` (e em `/health-detail`,
#: para quem tem acesso).
PAYLOAD_HEALTHZ = {"status": "ok"}


def _registrar(metrica: str, situacao: str) -> None:
    METRICAS.incrementar(metrica, 1, situacao=situacao)


@never_cache
@csrf_exempt
def healthz(request):
    """
    Resposta genérica e pública.

    NÃO consulta o banco. Antes consultava, e devolvia `str(exc)` numa
    falha — o que expunha host, porta, nome do banco e usuário do Postgres
    para qualquer visitante de `/healthz`. Um endpoint que monitor externo
    e Docker chamam em intervalos curtos é uma superfície de vazamento
    garantida.

    O contrato com o Docker `HEALTHCHECK` e com o proxy é "200 = o
    processo responde", que é exatamente o que `/livez` formaliza. Quem
    precisa do estado de dependências usa `/readyz`.
    """
    _registrar("portal_healthz_total", "ok")
    return JsonResponse(PAYLOAD_HEALTHZ)


@never_cache
@csrf_exempt
def livez(request):
    """
    Liveness: o PROCESSO responde. Não toca em banco, cache ou broker.

    Depende disto que responder seja instantâneo e nunca falhe por causa de
    third-party. Se `/livez` fizesse checagem de dependência, uma indisponibilidade
    do Postgres provocaria um restart storm — o oposto do desejado.
    """
    _registrar("portal_livez_total", "ok")
    return JsonResponse({"status": "vivo"})


@never_cache
@csrf_exempt
def readyz(request):
    """
    Readiness: pode receber tráfego agora?

    Status HTTP: 200 quando `ok`, 503 quando não. O corpo lista as
    checagens com categoria e motivo redigido.

    `ok` é DERIVADO das checagens — não há caminho que devolva 200 sem que
    o banco tenha sido verificado com sucesso NESTA chamada. Um `ok` falso
    é pior que um 503, porque mantém tráfego chegando a um serviço que não
    funciona.
    """
    relatorio = verificar_prontidao()
    METRICAS.incrementar("portal_readyz_total", 1, situacao="ok" if relatorio.ok else "nao_pronto")
    METRICAS.observar("portal_readyz_duracao_ms", sum(c.duracao_ms for c in relatorio.checagens.values()))
    corpo = {
        "status": "pronto" if relatorio.ok else "nao_pronto",
        "checagens": relatorio.por_checagem(),
    }
    if relatorio.nao_verificadas:
        corpo["nao_verificadas"] = sorted(relatorio.nao_verificadas)
    return JsonResponse(corpo, status=200 if relatorio.ok else 503)


@never_cache
@csrf_exempt
def health_detail(request):
    """
    Detalhe por dependência. RESTRITO a staff autenticado ou token válido.

    Anônimo e token errado recebem 401 — nunca 403 com corpo de detalhe, e
    nunca 200. O corpo inclui `detalhe` (nome da exceção), que é
    justamente o que não pode vazar pelo endpoint público.
    """
    if not autorizado_para_detalhe(request):
        METRICAS.incrementar("portal_acesso_negado_total", 1, recurso="health_detail")
        return JsonResponse({"detail": "Não autorizado."}, status=401)

    relatorio = verificar_prontidao()
    METRICAS.incrementar("portal_health_detail_total", 1, situacao="ok" if relatorio.ok else "degradado")
    corpo = {
        "status": "ok" if relatorio.ok else "degradado",
        "checagens": relatorio.por_checagem_detalhada(),
    }
    if relatorio.nao_verificadas:
        corpo["nao_verificadas"] = sorted(relatorio.nao_verificadas)
    return JsonResponse(corpo)


@never_cache
@csrf_exempt
def metrics(request):
    """
    Exposição no formato do Prometheus. RESTRITO — nunca público.

    Recusa explícita de `text/html` e `nosniff`: sem isso, um navegador
    poderia interpretar a resposta e executar algo vindo de um rótulo de
    métrica controlado por terceiro.
    """
    if not autorizado_para_detalhe(request):
        METRICAS.incrementar("portal_acesso_negado_total", 1, recurso="metrics")
        return JsonResponse({"detail": "Não autorizado."}, status=401)

    METRICAS.incrementar("portal_metrics_total", 1)
    corpo = METRICAS.render()
    resposta = HttpResponse(corpo, content_type="text/plain; version=0.0.4; charset=utf-8")
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta
