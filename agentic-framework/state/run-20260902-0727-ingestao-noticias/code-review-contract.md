<!--
CONTRACT: code-review-contract
DONO: reviewer
QUANDO E CRIADO: sempre que review-triggers.md indicar revisao obrigatoria, ou sob demanda (skill agentic-review).
PARA ONDE VAI A INSTANCIA: agentic-framework/state/run-<run_id>/code-review-contract.md
-->

# Code Review Contract - 20260902-0727-ingestao-noticias

## Metadados
- **run_id:** 20260902-0727-ingestao-noticias
- **Escopo revisado (TERCEIRA e ultima passada permitida pelo orchestrator, 3/3):** revalidacao independente dos 4 findings da segunda passada (major Finding 1 reaberto + major Finding 2 + minor Finding 4 + minor Finding 5) apos remediacao registrada em implementation-history.md, "Iteracao 4 - remediator". Arquivos revisados: backend/catalogo_noticias/services/deduplicacao.py, backend/catalogo_noticias/services/ingestao.py, backend/config/settings.py, backend/.env.example, backend/catalogo_noticias/tests/test_acceptance_criteria.py.
- **Contrato de referencia:** implementation-contract.md (20260902-0727-ingestao-noticias)
- **Gatilhos aplicados (de review-triggers.md):** direitos autorais/compliance (BRD secao 18) - restricao mais critica deste run, presente nas 3 passadas; mudanca de algoritmo de deduplicacao/merge de clusters.
- **Metodologia:** nao aceitei a palavra do remediator. Li o codigo linha a linha, rodei a suite completa eu mesmo (DJANGO_DB_ENGINE=sqlite3 pytest -q -> 106 passed, 7 warnings, confirmado, mesmo numero que o remediator relatou) e manage.py check (limpo). Escrevi scripts adversariais proprios, deliberadamente com vocabulario e cenarios diferentes dos que o remediator usou em sua propria calibracao/suite, para nao validar apenas "o que passa no teste que eles escreveram" - exatamente a instrucao recebida para esta ultima passada.

## Findings

### Finding 1 (major - REABERTO pela 2a vez; NAO RESOLVIDO de forma estrutural)
- **Arquivo:** backend/catalogo_noticias/services/deduplicacao.py
- **Linha:** _pesos_por_frequencia_no_lote (linhas 165-219) + _CONECTORES_JORNALISTICOS_COMUNS_PT (linhas 123-156)
- **Categoria:** correctness, com efeito colateral de compliance/moderacao (BRD secao 18 - misattribution de conteudo; adjacente tambem a "regras que decidem o que e publicado sem revisao previa")
- **Severidade:** major
- **Resumo:** A correcao desta rodada (lista curada de conectores jornalisticos, complementando o mecanismo dinamico por lote) neutraliza corretamente o cenario EXATO que a 2a passada reproduziu ("Prefeitura... anuncia novo plano de..."). Confirmei isso rodando o cenario original do reviewer da 2a passada contra o codigo atual: nao mais se agrupa. Porem, o mecanismo continua sendo, por construcao, uma lista finita e curada de palavras - qualquer verbo/substantivo de anuncio institucional em portugues que NAO esteja na lista, combinado com um lote pequeno (onde o mecanismo dinamico nao tem itens suficientes para ativar, _TAMANHO_MINIMO_LOTE_PARA_PESO = 6), reproduz o MESMO falso-positivo. Isso nao e uma suposicao - reproduzi de forma independente, com vocabulario que eu mesmo escolhi (nao usado em nenhum teste/calibracao do remediator), dois cenarios plausiveis de producao:
  1. Verbo "confirma" (sinonimo comum de "anuncia", nao esta na lista curada) + substantivo "surto" (nao esta na lista) em um lote de 4 itens (as 4 fontes-semente do contrato) - dois fatos DIFERENTES (surto de dengue vs. surto de sarampo) sao agrupados no mesmo cluster.
  2. O caso mais grave: a propria calibracao desta rodada excluiu DELIBERADAMENTE titulos de cargo individual ("presidente", "prefeito", "ministro", "secretario") da lista curada, exatamente para nao regredir 2 testes existentes (documentado no proprio codigo, linhas 135-148). Isso reabre, por construcao, a mesma classe de falso-positivo sempre que o termo compartilhado por dois fatos DIFERENTES for justamente um desses cargos - reproduzi com um lote de apenas 2 itens: "Presidente confirma viagem oficial aos Estados Unidos em outubro" vs. "Presidente confirma viagem oficial a China em outubro" (duas viagens/pautas de politica externa distintas) sao agrupadas no mesmo NewsCluster.
- **Cenario de falha (scripts adversarios proprios, fora da suite do remediator, reproduzidos com agrupar_itens_brutos() direto):**

  ```python
  casoA = [
      ("Ministerio da Saude confirma novo surto de dengue na capital", "G1"),
      ("Ministerio da Saude confirma novo surto de sarampo na capital", "UOL"),
      ("Selecao brasileira vence amistoso por 2 a 0", "CNN Brasil"),
      ("Dolar fecha em alta nesta quinta-feira", "Folha"),
  ]
  # resultado: os dois itens de saude (dengue x sarampo, fatos DIFERENTES) caem no MESMO grupo

  casoC = [
      ("Presidente confirma viagem oficial aos Estados Unidos em outubro", "G1"),
      ("Presidente confirma viagem oficial a China em outubro", "UOL"),
  ]
  # resultado: os 2 itens (unico lote, 2 fontes) caem no MESMO grupo - apenas 2 itens, nenhuma
  # elaboracao artificial de lote necessaria
  ```

  Como controle, tambem testei um caso de vocabulario novo ("pesquisa revela X no primeiro trimestre") que corretamente nao se agrupou - a correcao desta rodada claramente reduziu a superficie do problema (nem todo vocabulario novo dispara falso-positivo), mas nao a eliminou por construcao.

  Consequencia identica as duas passadas anteriores: _persistir_grupo faz UMA chamada ao SummarizationProvider para o grupo combinado e grava o MESMO resumo_proprio em NewsItems cujo url_fonte_original/nome_fonte sao de materias sobre fatos diferentes. Adicionalmente, no Caso C (2 fontes apenas), o cluster resultante tem numero_fontes_distintas == 2, abaixo do CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA default (3) - ou seja, nao aciona revisao humana automaticamente (a menos que a categoria seja sensivel), o conteudo misto/incorreto seria publicado automaticamente sem qualquer checagem.
- **Por que isso nao e uma repeticao inutil do mesmo finding:** as duas primeiras rodadas de remediacao genuinamente reduziram a superficie do problema a cada iteracao (de "qualquer padrao repetido" -> "so em lotes >=6 com repeticao >=4" -> "tambem cobre lotes pequenos, mas so para ~30 palavras curadas"). O padrao se repete porque a abordagem escolhida (lista finita de conectores + heuristica lexical/Jaccard) e estruturalmente incapaz de cobrir todo o vocabulario jornalistico em portugues sem se tornar uma lista interminavel - e cada palavra adicionada carrega risco de nova regressao (como a propria calibracao desta rodada documentou ao excluir titulos de cargo).
- **Sugestao (para nao perpetuar whack-a-mole em uma 4a rodada):**
  - (a) Recomendada, estrutural, nao mais lista de palavras: alem do score ponderado por peso >= limiar, exigir que exista pelo menos 1 token de peso pleno (1.0, isto e, nao-generico/nao-curado) em comum entre os dois titulos antes de agrupar - dois fatos genuinamente diferentes tendem a nao compartilhar NENHUM termo especifico (so o molde institucional), enquanto fatos iguais contados por fontes diferentes normalmente compartilham ao menos um substantivo/nome proprio especifico do fato. Isso ataca a causa raiz (falta de sinal especifico em comum), nao mais um vocabulario finito.
  - (b) Complementar, de baixo risco, aproveitando o mecanismo ja existente de revisao humana: quando um cluster e formado a partir de um lote pequeno (abaixo de _TAMANHO_MINIMO_LOTE_PARA_PESO, isto e, exatamente onde o sinal dinamico nao tem dados suficientes) E o numero de fontes do cluster resultante ficar abaixo do limiar de alta relevancia, forcar status_revisao=pendente mesmo assim - nao tentar decidir com confianca insuficiente, e deixar a decisao para o humano em vez de arriscar publicacao automatica de conteudo potencialmente misturado. Baixo risco de regressao (nao muda o algoritmo de similaridade, so a decisao de publicacao para o caso especifico de menor confianca).
  - (c) Se nenhuma das duas opcoes acima for viavel nesta janela, documentar explicitamente como risco residual aceito para o MVP (nao mais tentar fechar via lista de palavras) e adicionar um teste de regressao com os 2 cenarios acima (que hoje falham) marcado como xfail - visivel no CI, nao silencioso - ate que dedup semantica real (ja registrada como upgrade futuro em implementation-history.md) seja priorizada.

### Finding 2 (major -> reclassificado MINOR nesta passada) - evasao residual da checagem de trecho copiado, via fragmentacao deliberada abaixo do limiar de bloco
- **Arquivo:** backend/catalogo_noticias/services/ingestao.py
- **Linha:** _proporcao_do_resumo_copiada_literalmente (linhas 140-178), _TAMANHO_MINIMO_TRECHO_COPIADO_CARACTERES = 20 (linha 137)
- **Categoria:** correctness (compliance/direitos autorais - BRD secao 18)
- **Severidade:** minor (rebaixada da severidade major da 2a passada - ver justificativa)
- **Resumo:** A correcao desta rodada (checagem de proporcao de trecho copiado, complementar ao ratio() do texto inteiro) resolve corretamente o cenario exato reportado na 2a passada (frase inteira copiada verbatim de uma materia longa) - confirmei rodando esse cenario contra o codigo atual (bloqueado, proporcao=0.68). Testei tambem 2 variacoes proprias adicionais (trecho copiado do meio+fim concatenado; parafrase leve com um unico bloco grande) - ambas corretamente bloqueadas. Porem, encontrei uma evasao residual: como a checagem so conta blocos continuos identicos com >= 20 caracteres, um resumo construido deliberadamente como um "mosaico" de fragmentos verbatim MENORES que 20 caracteres cada (retirados de partes distantes do bruto), costurados com texto de preenchimento generico/proprio, evade completamente as duas checagens (proporcao=0.0, ratio() tambem baixo por causa do preenchimento). Reproduzi isso de forma independente com um script proprio (5 fragmentos de 17-18 caracteres cada, retirados de pontos distintos do bruto, entremeados com frases de transicao genericas de aparencia autoral) - _resumo_e_copia_ou_quase_copia retornou False.
- **Por que rebaixei a severidade (nao e o mesmo peso do finding original):** ao contrario dos 2 gaps anteriores (copia identica do texto inteiro; copia verbatim de uma frase/trecho continuo - ambos comportamentos plausiveis de um LLM "preguicoso" real, que tende a reproduzir blocos continuos de texto-fonte), este cenario exige uma construcao deliberada e adversarial: escolher a dedo fragmentos exatamente abaixo do limiar de 20 caracteres e intercala-los com preenchimento generico suficiente para diluir a proporcao total. Isso nao e um padrao de falha natural esperado de um SummarizationProvider real "mal comportado" (que tende a copiar blocos continuos maiores, nao fatiar deliberadamente o texto para escapar de um limiar que ele nem conhece) - e mais proximo de um ataque desenhado especificamente contra este detector especifico do que de um modo de falha organico. Qualquer detector baseado em limiar de tamanho de bloco continuo tem esta mesma propriedade matematica (e sempre "gameavel" por quem conhece o limiar) - nao e um bug pontual corrigivel, e uma limitacao de categoria inteira de algoritmo (deteccao de plagio via blocos continuos, sem shingling/n-gramas sobrepostos).
- **Sugestao (nao bloqueante, registrar como melhoria futura, nao commit obrigatorio):** se o "patchwork plagiarism" for uma preocupacao real de negocio (mais provavel quando o SummarizationProvider real for um LLM de terceiros, nao neste MVP com providers mockados), trocar o algoritmo de blocos continuos por comparacao de n-gramas sobrepostos (shingling, ex.: janelas de 8-10 palavras com hash, contando proporcao de shingles do resumo que aparecem no bruto) - deteccao padrao de plagio parcial, robusta a fragmentacao deliberada, sem depender de um unico limiar de tamanho de bloco.

### Finding 3 (era Finding 3 da 1a/2a passada - permanece RESOLVIDO)
- **Status:** sem mudanca de codigo nesta iteracao (o remediator nao tocou a logica de merge entre execucoes). Nao re-verifiquei em profundidade nesta passada por nao fazer parte do escopo dos 4 findings pendentes indicados, mas confirmei que os 3 testes de TestFinding3DeduplicacaoEntreExecucoesDaTask continuam passando na suite completa.

### Finding 4 (minor - RESOLVIDO, revalidado de forma independente)
- **Arquivo:** backend/catalogo_noticias/services/ingestao.py::_persistir_grupo_mesclado (linhas 376-387)
- **Status:** resolvido. Confirmei lendo o codigo (nao so o relato do remediator): apos NewsItem.objects.filter(cluster_id__in=outros_ids).update(cluster=cluster), a linha seguinte executa NewsCluster.objects.filter(pk__in=outros_ids).delete() - o(s) cluster(s) nao-canonico(s) e(sao) removido(s) de fato, nao apenas esvaziado(s). on_delete=SET_NULL na FK NewsItem.cluster (verificado em models.py) torna a ordem (mover itens ANTES de deletar) segura, e a ordem no codigo esta correta (mover primeiro, deletar depois). O teste TestFinding4ClusterOrfaoAposMesclagemERemovido exercita isso diretamente (2 NewsCluster reais criados, cluster nao-canonico confirmado deletado do banco apos a chamada) - rodei este teste isoladamente (-v), passou.

### Finding 5 (minor/performance - RESOLVIDO, revalidado de forma independente)
- **Arquivo:** backend/catalogo_noticias/services/ingestao.py::_itens_recentes_persistidos (linhas 101-113) + backend/config/settings.py (linhas 361-363)
- **Status:** resolvido. Confirmei lendo o codigo: nova setting CATALOGO_NOTICIAS_DEDUP_MAX_ITENS_RECENTES (default 300, configuravel via env var) e a query agora usa .order_by("-timestamp_ingestao")[:limite_itens] alem do filtro por janela de tempo - o lote combinado passado a agrupar_itens_brutos agora tem um teto superior determinado, nao cresce sem limite com o volume acumulado da janela. O teste TestFinding5TetoDeItensRecentesTrazidosParaOAgrupamento confirma que, com o teto reduzido, apenas os N itens mais RECENTES (por timestamp_ingestao, nao por ordem de criacao) sao trazidos - rodei isoladamente, passou.

## Findings anteriores (1a e 2a passada) - status final consolidado

| # | Resumo original | Severidade original | Status final (3a passada) |
|---|---|---|---|
| Finding 1 (1a passada) | resumo_proprio podia ser copia identica do bruto | blocker | Resolvido (revalidado na 2a e 3a passada). |
| Finding 2 (1a passada) | falsos-positivos de agrupamento por padrao sintatico comum | major | Parcialmente resolvido em 2 rodadas sucessivas; residual real e reproduzivel ainda existe - ver Finding 1 desta passada. |
| Finding 3 (1a passada) | deduplicacao nao considerava itens de execucoes anteriores | major | Resolvido (revalidado na 2a e 3a passada). |
| Finding 4/5 (1a passada) | LLM_API_BASE_URL / N+1 query | minor | Resolvidos (2a passada). |
| Finding 1 (2a passada) | falso-positivo em lotes pequenos (4 itens) | major | Reduzido, mas nao eliminado por construcao - ver Finding 1 desta passada (reproduzido com vocabulario/cenario novo). |
| Finding 2 (2a passada) | copia parcial verbatim evade checagem | major | Resolvido para o cenario reportado; gap residual estreito (evasao deliberada) rebaixado a minor - ver Finding 2 desta passada. |
| Finding 4 (2a passada) | clusters orfaos apos merge | minor | Resolvido - ver Finding 4 desta passada. |
| Finding 5 (2a passada) | lote de dedup sem limite superior | minor | Resolvido - ver Finding 5 desta passada. |

## Resumo quantitativo (3a passada)
| Severidade | Quantidade |
|---|---|
| blocker | 0 |
| major | 1 |
| minor | 1 |
| nit | 0 |

## Suite de testes (revalidacao independente)

Comando: DJANGO_DB_ENGINE=sqlite3 ./.venv/Scripts/python.exe -m pytest -q
Resultado: 106 passed, 7 warnings in ~40s (confirmado por mim, mesmo numero relatado pelo remediator em implementation-history.md).
manage.py check: System check identified no issues (0 silenced).

## Veredito
**changes_requested**

Esta e a 3a e ultima passada permitida pelo orchestrator antes de escalar para decisao humana - e essa e, na minha avaliacao, a decisao correta aqui, nao um "changes_requested" automatico/reflexivo.

Dos 4 findings pendentes da 2a passada, 3 foram genuinamente resolvidos e revalidados de forma independente nesta passada (Finding 2 da 2a passada rebaixado a minor com um gap residual estreito e nao-organico; Finding 4 e Finding 5 totalmente resolvidos). O trabalho do remediator nesta rodada foi honesto e rigoroso - a propria entrada de implementation-history.md documenta uma regressao encontrada e corrigida DURANTE a propria calibracao (nao escondida), e a suite de 106 testes (16 novos nesta rodada) cobre bem os cenarios ja conhecidos.

Porem, o Finding 1 (falso-positivo de agrupamento) continua sem solucao estrutural, pela 3a vez consecutiva. Nao e uma questao de o remediator nao ter se esforcado - e que a abordagem escolhida (lista curada de conectores jornalisticos) e, por construcao, uma lista finita que nunca vai cobrir todo o vocabulario de anuncio institucional em portugues, e cada palavra adicionada a lista carrega risco real de nova regressao (como a propria calibracao desta rodada documentou, ao ter que excluir titulos de cargo individual para nao quebrar 2 testes genuinos - o que, por sua vez, reabriu exatamente essa classe de falso-positivo para titulos de cargo). Reproduzi de forma independente, com vocabulario que eu mesmo escolhi (nao usado em nenhum teste da suite), 2 cenarios plausiveis de producao com lotes de 2 e 4 itens - nao artificiais, nao adversariais no sentido de "ataque desenhado contra o detector", apenas manchetes jornalisticas comuns em portugues que a lista curada nao cobre. Um deles (Caso C, 2 fontes) nem sequer aciona revisao humana automaticamente pelo limiar de fontes, o que significa publicacao automatica de conteudo potencialmente misturado sem qualquer checagem - o mesmo risco de misattribution (BRD secao 18) que motivou o veredito blocked original da 1a passada, ainda que num mecanismo diferente (merge de clusters, nao copia literal).

Diferente do Finding 2 desta passada (que rebaixei a minor porque a evasao exige construcao deliberada, um modo de falha nao-organico), o Finding 1 continua sendo reproduzivel com esforco minimo e vocabulario comum - nao considero isso "risco residual aceitavel para MVP sem ressalva", e sim um major genuino que ainda nao tem uma correcao estrutural aplicada (apenas mitigacoes sucessivas que reduzem, mas nao eliminam, a superficie do problema).

**Recomendacao concreta para o orchestrator, dado o limite de 3 iteracoes atingido:** nao enviar para uma 4a rodada de "adicionar mais palavras a lista curada" (whack-a-mole ja demonstrado ineficaz de forma estrutural). As duas opcoes com melhor custo-beneficio, registradas em detalhe no Finding 1 acima, sao: (a) exigir pelo menos 1 token de peso pleno (nao-generico) em comum antes de agrupar - ataca a causa raiz, nao mais vocabulario; ou (b) para lotes pequenos (onde o sinal dinamico nao tem dados suficientes), forcar status_revisao=pendente em vez de auto-publicar - aproveita o mecanismo de revisao humana ja existente no sistema, baixo risco de regressao, nao exige mexer no algoritmo de similaridade. Qualquer uma das duas e um escopo pequeno e bem definido (nao uma reescrita), adequada para uma decisao humana rapida seguida de uma unica correcao pontual, em vez de mais uma rodada do loop automatico.
