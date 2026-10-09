"""
Expurgo de analytics de produto — retenção (P2-02, WS-13/WS-14).

Este módulo fecha a promessa de "12 meses, expurgo diário" da tabela de
`infra/observability/README.md`: até ele existir, aquela linha era promessa
sem código.

O QUE É EXPURGADO, E POR QUE ESTES TRÊS MODELOS
-----------------------------------------------
Todos os eventos de analytics de produto que o portal grava, e que são
comportamentais por definição (LGPD: dado de navegação, com `user`/`sessao`
associados). São eles:

- `metricas.EventoSite` — o restante da taxonomia (page_view, category_view,
  location_selected, community_view...);
- `feed.InteracaoNoticia` — view/click/read/save/share/search_click;
- `feed.EventoBusca` — as buscas (inclui `query`, que é dado pessoal).

Os dois últimos são mantidos pelo app `feed` porque são a ÚNICA fonte de
engajamento e de termos populares (ver `metricas/models.py`), mas continuam
sendo analytics de produto: são atingidos pelo endpoint
`POST /api/metricas/eventos/`. Nenhum outro modelo do portal tem FK para
estes três (verificado: todos apontam para `catalogo_noticias`, nunca o
contrário), então apagar não cascateia para conteúdo.

O QUE NÃO É EXPURGADO, E POR QUE
---------------------------------
Todo agregado deste projeto é calculado na LEITURA (`Count`/`Sum` sobre os
eventos brutos), e toda janela de leitura é de dias: `feed/recomendacao.py`
agrega 7d e 24h; `metricas/services_inteligencia.py` aceita no máximo `90d`;
`termos_em_alta` usa 7d. Uma retenção de 365 dias está muito acima de
qualquer janela, então nenhum produto quebre por perder dado. O que PODE
sobreviver ao expurgo é o SNAPSHOT em cache
(`feed:autocomplete:v2:populares`, derivado de `EventoBusca`) — por isso a
invalidação abaixo.

AS TRÊS PROPRIEDADES QUE ESTE ITEM EXIGE
----------------------------------------
1. **Idempotente.** O filtro é sempre "anterior ao corte", e o corte depende
   só do relógio e da retenção. Rodar duas vezes seguidas, reentregar, ter
   dois workers: a segunda passada não seleciona nada e não muda nenhuma
   contagem. Não há estado de "o que já foi removido" que possa divergir.

2. **Em lotes, e interrompível no meio.** `DELETE` de tabela inteira numa
   base de produção segura segura lock de tabela e degrada o banco INTEIRO —
   o app inteiro fica lento, não só o expurgo. A task apaga N linhas por
   requisição, cada uma em autocommit: uma interrupção no meio deixa um
   banco consistente e a próxima execução (ou a próxima hora) continua de
   onde parou, sem estado intermediário corrompido porque não existe estado
   intermediário. `MAX_LOTES` evita laço infinito.

3. **Auditável sem dado pessoal.** A prova do que saiu fica em DOIS lugares,
   ambos só com contagem, faixa de tempo e duração:
   - o log técnico (contagem por modelo, corte, retenção, duração);
   - o registro durável de `config/filas_estado.py`, que é o que
     `manage.py saude_filas` lê e o que a malha de observabilidade indexa.

   NUNCA o conteúdo do evento: não `user`, não `sessao`/`session_key`, não
   `query`, não `path`, não IP, não `user_agent`. Um job que existe para
   REDUZIR dado pessoal não o imprime no stdout, que é ingerido por um
   agregador de logs de longa retenção.
"""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from config import filas_estado

logger = logging.getLogger(__name__)

#: Nome público da task. É o contrato entre o `CELERY_BEAT_SCHEDULE`
#: (`metricas-expurgar-analytics`) e o worker; `config/tests/test_filas.py`
#: já prova que toda entrada da agenda resolve para uma task registrada.
NOME_EXPURGO = "metricas.tasks.expurgar_analytics"

#: Teto de lotes por modelo por execução. Com `ANALYTICS_EXPURGO_LOTE=500` dá
#: 5 milhões de linhas por execução, muito acima do que um dia de analytics
#: produz neste portal. Existe para o caso patológico de um `delete` que não
#: remove as linhas selecionadas: melhor parar (e ficar visível no log) do que
#: um job de limpeza que roda para sempre.
MAX_LOTES = 10_000

#: Intervalo padrão do expurgo em segundos (24 h), espelhado de
#: `settings.ANALYTICS_EXPURGO_INTERVALO_SEGUNDOS` para conferência (e para o
#: teste que compara os dois). O agendamento real fica no beat schedule.
INTERVALO_EXPURGO_PADRAO = 86400

#: Retenção padrão em dias (12 meses), espelhada de
#: `settings.ANALYTICS_RETENCAO_DIAS`.
RETENCAO_PADRAO = 365


class RetencaoInvalida(ValueError):
    """
    A retenção configurada não é uma retenção.

    Existe como tipo próprio (e não como `ImproperlyConfigured`) porque quem
    a levanta é a task, em tempo de execução, e a task tem uma obrigação
    diferente do boot: registrar o ciclo como FALHA para que
    `manage.py saude_filas` veja, em vez de o job sumir em silêncio.
    """


def modelos_de_evento() -> list[tuple[str, Any]]:
    """
    Eventos brutos de analytics, na ordem de maior para menor volume.

    Import local de propósito: `feed` importa `catalogo_noticias`, e um
    import no topo do módulo criaria dependência circular durante o
    autodiscover do Celery, que importa este arquivo antes do fim do
    `django.setup()`.
    """
    from feed.models import EventoBusca, InteracaoNoticia

    from .models import EventoSite

    return [
        ("metricas.EventoSite", EventoSite),
        ("feed.InteracaoNoticia", InteracaoNoticia),
        ("feed.EventoBusca", EventoBusca),
    ]


def retencao_dias(valor: Any = None) -> int:
    """
    Resolve a retenção em DIAS, e RECUSA o que não faz sentido.

    `valor` (a task aceita um override para operação manual em ambiente
    controlado) passa pela MESMA validação de
    `settings._erro_retencao_analytics`, para que não exista um caminho pelo
    qual um 0 entre e apague o banco inteiro.

    Por que recusa em vez de corrigir para um default:

    - **0 ou negativo** significaria `corte = agora`, e "anteriores a agora"
      é TUDO. Um `max(0, ...)` — que é o que a versão de setembro fazia —
      transforma um erro de configuração na maiordemeção possível do módulo.
      Recusar é o comportamento oposto: o pior desfecho de uma task de
      limpeza é apagar tudo por configuração errada, então a configuração
      errada tem de não apagar nada.
    - **não-número** não pode virar `0` por acidente de `int()` nem 365 em
      silêncio.

    Um valor ausente (None) NÃO é erro: significa "use o default
    configurado", que é o caminho normal do agendamento.
    """
    if valor is None:
        resolvido = getattr(settings, "ANALYTICS_RETENCAO_DIAS", RETENCAO_PADRAO)
        try:
            dias = int(resolvido)
        except (TypeError, ValueError) as exc:
            raise RetencaoInvalida(
                f"ANALYTICS_RETENCAO_DIAS={resolvido!r} não é um número inteiro; "
                "o expurgo foi recusado em vez de assumir um default, porque "
                "assumir pode significar apagar todo o histórico de analytics."
            ) from exc
    else:
        try:
            dias = int(valor)
        except (TypeError, ValueError) as exc:
            raise RetencaoInvalida(
                f"retencao={valor!r} não é um número inteiro de dias; expurgo recusado."
            ) from exc

    if dias < 1:
        raise RetencaoInvalida(
            f"retencao={dias} dia(s): um valor menor que 1 colocaria o corte em "
            "'agora' e apagaria TODO o histórico de analytics. O expurgo foi "
            "recusado. Use um valor positivo em dias."
        )
    maximo = int(getattr(settings, "ANALYTICS_RETENCAO_DIAS_MAXIMA", 36500))
    if dias > maximo:
        raise RetencaoInvalida(
            f"retencao={dias} dias excede o máximo de {maximo}; recusado por trava "
            "de plausibilidade (quase sempre é erro de digitação)."
        )
    return dias


def tamanho_lote(valor: Any = None) -> int:
    """
    Linhas por requisição, sempre >= 1 e <= 50 000.

    Aqui o clamp é seguro e é o comportamento certo, diferente da retenção:
    um `lote=0` não apaga nada por engano — ele só deixaria o job sem
    progresso, o que é inofensivo e visível. Já um `lote` enorme reintroduz
    o lock de tabela que o item existe para evitar, então também é limitado.
    """
    bruto = getattr(settings, "ANALYTICS_EXPURGO_LOTE", 500) if valor is None else valor
    try:
        tamanho = int(bruto)
    except (TypeError, ValueError):
        logger.warning(
            "ANALYTICS_EXPURGO_LOTE=%r invalido; usando o padrao de 500 linhas por lote",
            bruto,
        )
        tamanho = 500
    return max(1, min(50_000, tamanho))


def _invalida_agregados_cache() -> None:
    """
    Dropa os snapshots derivados dos eventos expurgados.

    Idempotente por natureza: apagar uma chave de cache que não existe é o
    mesmo que apagar uma que existe. Sem isto, a UI continuaria servindo
    "termos populares" computados sobre eventos que já não existem mais.
    """
    from feed.busca import invalidar_cache_autocomplete

    invalidar_cache_autocomplete()


def _expurgar_modelo(model: Any, corte, tamanho: int) -> tuple[int, int]:
    """
    Apaga, em lotes, as linhas de UM modelo anteriores ao corte.

    Devolve `(removidos, lotes)`. Cada lote é um `values_list` + um `delete`
    por `pk__in`, em autocommit — nenhuma transação aberta por vários lotes,
    que é o que segura lock de tabela e tranca o banco.

    A seleção usa o índice de `criado_em` (`db_index=True` nos três modelos) e
    `LIMIT`, então o custo por lote não cresce com o tamanho da tabela: sem
    isso, apagar um mês de um ano seria mais lento que apagar o ano inteiro,
    que é o comportamento oposto do desejado.
    """
    removidos_total = 0
    lotes = 0
    while lotes < MAX_LOTES:
        pks = list(
            model.objects.filter(criado_em__lt=corte)
            .order_by("criado_em", "pk")
            .values_list("pk", flat=True)[:tamanho]
        )
        if not pks:
            break
        apagados, _detalhe = model.objects.filter(pk__in=pks).delete()
        lotes += 1
        if not apagados:
            # As linhas continuam selecionáveis mas não saem. Sem este corte,
            # o while repetiria para sempre selecionando as mesmas linhas:
            # um job de limpeza que não termina é pior do que um job que roda
            # amanhã. Registrado como erro porque é anomalia, não normalidade.
            logger.error(
                "expurgo de analytics: %s selecionou %s linha(s) e apagou 0 — "
                "lote interrompido para nao entrar em laco",
                model.__name__,
                len(pks),
            )
            break
        removidos_total += int(apagados)
    return removidos_total, lotes


@shared_task(
    name=NOME_EXPURGO,
    acks_late=True,
    reject_on_worker_lost=True,
    bind=True,
    ignore_result=True,
)
def expurar_analytics(self, dias: int | None = None, lote: int | None = None) -> dict:
    """
    Expurga eventos de analytics anteriores à janela de retenção.

    `dias` e `lote` existem para operação manual em ambiente controlado
    (reduzir a janela para testar o caminho de remoção). O agendamento do beat
    não passa nenhum dos dois: usa os valores configurados.

    Idempotente por construção, não por marca de execução: o corte é derivado
    do relógio, e a seleção é sempre "anterior ao corte". Uma segunda
    execução no mesmo estado não seleciona nenhuma linha.

    Devolve o resumo (contagens, corte, duração) — que é também o que vai
    para o log e para o registro durável. Não devolve nenhum dado de evento.
    """
    started = time.perf_counter()

    # A retenção é validada ANTES de qualquer escrita: uma retenção inválida
    # não pode apagar "tudo o que dá" no caminho do erro.
    try:
        retencao = retencao_dias(dias)
    except RetencaoInvalida as exc:
        _registra_ciclo(
            estado=filas_estado.ESTADO_FALHA,
            erro=exc,
            detalhe={"expurgado": False, "motivo": "retencao_invalida"},
            tentativa=_tentativa(self),
        )
        logger.error(
            "expurgo de analytics RECUSADO: %s — nada foi removido", exc
        )
        raise

    tamanho = tamanho_lote(lote)
    corte = timezone.now() - timedelta(days=retencao)

    removidos: dict[str, int] = {}
    lotes: dict[str, int] = {}
    for nome, model in modelos_de_evento():
        removidos[nome], lotes[nome] = _expurgar_modelo(model, corte, tamanho)

    _invalida_agregados_cache()

    total_removido = sum(removidos.values())
    duracao = time.perf_counter() - started

    detalhe = {
        # Contagem e faixa de tempo. Nada de conteúdo de evento: é este dict
        # que fica gravado em disco e é lido por `manage.py saude_filas`.
        "corte": corte.isoformat(),
        "retencao_dias": retencao,
        "lote": tamanho,
        "removidos": removidos,
        "lotes": lotes,
        "total_removido": total_removido,
        "duracao_s": round(duracao, 3),
        "expurgado": True,
    }
    _registra_ciclo(
        estado=filas_estado.ESTADO_SUCESSO,
        detalhe=detalhe,
        tentativa=_tentativa(self),
    )

    # Log técnico: contagens e janela, nunca conteúdo de evento.
    logger.info(
        "expurgo de analytics concluido: corte=%s retencao_dias=%s lote=%s "
        "removidos=%s lotes=%s total_removido=%s duracao_s=%.3f",
        corte.isoformat(),
        retencao,
        tamanho,
        removidos,
        lotes,
        total_removido,
        duracao,
    )
    return detalhe


# ---------------------------------------------------------------------------
# Registro durável — a auditoria e a observabilidade moram AQUI
# ---------------------------------------------------------------------------


def _tentativa(task) -> int:
    """Número da tentativa (1 na primeira), como em `catalogo_noticias`."""
    return int(getattr(getattr(task, "request", None), "retries", 0) or 0) + 1


def _registra_ciclo(*, estado: str, tentativa: int, erro=None, detalhe: dict | None = None) -> None:
    """
    Grava o resultado do ciclo em `config/filas_estado.py`.

    É este registro — e não uma métrica em processo — que faz o expurgo ser
    OBSERVÁVEL em `develop`. A razão é concreta: o registro em memória
    (`config.health.METRICAS`) é exposto por `/metrics`, que é servido pelo
    Gunicorn; esta task roda no WORKER do Celery, um processo diferente. Um
    contador incrementado aqui ficaria em memória de um processo que ninguém
    raspa — sinal invisível, que é pior que sinal ausente. O arquivo de estado
    é durável, compartilhado, e é a fonte que `manage.py saude_filas` já usa
    e que `infra/observability/README.md` §6 já indexa.

    Uma falha de gravação NUNCA é engolida em silêncio: um expurgo que rodou e
    não deixou prova não é auditável.
    """
    gravou, problema = filas_estado.registrar_ciclo(
        task=NOME_EXPURGO,
        estado=estado,
        tentativa=tentativa,
        max_tentativas=tentativa,
        erro=erro,
        detalhe=detalhe,
    )
    if not gravou:
        logger.error(
            "expurgo de analytics NAO pode ser gravado no estado duravel "
            "(%s): %s — esta execucao rodou sem prova auditavel",
            filas_estado.caminho_estado(),
            problema,
        )


__all__ = [
    "INTERVALO_EXPURGO_PADRAO",
    "MAX_LOTES",
    "NOME_EXPURGO",
    "RETENCAO_PADRAO",
    "RetencaoInvalida",
    "expurar_analytics",
    "retencao_dias",
    "tamanho_lote",
]