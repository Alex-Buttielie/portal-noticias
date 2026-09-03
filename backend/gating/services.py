"""
Camada central de verificação de acesso Free x Premium
(implementation-contract.md run 20260902-1420-gating-free-premium) — QUALQUER
módulo que precise checar se um usuário tem acesso a um recurso deve usar
`has_feature`/`obter_limite_numerico`/`exigir_feature` daqui, nunca checar
`user.papel == "premium"` diretamente (critério de sucesso da própria spec).
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import APIException

from .models import FeatureLimit

_VALORES_VERDADEIROS = {"true", "1", "sim", "yes"}


class RecursoGatedException(APIException):
    """
    Levantada por `exigir_feature` quando o usuário não tem acesso ao
    recurso — HTTP 403 com mensagem clara (implementation-contract.md,
    critério de aceite 7; spec, requisito funcional 3: "o sistema deve
    comunicar isso de forma clara, não falhar silenciosamente").
    """

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Este recurso não está disponível no seu plano atual."
    default_code = "recurso_gated"


def plano_do_usuario(user) -> str:
    """
    Resolve o "plano" de gating a partir de `User.papel` (`identidade/`) —
    fonte de verdade até `assinatura-premium` existir e manter esse campo
    atualizado conforme o ciclo de vida da assinatura (ver task-plan.md,
    "Suposições assumidas"). `papel=admin` é tratado como Premium
    (critério de aceite 5) — administradores não devem ser limitados pelas
    mesmas regras de um usuário final. Usuário anônimo (ou qualquer usuário
    sem `papel` reconhecido) é tratado como Free — nunca libera acesso por
    omissão (fail-safe).
    """
    if getattr(user, "is_authenticated", False):
        papel = getattr(user, "papel", None)
        if papel in ("premium", "admin"):
            return FeatureLimit.PLANO_PREMIUM
    return FeatureLimit.PLANO_FREE


def obter_valor(chave: str, plano: str) -> str | None:
    """
    Valor bruto (string) configurado para `(chave, plano)`, ou `None` se não
    houver registro — função pública de baixo nível, usada internamente por
    `has_feature`/`obter_limite_numerico` e também pela view
    `MeusRecursosView` (não precisa reimplementar a consulta).
    """
    try:
        registro = FeatureLimit.objects.get(chave=chave, plano=plano)
    except FeatureLimit.DoesNotExist:
        return None
    return registro.valor


def has_feature(user, chave: str) -> bool:
    """
    Critérios de aceite 1-4: interpretação booleana de uma feature. Ausência
    de registro para `(chave, plano)` retorna `False` — nunca lança exceção,
    nunca libera acesso por omissão de configuração (fail-safe, critério 3).
    """
    plano = plano_do_usuario(user)
    valor = obter_valor(chave, plano)
    if valor is None:
        return False
    return valor.strip().lower() in _VALORES_VERDADEIROS


def obter_limite_numerico(user, chave: str, default: int = 0) -> int:
    """
    Critério de aceite 9: interpretação numérica de uma feature (ex.: limite
    de alertas personalizados). Convenção: `-1` = ilimitado. Ausência de
    registro OU valor não-numérico cai no `default` (nunca lança exceção por
    dado malformado no admin).
    """
    plano = plano_do_usuario(user)
    valor = obter_valor(chave, plano)
    if valor is None:
        return default
    try:
        return int(valor.strip())
    except (TypeError, ValueError):
        return default


def exigir_feature(user, chave: str, mensagem: str | None = None) -> None:
    """
    Critério de aceite 7 — uso típico em outro módulo:
    `gating.services.exigir_feature(request.user, "personalizacao_avancada")`
    no início de uma view/serializer que implementa um recurso premium.
    """
    if not has_feature(user, chave):
        raise RecursoGatedException(
            mensagem or f"Recurso '{chave}' não disponível no seu plano atual. Faça upgrade para Premium."
        )
