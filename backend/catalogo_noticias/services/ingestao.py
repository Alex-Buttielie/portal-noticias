"""
Orquestracao do pipeline de ingestao de noticias
(implementation-contract.md, criterios de aceite 1-6): busca em cada fonte
configurada -> normaliza -> deduplica/agrupa -> resume/classifica via
`SummarizationProvider` -> decide publicacao direta vs. fila de revisao
humana -> persiste `NewsItem`/`NewsCluster` + registro de observabilidade.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from difflib import SequenceMatcher
from typing import Optional

from django.conf import settings
from django.db import DatabaseError, DataError, IntegrityError, transaction
from django.utils import timezone

from ..models import NewsCluster, NewsItem, RegistroExecucaoIngestao
from ..providers.fallback_local import (
    MOTIVO_CONTEUDO_INSUFICIENTE,
    MOTIVO_ERRO_DO_PROVIDER,
    MOTIVO_TETO_DE_GASTO,
    marcadores_tags,
    normalizar_motivo,
)
from ..providers.news_source import (
    FonteIndisponivelError,
    ItemBruto,
    NewsSourceProvider,
    RSSNewsSourceProvider,
)
from ..providers.summarization import (
    LLMHttpSummarizationProvider,
    ResultadoResumo,
    SummarizationProvider,
    SummarizationProviderError,
)
# P1-01: politica de limites de campo e isolamento de falha.
# P1-02: telemetria rotulada do resultado da sumarizacao.
# Os dois coexistem: `limites` limita e isola, `telemetria_resumo` observa.
from . import orcamento
from . import limites
from . import telemetria_resumo
from .config_robo import cache_por_execucao
from .deduplicacao import agrupar_itens_brutos

logger = logging.getLogger(__name__)


def construir_fontes_configuradas() -> list[NewsSourceProvider]:
    from ..models import FonteRobo
    from .config_robo import fontes_rss

    fontes = fontes_rss()
    ids = [fonte.get("id") for fonte in fontes if fonte.get("id") is not None]
    registros = FonteRobo.objects.in_bulk(ids) if ids else {}
    return [
        RSSNewsSourceProvider(
            nome_fonte=fonte["nome"],
            url_feed=fonte["url"],
            estado_fonte=fonte.get("uf", ""),
            pais_fonte="Brasil" if fonte.get("uf") else "",
            etag=fonte.get("etag", ""),
            last_modified=fonte.get("last_modified", ""),
            fonte_robo=registros.get(fonte.get("id")),
            ultima_revalidacao_completa=fonte.get("ultima_revalidacao_completa"),
        )
        for fonte in fontes
    ]


def _urls_ja_ingeridas(itens: list[ItemBruto]) -> set[str]:
    """
    Uma unica query por fonte para descobrir quais URLs ja foram ingeridas
    em execucoes anteriores (code-review-contract.md run
    20260902-0727-ingestao-noticias, Finding 5 — evita N+1 SELECT EXISTS,
    um por item bruto, substituindo a versao anterior item-a-item).
    """
    urls = [item.url_fonte_original for item in itens]
    if not urls:
        return set()
    return set(
        NewsItem.objects.filter(url_fonte_original__in=urls).values_list(
            "url_fonte_original", flat=True
        )
    )


def _deduplicar_itens_por_url(itens: list[ItemBruto]) -> list[ItemBruto]:
    """Mantém a primeira ocorrência de cada URL do lote.

    A query de URLs já ingeridas é apenas uma otimização: duas URLs iguais
    no mesmo feed, ou a mesma URL retornada por duas fontes, ainda podem
    passar por ela. Deduplicar antes do agrupamento evita que o LLM seja
    chamado duas vezes para o mesmo item e deixa a constraint única do banco
    como defesa final para uma corrida entre execuções.
    """
    vistos: set[str] = set()
    unicos: list[ItemBruto] = []
    for item in itens:
        chave = item.url_fonte_original
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(item)
    return unicos


def _estimar_custo_chamada(
    provider: SummarizationProvider, quantidade_itens: int
) -> float:
    """Obtém a reserva opcional de custo antes de uma chamada ao LLM.

    Provedores de teste/fallback que não possessam esse método têm custo
    externo zero. O provider HTTP real expõe a estimativa conservadora
    baseada no teto de tokens de saída e no preço configurado.
    """
    estimador = getattr(provider, "estimar_custo_em_lote", None)
    if not callable(estimador):
        return 0.0
    try:
        return max(0.0, float(estimador(quantidade_itens)))
    except (TypeError, ValueError, AttributeError):
        logger.warning(
            "Não foi possível estimar custo da chamada de sumarização; "
            "a chamada seguirá sem reserva numérica.",
            exc_info=True,
        )
        return 0.0


def _atualizar_metricas_execucao(
    registro: RegistroExecucaoIngestao,
    *,
    chamadas: int,
    tokens: int,
    custo: float,
) -> None:
    """Persiste o acumulado antes/depois de cada chamada ao provider."""
    registro.chamadas_summarization_provider = chamadas
    registro.tokens_utilizados_summarization = tokens or None
    registro.custo_estimado_summarization_usd = custo
    registro.save(
        update_fields=[
            "chamadas_summarization_provider",
            "tokens_utilizados_summarization",
            "custo_estimado_summarization_usd",
        ]
    )


def _itens_recentes_persistidos() -> tuple[list[ItemBruto], dict[str, NewsItem]]:
    """
    Finding 3 (code-review-contract.md run 20260902-0727-ingestao-noticias,
    major): `agrupar_itens_brutos()` so comparava itens do LOTE ATUAL entre
    si — um `NewsItem` ja persistido em uma execucao anterior (ex.: G1 as
    10:00) nunca era reavaliado contra cobertura que chega depois (ex.:
    UOL/CNN Brasil as 10:15 sobre o MESMO fato), entao o criterio de "3+
    fontes -> revisao humana" nunca era atingido para um fato que so cruza
    esse limiar ao longo de VARIAS execucoes da task periodica.

    Busca (em UMA UNICA query, mesmo cuidado do Finding 5 em
    `_urls_ja_ingeridas` — nao um SELECT por item) todo `NewsItem` cujo
    `timestamp_ingestao` esteja dentro de
    `settings.CATALOGO_NOTICIAS_DEDUP_JANELA_RECENTE_HORAS` — uma janela
    configuravel, nao o historico inteiro do banco (evita full table scan
    a cada execucao). Devolve os itens como `ItemBruto` "pseudo" (mesmos
    campos usados por `agrupar_itens_brutos` para comparar titulos, dentro
    do MESMO lote combinado que os itens novos desta execucao) + um dict
    `url -> NewsItem` para o chamador identificar, depois do agrupamento,
    quais membros de um grupo sao NOVOS e quais ja estavam persistidos.

    Nao deve ser confundida com `_urls_ja_ingeridas`/idempotencia por URL
    (proposito diferente: aqui buscamos itens de URLs DIFERENTES que podem
    cobrir o MESMO acontecimento, nao a mesma URL reprocessada).

    Finding 5 (code-review-contract.md run 20260902-0727-ingestao-noticias,
    minor/performance): alem do filtro por janela de tempo, o resultado e
    limitado a `settings.CATALOGO_NOTICIAS_DEDUP_MAX_ITENS_RECENTES` itens
    (os mais recentes primeiro) — sem isso, o lote combinado passado a
    `agrupar_itens_brutos` (custo O(n^2)) cresceria sem teto junto com o
    volume acumulado de noticias na janela, em vez de so com o volume do
    lote da execucao atual.
    """
    from .config_robo import cfg_valor
    janela_horas = cfg_valor("CATALOGO_NOTICIAS_DEDUP_JANELA_RECENTE_HORAS", "dedup_janela_horas", float)
    limite_itens = int(cfg_valor("CATALOGO_NOTICIAS_DEDUP_MAX_ITENS_RECENTES", "dedup_max_itens", int))
    corte = timezone.now() - timedelta(hours=janela_horas)
    # `select_related("cluster")`: ainda UMA UNICA query (join), evita N+1 ao
    # acessar `news_item.cluster` depois, em `_persistir_grupo_mesclado`.
    # `order_by("-timestamp_ingestao")[:limite_itens]`: teto superior de
    # itens (Finding 5) — os mais recentes tem prioridade sobre os mais
    # antigos da janela quando o volume excede o limite.
    news_items_recentes = (
        NewsItem.objects.filter(timestamp_ingestao__gte=corte)
        .select_related("cluster")
        .order_by("-timestamp_ingestao")[:limite_itens]
    )

    por_url: dict[str, NewsItem] = {ni.url_fonte_original: ni for ni in news_items_recentes}
    itens_pseudo = [
        ItemBruto(
            titulo=ni.titulo,
            url_fonte_original=ni.url_fonte_original,
            nome_fonte=ni.nome_fonte,
            conteudo_bruto=ni.conteudo_bruto,
            categoria=ni.categoria,
            imagem_url=getattr(ni, "imagem_url", "") or "",
            timestamp_publicacao_fonte=ni.timestamp_publicacao_fonte,
        )
        for ni in por_url.values()
    ]
    return itens_pseudo, por_url


# Finding 2 (code-review-contract.md run 20260902-0727-ingestao-noticias, 2a
# passada, major): tamanho minimo (em caracteres) de um bloco continuo
# identico entre resumo e bruto para contar como "trecho copiado" em
# `_proporcao_do_resumo_copiada_literalmente` — cerca de 3-4 palavras em
# portugues. Filtra coincidencias triviais (uma unica palavra comum, um
# numero, uma unica preposicao) que nao representam copia de um TRECHO, so
# vocabulario compartilhado normal entre um resumo autoral e sua fonte.
_TAMANHO_MINIMO_TRECHO_COPIADO_CARACTERES = 20


def _proporcao_do_resumo_copiada_literalmente(resumo: str, bruto: str) -> float:
    """
    Finding 2 (code-review-contract.md run 20260902-0727-ingestao-noticias,
    2a passada, major): `SequenceMatcher(None, resumo, bruto).ratio()`
    (usado em `_resumo_e_copia_ou_quase_copia` abaixo) e a formula
    2*M/T, T = len(resumo)+len(bruto) — sensivel a DIFERENCA DE TAMANHO
    entre os dois textos. Quando `resumo` e um trecho VERBATIM (copiado
    literalmente, sem sintese) mas CURTO em relacao a um `bruto` bem mais
    longo (materia real com varios paragrafos), essa formula cai bem abaixo
    do limiar mesmo sendo 100% de copia literal do proprio trecho usado —
    o reviewer reproduziu isso com um resumo = primeira frase de uma
    materia de 7 frases, copiada e colada literalmente (ratio() = 0.41,
    abaixo do limiar 0.6).

    Esta funcao mede uma coisa DIFERENTE, normalizada pelo tamanho do
    PROPRIO resumo (nao pelo tamanho combinado dos dois textos): que
    PROPORCAO dos caracteres do resumo pertence a algum bloco continuo
    identico encontrado em QUALQUER trecho do bruto — nao so no inicio, em
    qualquer posicao. Usa `SequenceMatcher.get_matching_blocks()`
    (autojunk=False — o autojunk do difflib pode desconsiderar caracteres
    "populares" como espaco em textos longos, o que enfraqueceria a deteccao
    justamente no caso que motivou este fix: bruto bem mais longo que
    resumo) e soma apenas os blocos com pelo menos
    `_TAMANHO_MINIMO_TRECHO_COPIADO_CARACTERES` caracteres — um resumo cujo
    conteudo e, em sua maior parte, um ou poucos trechos copiados
    literalmente do bruto (mesmo que nao seja o texto inteiro, e mesmo que
    o trecho copiado esteja no meio/fim do bruto, nao so no inicio) tera
    proporcao alta aqui, mesmo quando `ratio()` sobre o texto inteiro nao
    capturaria isso.
    """
    if not resumo:
        return 0.0
    matcher = SequenceMatcher(None, resumo, bruto, autojunk=False)
    total_copiado = sum(
        bloco.size
        for bloco in matcher.get_matching_blocks()
        if bloco.size >= _TAMANHO_MINIMO_TRECHO_COPIADO_CARACTERES
    )
    return total_copiado / len(resumo)


def _resumo_e_copia_ou_quase_copia(resumo: str, grupo: list[ItemBruto]) -> bool:
    """
    Compara `resumo` (resultado.resumo, ja destinado a `resumo_proprio`)
    contra o `conteudo_bruto` de CADA item do grupo (code-review-contract.md
    run 20260902-0727-ingestao-noticias, Finding 1 — BRD secao 18, direitos
    autorais): nenhuma validacao de sistema impedia um SummarizationProvider
    "mal-comportado" (LLM alucinando/copiando, ou bug futuro de copy-paste)
    de fazer o pipeline publicar automaticamente um "resumo" identico ou
    quase identico ao texto bruto da fonte. Duas checagens complementares,
    QUALQUER uma bastando para bloquear (Finding 2, 2a passada — a checagem
    1 sozinha nao pega copia VERBATIM de um trecho curto de um bruto bem
    mais longo, ver docstring de `_proporcao_do_resumo_copiada_literalmente`):

    1. Similaridade do texto INTEIRO (`SequenceMatcher.ratio()`) >=
       `settings.CATALOGO_NOTICIAS_RESUMO_SIMILARIDADE_MAXIMA` — pega copia
       total/quase-total (resumo e o bruto inteiro, ou uma paráfrase muito
       proxima do texto inteiro).
    2. Proporcao do PROPRIO resumo que e um trecho continuo identico em
       QUALQUER parte do bruto (`_proporcao_do_resumo_copiada_literalmente`)
       >= `settings.CATALOGO_NOTICIAS_RESUMO_TRECHO_COPIADO_MAXIMO` — pega
       copia VERBATIM de um trecho curto (ex.: uma frase) dentro de uma
       materia bem mais longa, o gap que a checagem 1 sozinha nao cobre.

    Em qualquer um dos dois casos, `_persistir_grupo` forca
    status_revisao=pendente, nunca publicacao automatica (mesmo tratamento
    ja dado a resumo vazio).
    """
    resumo_normalizado = (resumo or "").strip()
    if not resumo_normalizado:
        return False  # resumo vazio ja e tratado separadamente (sem_resumo_confiavel)

    from .config_robo import cfg_valor
    limiar_similaridade_total = cfg_valor("CATALOGO_NOTICIAS_RESUMO_SIMILARIDADE_MAXIMA", "resumo_similaridade_maxima", float)
    limiar_trecho_copiado = cfg_valor("CATALOGO_NOTICIAS_RESUMO_TRECHO_COPIADO_MAXIMO", "resumo_trecho_copiado_maximo", float)
    for item_bruto in grupo:
        bruto_normalizado = (item_bruto.conteudo_bruto or "").strip()
        if not bruto_normalizado:
            continue

        similaridade = SequenceMatcher(None, resumo_normalizado, bruto_normalizado).ratio()
        if similaridade >= limiar_similaridade_total:
            logger.warning(
                "resumo_proprio suspeito de copia/quase-copia do conteudo_bruto "
                "(similaridade=%.2f >= limiar=%.2f) para item de '%s' — forcando "
                "status_revisao=pendente em vez de publicacao automatica.",
                similaridade,
                limiar_similaridade_total,
                item_bruto.nome_fonte,
            )
            return True

        proporcao_copiada = _proporcao_do_resumo_copiada_literalmente(
            resumo_normalizado, bruto_normalizado
        )
        if proporcao_copiada >= limiar_trecho_copiado:
            logger.warning(
                "resumo_proprio suspeito de conter um TRECHO copiado literalmente do "
                "conteudo_bruto (proporcao=%.2f >= limiar=%.2f) para item de '%s' — "
                "forcando status_revisao=pendente em vez de publicacao automatica.",
                proporcao_copiada,
                limiar_trecho_copiado,
                item_bruto.nome_fonte,
            )
            return True
    return False


def _eh_alta_relevancia(categoria: str, numero_fontes_distintas: int) -> bool:
    """
    Criterio de alta relevancia (task-plan.md, "Suposicoes assumidas";
    implementation-contract.md, criterio de aceite 5 e 7): categoria
    sensivel OU cluster com N ou mais fontes distintas — ambos
    parametrizaveis via `settings` (env vars), sem alteracao de codigo.
    """
    from .config_robo import categorias_sensiveis as _cats, cfg_valor
    categorias_sensiveis = set(_cats())
    limiar_fontes = int(cfg_valor("CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA", "limiar_fontes_alta_relevancia", int))
    categoria_normalizada = (categoria or "").strip().lower()
    return (categoria_normalizada in categorias_sensiveis) or (numero_fontes_distintas >= limiar_fontes)


# Finding 1 (code-review-contract.md run 20260902-0727-ingestao-noticias, 3a
# passada, major — MUDANCA DE ESTRATEGIA, nao mais um ajuste de lista): nas
# duas rodadas anteriores, o reviewer reproduziu repetidamente (com
# vocabulario NOVO a cada vez — "prefeitura/plano", depois "ministerio/surto",
# "presidente/viagem") o mesmo tipo de falso-positivo de agrupamento por
# estrutura sintatica/institucional comum. Tentar consertar isso ampliando
# uma lista curada de termos genericos e estruturalmente "whack-a-mole": o
# portugues tem um numero pratico ilimitado de verbos/substantivos
# institucionais genericos, entao sempre vai existir vocabulario nao coberto
# pela lista.
#
# A mudanca de estrategia desta correcao: TODA chamada ao
# `SummarizationProvider` passa a ser feita INDIVIDUALMENTE, por item (nunca
# mais um resumo unico compartilhado por todos os itens de um `NewsCluster`)
# — ver `executar_ingestao`. Isso elimina ESTRUTURALMENTE (nao por
# heuristica de similaridade) o risco central de misattribution do BRD
# secao 18: mesmo que o algoritmo de agrupamento erre e junte "surto de
# dengue" com "surto de sarampo" no mesmo `NewsCluster`, cada `NewsItem`
# continua tendo seu PROPRIO `resumo_proprio`, gerado exclusivamente a
# partir do seu PROPRIO `conteudo_bruto` — nunca um resumo de um fato
# atribuido a uma fonte que noticiou outro fato.
#
# NAO adotamos, junto disso, "todo NewsCluster com 2+ itens forca pendente
# incondicionalmente" (a outra metade da sugestao do reviewer) — essa opcao
# foi implementada e depois REVERTIDA nesta mesma iteracao, ao descobrir que
# ela quebra `TestAC7ConfiguravelSemAlterarCodigo::
# test_aumentar_limiar_via_override_settings_tambem_muda_comportamento`
# (implementation-contract.md, criterio de aceite 7 — ja EXISTENTE e testado
# antes desta correcao): esse teste prova que o admin deve poder configurar
# `CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA` alto o suficiente para
# DESATIVAR a revisao automatica por numero de fontes, e um cluster de 3
# itens com esse limiar elevado deve continuar `nao_aplicavel`. Forcar
# pendente para qualquer cluster, incondicionalmente, romperia essa garantia
# de configurabilidade ja aceita e testada — nao e uma correcao que o
# remediator deveria aplicar por conta propria sobre um criterio de aceite
# preexistente. Ver nota em implementation-history.md ("Iteracao 5") e o
# relato ao usuario: o residual "cluster de 2 itens abaixo do limiar de
# fontes continua podendo ser nao_aplicavel" e um risco RESIDUAL, MENOR
# (agrupamento de exibicao possivelmente impreciso, ja SEM risco de
# conteudo/resumo incorreto atribuido a uma fonte errada) — decisao
# consciente, nao um descuido, registrada para o `orchestrator`/humano julgar
# se aceita esse residual ou pede uma revisao de produto do proprio AC-7.


def _persistir_news_items_em_lote(itens: list[NewsItem]) -> list[NewsItem]:
    """Valida, limita e persiste NewsItems em lote.

    ``bulk_create`` não chama ``save()``/signals, mas o modelo não possui
    signals registrados no projeto e toda a decisão de status já foi feita
    antes desta chamada. ``clean()`` é chamado explicitamente para preservar
    a validação de URL/fonte; a check constraint e a unique do banco são as
    camadas finais. ``full_clean`` foi avaliado, mas rejeita URLs históricas
    aceitas pelo pipeline (por exemplo, hosts sem sufixo público); manter
    ``clean()`` preserva o contrato de ingestão e deixa a validação sintática
    de URL como residual. A lista é deduplicada por URL antes do insert e
    ``ignore_conflicts`` trata a corrida entre duas execuções que passaram
    pelo SELECT inicial.

    P1-01 (esta função é o ÚLTIMO ponto antes do INSERT, então é aqui que mora
    a garantia final de que nenhum `DataError` escapa):

    * Cada item passa por `services.limites` (defesa em profundidade). Os
      chamadores (`_persistir_grupo`/`_persistir_grupo_mesclado`) ja limitaram
      antes; aqui a operacao é idempotente e cobre qualquer chamador futuro
      (admin, API, script) sem depender de saber da existencia de limites.
    * Um `DataError` do banco (campo novo sem teto, trigger, bug futuro) cai
      no fallback LINHA A LINHA: cada item é inserido no seu proprio savepoint
      e o que falhar é registrado e descartado. Perde-se o item ruim, nunca o
      grupo inteiro.
    """
    if not itens:
        return []

    vistos: set[str] = set()
    itens_unicos: list[NewsItem] = []
    for item in itens:
        if item.url_fonte_original in vistos:
            continue
        vistos.add(item.url_fonte_original)
        # DEFESA EM PROFUNDIDADE (P1-01). Os chamadores ja construiram cada
        # item por `_construir_news_item`, que aplica os limites; aqui eles
        # sao reaplicados porque esta e a ULTIMA porta antes do INSERT e
        # qualquer chamador novo (outro servico, script de carga, tarefa
        # futura) herdaria a garantia sem precisar saber que `services.limites`
        # existe. E idempotente: um item ja dentro do limite nao muda.
        #
        # `CampoForaDoLimiteError` aqui significa que o item foi montado SEM
        # passar pelo construtor. Ele nao pode ser engolido em silencio: o
        # item e descartado e a falha registrada com fonte/item/motivo, e o
        # restante do lote segue — que e o mesmo contrato do construtor.
        try:
            limites.limitar_textos(item)
        except Exception as exc:  # noqa: BLE001 — um item ruim não derruba o lote
            item.pk = None
            limites.registrar_falha(
                limites.mensagem_para_erro(
                    exc,
                    nome_fonte=item.nome_fonte,
                    identificador=item.url_fonte_original,
                ),
                nome_fonte=item.nome_fonte,
                identificador=item.url_fonte_original,
                escopo="persistencia_item",
                exc=exc,
            )
            continue
        item.clean()
        itens_unicos.append(item)

    try:
        # No caminho normal mantemos o INSERT único e os PKs preenchidos.
        # A captura fica num savepoint para que um conflito de corrida possa
        # ser tratado sem deixar a transação externa quebrada.
        with transaction.atomic():
            NewsItem.objects.bulk_create(itens_unicos, batch_size=500)
    except IntegrityError:
        # Outra execução pode ter inserido a mesma URL entre o SELECT
        # inicial e este INSERT. Requery + INSERT IGNORE é a segunda camada
        # atômica; URLs já existentes são apenas descartadas.
        urls = [item.url_fonte_original for item in itens_unicos]
        existentes = set(
            NewsItem.objects.filter(url_fonte_original__in=urls).values_list(
                "url_fonte_original", flat=True
            )
        )
        restantes = [
            item for item in itens_unicos if item.url_fonte_original not in existentes
        ]
        if restantes:
            with transaction.atomic():
                NewsItem.objects.bulk_create(
                    restantes,
                    batch_size=500,
                    ignore_conflicts=True,
                )
    except DataError as exc:
        # O banco recusou o LOTE por um valor grande demais
        # (`StringDataRightTruncation` -> `django.db.DataError`). Um INSERT em
        # lote e tudo-ou-nada: perder o grupo inteiro por causa de UMA linha
        # seria o mesmo defeito que este item de backlog veio corrigir.
        #
        # Fallback LINHA A LINHA, cada uma no seu proprio savepoint: um item
        # que o banco recusa e registrado e descartado, os demais entram. O
        # savepoint por item e o que impede que a falha de uma linha deixe a
        # transacao inutilizavel para as seguinte.
        limites.registrar_falha(
            f"DataError ao inserir o lote de {len(itens_unicos)} item(ns); "
            f"refazendo item a item. Motivo do banco: {exc}",
            nome_fonte="(lote)",
            identificador=f"{len(itens_unicos)} item(ns)",
            escopo="persistencia_em_lote",
            exc=exc,
        )
        for item in itens_unicos:
            try:
                with transaction.atomic():
                    NewsItem.objects.bulk_create([item], batch_size=1)
            except (DataError, IntegrityError) as exc_item:
                # `pk` fica None: o item nao entrou, e o bloco de religamento
                # abaixo nao vai "adivinhar" um id para ele.
                item.pk = None
                limites.registrar_falha(
                    limites.mensagem_para_erro(
                        exc_item,
                        nome_fonte=item.nome_fonte,
                        identificador=item.url_fonte_original,
                    ),
                    nome_fonte=item.nome_fonte,
                    identificador=item.url_fonte_original,
                    escopo="persistencia_item",
                    exc=exc_item,
                )
    except DatabaseError as exc:
        # Qualquer outro erro do banco no INSERT em lote (violacao de CHECK,
        # tipo invalido) e falha da TRANSAÇÃO, nao de um item: nesse caso nao
        # da para isolar linha a linha, porque todas as linhas do lote estao
        # igualmente comprometidas. Registrado com traceback e re-lancado: o
        # isolamento por grupo em `executar_ingestao` e quem decide o que
        # fazer, e ele precisa saber que a falha foi de banco.
        limites.registrar_falha(
            f"Falha de banco ao inserir o lote de {len(itens_unicos)} item(ns): {exc}",
            nome_fonte="(lote)",
            identificador=f"{len(itens_unicos)} item(ns)",
            escopo="persistencia_em_lote",
            exc=exc,
        )
        raise

    # `ignore_conflicts` não preenche PKs em todos os backends. Se um objeto
    # perdeu a corrida, religamos apenas os PKs já persistidos; isso mantém
    # o retorno da função utilizável sem mascarar outras constraints.
    if any(item.pk is None for item in itens_unicos):
        persisted = {
            url: pk
            for url, pk in NewsItem.objects.filter(
                url_fonte_original__in=[item.url_fonte_original for item in itens_unicos]
            ).values_list("url_fonte_original", "pk")
        }
        for item in itens_unicos:
            if item.pk is None and item.url_fonte_original in persisted:
                item.pk = persisted[item.url_fonte_original]

    # O autocomplete é uma otimização reconstruível; uma escrita real deve
    # torná-lo consistente sem esperar o TTL de 300 s. Esta função é chamada
    # por _persistir_grupo/_persistir_grupo_mesclado, ambos decorators
    # @transaction.atomic; agendar evita a janela de repopulação pré-commit.
    if itens_unicos:
        try:
            from feed.busca import invalidar_cache_autocomplete

            transaction.on_commit(invalidar_cache_autocomplete)
        except Exception:
            # A invalidação é best-effort; a ingestão e a fonte de verdade
            # não podem depender do backend de cache.
            logger.warning(
                "Falha ao invalidar cache de autocomplete após ingestão",
                exc_info=True,
            )
    return itens_unicos


def _construir_news_item(
    item_bruto: ItemBruto,
    resultado: ResultadoResumo,
    *,
    cluster: Optional[NewsCluster],
    categoria_grupo: str = "",
    categoria_item_override: str = "",
    categoria_fallback: str = "",
) -> NewsItem:
    """Constroi UM `NewsItem` a partir de um `ItemBruto` + `ResultadoResumo`,
    ja com os limites de campo aplicados (`services.limites`).

    P1-01: existe como funcao unica (antes a construcao estava DUPLICADA em
    `_persistir_grupo` e `_persistir_grupo_mesclado`, e um limite forgotten
    em uma das copias viraria um `DataError` que so apareceria no caminho de
    mesclagem). Um ponto de construcao = um ponto onde o limite e aplicado.

    P1-02: este tambem e o UNICO ponto onde o marcador de origem do resumo
    (`NewsItem.tags`) e carregado. A raza de o marcador morar AQUI, e nao em
    um `NewsItem(...)` inline nos dois loops de persistencia, e a INVARIANTE
    CRITICA deste merge:

        Um item cujo resumo venha do fallback LOCAL tem de passar pela politica
        de limites de campo do P1-01.

    Como `resultado.resumo` pode vir de qualquer fonte (provedor externo OU
    `providers/fallback_local.py`), e o fallback local nao estava no radar do
    P1-01, o risco concreto e o seguinte: o texto do fallback local e montado
    por concatenacao do TITULO da fonte, e um feed com titulo/`nome_fonte`/
    `categoria` enormes produz um `resumo_proprio` enorme. Se o item do
    fallback fosse construido por um caminho que nao passa por
    `limites.limitar_textos`, o `StringDataRightTruncation` voltaria e mataria
    a rodada INTEIRA — exatamente o defeito que o P1-01 fechou. Por isso o
    marcador entra AQUI, no construtor unico, e nao em uma copia: assim todo
    item, de qualquer origem, e limitado antes de qualquer escrita.

    Levanta `limites.CampoForaDoLimiteError` quando um campo identificador
    passou do limite — nesse caso o item e descartado pelo chamador, que
    registra a falha com o contexto. Nao ha `except` aqui: quem decide o que
    fazer com a falha de um item e o loop de persistencia, que tem o contexto
    do lote.
    """
    if categoria_item_override:
        categoria_item = categoria_item_override
    elif categoria_grupo:
        categoria_item = (
            resultado.categoria or item_bruto.categoria or categoria_grupo or ""
        ).strip().lower()
    else:
        categoria_item = (
            resultado.categoria or item_bruto.categoria or categoria_fallback or ""
        ).strip().lower()

    # Sem resumo confiavel (ex.: SummarizationProvider falhou e caiu no
    # fallback de erro, OU devolveu um resumo vazio), o item NUNCA e publicado
    # automaticamente, independente do criterio de categoria/fontes — forcamos
    # revisao humana (implementation-contract.md, criterio de aceite 4: nunca
    # publicar sem resumo proprio real).
    sem_resumo_confiavel = not (resultado.resumo or "").strip()
    # Finding 1 (code-review-contract.md run 20260902-0727-ingestao-noticias,
    # 1a passada, blocker — BRD secao 18): mesmo com um resumo NAO vazio, se
    # ele acabou identico ou quase identico ao conteudo_bruto DESTE item
    # (provider "copiando" a fonte), tambem forcamos revisao humana em vez de
    # publicar automaticamente.
    resumo_suspeito_de_copia = not sem_resumo_confiavel and _resumo_e_copia_ou_quase_copia(
        resultado.resumo, [item_bruto]
    )

    news_item = NewsItem(
        titulo=item_bruto.titulo,
        resumo_proprio=resultado.resumo,
        conteudo_bruto=item_bruto.conteudo_bruto,
        conteudo_completo=getattr(item_bruto, "conteudo_completo", "") or "",
        url_fonte_original=item_bruto.url_fonte_original,
        nome_fonte=item_bruto.nome_fonte,
        categoria=categoria_item,
        imagem_url=getattr(item_bruto, "imagem_url", "") or "",
        timestamp_publicacao_fonte=item_bruto.timestamp_publicacao_fonte,
        urgente=resultado.urgente,
        status_revisao="",  # definido abaixo, depois de decidir
        cluster=cluster,
        # Marcador de origem do resumo (P1-02): carregado APENAS quando o
        # resumo veio do fallback local deterministico, para que a UI, a
        # metrica e o editorial saibam que este item nao passou pelo provedor
        # externo. No caminho feliz (`fallback=False`) `_tags_com_origem`
        # devolve `[]` e `NewsItem.tags` fica como sempre ficou — a ausencia do
        # marcador e o sinal de "resumo do provedor", o que mantem o caminho
        # feliz inalterado.
        tags=_tags_com_origem(resultado),
    )
    # Recorte regional herdado da fonte (ex.: G1 Goias -> GO/Brasil) quando o
    # RSS nao informa localidade propria; nunca inventado. `pais`/`estado`
    # NUNCA eram limitados antes (varchar(100) sem teto vindo do config).
    news_item.estado = getattr(item_bruto, "estado_fonte", "") or ""
    news_item.pais = getattr(item_bruto, "pais_fonte", "") or ""

    # O limite e aplicado AQUI, no servico, antes de qualquer escrita — e nao
    # na view nem so no provider: assim vale para todas as fontes (RSS hoje,
    # APIlicensed amanha) e para todos os caminhos de escrita.
    #
    # INVARIANTE CRITICA DO MERGE P1-01 x P1-02: como o `resumo_proprio` acima
    # pode ter vindo do FALLBACK LOCAL (P1-02) e nao so do provedor externo,
    # esta e a unica linha que garante que o fallback local tambem respeita a
    # politica de limites. Um item do fallback cujo `resumo` (montado a partir
    # do titulo da fonte) passe do teto e truncado aqui, e nao lancado como
    # `DataError` no INSERT. Ver o docstring desta funcao.
    limites.limitar_textos(news_item)

    return news_item


def _construir_news_cluster(
    titulo: str,
    categoria: str,
    numero_fontes_distintas: int,
) -> NewsCluster:
    """Cria um `NewsCluster` com os limites aplicados.

    `titulo_acontecimento` e `varchar(300)` e recebia o titulo do RSS sem
    teto: um feed com titulo grande estourava o banco e matava a execucao
    ANTES de qualquer `NewsItem` ser criado (P1-01).
    """
    cluster = NewsCluster(
        titulo_acontecimento=titulo,
        categoria_dominante=categoria,
        numero_fontes_distintas=numero_fontes_distintas,
    )
    limites.limitar_textos(cluster)
    cluster.save()
    return cluster


@transaction.atomic
def _persistir_grupo(
    resultados_por_item: list[tuple[ItemBruto, ResultadoResumo]],
) -> tuple[Optional[NewsCluster], list[NewsItem]]:
    """
    `resultados_por_item`: um `ResultadoResumo` INDIVIDUAL por `ItemBruto`
    (Finding 1, 3a passada — ver o comentario acima desta funcao para o
    porque) — `executar_ingestao` chama o `SummarizationProvider` uma vez
    por item, nunca mais uma vez para o grupo inteiro.
    """
    grupo = [item_bruto for item_bruto, _ in resultados_por_item]
    numero_fontes_distintas = len({item.nome_fonte for item in grupo})
    grupo_multiplo = len(grupo) > 1

    cluster = None
    if grupo_multiplo:
        primeira_categoria = (
            resultados_por_item[0][1].categoria or grupo[0].categoria or ""
        ).strip().lower()
        # P1-1 (run 20260923-1216): coluna denormalizada gravada já na
        # criação — o caminho quente do feed lê o campo sem COUNT.
        # P1-01: titulo e categoria limitados dentro de `_construir_news_cluster`.
        cluster = _construir_news_cluster(
            grupo[0].titulo, primeira_categoria, numero_fontes_distintas
        )

    itens_criados: list[NewsItem] = []
    for item_bruto, resultado in resultados_por_item:
        # ISOLAMENTO POR ITEM (P1-01): um item cujo campo identificador passou
        # do limite nao pode derrubar o restante do grupo. A falha e
        # registrada com fonte, item e motivo e o loop segue.
        try:
            news_item = _construir_news_item(
                item_bruto, resultado, cluster=cluster
            )
        except Exception as exc:  # noqa: BLE001 — um item ruim não derruba o grupo
            limites.registrar_falha(
                limites.mensagem_para_erro(
                    exc,
                    nome_fonte=item_bruto.nome_fonte,
                    identificador=item_bruto.url_fonte_original,
                ),
                nome_fonte=item_bruto.nome_fonte,
                identificador=item_bruto.url_fonte_original,
                escopo="construcao_item",
                exc=exc,
            )
            continue

        # O status depende do numero de fontes do grupo, que so e conhecido
        # aqui (o cluster ja pode existir).
        categoria_item = news_item.categoria
        sem_resumo_confiavel = not (resultado.resumo or "").strip()
        resumo_suspeito_de_copia = not sem_resumo_confiavel and _resumo_e_copia_ou_quase_copia(
            resultado.resumo, [item_bruto]
        )
        alta_relevancia = (
            sem_resumo_confiavel
            or resumo_suspeito_de_copia
            or _eh_alta_relevancia(categoria_item, numero_fontes_distintas)
        )
        # DISPUTA REAL DE COMPORTAMENTO, resolvida a favor do P1-01.
        #
        # O lado P1-02 substituia o construtor unico por um `NewsItem(...)`
        # inline, so para acrescentar `tags=_tags_com_origem(resultado)`. Aceitar
        # isso reintroduziria a DUPLICACAO de construcao que o P1-01 eliminou
        # e, com ela, o defeito que ele fechou: esta copia nao passaria por
        # `limites.limitar_textos`, e um item com campo fora do limite voltaria
        # a levantar `DataError` no INSERT — derrubando a rodada INTEIRA.
        #
        # O que o P1-02 genuinamente acrescenta (o marcador de origem) e
        # ENTREGUE pelo construtor unico, em `_construir_news_item`, que e o
        # unico ponto de construcao de `NewsItem` do pipeline. Assim todo item
        # — do provedor OU do fallback local — passa pelos limites, e nenhum
        # caminho de escrita pode contorna-los.
        news_item.status_revisao = (
            NewsItem.STATUS_PENDENTE if alta_relevancia else NewsItem.STATUS_NAO_APLICAVEL
        )
        itens_criados.append(news_item)

    itens_criados = _persistir_news_items_em_lote(itens_criados)
    return cluster, itens_criados


@transaction.atomic
def _persistir_grupo_mesclado(
    resultados_por_item: list[tuple[ItemBruto, ResultadoResumo]],
    news_items_existentes: list[NewsItem],
) -> tuple[NewsCluster, list[NewsItem]]:
    """
    Finding 3 (code-review-contract.md run 20260902-0727-ingestao-noticias,
    major): persiste um grupo formado por `agrupar_itens_brutos` que mistura
    itens NOVOS desta execucao com `NewsItem`(s) JA PERSISTIDOS (de execucoes
    anteriores, dentro da janela recente — ver `_itens_recentes_persistidos`)
    que o algoritmo de agrupamento considerou o MESMO acontecimento.

    Decisoes de design (documentadas aqui, nao so em implementation-history.md,
    porque sao especificas desta funcao):

    1. Os itens ja existentes NAO sao re-resumidos (evita uma chamada
       redundante ao `SummarizationProvider` — custo, AC-6) — mantem seu
       `resumo_proprio` original. Isso significa que itens do MESMO cluster
       podem ficar com resumos "desconectados" entre si (o dos itens antigos
       nao menciona as fontes que chegaram depois) — limitacao conhecida,
       nao um bug novo introduzido aqui.
    2. Cluster canonico: se os itens existentes do grupo ja pertencem a UM
       `NewsCluster`, os novos entram nele. Se estao standalone
       (`cluster=None`), promovemos — criamos um `NewsCluster` novo e
       associamos itens antigos + novos a ele. No caso raro de itens
       existentes do grupo pertencerem a DOIS clusters diferentes (dois
       clusters que só agora, com o item novo fazendo ponte, se revelam
       serem o mesmo acontecimento), o cluster mais antigo (menor id) vira o
       canonico e os demais sao mesclados nele — e, apos mover todos os
       `NewsItem` para o canonico, o(s) `NewsCluster` nao-canonico(s) (agora
       orfao(s), zero itens associados) e(sao) deletado(s) (Finding 4,
       code-review-contract.md run 20260902-0727-ingestao-noticias, minor —
       evita acumular clusters "fantasma" na fila de auditoria do admin;
       seguro porque `NewsItem.cluster` usa `on_delete=SET_NULL` e todos os
       itens ja foram movidos para o canonico ANTES do delete).
    3. Reavaliacao de status_revisao (o cerne do Finding 3, comportamento
       preservado): sempre que a uniao (existentes + novos) faz o cluster
       cruzar o criterio de alta relevancia (`_eh_alta_relevancia` —
       categoria sensivel OU numero de fontes distintas), TODOS os itens do
       cluster sao reavaliados — mas SO mudamos itens cujo status_revisao
       ainda seja `nao_aplicavel` ou `pendente`; nunca sobrescrevemos
       `aprovado`/`rejeitado`. Cada item NOVO tem seu PROPRIO
       `resumo_proprio`, gerado individualmente por `executar_ingestao`
       (Finding 1, 3a passada — nunca mais um resultado compartilhado entre
       itens do grupo, ver comentario acima de `_persistir_grupo`) — elimina
       o risco de misattribution de CONTEUDO mesmo quando a decisao de
       agrupamento em si estiver errada. O criterio de QUANDO exigir revisao
       humana (categoria/numero de fontes) continua o mesmo de antes,
       deliberadamente — ver a nota sobre `AC-7`/`test_aumentar_limiar_...`
       no comentario acima de `_persistir_grupo`.
    """
    clusters_existentes = {
        news_item.cluster_id: news_item.cluster
        for news_item in news_items_existentes
        if news_item.cluster_id is not None
    }

    if clusters_existentes:
        cluster = min(clusters_existentes.values(), key=lambda c: c.id)
        outros_ids = [cluster_id for cluster_id in clusters_existentes if cluster_id != cluster.id]
        if outros_ids:
            logger.info(
                "Finding 3: mesclando cluster(s) %s no cluster canonico %s (item novo revelou que "
                "cobrem o mesmo acontecimento).",
                outros_ids,
                cluster.id,
            )
            NewsItem.objects.filter(cluster_id__in=outros_ids).update(cluster=cluster)
            # Finding 4 (minor): os clusters nao-canonicos ficam sem NENHUM
            # NewsItem associado apos o update acima — deletar em vez de
            # deixar a linha "fantasma" (zero fontes) na fila de
            # auditoria/admin.
            deletados, _ = NewsCluster.objects.filter(pk__in=outros_ids).delete()
            logger.info(
                "Finding 4: %d NewsCluster orfao(s) (%s) removido(s) apos mesclagem no canonico %s.",
                deletados,
                outros_ids,
                cluster.id,
            )
    else:
        item_existente_mais_antigo = min(news_items_existentes, key=lambda ni: ni.timestamp_ingestao)
        # P1-01: o mesmo construtor com limites usado em `_persistir_grupo` —
        # os dois pontos que criavam `NewsCluster` precisavam do mesmo cuidado
        # (`titulo_acontecimento` e `varchar(300)` e recebia o titulo do RSS
        # sem teto). `numero_fontes_distintas` e recomputada no fim desta
        # funcao por `recalcular_numero_fontes` (fonte da verdade: o banco).
        cluster = _construir_news_cluster(
            item_existente_mais_antigo.titulo,
            item_existente_mais_antigo.categoria or resultados_por_item[0][1].categoria or "",
            len({ni.nome_fonte for ni in news_items_existentes}),
        )
        NewsItem.objects.filter(pk__in=[ni.pk for ni in news_items_existentes]).update(cluster=cluster)
        logger.info(
            "Finding 3: item(ns) previamente standalone promovido(s) a NewsCluster %s por cobertura "
            "adicional chegada em execucao posterior.",
            cluster.id,
        )

    categoria_grupo = (
        resultados_por_item[0][1].categoria
        or resultados_por_item[0][0].categoria
        or cluster.categoria_dominante
        or ""
    ).strip().lower()
    if not cluster.categoria_dominante and categoria_grupo:
        cluster.categoria_dominante = categoria_grupo
        # P1-01: `categoria_dominante` e `varchar(100)`; limitar tambem no
        # caminho de `update_fields`, nao so no `create`.
        limites.limitar_textos(cluster)
        cluster.save(update_fields=["categoria_dominante"])

    # Finding 1 (3a passada): cada item novo tem seu PROPRIO
    # `resumo_proprio`, gerado individualmente por `executar_ingestao` (nunca
    # mais um resultado compartilhado por todos os itens novos do grupo) —
    # elimina o risco estrutural de misattribution de CONTEUDO mesmo quando
    # a decisao de agrupamento em si estiver errada.
    itens_criados: list[NewsItem] = []
    for item_bruto, resultado in resultados_por_item:
        # ISOLAMENTO POR ITEM (P1-01): igual a `_persistir_grupo` — um item com
        # campo fora do limite e registrado e descartado, os demais do grupo
        # entram. Reusa o MESMO construtor, que aplica os limites: um limite
        # esquecido em uma das duas copias de construcao viraria um `DataError`
        # que so apareceria no caminho de mesclagem.
        try:
            news_item = _construir_news_item(
                item_bruto,
                resultado,
                cluster=cluster,
                categoria_grupo=categoria_grupo,
            )
        except Exception as exc:  # noqa: BLE001 — um item ruim não derruba o grupo
            limites.registrar_falha(
                limites.mensagem_para_erro(
                    exc,
                    nome_fonte=item_bruto.nome_fonte,
                    identificador=item_bruto.url_fonte_original,
                ),
                nome_fonte=item_bruto.nome_fonte,
                identificador=item_bruto.url_fonte_original,
                escopo="construcao_item",
                exc=exc,
            )
            continue

        sem_resumo_confiavel = not (resultado.resumo or "").strip()
        resumo_suspeito_de_copia = not sem_resumo_confiavel and _resumo_e_copia_ou_quase_copia(
            resultado.resumo, [item_bruto]
        )
        news_item.status_revisao = (
            NewsItem.STATUS_PENDENTE
            if (sem_resumo_confiavel or resumo_suspeito_de_copia)
            else NewsItem.STATUS_NAO_APLICAVEL
        )
        # DISPUTA REAL DE COMPORTAMENTO, resolvida a favor do P1-01 — mesma
        # decisao de `_persistir_grupo`, e pelo mesmo motivo: o lado P1-02
        # trocava o construtor unico por um `NewsItem(...)` inline (so para
        # ganhar `tags=_tags_com_origem(resultado)`), o que reintroduziria a
        # duplicacao de construcao e o `DataError` que matava a rodada. O
        # marcador de origem entra pelo MESMO construtor unico, com os
        # limites aplicados — inclusive no caminho de mesclagem, que era
        # justamente onde um limite esquecido so apareceria em producao.
        itens_criados.append(news_item)

    itens_criados = _persistir_news_items_em_lote(itens_criados)

    # Reavalia o cluster INTEIRO (itens antigos + novos) contra o criterio de
    # alta relevancia agora que cresceu — sem isso, um cluster que so cruza o
    # limiar de fontes tardiamente (itens antigos + novos, nao so os desta
    # execucao) nunca aciona revisao humana para os itens antigos ja
    # publicados automaticamente (o proprio problema que o Finding 3 aponta).
    # Comportamento preservado da 2a passada — ver nota sobre AC-7 acima de
    # `_persistir_grupo` para o porque este criterio NAO virou incondicional.
    #
    # P1-1 (run 20260923-1216): a contagem denormalizada e atualizada aqui
    # (único ponto de mesclagem/movimentação de itens entre clusters) a
    # partir do estado real do banco — cobre promoção de standalone,
    # crescimento do canônico e fusão de clusters não-canônicos. Usa o
    # método canônico do modelo (mesma lógica do backfill da migração) para
    # as duas implementações nunca divergirem.
    numero_fontes_distintas = cluster.recalcular_numero_fontes()
    if _eh_alta_relevancia(categoria_grupo or cluster.categoria_dominante, numero_fontes_distintas):
        atualizados = cluster.itens.exclude(
            status_revisao__in=[NewsItem.STATUS_APROVADO, NewsItem.STATUS_REJEITADO]
        ).update(status_revisao=NewsItem.STATUS_PENDENTE)
        logger.info(
            "Finding 3: NewsCluster %s cruzou o criterio de alta relevancia (%d fontes distintas) apos "
            "mesclagem — %d item(ns) com status_revisao reavaliado(s) para pendente (aprovado/rejeitado "
            "preservados).",
            cluster.id,
            numero_fontes_distintas,
            atualizados,
        )
        for news_item in itens_criados:
            if news_item.pk:
                news_item.refresh_from_db(fields=["status_revisao"])

    return cluster, itens_criados


def _resultado_fallback_local(item_bruto: ItemBruto, motivo: str) -> ResultadoResumo:
    """
    Fallback LOCAL deterministico (`providers/fallback_local.py`) para UM item.

    Substitui o antigo `_resultado_fallback_erro`, que devolvia
    `ResultadoResumo(resumo="")`. Resumo vazio significava
    `sem_resumo_confiavel=True` em `_persistir_grupo` ->
    `status_revisao=pendente` -> item INVISIVEL no feed
    (`feed/services.py::STATUS_PUBLICAVEIS`), ou seja, a noticia simplesmente
    nao existia para o leitor. Era o "rascunho fantasma" do backlog P1-02.

    Agora o item recebe conteudo honesto, deterministico e sem rede, e o
    resultado fica marcado (`fallback=True` + `motivo_fallback`) para que a
    metrica, o log, a UI e o editorial saibam que ele NAO veio do provedor.

    Se o material de origem nao sustenta um resumo honesto (sem TITULO — a
    manchete e o unico campo que identifica a noticia; `nome_fonte` e
    obrigatorio por `NewsItem.clean()`), `gerar_resumo_local` devolve
    `suficiente=False` e aqui o motivo vira `conteudo_insuficiente`: o
    fallback **sinaliza** a falta em vez de preencher, e o item volta para
    revisao humana (nenhuma noticia publicada com texto invented).
    """
    from ..providers.fallback_local import gerar_resumo_local

    gerado = gerar_resumo_local(item_bruto)
    # O motivo do CHAMADOR e preservado; `conteudo_insuficiente` so substitui
    # ele quando o material de origem realmente nao sustentou um resumo
    # honesto — e nesse caso o item volta para revisao humana (nenhuma noticia
    # publicada com texto invented).
    return ResultadoResumo(
        resumo=gerado.resumo,
        categoria=(item_bruto.categoria or "").strip().lower(),
        urgente=False,
        fallback=True,
        motivo_fallback=normalizar_motivo(
            motivo if gerado.suficiente else MOTIVO_CONTEUDO_INSUFICIENTE
        ),
    )


def _resultado_sem_resumo_por_teto(item_bruto: ItemBruto) -> ResultadoResumo:
    """
    Fail-safe de CUSTO (nao de falha do provedor): quando o teto diario de
    gasto seria ultrapassado, o provedor externo NAO e chamado.

    Diferente de `_resultado_fallback_local` de proposito: aqui o item
    continua sem resumo automatico e portanto segue para REVISAO HUMANA,
    conforme o AC-2/AC-3 ja pactuado em `run 20260903-1211-teto-gasto-diario-llm`
    (que este item nao reopens). O que esta intervencao acrescenta e a
    DISTINGUIBILIDADE: o item fica marcado com `motivo_fallback=teto_de_gasto`
    e a metrica/log passam a registrar o rotulo, de modo que o operador
    differentiate "custo estourado" de "provedor caiu".
    """
    return ResultadoResumo(
        resumo="",
        categoria=(item_bruto.categoria or "").strip().lower(),
        urgente=False,
        fallback=True,
        motivo_fallback=MOTIVO_TETO_DE_GASTO,
    )


def _tags_com_origem(resultado: ResultadoResumo) -> list[str]:
    """
    Marcador de origem gravado em `NewsItem.tags` (sem migration — ver a
    justificativa em `providers/fallback_local.py`).

    Quando o resumo veio do provedor externo, o item NAO recebe marcador
    nenhum (a pipeline nunca populou `NewsItem.tags` ate aqui, e segue assim):
    a AUSENCIA do marcador e, portanto, o sinal de "resumo do provedor", o
    que mantem o caminho feliz byte-identico ao comportamento anterior a esta
    intervencao.
    """
    if not getattr(resultado, "fallback", False):
        return []
    return marcadores_tags(resultado.motivo_fallback)


def _registrar_resultado_lote(resultados: list[ResultadoResumo]) -> None:
    """
    Emite a metrica rotulada (`sucesso`/`fallback` + motivo) do LOTE.

    Um lote pode misturar itens com resumo do provedor e itens que caíram no
    fallback (ex.: `resumir_e_classificar_em_lote` levantou e o lote inteiro
    virou fallback local), por isso os dois rotulos sao emitidos separadamente,
    com a contagem de cada um.

    `ResultadoResumo.motivo_fallback` e a fonte da verdade do rotulo quando
    `fallback=True` — setado no momento em que o resultado e construido, sem
    rederivacao (nada e rotulado "conteudo_insuficiente" so por ter resumo
    vazio: o fail-safe de custo tambem produz resumo vazio, com o rotulo
    `teto_de_gasto`).
    """
    if not resultados:
        return
    com_resumo_do_provedor = [r for r in resultados if not getattr(r, "fallback", False)]
    em_fallback = [r for r in resultados if getattr(r, "fallback", False)]
    if com_resumo_do_provedor:
        telemetria_resumo.registrar_sucesso(len(com_resumo_do_provedor))
    contagem_por_motivo: dict[str, int] = {}
    for resultado in em_fallback:
        motivo = normalizar_motivo(resultado.motivo_fallback)
        contagem_por_motivo[motivo] = contagem_por_motivo.get(motivo, 0) + 1
    for motivo, quantidade in contagem_por_motivo.items():
        telemetria_resumo.registrar_fallback(motivo, quantidade)


@cache_por_execucao()
@limites.coletar_falhas()
def executar_ingestao(
    fontes: Optional[list[NewsSourceProvider]] = None,
    summarization_provider: Optional[SummarizationProvider] = None,
) -> RegistroExecucaoIngestao:
    """
    Executa uma rodada completa do pipeline de ingestao. `fontes` e
    `summarization_provider` sao injetaveis (usados pelos testes com
    mocks, sem rede real); em producao, a task Celery
    (`tasks.ingerir_noticias`) chama sem argumentos, usando a configuracao
    corrente de `settings`.

    P1-01: a execucao e ISOLADA em dois niveis — por item (um item com campo
    fora do limite e descartado e registrado, o restante do grupo entra) e por
    grupo (um grupo que falha nao impede os demais de serem tentados). O fim
    da rodada reporta o placar de sucesso/falha. Nenhuma falha e engolida: toda
    uma passa por `limites.registrar_falha` (log de ERROR com traceback e
    contexto de fonte/item/motivo) e pelo `erros_por_fonte` do
    `RegistroExecucaoIngestao`.
    """
    fontes = fontes if fontes is not None else construir_fontes_configuradas()
    summarization_provider = summarization_provider or LLMHttpSummarizationProvider()

    itens_por_fonte: dict[str, int] = {}
    erros_por_fonte: dict[str, str] = {}
    todos_itens_brutos: list[ItemBruto] = []
    fontes_para_confirmar: list[NewsSourceProvider] = []

    # Busca das fontes em paralelo (80+ fontes regionais): sequencial com
    # timeout de 15s por fonte estouraria a janela do beat. Cada provider é
    # independente e os erros já são isolados por fonte (criterio de aceite 1)
    # — a ordem de `fontes` é preservada na coleta para determinismo.
    def _buscar(fonte):
        nome = getattr(fonte, "nome_fonte", None) or getattr(fonte, "nome", None) or fonte.__class__.__name__
        try:
            return (fonte, nome, fonte.buscar_itens(), None)
        except FonteIndisponivelError as exc:
            return (fonte, nome, [], str(exc))
        except Exception as exc:  # noqa: BLE001 — erro inesperado de UMA fonte nao pode derrubar as demais
            logger.exception("Erro inesperado ao buscar itens da fonte '%s'", nome)
            return (fonte, nome, [], f"Erro inesperado: {exc}")

    try:
        workers = int(getattr(settings, "CATALOGO_NOTICIAS_FETCH_WORKERS", 8))
    except Exception:
        workers = 8
    workers = max(1, min(workers, 16))
    from concurrent.futures import ThreadPoolExecutor

    urls_vistas_no_lote: set[str] = set()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for fonte, nome_fonte, itens, erro in pool.map(_buscar, fontes):
            if erro is not None:
                # Criterio de aceite 1: falha de UMA fonte nao propaga como
                # excecao fatal — registrada (log + RegistroExecucaoIngestao)
                # e seguimos para as proximas fontes.
                logger.error("Fonte '%s' indisponivel nesta execucao: %s", nome_fonte, erro)
                erros_por_fonte[nome_fonte] = erro
                itens_por_fonte[nome_fonte] = 0
                invalidar = getattr(fonte, "invalidar_validadores_apos_erro", None)
                if callable(invalidar):
                    try:
                        invalidar()
                    except Exception:
                        logger.warning(
                            "Falha ao invalidar validators após erro da fonte '%s'",
                            nome_fonte,
                            exc_info=True,
                        )
                continue

            # O provider só confirma os validators depois de todo o pipeline
            # persistir os itens; se a execução cair antes, a próxima rodada
            # baixa o XML novamente em vez de perder o lote por um 304.
            fontes_para_confirmar.append(fonte)

            # Idempotencia da task periodica: nao reprocessa um item cuja URL ja
            # foi ingerida em execucao anterior (evita violar a constraint de
            # unicidade de url_fonte_original a cada novo ciclo do mesmo feed).
            # Finding 5 (minor, performance): uma unica query por fonte
            # (`_urls_ja_ingeridas`) em vez de um SELECT EXISTS por item bruto.
            itens_unicos_da_fonte = _deduplicar_itens_por_url(itens)
            urls_ja_ingeridas = _urls_ja_ingeridas(itens_unicos_da_fonte)
            itens_novos = []
            for item in itens_unicos_da_fonte:
                if item.url_fonte_original in urls_ja_ingeridas:
                    continue
                if item.url_fonte_original in urls_vistas_no_lote:
                    continue
                urls_vistas_no_lote.add(item.url_fonte_original)
                itens_novos.append(item)
            itens_por_fonte[nome_fonte] = len(itens_novos)
            todos_itens_brutos.extend(itens_novos)

    # Finding 3 (code-review-contract.md run 20260902-0727-ingestao-noticias,
    # major): alem dos itens NOVOS deste lote, tambem trazemos os `NewsItem`
    # ja persistidos numa janela recente (`_itens_recentes_persistidos`) para
    # DENTRO do mesmo agrupamento — assim `agrupar_itens_brutos` pode
    # detectar que um item novo cobre o MESMO acontecimento que algo ja
    # ingerido numa execucao anterior, nao so entre itens do lote atual.
    itens_recentes_persistidos, news_items_persistidos_por_url = _itens_recentes_persistidos()
    itens_para_agrupar = todos_itens_brutos + itens_recentes_persistidos

    from .config_robo import cfg_valor as _cv2
    grupos = agrupar_itens_brutos(
        itens_para_agrupar, limiar_similaridade=float(_cv2("CATALOGO_NOTICIAS_DEDUP_LIMIAR_SIMILARIDADE", "dedup_limiar_similaridade", float))
    )

    chamadas_summarization = 0
    tokens_utilizados_total = 0
    custo_total = 0.0
    algum_custo_conhecido = False
    total_grupos = 0

    # Finding 1 (code-review-contract.md run 20260902-0727-ingestao-noticias,
    # 3a passada, major): o `SummarizationProvider` e chamado com cada item
    # de forma INDEPENDENTE (nunca um resumo combinado compartilhado por
    # varios itens de um grupo/cluster) — isso elimina estruturalmente o
    # risco de um `resumo_proprio` ser atribuido a uma fonte que noticiou um
    # fato diferente, mesmo que o algoritmo de deduplicacao (heuristica, nao
    # garantia) erre e agrupe itens de fatos diferentes no mesmo
    # `NewsCluster`.
    #
    # Reducao de custo/numero de chamadas (pedido do usuario apos configurar
    # uma chave real de LLM): em vez de 1 chamada HTTP por item, os itens
    # NOVOS de TODOS os grupos desta execucao sao juntados numa lista unica
    # e resumidos em LOTES de `CATALOGO_NOTICIAS_LLM_TAMANHO_LOTE` itens por
    # chamada (`SummarizationProvider.resumir_e_classificar_em_lote`) — a
    # garantia acima (cada item so pode receber o SEU PROPRIO resumo) e
    # preservada porque `resumir_e_classificar_em_lote` devolve uma lista
    # posicionalmente correspondente a entrada, e o codigo abaixo confere
    # explicitamente esse tamanho antes de usar qualquer resultado (ver
    # comentario no loop de lotes). Agrupar por grupo (cluster) continua
    # decidindo isso so DEPOIS, na fase de persistencia — o lote em si pode
    # (e normalmente vai) misturar itens de VARIOS grupos diferentes, o que
    # e seguro porque cada resultado so e usado para o item que o gerou.
    grupos_processados: list[tuple[list[ItemBruto], list[NewsItem]]] = []
    todos_itens_novos: list[ItemBruto] = []

    for grupo in grupos:
        itens_novos_do_grupo = [
            item for item in grupo if item.url_fonte_original not in news_items_persistidos_por_url
        ]
        if not itens_novos_do_grupo:
            # Grupo formado inteiramente por itens JA persistidos (nenhum
            # item novo desta execucao se juntou a ele) — nao ha trabalho
            # novo a fazer (nao re-resumimos/re-persistimos cobertura ja
            # processada em execucoes anteriores).
            continue

        news_items_existentes_do_grupo = [
            news_items_persistidos_por_url[item.url_fonte_original]
            for item in grupo
            if item.url_fonte_original in news_items_persistidos_por_url
        ]

        total_grupos += 1
        grupos_processados.append((itens_novos_do_grupo, news_items_existentes_do_grupo))
        todos_itens_novos.extend(itens_novos_do_grupo)

    # O registro passa a existir antes de qualquer chamada ao provider. Isso
    # transforma a última linha em uma reserva durável de custo: se o worker
    # cair depois da resposta do LLM e antes de `_persistir_grupo`, a reserva
    # continua no cálculo do teto/painel em vez de desaparecer com o processo.
    registro = RegistroExecucaoIngestao.objects.create(
        itens_por_fonte=dict(itens_por_fonte),
        erros_por_fonte=dict(erros_por_fonte),
        total_itens_ingeridos=sum(itens_por_fonte.values()),
        total_grupos_formados=total_grupos,
        total_duplicatas_agrupadas=max(sum(itens_por_fonte.values()) - total_grupos, 0),
    )
    resultado_por_url: dict[str, ResultadoResumo] = {}
    from .config_robo import cfg_valor as _cv3
    tamanho_lote = max(1, int(_cv3("CATALOGO_NOTICIAS_LLM_TAMANHO_LOTE", "llm_tamanho_lote", int)))
    # Enforcement do teto diario de gasto (implementation-contract.md, run
    # 20260903-1211-teto-gasto-diario-llm, criterios de aceite 1-3): o registro
    # desta execução já é persistido, portanto `gasto_llm_hoje_usd()` inclui
    # as reservas das chamadas anteriores. Uma nova reserva é feita somente
    # depois de decidir que ainda há orçamento; se a worker cair, a reserva
    # permanece e conta na próxima tentativa.
    teto_ja_excedido_nesta_execucao = False
    for inicio in range(0, len(todos_itens_novos), tamanho_lote):
        lote = todos_itens_novos[inicio : inicio + tamanho_lote]
        custo_reservado_lote = 0.0

        if not teto_ja_excedido_nesta_execucao:
            gasto_atual = orcamento.gasto_llm_hoje_usd()
            custo_reservado_lote = _estimar_custo_chamada(
                summarization_provider, len(lote)
            )
            if orcamento.teto_excedido(
                gasto_atual
            ) or (
                custo_reservado_lote > 0
                and orcamento.teto_excedido(gasto_atual + custo_reservado_lote)
            ):
                teto_ja_excedido_nesta_execucao = True
                logger.warning(
                    "Teto diario de gasto do SummarizationProvider seria atingido "
                    "pela reserva desta chamada (%.4f USD; gasto atual %.4f USD) "
                    "— pulando o restante para revisao humana.",
                    custo_reservado_lote,
                    gasto_atual,
                )

        if teto_ja_excedido_nesta_execucao:
            # Fail-safe de CUSTO (nao de erro do provedor) — ver
            # `_resultado_sem_resumo_por_teto`: o provedor NAO e chamado e o
            # item segue para revisao humana (AC-2/AC-3 de
            # run 20260903-1211-teto-gasto-diario-llm, inalterado). A novelty
            # do P1-02 aqui e so a distinguish: rotulo `teto_de_gasto` na
            # metrica, no log e no marcador persistido.
            resultados_lote = [_resultado_sem_resumo_por_teto(item) for item in lote]
            _registrar_resultado_lote(resultados_lote)
            for item_bruto, resultado_item in zip(lote, resultados_lote):
                resultado_por_url[item_bruto.url_fonte_original] = resultado_item
            continue

        # A reserva é gravada ANTES da chamada externa. Se o worker cair
        # depois da resposta, o custo anterior não desaparece e o orçamento
        # seguinte o inclui.
        chamadas_summarization += 1
        custo_total += custo_reservado_lote
        if custo_reservado_lote > 0:
            algum_custo_conhecido = True
        _atualizar_metricas_execucao(
            registro,
            chamadas=chamadas_summarization,
            tokens=tokens_utilizados_total,
            custo=custo_total if algum_custo_conhecido else 0.0,
        )

        # Se a chamada levantar `SummarizationProviderError`, `resultados_lote`
        # vira fallback local e o motivo viaja em cada `ResultadoResumo`. A
        # metrica e emitida em UM UNICO ponto (logo abaixo do calculo de
        # custo), para nunca contar o mesmo lote duas vezes.
        try:
            resultados_lote = summarization_provider.resumir_e_classificar_em_lote(lote)
            if len(resultados_lote) != len(lote):
                # Nunca confiamos num `zip` desalinhado (arriscaria atribuir
                # o resumo de um item a OUTRO item do lote) — um provider
                # que devolve o numero errado de resultados descarta o LOTE
                # INTEIRO para revisao humana, nao tenta adivinhar o
                # alinhamento correto.
                raise SummarizationProviderError(
                    f"resumir_e_classificar_em_lote devolveu {len(resultados_lote)} "
                    f"resultado(s) para {len(lote)} item(ns) — descartando o lote "
                    "inteiro (revisao humana) em vez de arriscar atribuir um resumo "
                    "ao item errado.",
                    motivo=MOTIVO_ERRO_DO_PROVIDER,
                )
        except SummarizationProviderError as exc:
            # P1-02: o motivo vem do proprio provider quando ele sabe dizer
            # (`summarization.py` classifica timeout/rate_limit/erro_http/
            # resposta_invalida/sem_credencial); `erro_do_provider` cobre um
            # provider de terceiro que levanta a excecao sem motivo. O log
            # leva o motivo e o TIPO da excecao, nunca o valor da credencial
            # nem o corpo da resposta do provedor.
            motivo_do_lote = (
                getattr(exc, "motivo", "") or MOTIVO_ERRO_DO_PROVIDER
            )
            logger.error(
                "SummarizationProvider falhou para um lote de %d item(ns) — "
                "motivo=%s erro=%s: %s. Publicando pelo fallback local.",
                len(lote),
                motivo_do_lote,
                type(exc).__name__,
                exc,
            )
            # A reserva permanece: a chamada foi tentada e pode ter gerado
            # cobrança mesmo sem resposta utilizável.
            # P1-02 vence AQUI: o item do fallback recebe conteudo local
            # deterministico e MARCADO, em vez de `resumo=""` (que produzia
            # `status_revisao=pendente` -> noticia INVISIVEL no feed, o
            # "rascunho fantasma"). O motivo viaja em cada
            # `ResultadoResumo` para metrica, log e marcador de origem.
            resultados_lote = [
                _resultado_fallback_local(item, motivo_do_lote) for item in lote
            ]
        except Exception as exc:  # noqa: BLE001 — provider inesperado não derruba a rodada
            # ISOLAMENTO POR ITEM (P1-01). Ate aqui so `SummarizationProviderError`
            # era tratado: um `RuntimeError`/bug/timeout inesperado dentro do
            # provider derrubava `executar_ingestao` e TODOS os itens dos outros
            # grupos. Agora o lote em lote cai para item a item: cada item e
            # resumido isoladamente e so o item que realmente falha vira fallback.
            #
            # A excecao NAO e engolida: registrada com traceback e com fonte +
            # identificador do item, e entra no placar de falhas da rodada.
            #
            # COEXISTENCIA (P1-01 x P1-02): este `except` largo e do P1-01 e
            # NAO substitui o `except SummarizationProviderError` acima, que
            # continua acima e portanto continua classificando o motivo com
            # precisao. Aqui nao ha motivo classificado (a excecao e
            # inesperada), logo o fallback local do item que falhar recebe
            # `erro_do_provider` — o umbrella honesto, e nao um rotulo livre.
            limites.registrar_falha(
                f"Falha inesperada do SummarizationProvider no lote de {len(lote)} "
                f"item(ns); refazendo item a item: {exc.__class__.__name__}: {exc}",
                nome_fonte=", ".join(sorted({i.nome_fonte for i in lote})) or "(desconhecida)",
                identificador=f"{len(lote)} item(ns) do lote de sumarizacao",
                escopo="sumarizacao_lote",
                exc=exc,
            )
            resultados_lote = []
            for item_bruto_do_lote in lote:
                try:
                    resultado_individual = summarization_provider.resumir_e_classificar(
                        [item_bruto_do_lote]
                    )
                except Exception as exc_item:  # noqa: BLE001 — um item não derruba os demais
                    limites.registrar_falha(
                        limites.mensagem_para_erro(
                            exc_item,
                            nome_fonte=item_bruto_do_lote.nome_fonte,
                            identificador=item_bruto_do_lote.url_fonte_original,
                        ),
                        nome_fonte=item_bruto_do_lote.nome_fonte,
                        identificador=item_bruto_do_lote.url_fonte_original,
                        escopo="sumarizacao_item",
                        exc=exc_item,
                    )
                    # P1-02: mesmo caminho do lote, com o motivo que o item
                    # conseguiu classificar (ou `erro_do_provider`).
                    motivo_individual = (
                        getattr(exc_item, "motivo", "") or MOTIVO_ERRO_DO_PROVIDER
                    )
                    resultado_individual = _resultado_fallback_local(
                        item_bruto_do_lote, motivo_individual
                    )
                resultados_lote.append(resultado_individual)

        custo_real_lote = 0.0
        custos_conhecidos: list[float] = []
        for resultado_item in resultados_lote:
            if resultado_item.tokens_utilizados:
                tokens_utilizados_total += resultado_item.tokens_utilizados
            if resultado_item.custo_estimado_usd is not None:
                custos_conhecidos.append(resultado_item.custo_estimado_usd)
        custo_real_conhecido = bool(custos_conhecidos) and len(
            custos_conhecidos
        ) == len(resultados_lote)
        custo_real_lote = sum(custos_conhecidos)

        if custo_real_conhecido:
            # Se o provider devolve uso, substitui a estimativa conservativa
            # pela medição. Sem uso conhecido, mantemos a reserva para não
            # subnotificar uma cobrança cujo response não voltou.
            custo_total += custo_real_lote - custo_reservado_lote
            algum_custo_conhecido = True

        # P1-02: fecha o ciclo de observabilidade do LOTE, em ponto UNICO.
        # Caminho feliz -> `resultado=sucesso`. Lote que caiu na excecao acima
        # -> `resultado=fallback` com o motivo que o provider informou. Itens
        # cujo id veio invalido do provider (resumo vazio, mas `fallback=False`)
        # sao contabilizados como `sucesso` e forcam revisao humana em
        # `_persistir_grupo` pelo caminho ja existente — comportamento
        # inalterado, apenas agora visivel na metrica.
        _registrar_resultado_lote(resultados_lote)

        _atualizar_metricas_execucao(
            registro,
            chamadas=chamadas_summarization,
            tokens=tokens_utilizados_total,
            custo=custo_total if algum_custo_conhecido else 0.0,
        )
        for item_bruto, resultado_item in zip(lote, resultados_lote):
            resultado_por_url[item_bruto.url_fonte_original] = resultado_item

    # ISOLAMENTO POR GRUPO (P1-01): cada grupo e persistido dentro do seu
    # proprio `try`. Antes, um unico grupo com problema (campo grande demais,
    # erro inesperado) derrubava `executar_ingestao` e TODOS os grupos
    # restantes nunca eram tentados — a falha de um nao pode abortar os outros.
    # A excecao nao e engolida: e registrada com traceback + contexto e
    # entra no placar de falhas da execucao.
    grupos_com_erro = 0
    itens_ingeridos_nesta_execucao = 0
    # Fontes cujo grupo NAO foi persistido. Servem para nao confirmar os
    # validators HTTP dessas fontes no fim da rodada (ver o laco de
    # `confirmar_validadores`): sem isso, a proxima rodada receberia um 304 e
    # os itens perdidos nunca mais seriam baixados.
    fontes_com_persistencia_falha: set[str] = set()
    for indice_grupo, (
        itens_novos_do_grupo,
        news_items_existentes_do_grupo,
    ) in enumerate(grupos_processados):
        try:
            resultados_por_item: list[tuple[ItemBruto, ResultadoResumo]] = [
                (item_bruto, resultado_por_url[item_bruto.url_fonte_original])
                for item_bruto in itens_novos_do_grupo
            ]

            if news_items_existentes_do_grupo:
                _cluster, itens_criados = _persistir_grupo_mesclado(
                    resultados_por_item, news_items_existentes_do_grupo
                )
            else:
                _cluster, itens_criados = _persistir_grupo(resultados_por_item)
            # Contagem de sucesso observada do proprio `bulk_create`: um item
            # so tem `pk` se realmente entrou. Nao e um `NewsItem.objects.count()`
            # no fim (que contaria o acervo inteiro, nem o que esta rodada fez)
            # nem um `IN` com todos os PKs (que cresceria com o lote sem teto).
            itens_ingeridos_nesta_execucao += sum(1 for i in itens_criados if i.pk)
        except Exception as exc:  # noqa: BLE001 — um grupo ruim não aborta os demais
            grupos_com_erro += 1
            fontes_do_grupo = sorted({item.nome_fonte for item in itens_novos_do_grupo})
            fontes_com_persistencia_falha.update(fontes_do_grupo)
            chave_erro = f"grupo#{indice_grupo} [{', '.join(fontes_do_grupo) or 'sem fonte'}]"
            mensagem = (
                f"Grupo {indice_grupo + 1}/{len(grupos_processados)} da execucao "
                f"({', '.join(fontes_do_grupo) or 'sem fonte'}) nao foi persistido: "
                f"{exc.__class__.__name__}: {exc}"
            )
            limites.registrar_falha(
                mensagem,
                nome_fonte=", ".join(fontes_do_grupo) or "(desconhecida)",
                identificador=chave_erro,
                escopo="persistencia_grupo",
                exc=exc,
            )
            # O registro da execucao (JSONField `erros_por_fonte`, ja exposto no
            # admin e na API) ganha a entrada do grupo, para que a falha seja
            # consultavel depois e nao exista so no log.
            erros_por_fonte[chave_erro] = f"{exc.__class__.__name__}: {exc}"

    # As falhas de ITEM (recusadas na construcao, em camadas profundas que
    # nao devolvem lista de erros) entram tambem no registro da execucao, para
    # que o `RegistroExecucaoIngestao` seja a trilha de auditoria completa da
    # rodada e nao apenas do log. A chave e truncada de proposito: a coluna e
    # um `JSONField` e o identificador completo (ate 1.000 chars de URL) nao
    # acrescenta informacao util aqui — o motivo completo esta no log de ERROR.
    for falha in limites.falhas_da_execucao():
        if falha["escopo"].endswith("grupo") or falha["escopo"] == "persistencia_em_lote":
            continue  # ja_entries com chave propria acima / sao do lote inteiro
        chave_item = f"item::{falha['escopo']}::{falha['fonte']}::{falha['item'][:120]}"
        erros_por_fonte[chave_item] = falha["motivo"]

    total_itens = sum(itens_por_fonte.values())

    registro.itens_por_fonte = dict(itens_por_fonte)
    registro.erros_por_fonte = dict(erros_por_fonte)
    registro.total_itens_ingeridos = total_itens
    registro.total_grupos_formados = total_grupos
    registro.total_duplicatas_agrupadas = max(total_itens - total_grupos, 0)
    registro.chamadas_summarization_provider = chamadas_summarization
    registro.tokens_utilizados_summarization = tokens_utilizados_total or None
    registro.custo_estimado_summarization_usd = (
        custo_total if algum_custo_conhecido else None
    )
    registro.save(
        update_fields=[
            "itens_por_fonte",
            "erros_por_fonte",
            "total_itens_ingeridos",
            "total_grupos_formados",
            "total_duplicatas_agrupadas",
            "chamadas_summarization_provider",
            "tokens_utilizados_summarization",
            "custo_estimado_summarization_usd",
        ]
    )

    # Só agora, depois de todos os NewsItems e do RegistroExecucao estarem
    # confirmados, o cache HTTP pode avançar. Uma queda antes deste ponto
    # deixa os validators antigos e força nova leitura, sem perda de itens.
    #
    # P1-01: o isolamento por grupo NAO pode comer essa garantia. Se o grupo de
    # uma fonte nao foi persistido, os itens dela podem ter sido perdidos em
    # silencio; confirmar o ETag faria a proxima rodada receber um 304 e esses
    # itens nunca mais seriam baixados. Entao a confirmacao e pulada para as
    # fontes afetadas — o ETag anterior delas expira naturalmente, forcando
    # nova leitura completa na proxima rodada.
    #
    # Item RECUSADO por limite de campo NAO entra nesta lista: a recusa e
    # deterministica e permanente (a mesma URL gigante voltaria a ser recusada
    # em toda rodada), entao nao ha item a perder e re-baixar o feed a cada 15
    # minutos seria desperdicio puro. O que nao pode acontecer e um erro
    # TRANSITORIO virar perda definitiva — e erro transitorio cai no caso do
    # grupo acima.
    for fonte in fontes_para_confirmar:
        nome_fonte = getattr(fonte, "nome_fonte", getattr(fonte, "nome", "desconhecida"))
        if nome_fonte in fontes_com_persistencia_falha:
            logger.warning(
                "Validator HTTP da fonte '%s' NAO sera confirmado nesta execucao: "
                "o grupo dessa fonte nao foi persistido (%d falha(s) de persistencia). "
                "A proxima rodada baixa o XML de novo em vez de aceitar um 304 que "
                "faria os itens perdidos nunca mais voltarem.",
                nome_fonte,
                grupos_com_erro,
            )
            continue
        confirmar = getattr(fonte, "confirmar_validadores", None)
        if callable(confirmar):
            try:
                confirmar()
            except Exception:
                logger.warning(
                    "Falha ao confirmar validators HTTP da fonte %s",
                    nome_fonte,
                    exc_info=True,
                )

    # PLACAR DE SUCESSO/FALHA (P1-01). Duas contagens distintas, que nao devem
    # ser confundidas:
    #
    #   itens_candidatos  — quantos itens NOVOS o lote trouxe (ja deduplicados
    #                       por URL). E o "o que a rodada tentou fazer".
    #   itens_ingeridos   — quantos desses realmente ganharam `pk` no banco.
    #
    # A diferenca entre as duas e o que o operador precisa ver: e a quantidade
    # de itens que o pipeline isolou e recusou (campo fora do limite, `DataError`
    # linha a linha, corrida de unicidade). `itens_por_fonte` sozinho nao
    # responde isso — ele conta candidatos, nao sucesso.
    itens_candidatos = total_itens
    itens_ingeridos = itens_ingeridos_nesta_execucao
    falhas_isoladas = limites.falhas_da_execucao()
    itens_recusados = max(itens_candidatos - itens_ingeridos, 0)

    logger.info(
        "Ingestao concluida: %d itens novos, %d grupos, %d chamadas ao SummarizationProvider, "
        "%d fonte(s) com erro. registro_id=%s",
        total_itens,
        total_grupos,
        chamadas_summarization,
        len(erros_por_fonte),
        registro.id,
    )
    logger.info(
        "Placar de ingestao: %d candidato(s), %d INGIRIDO(S), %d recusado(s)/isolado(s) "
        "em %d falha(s) registrada(s); %d grupo(s) com erro de %d processado(s). registro_id=%s",
        itens_candidatos,
        itens_ingeridos,
        itens_recusados,
        len(falhas_isoladas),
        grupos_com_erro,
        len(grupos_processados),
        registro.id,
    )
    if falhas_isoladas:
        # Uma linha por falha, com escopo (item/grupo), fonte e motivo: o
        # placar e legivel no log, sem precisar abrir traceback por item.
        for falha in falhas_isoladas:
            logger.warning(
                "Placar de ingestao — falha isolada: escopo=%s fonte=%s item=%s motivo=%s",
                falha["escopo"],
                falha["fonte"],
                falha["item"],
                falha["motivo"],
            )

    return registro
