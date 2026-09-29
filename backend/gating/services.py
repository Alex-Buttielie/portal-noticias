"""
Camada central de verificação de acesso Free x Premium
(implementation-contract.md run 20260902-1420-gating-free-premium) — QUALQUER
módulo que precise checar se um usuário tem acesso a um recurso deve usar
`has_feature`/`obter_limite_numerico`/`exigir_feature` daqui, nunca checar
`user.papel == "premium"` diretamente (critério de sucesso da própria spec).
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.exceptions import APIException

from .models import ConfiguracaoSistema, FeatureLimit

logger = logging.getLogger(__name__)

_VALORES_VERDADEIROS = {"true", "1", "sim", "yes"}

# Run 20260923-1216-p1-feed-cache-indices (P1-1): chaves do cache curto de
# configuração (`settings.GATING_CACHE_TTL_SEGUNDOS`). Invalidadas em
# `invalidar_cache_gating()` (chamado pelos `save()`/`delete()` dos modelos
# abaixo — cobre admin, Central e testes que escrevem via ORM).
_CACHE_PREMIUM_ATIVO = "gating:v1:premium_ativo"
_CACHE_MEUS_RECURSOS = "gating:v1:meus-recursos"


def _ttl_gating() -> int:
    try:
        return max(1, int(getattr(settings, "GATING_CACHE_TTL_SEGUNDOS", 45)))
    except (TypeError, ValueError):
        return 45


def invalidar_cache_gating() -> None:
    """Descarta flag premium + respostas de `MeusRecursosView` (por plano)."""
    try:
        cache.delete_many(
            [
                _CACHE_PREMIUM_ATIVO,
                f"{_CACHE_MEUS_RECURSOS}:free",
                f"{_CACHE_MEUS_RECURSOS}:premium",
            ]
        )
    except Exception:
        pass


def premium_ativo() -> bool:
    """
    Flag geral da Central (`/admin/configuracoes` > "Ativar planos Premium").
    Quando DESMARCADA, o produto opera como se todo mundo fosse Premium e as
    assinaturas ficam pausadas (`premium_liberado_geral`).

    Run 20260923-1216-p1-feed-cache-indices (P1-1): cache curto — a flag era
    lida do banco a cada `has_feature`/`plano_do_usuario` (até ~3N queries em
    `MeusRecursosView`). Invalidado em cada escrita (`models.save()`/`delete()`).

    P1-08 — CORREÇÃO DE FALHA PARA O LADO PERMISSIVO (esta é a linha mais
    importante do arquivo). A versão anterior terminava em
    `except Exception: return False`, e `False` significa "Premium liberado
    para TODO MUNDO" (ver `premium_liberado_geral`). Ou seja: banco fora do
    ar, cache fora do ar, migração `0004` ainda não aplicada — qualquer uma
    dessas falhas abria o conteúdo Premium para visitantes anônimos, sem
    nenhum erro em log, porque `return False` é um caminho silencioso.

    Numa trava de pagamento, o lado seguro de uma falha é NEGAR. Por isso os
    DOIS casos agora fecham a porta: a exceção devolve `True` ("a cobrança
    está de pé") e a LINHA AUSENTE também — a versão anterior dizia
    `valor = ... if cfg is not None else False`, de modo que a migração
    `0004` ainda não aplicada (ou uma linha apagada) abria o Premium para
    todos sem nenhuma exceção envolvida. Ambos deixam ERROR alto: o efeito é
    o oposto do vazamento — o visitante cai no plano Free (sem anúncios), que
    é exatamente o fallback exigido, e o operador vê a causa no log em vez de
    ver conteúdo sendo entregue de graça.

    O que NÃO mudou, deliberadamente: a flag DESMARCADA com a linha presente
    (o seed de `gating/migrations/0004_configuracao_sistema.py:7` marca
    `False`) continua liberando tudo. Esse é o modo de lançamento escolhido
    pela Central — "opera como se todo mundo fosse Premium, sem cobrar
    ninguém" — e inverter isso é decisão de produto, não correção de bug.
    O que se corrige aqui é a AUSÊNCIA de decisão, que é diferente de uma
    decisão explícita.
    """
    try:
        valor = cache.get(_CACHE_PREMIUM_ATIVO)
        if valor is None:
            cfg = ConfiguracaoSistema.objects.filter(pk=1).first()
            if cfg is None:
                logger.error(
                    "GATING: ConfiguracaoSistema(pk=1) AUSENTE (migração "
                    "gating.0004_configuracao_sistema não aplicada, ou a linha "
                    "foi apagada). Assumindo Premium LIGADO (fail-closed) — "
                    "ausência de configuração não é autorização. Ninguém "
                    "recebe Premium até a Central marcar a flag."
                )
                valor = True
            else:
                valor = bool(cfg.premium_ativo)
            cache.set(_CACHE_PREMIUM_ATIVO, valor, _ttl_gating())
        return bool(valor)
    except Exception:
        logger.exception(
            "GATING: falha ao ler ConfiguracaoSistema.premium_ativo. Assumindo "
            "Premium LIGADO (fail-closed) para NÃO liberar conteúdo Premium a "
            "quem não pagou; até a leitura se recuperar, todos caem no Free."
        )
        return True


def premium_liberado_geral() -> bool:
    """`True` quando a flag está DESMARCADA: todo mundo navega como Premium."""
    return not premium_ativo()


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


def _assinatura_autoriza_premium(user) -> bool:
    """
    Confere a assinatura AUTORITATIVA antes de confiar em `User.papel`.

    Por que isto existe (achado de segurança P1-08): `User.papel` é um cache
    denormalizado, reescrito em UM lugar só —
    `assinatura.services._sincronizar_papel_usuario`, chamado de
    `_transicionar`. Ele é, portanto, uma fotografia: fica desatualizado
    quando o tempo passa (o `vencimento` chegou) e quando a mudança vem de
    fora (o provedor cancelou). Ler só a fotografia é o que fazia uma
    assinatura vencida continuar Premium (HTTP 200 no Radar) e o que faria um
    `papel=premium` qualquer durar para sempre.

    `_transicionar` continua sendo o único ESCITOR de `papel` (esta função
    só lê), então a hierarquia de verdade é: assinatura decide, `papel` é
    índice.

    Fail-closed: exceção de banco/tabela ausente -> `False` (nega Premium).
    A única exceção é `ImportError` (app `assinatura` não instalado), onde
    não existe noção de assinatura no projeto e o `papel` passa a ser a
    única fonte possível — negar ali transformaria um app removido em
    "ninguém tem Premium", que é o outro erro catastrófico do par — e,
    como o primeiro, igualmente silencioso.

    Custo: UMA query, e só para quem afirma `papel=premium`. Free/anônimo,
    que é o caminho quente do tráfego, não paga nada.
    """
    try:
        from assinatura.models import Subscription
    except ImportError:
        return True

    try:
        assinatura = (
            Subscription.objects.filter(user_id=user.pk).order_by("-criado_em").first()
        )
    except Exception:
        logger.exception(
            "GATING: falha ao conferir a assinatura do usuário %s — NEGANDO "
            "Premium (fail-closed).", getattr(user, "pk", "?")
        )
        return False

    if assinatura is None:
        # `papel=premium` sem nenhuma assinatura é o estado incoerente por
        # definição: nada foi pago. Nega.
        return False
    return bool(assinatura.deveria_ter_acesso_premium)


def plano_do_usuario(user) -> str:
    """
    Resolve o "plano" de gating — CRITÉRIO DE ACEITE DO P1-08: "Premium só
    abre após TODOS os gates de pagamento; caso contrário, fechado".

    Gates aplicados, em ordem (o primeiro que nega, vence):
      1. `ConfiguracaoSistema.premium_ativo` (flag da Central) — desligada,
         o produto é de graça para todos por decisão de produto.
      2. `papel == "admin"` — administrador não é limitado (critério de
         aceite 5 da spec original).
      3. `papel == "premium"` E a assinatura autoritativa diz que há direito
         (`_assinatura_autoriza_premium`).

    Qualquer visitor anônimo, ou autenticado sem `papel` reconhecido, ou com
    `papel=premium` sem assinatura válida, cai em Free. O padrão é NEGAR:
    nenhuma ausência libera acesso.
    """
    if premium_liberado_geral():
        return FeatureLimit.PLANO_PREMIUM
    if getattr(user, "is_authenticated", False):
        papel = getattr(user, "papel", None)
        if papel == "admin":
            return FeatureLimit.PLANO_PREMIUM
        if papel == "premium" and _assinatura_autoriza_premium(user):
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

    Exceção deliberada: com a flag de Premium DESLIGADA na Central, tudo
    fica liberado para todos (`premium_liberado_geral`).
    """
    if premium_liberado_geral():
        return True
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
