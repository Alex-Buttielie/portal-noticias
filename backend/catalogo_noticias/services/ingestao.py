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
from django.db import transaction
from django.utils import timezone

from ..models import NewsCluster, NewsItem, RegistroExecucaoIngestao
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
from . import orcamento
from .deduplicacao import agrupar_itens_brutos

logger = logging.getLogger(__name__)


def construir_fontes_configuradas() -> list[NewsSourceProvider]:
    """
    Constroi as `NewsSourceProvider` a partir de
    `settings.CATALOGO_NOTICIAS_FONTES_RSS` — a lista de fontes-semente vive
    em configuracao (config/settings.py), nao hardcoded na logica de
    negocio (implementation-contract.md, "Areas/arquivos esperados").
    """
    return [
        RSSNewsSourceProvider(nome_fonte=fonte["nome"], url_feed=fonte["url"])
        for fonte in settings.CATALOGO_NOTICIAS_FONTES_RSS
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
    janela_horas = settings.CATALOGO_NOTICIAS_DEDUP_JANELA_RECENTE_HORAS
    limite_itens = settings.CATALOGO_NOTICIAS_DEDUP_MAX_ITENS_RECENTES
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

    limiar_similaridade_total = settings.CATALOGO_NOTICIAS_RESUMO_SIMILARIDADE_MAXIMA
    limiar_trecho_copiado = settings.CATALOGO_NOTICIAS_RESUMO_TRECHO_COPIADO_MAXIMO
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
    categorias_sensiveis = {c.strip().lower() for c in settings.CATALOGO_NOTICIAS_CATEGORIAS_SENSIVEIS}
    limiar_fontes = settings.CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA
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
        primeira_categoria = (resultados_por_item[0][1].categoria or grupo[0].categoria or "").strip().lower()
        cluster = NewsCluster.objects.create(
            titulo_acontecimento=grupo[0].titulo,
            categoria_dominante=primeira_categoria,
        )

    itens_criados = []
    for item_bruto, resultado in resultados_por_item:
        categoria_item = (resultado.categoria or item_bruto.categoria or "").strip().lower()

        # Sem resumo confiavel (ex.: SummarizationProvider falhou e caiu no
        # fallback de erro, OU devolveu um resumo vazio), o item NUNCA e
        # publicado automaticamente, independente do criterio de
        # categoria/fontes — forcamos revisao humana (implementation-contract.md,
        # criterio de aceite 4: nunca publicar sem resumo proprio real).
        sem_resumo_confiavel = not (resultado.resumo or "").strip()
        # Finding 1 (code-review-contract.md run 20260902-0727-ingestao-noticias,
        # 1a passada, blocker — BRD secao 18): mesmo com um resumo NAO vazio, se
        # ele acabou identico ou quase identico ao conteudo_bruto DESTE item
        # (provider "copiando" a fonte), tambem forcamos revisao humana em vez
        # de publicar automaticamente.
        resumo_suspeito_de_copia = not sem_resumo_confiavel and _resumo_e_copia_ou_quase_copia(
            resultado.resumo, [item_bruto]
        )
        alta_relevancia = (
            sem_resumo_confiavel
            or resumo_suspeito_de_copia
            or _eh_alta_relevancia(categoria_item, numero_fontes_distintas)
        )
        status_revisao = NewsItem.STATUS_PENDENTE if alta_relevancia else NewsItem.STATUS_NAO_APLICAVEL

        news_item = NewsItem.objects.create(
            titulo=item_bruto.titulo,
            resumo_proprio=resultado.resumo,
            conteudo_bruto=item_bruto.conteudo_bruto,
            url_fonte_original=item_bruto.url_fonte_original,
            nome_fonte=item_bruto.nome_fonte,
            categoria=categoria_item,
            timestamp_publicacao_fonte=item_bruto.timestamp_publicacao_fonte,
            urgente=resultado.urgente,
            status_revisao=status_revisao,
            cluster=cluster,
        )
        itens_criados.append(news_item)

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
        cluster = NewsCluster.objects.create(
            titulo_acontecimento=item_existente_mais_antigo.titulo,
            categoria_dominante=item_existente_mais_antigo.categoria or resultados_por_item[0][1].categoria or "",
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
        cluster.save(update_fields=["categoria_dominante"])

    # Finding 1 (3a passada): cada item novo tem seu PROPRIO
    # `resumo_proprio`, gerado individualmente por `executar_ingestao` (nunca
    # mais um resultado compartilhado por todos os itens novos do grupo) —
    # elimina o risco estrutural de misattribution de CONTEUDO mesmo quando
    # a decisao de agrupamento em si estiver errada.
    itens_criados = []
    for item_bruto, resultado in resultados_por_item:
        categoria_item = (resultado.categoria or item_bruto.categoria or categoria_grupo or "").strip().lower()
        sem_resumo_confiavel = not (resultado.resumo or "").strip()
        resumo_suspeito_de_copia = not sem_resumo_confiavel and _resumo_e_copia_ou_quase_copia(
            resultado.resumo, [item_bruto]
        )
        status_revisao_item = (
            NewsItem.STATUS_PENDENTE
            if (sem_resumo_confiavel or resumo_suspeito_de_copia)
            else NewsItem.STATUS_NAO_APLICAVEL
        )
        news_item = NewsItem.objects.create(
            titulo=item_bruto.titulo,
            resumo_proprio=resultado.resumo,
            conteudo_bruto=item_bruto.conteudo_bruto,
            url_fonte_original=item_bruto.url_fonte_original,
            nome_fonte=item_bruto.nome_fonte,
            categoria=categoria_item,
            timestamp_publicacao_fonte=item_bruto.timestamp_publicacao_fonte,
            urgente=resultado.urgente,
            status_revisao=status_revisao_item,
            cluster=cluster,
        )
        itens_criados.append(news_item)

    # Reavalia o cluster INTEIRO (itens antigos + novos) contra o criterio de
    # alta relevancia agora que cresceu — sem isso, um cluster que so cruza o
    # limiar de fontes tardiamente (itens antigos + novos, nao so os desta
    # execucao) nunca aciona revisao humana para os itens antigos ja
    # publicados automaticamente (o proprio problema que o Finding 3 aponta).
    # Comportamento preservado da 2a passada — ver nota sobre AC-7 acima de
    # `_persistir_grupo` para o porque este criterio NAO virou incondicional.
    numero_fontes_distintas = cluster.numero_fontes_distintas
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
            news_item.refresh_from_db(fields=["status_revisao"])

    return cluster, itens_criados


def _resultado_fallback_erro(grupo: list[ItemBruto]) -> ResultadoResumo:
    """
    Usado quando o `SummarizationProvider` falha para um grupo — em vez de
    propagar a excecao e perder os itens da execucao inteira, registramos
    resumo vazio (o que forca `status_revisao=pendente` em `_persistir_grupo`,
    nunca publicacao automatica) e seguimos para os proximos grupos.
    """
    return ResultadoResumo(resumo="", categoria=grupo[0].categoria, urgente=False)


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
    """
    fontes = fontes if fontes is not None else construir_fontes_configuradas()
    summarization_provider = summarization_provider or LLMHttpSummarizationProvider()

    itens_por_fonte: dict[str, int] = {}
    erros_por_fonte: dict[str, str] = {}
    todos_itens_brutos: list[ItemBruto] = []

    for fonte in fontes:
        nome_fonte = getattr(fonte, "nome_fonte", fonte.__class__.__name__)
        try:
            itens = fonte.buscar_itens()
        except FonteIndisponivelError as exc:
            # Criterio de aceite 1: falha de UMA fonte nao pode propagar
            # como excecao fatal da task inteira — registrada (log +
            # RegistroExecucaoIngestao.erros_por_fonte) e seguimos para as
            # proximas fontes.
            logger.error("Fonte '%s' indisponivel nesta execucao: %s", nome_fonte, exc)
            erros_por_fonte[nome_fonte] = str(exc)
            itens_por_fonte[nome_fonte] = 0
            continue
        except Exception as exc:  # noqa: BLE001 — erro inesperado de UMA fonte nao pode derrubar as demais
            logger.exception("Erro inesperado ao buscar itens da fonte '%s'", nome_fonte)
            erros_por_fonte[nome_fonte] = f"Erro inesperado: {exc}"
            itens_por_fonte[nome_fonte] = 0
            continue

        # Idempotencia da task periodica: nao reprocessa um item cuja URL ja
        # foi ingerida em execucao anterior (evita violar a constraint de
        # unicidade de url_fonte_original a cada novo ciclo do mesmo feed).
        # Finding 5 (minor, performance): uma unica query por fonte
        # (`_urls_ja_ingeridas`) em vez de um SELECT EXISTS por item bruto.
        urls_ja_ingeridas = _urls_ja_ingeridas(itens)
        itens_novos = [item for item in itens if item.url_fonte_original not in urls_ja_ingeridas]
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

    grupos = agrupar_itens_brutos(
        itens_para_agrupar, limiar_similaridade=settings.CATALOGO_NOTICIAS_DEDUP_LIMIAR_SIMILARIDADE
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

    resultado_por_url: dict[str, ResultadoResumo] = {}
    tamanho_lote = max(1, settings.CATALOGO_NOTICIAS_LLM_TAMANHO_LOTE)
    # Enforcement do teto diario de gasto (implementation-contract.md, run
    # 20260903-1211-teto-gasto-diario-llm, criterios de aceite 1-3): uma vez
    # que o gasto acumulado (execucoes anteriores do dia, via
    # `orcamento.gasto_llm_hoje_usd()`, + `custo_total` ja acumulado NESTA
    # execucao) cruza o teto, `teto_ja_excedido_nesta_execucao` fica `True`
    # pelo resto do loop — os lotes restantes NUNCA mais chamam o provedor
    # (mesmo tratamento de `_resultado_fallback_erro` ja usado para falha de
    # rede/parsing, sem incrementar `chamadas_summarization`: nenhuma
    # chamada HTTP foi feita).
    teto_ja_excedido_nesta_execucao = False
    for inicio in range(0, len(todos_itens_novos), tamanho_lote):
        lote = todos_itens_novos[inicio : inicio + tamanho_lote]

        if not teto_ja_excedido_nesta_execucao:
            gasto_acumulado_usd = orcamento.gasto_llm_hoje_usd() + custo_total
            teto_ja_excedido_nesta_execucao = orcamento.teto_excedido(gasto_acumulado_usd)
            if teto_ja_excedido_nesta_execucao:
                itens_restantes = len(todos_itens_novos) - inicio
                logger.warning(
                    "Teto diario de gasto do SummarizationProvider (%.4f USD) atingido/excedido "
                    "(gasto acumulado do dia: %.4f USD) — pulando o restante desta execucao "
                    "(%d item(ns) restante(s), a partir deste lote) sem chamar o provedor; "
                    "itens vao para revisao humana (status_revisao=pendente).",
                    orcamento.teto_diario_usd(),
                    gasto_acumulado_usd,
                    itens_restantes,
                )

        if teto_ja_excedido_nesta_execucao:
            # Fail-safe de custo (nao de erro do provedor): mesmo fallback
            # ja usado para falha de rede/parsing (`_resultado_fallback_erro`)
            # — o item continua sendo ingerido, so sem resumo automatico
            # (forca status_revisao=pendente em `_persistir_grupo`).
            resultados_lote = [_resultado_fallback_erro([item]) for item in lote]
            for item_bruto, resultado_item in zip(lote, resultados_lote):
                resultado_por_url[item_bruto.url_fonte_original] = resultado_item
            continue

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
                    "ao item errado."
                )
        except SummarizationProviderError as exc:
            logger.error(
                "Falha do SummarizationProvider para um lote de %d item(ns): %s",
                len(lote),
                exc,
            )
            resultados_lote = [_resultado_fallback_erro([item]) for item in lote]

        chamadas_summarization += 1
        for item_bruto, resultado_item in zip(lote, resultados_lote):
            if resultado_item.tokens_utilizados:
                tokens_utilizados_total += resultado_item.tokens_utilizados
            if resultado_item.custo_estimado_usd is not None:
                custo_total += resultado_item.custo_estimado_usd
                algum_custo_conhecido = True
            resultado_por_url[item_bruto.url_fonte_original] = resultado_item

    for itens_novos_do_grupo, news_items_existentes_do_grupo in grupos_processados:
        resultados_por_item: list[tuple[ItemBruto, ResultadoResumo]] = [
            (item_bruto, resultado_por_url[item_bruto.url_fonte_original])
            for item_bruto in itens_novos_do_grupo
        ]

        if news_items_existentes_do_grupo:
            _persistir_grupo_mesclado(resultados_por_item, news_items_existentes_do_grupo)
        else:
            _persistir_grupo(resultados_por_item)

    total_itens = sum(itens_por_fonte.values())

    registro = RegistroExecucaoIngestao.objects.create(
        itens_por_fonte=itens_por_fonte,
        erros_por_fonte=erros_por_fonte,
        total_itens_ingeridos=total_itens,
        total_grupos_formados=total_grupos,
        total_duplicatas_agrupadas=max(total_itens - total_grupos, 0),
        chamadas_summarization_provider=chamadas_summarization,
        tokens_utilizados_summarization=tokens_utilizados_total or None,
        custo_estimado_summarization_usd=custo_total if algum_custo_conhecido else None,
    )

    logger.info(
        "Ingestao concluida: %d itens novos, %d grupos, %d chamadas ao SummarizationProvider, "
        "%d fonte(s) com erro. registro_id=%s",
        total_itens,
        total_grupos,
        chamadas_summarization,
        len(erros_por_fonte),
        registro.id,
    )

    return registro
