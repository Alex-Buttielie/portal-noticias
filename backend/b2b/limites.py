"""
Cota de critérios de monitoramento por plano comercial (backlog P1-13 —
"papéis, isolamento e alertas testados"; workstream WS-12).

Por que existe
--------------
Cada critério ativo de uma organização é uma varredura de `NewsItem` por
execução de `verificar_e_enviar_alertas` (job de 60 min, `CELERY_BEAT_SCHEDULE`).
`criar_criterio` era ilimitado: uma conta comprometida — ou só um cliente
desaplicado — criava critérios sem teto e transformava o job periódico em
laço de varredura, com um e-mail por critério por execução. A cota é o que
torna o custo do job previsível por tenant.

Sem migration
-------------
A cota é derivada do campo que JÁ existe, `Organizacao.plano`
(`basic`/`pro`/`enterprise`), lida de `config.settings`
(`B2B_COTA_CRITERIOS_*`). Nenhum campo novo, nenhuma migration: mudar a cota
comercial é mudar env, não migrar tabela. O que exigiria migration (cota por
organização configurável no admin, contador de consumo persistido, histórico
de consumo para faturamento) está reportado como dependência, não improvisado
aqui.

A contagem é escopada na organização
------------------------------------
`criar_criterio` não pode confiar em "chamei isto no contexto da org X": a
conta é `CriterioMonitoramento.objects.filter(organizacao=organizacao)`
(checado em `b2b/tests/test_limites.py`), porque uma contagem errada aqui
vaza duas coisas ao mesmo tempo — o consumo de outra empresa (contagem) e o
conteúdo dos critérios dela (quais valores estão sendo monitorados).
"""

from __future__ import annotations

from django.conf import settings

from .models import CriterioMonitoramento, Organizacao


class CotaDeCriteriosExcedidaError(Exception):
    """
    A organização já está na cota de critérios do seu plano. A mensagem é
    sobre a cota do REQUISITANTE (plano, teto atingido, o que fazer) — nunca
    sobre o conteúdo dos critérios, que é dado da própria organização.
    """


def _teto_do_plano(plano: str) -> int:
    tetos = {
        Organizacao.PLANO_BASIC: settings.B2B_COTA_CRITERIOS_BASIC,
        Organizacao.PLANO_PRO: settings.B2B_COTA_CRITERIOS_PRO,
        Organizacao.PLANO_ENTERPRISE: settings.B2B_COTA_CRITERIOS_ENTERPRISE,
    }
    # Plano desconhecido cai no teto mais PERMISSIVO do catálogo em vez do mais
    # restritivo: um plano novo (ou um valor nulo herdado de linha antiga)
    # nunca pode trancar o cliente que já pagou.
    return int(tetos.get(plano, max(int(v) for v in tetos.values())))


def cota_de_criterios(organizacao: Organizacao) -> int:
    """Teto de critérios ATIVOS do plano da organização."""
    return _teto_do_plano(organizacao.plano)


def criterios_ativos_da_organizacao(organizacao: Organizacao) -> int:
    """
    Quantos critérios ativos a organização tem. Sempre escopado em
    `organizacao` — nunca `CriterioMonitoramento.objects.filter(ativo=True)`
    (essa forma agregaria as empresas vizinhas e é justamente o vetor de
    inferência que a contagem não pode ter).
    """
    return CriterioMonitoramento.objects.filter(organizacao=organizacao, ativo=True).count()


def within_quota(organizacao: Organizacao) -> bool:
    """`True` se a organização ainda pode criar mais um critério ativo."""
    return criterios_ativos_da_organizacao(organizacao) < cota_de_criterios(organizacao)


def exigir_dentro_da_cota(organizacao: Organizacao) -> None:
    """
    Guarda de cota de `criar_criterio`. A mensagem é acionável de propósito:
    diz o plano, o teto, quanto já é usado e a saída (remover um critério ou
    mover de plano), para que o 403 chegue ao cliente como instrução e não
    como número morto.
    """
    if within_quota(organizacao):
        return
    teto = cota_de_criterios(organizacao)
    usados = criterios_ativos_da_organizacao(organizacao)
    raise CotaDeCriteriosExcedidaError(
        f"Cota de critérios do plano '{organizacao.plano}' atingida "
        f"({usados}/{teto} ativos). Exclua um critério que não usa mais ou "
        f"contrate um plano com cota maior para continuar monitorando."
    )


def remanescente(organizacao: Organizacao) -> int:
    """Quantos critérios ativos ainda podem ser criados (nunca negativo)."""
    return max(0, cota_de_criterios(organizacao) - criterios_ativos_da_organizacao(organizacao))
