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
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

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
    for token_a in restantes_a:
        melhor_par = None
        melhor_score = 0.0
        for token_b in restantes_b:
            score = SequenceMatcher(None, token_a, token_b).ratio()
            if score > melhor_score:
                melhor_score = score
                melhor_par = token_b
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

    Retorna uma lista de grupos (cada grupo e uma lista de `ItemBruto`);
    grupos de tamanho 1 representam itens sem cobertura duplicada
    encontrada nesta execucao (nao geram `NewsCluster`, ver
    `services/ingestao.py`).
    """
    tokens_por_item = [_tokens_titulo(item.titulo) for item in itens]
    pesos_tokens = _pesos_por_frequencia_no_lote(tokens_por_item)

    grupos_indices: list[list[int]] = []

    for indice_item, tokens_item in enumerate(tokens_por_item):
        melhor_grupo_indice = None
        melhor_score = 0.0
        for grupo_indice, indices_do_grupo in enumerate(grupos_indices):
            score = max(
                _similaridade_ponderada(tokens_item, tokens_por_item[outro_indice], pesos_tokens)
                for outro_indice in indices_do_grupo
            )
            if score > melhor_score:
                melhor_score = score
                melhor_grupo_indice = grupo_indice

        if melhor_grupo_indice is not None and melhor_score >= limiar_similaridade:
            grupos_indices[melhor_grupo_indice].append(indice_item)
        else:
            grupos_indices.append([indice_item])

    return [[itens[indice] for indice in indices_do_grupo] for indices_do_grupo in grupos_indices]
