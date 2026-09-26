"""
Idempotência da ingestão sob falha e reprocessamento (P1-03, WS-06).

Este teste fecha o requisito "task de ingestão que falha e é reprocessada não
pode duplicar conteúdo". Ele é DIFFERENTE do
`test_ingestao_reentrega_nao_duplica_url` que já existe em
`test_p2_ingestao_performance.py`: aquele executa a ingestão duas vezes com
sucesso. Aqui a ingestão grava e só DEPOIS falha — o cenário real de queda
de worker / banco que some no meio do ciclo — e então é reprocessada.

Os dublês seguem a convenção de `test_p2_ingestao_performance.py` para que o
teste exercite o pipeline real de persistência, e não um caminho paralelo.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.db import OperationalError
from django.db.models import Sum

from catalogo_noticias import tasks as ingestao_tasks
from catalogo_noticias.models import NewsItem, RegistroExecucaoIngestao
from catalogo_noticias.providers.summarization import ResultadoResumo, SummarizationProvider
from catalogo_noticias.services.ingestao import ItemBruto, executar_ingestao
from config import filas_estado

pytestmark = pytest.mark.django_db


class _FonteRepetida:
    """Fonte que devolve sempre os MESMOS itens, em toda chamada."""

    nome_fonte = "Fonte Idempotente"

    def __init__(self, itens):
        self.itens = itens

    def buscar_itens(self):
        return list(self.itens)


class _ResumoBarato(SummarizationProvider):
    """Sumarização determinística e textualmente diferente do bruto."""

    def __init__(self):
        self.chamadas = 0

    def resumir_e_classificar(self, itens_brutos):
        self.chamadas += 1
        return ResultadoResumo(
            resumo=(
                f"Sintese autoral do grupo de {len(itens_brutos)} item(ns) desta "
                f"rodada do teste de idempotencia da ingestao do portal."
            ),
            categoria="geral",
            urgente=False,
            tokens_utilizados=11,
            custo_estimado_usd=0.0002,
        )


def _itens():
    return [
        ItemBruto(
            titulo="Materia A sobre um mesmo assunto",
            url_fonte_original="https://p1-03.test/idempotente/a",
            nome_fonte="Fonte Idempotente",
            conteudo_bruto="Conteudo bruto original da materia A, distinto do resumo.",
        ),
        ItemBruto(
            titulo="Materia B sobre um mesmo assunto",
            url_fonte_original="https://p1-03.test/idempotente/b",
            nome_fonte="Fonte Idempotente",
            conteudo_bruto="Conteudo bruto original da materia B, tambem distinto.",
        ),
    ]


def _estado_do_conteudo():
    """
    Retrato do conteúdo persistido + do custo de IA gasto.

    O custo vem de `RegistroExecucaoIngestao` (chamadas e tokens ao
    `SummarizationProvider`), que é onde o pipeline registra uso de LLM — é
    esse número que duplica se o reprocessamento re-resumir o mesmo item.
    """
    registros = RegistroExecucaoIngestao.objects.all()
    return {
        "itens": NewsItem.objects.count(),
        "clusters": NewsItem.objects.values("cluster").distinct().count(),
        "chamadas_llm": registros.aggregate(s=Sum("chamadas_summarization_provider"))["s"],
        "tokens_llm": registros.aggregate(s=Sum("tokens_utilizados_summarization"))["s"],
    }


def test_ingestao_que_falha_depois_de_gravar_nao_duplica_no_reprocessamento(diretorio_estado):
    """
    PROVA: uma execução que grava conteúdo e só depois falha, seguida de
    reprocessamento, deixa o conteúdo exatamente igual — nenhum item
    repetido, nenhum cluster novo, nenhuma chamada de sumarização a mais.

    Se a idempotência dependesse só do `UNIQUE` do banco, a contagem de itens
    ficaria certa mas o custo de sumarização dobraria em cada queda de worker
    — por isso o número de chamadas ao provider também é conferido.
    """
    fonte = _FonteRepetida(_itens())
    provider = _ResumoBarato()

    def _grava_e_cai():
        executar_ingestao(fontes=[fonte], summarization_provider=provider)
        raise OperationalError("worker caiu depois de gravar o lote")

    with patch.object(ingestao_tasks, "executar_ingestao", side_effect=_grava_e_cai):
        with pytest.raises(OperationalError):
            ingestao_tasks.ingerir_noticias()

    antes = _estado_do_conteudo()
    assert antes["itens"] == 2, "a primeira passada deveria ter gravado os 2 itens"
    assert antes["chamadas_llm"] == 1
    # O provider padrao chama `resumir_e_classificar` uma vez por item
    # (`resumir_e_classificar_em_lote` so e uma chamada HTTP unica no
    # provider real), entao 2 itens = 2 chamadas. O que importa aqui e a
    # INDIRECAO: o numero de chamadas fica congelado apos o reprocessamento.
    chamadas_antes = provider.chamadas
    assert chamadas_antes == 2

    # `side_effect` e nao `wraps`: a task chama `executar_ingestao()` sem
    # argumento (le a configuracao de settings em producao), entao o `wraps`
    # buscaria as 80+ fontes REAIS da rede. Aqui o duble injeta a fonte
    # unica e o provider barato.
    def _reprocessa():
        return executar_ingestao(fontes=[fonte], summarization_provider=provider)

    with patch.object(
        ingestao_tasks, "executar_ingestao", side_effect=_reprocessa
    ) as spy:
        ingestao_tasks.ingerir_noticias()

    assert spy.call_count == 1, "o reprocessamento deveria ter executado a ingestao de novo"
    assert _estado_do_conteudo() == antes
    assert (
        provider.chamadas == chamadas_antes
    ), "a sumarizacao foi refeita: custo de IA duplicado no reprocessamento"
    for url in ("https://p1-03.test/idempotente/a", "https://p1-03.test/idempotente/b"):
        assert NewsItem.objects.filter(url_fonte_original=url).count() == 1

    # O estado durável mostra que houve falha e depois sucesso — um operador
    # consegue distinguir "recuperou sozinho" de "nunca rodou".
    ciclo = filas_estado.ler_estado()["ciclos"][ingestao_tasks.TASK_INGESTAO]
    assert ciclo["estado"] == "sucesso"
    assert ciclo["detalhe"]["itens_ingeridos"] == 0, "o 2o ciclo não deveria criar item novo"


def test_tres_reentregas_da_task_nao_criam_nada_novo(diretorio_estado):
    """
    PROVA (complementar): três reentregas da MESMA task não criam conteúdo
    novo. É o caminho que `acks_late=True` + `reject_on_worker_lost=True`
    abrem quando o worker morre com a task em mãos: a constraint de
    `url_fonte_original` precisa segurar a reentrega.
    """
    fonte = _FonteRepetida(_itens())
    provider = _ResumoBarato()
    contagens = []

    def _reprocessa():
        return executar_ingestao(fontes=[fonte], summarization_provider=provider)

    for _ in range(3):
        with patch.object(ingestao_tasks, "executar_ingestao", side_effect=_reprocessa):
            ingestao_tasks.ingerir_noticias()
        contagens.append(NewsItem.objects.count())

    assert contagens == [2, 2, 2]
    assert (
        provider.chamadas == 2
    ), "tres reentregas chamaram a IA de novo para conteudo ja ingerido"
    assert (
        RegistroExecucaoIngestao.objects.aggregate(s=Sum("chamadas_summarization_provider"))["s"]
        == 1
    ), "tres reentregas custaram uma chamada de LLM, nao tres"
    assert (
        NewsItem.objects.filter(url_fonte_original="https://p1-03.test/idempotente/a").count()
        == 1
    )
