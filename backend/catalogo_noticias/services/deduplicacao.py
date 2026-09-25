"""
Agrupamento de `ItemBruto` que cobrem o MESMO acontecimento em clusters.
`NewsCluster` e criado por `services/ingestao.py` a partir do resultado
desta funcao — este modulo so decide O QUE agrupar, nao persiste nada no
banco (mantem a logica de agrupamento testavel isoladamente, sem banco).

Abordagem (revisada — code-review-contract.md run
20260902-0727-ingestao-noticias, Finding 2, major): a versao anterior usava
`max(jaccard, SequenceMatcher sobre tokens ordenados concatenados)`, que
gerava falsos positivos sistematicos para manchetes que compartilham o MESMO
padrao sintatico jornalistico mas descrevem fatos DIFERENTES (ex.:
"Prefeitura de Sao Paulo anuncia novo plano de seguranca publica" vs.
"...de mobilidade urbana" pontuava 0.789, acima do limiar default 0.55) — o
`reviewer` demonstrou que nao existe um unico limiar numerico capaz de
separar esses falsos positivos dos pares genuinos exigidos pelos testes
existentes usando aquele algoritmo (os intervalos de score se sobrepoem).

A nova abordagem identifica, a partir da propria distribuicao de frequencia
do LOTE sendo agrupado (nao uma lista fixa hardcoded de "palavras de
molde", o que seria fragil e nao generalizaria para vocabulario novo),
quais tokens se repetem em VARIOS itens do lote — sinal de linguagem
estrutural comum ("anuncia", "governo", "prefeitura", "novo", "pacote"...,
tipico de um lote real de RSS com varias fontes/noticias) — e da a esses
tokens um peso residual bem menor na hora de comparar dois titulos; tokens
especificos do acontecimento ("mobilidade", "homicidio", "fraude"), que
aparecem em poucos itens do lote, mantem peso pleno — e sao eles que
decidem se duas manchetes com a MESMA estrutura sao ou nao o MESMO fato
(ver `_pesos_por_frequencia_no_lote` para os limiares exatos, calibrados
para so entrar em vigor em lotes com itens suficientes para o sinal ser
estatisticamente confiavel). Pareamento de tokens e "fuzzy" (via
`difflib.SequenceMatcher` por token, limiar alto) para preservar a
robustez a variacao de genero/numero que a versao anterior ja tinha (ex.
"grande"/"grandes") sem depender de comparar as strings inteiras
concatenadas (a causa raiz dos falsos positivos do Finding 2).

Deliberadamente NAO usa `conteudo_bruto` como sinal de similaridade (uma das
opcoes sugeridas pelo `reviewer`): nos dublês de teste existentes (e,
plausivelmente, em muitos feeds RSS reais) o snippet/summary de itens
NAO relacionados pode ser genérico/repetido, o que tornaria esse sinal
pouco confiável sem uma normalização adicional fora do escopo deste
contrato — decisao de design registrada aqui, nao um esquecimento.

REABERTO (code-review-contract.md run 20260902-0727-ingestao-noticias, 2a
passada, Finding 1, major): o mecanismo dinamico acima so ativa em lotes
>= 6 itens com o padrao repetido >= 4 vezes — o reviewer reproduziu, de
forma independente, que em um lote pequeno e realista (4 itens, como um
ciclo de 15 min com as 4 fontes-semente do contrato) o falso-positivo
original volta a ocorrer, ja que o sinal dinamico nunca tem dados
suficientes para ativar. A correcao desta rodada complementa (nao
substitui) o mecanismo dinamico com uma pequena lista curada de conectores
jornalisticos comuns em portugues (`_CONECTORES_JORNALISTICOS_COMUNS_PT`)
que recebe peso reduzido INCONDICIONALMENTE, independente do tamanho do
lote — ver docstring de `_pesos_por_frequencia_no_lote` para os detalhes e
a calibracao que motivou excluir titulos de cargo individual
("presidente", "prefeito" etc.) dessa lista.

Ainda uma heuristica deliberadamente simples para o MVP — dedup
verdadeiramente semantica (ex.: embeddings via o proprio
`SummarizationProvider`) continua sendo um upgrade natural para uma execucao
futura; registrado como decisao tecnica em implementation-history.md.

OTIMIZACAO v2 (implementation-contract.md run
20260924-2136-ingestao-noticias, Versao 2 — comportamento-PRESERVANDO,
mesmos grupos de saida para qualquer entrada): com o lote combinado grande
(itens novos + persistidos recentes — um backlog de 3 dias x 91 fontes tem
milhares de itens), o pareamento fuzzy O(n^2) por par via SequenceMatcher
tornava uma rodada de ingestao LONGA DEMAIS (horas de CPU; o cache
`_CACHE_FUZZY_RATIO` se LIMPAVA inteiro a cada 8000 entradas e, em lote
grande, quase toda chamada era MISS e o SequenceMatcher rodava de novo).
Tres tecnicas aplicadas SEM mudar semantica de similaridade, limiares,
ponderacao ou agrupamento single-linkage (os testes de calibracao Finding
2/3 em `tests/test_acceptance_criteria.py` sao a regua):

1. Pre-filtro por limite SUPERIOR (upper bound) exato do score possivel por
   par (ver `_bound_similaridade`): pares cujo bound ja esta abaixo do
   limiar sao pulados SEM o pareamento fuzzy caro — o score real e
   garantidamente menor que o bound, entao a decisao de agrupamento e
   identica (criterio de aceite 9 do contrato v2);
2. Cache LRU real para o cache de ratio fuzzy (ver `_ratio_cached`):
   `functools.lru_cache` com capacidade fixa substitui o clear-total —
   mesmos valores, retencao melhor, sem thrash;
3. Pre-calculo por item dos pesos ordenados (decrescente) e da soma de peso
   dos tokens (que e o denominador do score), evitando recomputacao O(n)
   repetida dentro do loop O(n^2).

`_similaridade_ponderada` NAO foi alterada: os pares que passam no
pre-filtro produzem EXATAMENTE os mesmos valores float da implementacao
anterior (a equivalencia formal antigo-vs-novo e do tester).
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from functools import lru_cache

from ..providers.news_source import ItemBruto

_STOPWORDS_PT = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "um",
    "uma", "para", "com", "por", "que", "no", "na", "nos", "nas", "ao",
    "aos", "se", "sobre",
}

# Limiar (SequenceMatcher.ratio, por token individual) acima do qual dois
# tokens DIFERENTES sao considerados a "mesma palavra" para fins de
# similaridade — cobre variacao de genero/numero (ex. "grande"/"grandes",
# "incendio"/"incendios"), mas alto o suficiente para nao confundir palavras
# curtas e apenas parecidas por acaso (ex. "novo"/"novos" cai aqui; "casa"/
# "caso" nao).
_LIMIAR_FUZZY_TOKEN = 0.82

# Peso residual de um token classificado como "generico do lote" (ver
# `_pesos_por_frequencia_no_lote`) — nao zero (um token generico ainda pode
# desempatar entre dois grupos igualmente genericos), mas baixo o bastante
# para que ele praticamente nao contribua para decidir se dois titulos sao o
# MESMO acontecimento.
_PESO_TOKEN_GENERICO_DO_LOTE = 0.15

# Ver docstring de `_pesos_por_frequencia_no_lote`.
_DF_MINIMO_GENERICO = 4
_TAMANHO_MINIMO_LOTE_PARA_PESO = 6

# Finding 1 REABERTO (code-review-contract.md run
# 20260902-0727-ingestao-noticias, 2a passada, major): o mecanismo acima
# (`_DF_MINIMO_GENERICO`/`_TAMANHO_MINIMO_LOTE_PARA_PESO`) so entra em vigor
# em lotes >= 6 itens com o padrao repetido >= 4 vezes — o reviewer
# reproduziu de forma independente que, num lote pequeno e realista (4 itens,
# as 4 fontes-semente do contrato rodando a cada ciclo de 15 min), esse sinal
# nunca tem dados suficientes para ativar, e o falso-positivo original volta
# a ocorrer (misattribution de conteudo, BRD secao 18).
#
# Esta lista curada complementa (nao substitui) a ponderacao dinamica: e um
# conjunto de conectores/termos jornalisticos MUITO comuns em manchetes em
# portugues do Brasil — verbos de anuncio/divulgacao ("anuncia", "lanca",
# "divulga", "apresenta"), substantivos de "veiculo do anuncio" ("plano",
# "pacote", "programa", "projeto", "medida") e orgaos/cargos genericos
# ("governo", "prefeitura", "ministerio", "presidente", "policia") — que
# recebem peso reduzido INCONDICIONALMENTE, independente do tamanho do lote
# ou de quantas vezes se repetem NESTE lote especifico. Isso e deliberado:
# esses termos raramente sao, sozinhos, o que distingue um acontecimento de
# outro (o termo especifico do fato — "mobilidade urbana", "seguranca
# publica", "homicidio", "fraude fiscal" — e que decide), entao penalizar seu
# peso e seguro mesmo sem confirmar a frequencia real do lote em producao.
# Lista mantida pequena e deliberadamente formada por palavras "vazias" de
# conteudo especifico (nao nomes proprios/temas), para minimizar o risco de
# suprimir sinal genuino de duplicata (ver calibracao em
# `tests/test_acceptance_criteria.py::TestFinding2FalsoPositivoPorPadraoSintaticoComum`,
# que inclui tanto casos de falso-positivo quanto pares genuinamente
# duplicados em lotes de 2 a 5 itens).
_PESO_TOKEN_CONECTOR_CURADO = 0.15
_CONECTORES_JORNALISTICOS_COMUNS_PT = {
    # verbos de "anuncio"/divulgacao, com variacoes de tempo/pessoa/genero
    "anuncia", "anuncio", "anuncios", "anunciam", "anunciou", "anunciando",
    "anunciado", "anunciada", "anunciados", "anunciadas",
    "lanca", "lança", "lancam", "lançam", "lancou", "lançou", "lancamento",
    "lançamento",
    "divulga", "divulgam", "divulgou", "divulgacao", "divulgação",
    "apresenta", "apresentam", "apresentou", "apresentacao", "apresentação",
    # "veiculo" do anuncio (nao o proprio fato)
    "plano", "planos", "pacote", "pacotes", "medida", "medidas",
    "programa", "programas", "projeto", "projetos", "proposta", "propostas",
    # orgaos/INSTITUICOES genericas (nao especificam O QUE aconteceu).
    # Deliberadamente NAO inclui titulos de CARGO INDIVIDUAL ("presidente",
    # "prefeito", "ministro", "secretario" etc.): calibracao mostrou que
    # esses termos, em manchetes politicas curtas e genuinas sobre o MESMO
    # acontecimento contado por 3+ fontes com redacoes bem diferentes (ex.:
    # "Presidente sanciona pacote fiscal" / "Pacote fiscal e sancionado
    # pelo presidente"), sao frequentemente uma das poucas palavras
    # remanescentes em comum apos remover stopwords — penalizar seu peso
    # incondicionalmente derrubava esses casos genuinos para abaixo do
    # limiar (regressao confirmada em
    # TestAC2DeduplicacaoEAgrupamento::test_tres_fontes_sobre_mesmo_acontecimento_formam_um_unico_cluster
    # e TestFinding3DeduplicacaoEntreExecucoesDaTask::test_status_revisao_ja_decidido_por_humano_nunca_e_sobrescrito_pela_mesclagem
    # durante a calibracao desta correcao). Instituicoes ("governo",
    # "prefeitura", "ministerio", "policia") nao tiveram esse efeito
    # colateral nos casos testados e permanecem na lista.
    "governo", "governamental", "prefeitura",
    "policia", "polícia", "policial", "policiais",
    # verbos genericos de acao investigativa (idem "anuncia")
    "investiga", "investigam", "investigou", "investigacao", "investigação",
    # qualificadores genericos de "novidade", quase sempre presentes em
    # manchetes de anuncio institucional, independente do assunto
    "novo", "nova", "novos", "novas",
}


def _tokens_titulo(titulo: str) -> set[str]:
    titulo = titulo.lower()
    titulo = re.sub(r"[^\w\s]", " ", titulo)
    return {p for p in titulo.split() if p not in _STOPWORDS_PT}


def _pesos_por_frequencia_no_lote(lista_de_tokens: list[set[str]]) -> dict[str, float]:
    """
    Classifica cada token do lote como "generico" (peso baixo) ou
    "especifico" (peso normal, 1.0), combinando DOIS mecanismos
    complementares (Finding 1 REABERTO, code-review-contract.md run
    20260902-0727-ingestao-noticias, 2a passada):

    1. Dinamico, dependente do lote: um token e "generico do lote" quando
       repete em pelo menos `_DF_MINIMO_GENERICO` (4) itens DIFERENTES do
       lote — nao um dicionario fixo hardcoded, calculado a cada chamada de
       `agrupar_itens_brutos` a partir da distribuicao real do lote sendo
       processado. So entra em vigor quando o lote tem pelo menos
       `_TAMANHO_MINIMO_LOTE_PARA_PESO` (6) itens — nunca dispara em lotes
       pequenos/artificiais, onde qualquer palavra repetida entre um par
       pode legitimamente ser o proprio nome do acontecimento (ex. "pacote
       fiscal"), nao um molde generico. Isso evita boost de tokens unicos
       (o que penalizaria titulos genuinamente equivalentes com pequenas
       variacoes de redacao — "anunciado ontem", "e sancionado" etc.).

    2. Curado, INDEPENDENTE do tamanho do lote (`_CONECTORES_JORNALISTICOS_
       COMUNS_PT`): uma pequena lista de conectores/termos jornalisticos
       muito comuns em portugues do Brasil (verbos de anuncio, "veiculo" do
       anuncio, orgaos/cargos genericos — ver constante) sempre recebe peso
       reduzido, mesmo em lotes com 2-5 itens onde o mecanismo 1 nao tem
       dados suficientes para ativar. Este e o mecanismo que fecha o gap
       reaberto pelo reviewer: o cenario de 4 itens (as 4 fontes-semente do
       contrato rodando por ciclo de 15 min) e pequeno demais para o sinal
       dinamico, mas os termos causadores do falso-positivo ("prefeitura",
       "anuncia", "novo", "plano") estao todos na lista curada.

    Quando os dois mecanismos discordam para o mesmo token, prevalece o
    MENOR peso (mais conservador em relacao ao risco de misattribution,
    BRD secao 18) — ver `min()` abaixo.
    """
    pesos: dict[str, float] = {}

    n = len(lista_de_tokens)
    if n > 0:
        frequencia_no_lote: dict[str, int] = {}
        for tokens in lista_de_tokens:
            for token in tokens:
                frequencia_no_lote[token] = frequencia_no_lote.get(token, 0) + 1

        limiar_generico = _DF_MINIMO_GENERICO if n >= _TAMANHO_MINIMO_LOTE_PARA_PESO else n + 1
        pesos = {
            token: (_PESO_TOKEN_GENERICO_DO_LOTE if freq >= limiar_generico else 1.0)
            for token, freq in frequencia_no_lote.items()
        }

    for tokens in lista_de_tokens:
        for token in tokens:
            if token in _CONECTORES_JORNALISTICOS_COMUNS_PT:
                pesos[token] = min(pesos.get(token, 1.0), _PESO_TOKEN_CONECTOR_CURADO)

    return pesos


# v2 (implementation-contract.md run 20260924-2136-ingestao-noticias, Versao
# 2): cache LRU REAL para o ratio fuzzy — substitui o dicionario anterior
# (`_CACHE_FUZZY_RATIO`), que se LIMPAVA inteiro a cada 8000 entradas. Em
# lote grande (milhares de pares unicos de tokens) o clear-total thrashava o
# cache: quase toda chamada era MISS e o SequenceMatcher (caro) rodava de
# novo. LRU com capacidade fixa retém os pares mais quentes — mesmos valores
# (a funcao e pura), retencao melhor, sem thrash. 65536 entradas ~ 15MB no
# pior caso: custo de memoria aceitavel para um processo de longa vida
# (agendador/worker), nenhuma dependencia nova (functools e stdlib).
_CACHE_FUZZY_MAXSIZE = 65536


@lru_cache(maxsize=_CACHE_FUZZY_MAXSIZE)
def _ratio_sequence_matcher_canonico(a: str, b: str) -> float:
    """SequenceMatcher puro para um par JA canonizado (a < b) — cache LRU."""
    return SequenceMatcher(None, a, b).ratio()


def _ratio_cached(a: str, b: str) -> float:
    """SequenceMatcher com cache LRU + poda barata por tamanho."""
    if a == b:
        return 1.0
    # poda: tokens muito diferentes em tamanho nunca atingem 0.82
    # ex.: "a" vs "internacionalizacao" — evita SequenceMatcher caro
    if abs(len(a) - len(b)) > 4 and min(len(a), len(b)) <= 4:
        return 0.0
    # cache simétrico: a chave canônica garante que (a, b) e (b, a) compartilham
    # a MESMA entrada do LRU (mesmo comportamento do dicionário anterior)
    if a < b:
        return _ratio_sequence_matcher_canonico(a, b)
    return _ratio_sequence_matcher_canonico(b, a)


def _tokens_fuzzy_pareados(tokens_a: set[str], tokens_b: set[str]) -> list[tuple[str, str]]:
    """
    Pares de tokens iguais OU muito parecidos (>= `_LIMIAR_FUZZY_TOKEN`)
    entre os dois conjuntos — cada token de cada lado participa de no maximo
    um par (pareamento guloso, suficiente para titulos curtos de manchete).
    """
    comuns = tokens_a & tokens_b
    pares = [(token, token) for token in comuns]

    restantes_a = tokens_a - comuns
    restantes_b = set(tokens_b - comuns)
    # poda grosseira: se não há overlap exato e os conjuntos são
    # completamente disjuntos com poucos tokens, um pré-filtro por
    # tamanho já descarta muitos pares antes do fuzzy caro
    if not comuns and len(restantes_a) > 0 and len(restantes_b) > 0:
        # heurística barata: se a interseção de 3-prefixos é vazia e ambos
        # têm >=3 tokens, é improvável haver fuzzy útil — mas não usamos
        # para decidir aqui, só para evitar o pior caso dentro do loop
        pass
    for token_a in restantes_a:
        melhor_par = None
        melhor_score = 0.0
        for token_b in restantes_b:
            score = _ratio_cached(token_a, token_b)
            if score > melhor_score:
                melhor_score = score
                melhor_par = token_b
                if score >= 0.99:
                    break  # ótimo já encontrado
        if melhor_par is not None and melhor_score >= _LIMIAR_FUZZY_TOKEN:
            pares.append((token_a, melhor_par))
            restantes_b.discard(melhor_par)

    return pares


def _similaridade_ponderada(
    tokens_a: set[str], tokens_b: set[str], pesos_tokens: dict[str, float]
) -> float:
    if not tokens_a or not tokens_b:
        return 0.0

    pares = _tokens_fuzzy_pareados(tokens_a, tokens_b)
    peso_intersecao = sum(
        max(pesos_tokens.get(token_a, 1.0), pesos_tokens.get(token_b, 1.0)) for token_a, token_b in pares
    )
    peso_uniao = sum(pesos_tokens.get(token, 1.0) for token in (tokens_a | tokens_b))
    if peso_uniao <= 0:
        return 0.0
    return peso_intersecao / peso_uniao


def calcular_similaridade_titulos(
    titulo_a: str, titulo_b: str, pesos_tokens: dict[str, float] | None = None
) -> float:
    """
    Similaridade ponderada entre dois titulos (ver docstring do modulo).
    `pesos_tokens` normalmente vem de `_pesos_por_frequencia_no_lote` sobre o
    lote inteiro sendo agrupado — chamado sem esse argumento (ex.: uso
    isolado/depuracao), cai para Jaccard "fuzzy" sem ponderacao (todo token
    com peso 1.0).
    """
    tokens_a = _tokens_titulo(titulo_a)
    tokens_b = _tokens_titulo(titulo_b)
    return _similaridade_ponderada(tokens_a, tokens_b, pesos_tokens or {})


# v2 (implementation-contract.md run 20260924-2136-ingestao-noticias, Versao
# 2, criterios de aceite 8-9): margem de seguranca do pre-filtro por limite
# superior. Os somatorios do bound tem erro de arredondamento float
# (~1e-14 relativo, composto); a poda so ocorre quando o bound computado ja
# esta ABAIXO do limiar com folga muito maior que esse erro — um par cujo
# score real poderia atingir o limiar NUNCA e podado (resultado do
# agrupamento garantidamente identico ao calculo completo).
_MARGEM_SEGURANCA_BOUND = 1e-12


def _soma_k_maiores_pesos(
    pesos_ordenados_a: list[float], pesos_ordenados_b: list[float], k: int
) -> float:
    """
    Soma dos `k` maiores pesos da UNIAO das duas listas (ambas ja em ordem
    DECRESCENTE) — two-pointer merge, O(k).

    E o limite superior EXATO do acrescimo fuzzy possivel entre os dois
    conjuntos (contrato v2): cada par fuzzy consome um token de cada lado e
    contribui com o peso do lado MAIOR; os tokens que contribuem sao
    distintos (restantes_a e restantes_b sao disjuntos — ambos vieram de
    tokens_a/tokens_b menos os comuns) e em numero <= `k`, entao a soma e
    maximizada exatamente pelos `k` maiores pesos da uniao. Como
    `k <= min(len(a), len(b))` e garantido pelo chamador (os restantes sao
    subconjuntos), o merge nunca estoura o fim de nenhuma lista.
    """
    total = 0.0
    i = j = 0
    for _ in range(k):
        if pesos_ordenados_a[i] >= pesos_ordenados_b[j]:
            total += pesos_ordenados_a[i]
            i += 1
        else:
            total += pesos_ordenados_b[j]
            j += 1
    return total


def _bound_similaridade(
    tokens_a: set[str],
    tokens_b: set[str],
    pesos_tokens: dict[str, float],
    pesos_ordenados_a: list[float],
    peso_uniao_a: float,
    pesos_ordenados_b: list[float],
    peso_uniao_b: float,
) -> float:
    """
    Limite SUPERIOR barato do valor que `_similaridade_ponderada` pode
    devolver para este par (contrato v2, run
    20260924-2136-ingestao-noticias) — nunca inferior ao score real, sem
    rodar o pareamento fuzzy caro:

    - `peso_comuns` (tokens EXATAMENTE comuns) e EXATO: todo token comum
      sempre forma um par `(t, t)` em `_tokens_fuzzy_pareados`, com
      contribuicao `max(w(t), w(t)) = w(t)`;
    - acrescimo fuzzy: cada par fuzzy consome um token de cada lado e
      contribui com o peso do lado MAIOR; o melhor pareamento possivel
      captura exatamente os `k = min(|restantes_a|, |restantes_b|)` maiores
      pesos da uniao (ver `_soma_k_maiores_pesos`). Os pesos ordenados vem
      PRE-CALCULADOS por item (incluem os pesos dos comuns — a uniao
      completa so deixa o bound mais folgado, nunca inferior);
    - denominador real do score = `peso_uniao_a + peso_uniao_b -
      peso_comuns` (a uniao de tokens e a soma dos dois conjuntos menos a
      intersecao), calculado aqui em O(1) a partir das somas pre-calculadas.

    Se o bound esta abaixo do limiar (com `_MARGEM_SEGURANCA_BOUND`), o
    score real tambem esta — a comparacao cara pode ser pulada com resultado
    identico (criterio de aceite 9: nunca pular um par que poderia atingir o
    limiar).
    """
    if not tokens_a or not tokens_b:
        return 0.0

    comuns = tokens_a & tokens_b
    peso_comuns = sum(pesos_tokens.get(token, 1.0) for token in comuns)
    k = min(len(tokens_a), len(tokens_b)) - len(comuns)
    if k > 0:
        acrescimo_fuzzy = _soma_k_maiores_pesos(
            pesos_ordenados_a, pesos_ordenados_b, k
        )
    else:
        acrescimo_fuzzy = 0.0

    peso_uniao = peso_uniao_a + peso_uniao_b - peso_comuns
    if peso_uniao <= 0:
        return 0.0
    return (peso_comuns + acrescimo_fuzzy) / peso_uniao


def agrupar_itens_brutos(
    itens: list[ItemBruto], limiar_similaridade: float = 0.55
) -> list[list[ItemBruto]]:
    """
    Agrupa itens cujo titulo tem similaridade ponderada (ver docstring do
    modulo) >= `limiar_similaridade` com ALGUM item ja presente em um grupo
    (agrupamento "single-linkage"). Os pesos por token sao calculados UMA
    VEZ, a partir da frequencia de cada token entre TODOS os itens de
    `itens` (Finding 2) — por isso a qualidade do agrupamento melhora quanto
    mais representativo/realista for o lote (varias fontes, varias
    noticias), e degrada para lotes muito pequenos/artificiais (ver testes).

    v2 (implementation-contract.md run 20260924-2136-ingestao-noticias,
    criterios de aceite 8-9): antes de rodar `_similaridade_ponderada` (cara)
    em cada par (item, membro de grupo), o pre-filtro por limite superior
    (`_bound_similaridade`, dois niveis: membro a membro e grupo inteiro)
    pula os pares cujo score possivel ja esta abaixo do limiar — resultado
    garantidamente identico ao calculo completo, porque o pareamento fuzzy
    carissimo (SequenceMatcher por token) so roda nos pares que ainda podem
    atingir o limiar. Em lote grande (backlog de dias x dezenas de fontes)
    isso reduz a rodada de horas para minutos.

    Retorna uma lista de grupos (cada grupo e uma lista de `ItemBruto`);
    grupos de tamanho 1 representam itens sem cobertura duplicada
    encontrada nesta execucao (nao geram `NewsCluster`, ver
    `services/ingestao.py`).
    """
    tokens_por_item = [_tokens_titulo(item.titulo) for item in itens]
    pesos_tokens = _pesos_por_frequencia_no_lote(tokens_por_item)

    # v2: pre-calculo por item — pesos ordenados em ordem DECRESCENTE e soma
    # de peso dos tokens do item (o denominador do score). Alimenta o
    # pre-filtro por limite superior sem recomputacao O(n) repetida dentro do
    # loop O(n^2). Usado SOMENTE para o bound: `_similaridade_ponderada`
    # continua calculando o denominador exato como antes — valores de saida
    # nao mudam (criterio de aceite 9).
    dados_por_item: list[tuple[list[float], float]] = []
    for tokens in tokens_por_item:
        pesos_ordenados = sorted(
            (pesos_tokens.get(token, 1.0) for token in tokens), reverse=True
        )
        dados_por_item.append((pesos_ordenados, sum(pesos_ordenados)))

    # v2: limiar efetivo do pre-filtro (limiar menos a margem de seguranca —
    # ver `_MARGEM_SEGURANCA_BOUND`): nunca pula um par que poderia atingir o
    # limiar.
    limiar_efetivo = limiar_similaridade - _MARGEM_SEGURANCA_BOUND

    grupos_indices: list[list[int]] = []

    for indice_item, tokens_item in enumerate(tokens_por_item):
        melhor_grupo_indice = None
        melhor_score = 0.0
        pesos_ordenados_item, peso_uniao_item = dados_por_item[indice_item]
        for grupo_indice, indices_do_grupo in enumerate(grupos_indices):
            score = 0.0
            algum_viavel = False
            for outro_indice in indices_do_grupo:
                dados_outro = dados_por_item[outro_indice]
                bound = _bound_similaridade(
                    tokens_item,
                    tokens_por_item[outro_indice],
                    pesos_tokens,
                    pesos_ordenados_item,
                    peso_uniao_item,
                    dados_outro[0],
                    dados_outro[1],
                )
                if bound < limiar_efetivo:
                    # v2, nivel (item, membro): score impossivel de atingir o
                    # limiar — a comparacao cara e pulada (resultado identico)
                    continue
                algum_viavel = True
                score_parcial = _similaridade_ponderada(
                    tokens_item, tokens_por_item[outro_indice], pesos_tokens
                )
                if score_parcial > score:
                    score = score_parcial
            if not algum_viavel:
                # v2, nivel (item, grupo): NENHUM membro pode atingir o
                # limiar — grupo inteiro pulado sem nenhuma comparacao cara
                continue
            if score > melhor_score:
                melhor_score = score
                melhor_grupo_indice = grupo_indice

        if melhor_grupo_indice is not None and melhor_score >= limiar_similaridade:
            grupos_indices[melhor_grupo_indice].append(indice_item)
        else:
            grupos_indices.append([indice_item])

    return [[itens[indice] for indice in indices_do_grupo] for indices_do_grupo in grupos_indices]
