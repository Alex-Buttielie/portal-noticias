<!--
CONTRACT: task-plan
DONO: orchestrator
QUANDO É CRIADO: no início de toda execução (agentic-run), antes de qualquer implementação.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/task-plan.md
-->

# Task Plan — 20260903-1211-teto-gasto-diario-llm

## Metadados
- **run_id:** 20260903-1211-teto-gasto-diario-llm
- **Data de abertura:** 2026-09-03
- **Solicitado por:** usuário (Alex), diretamente no chat
- **Spec de origem:** `BRD_portal_noticias_versao_1.docx` seção 30 (risco "Custo de IA/infraestrutura", impacto Alto); `ARCHITECTURE.md` seção 7 ("Custo de IA controlado") e seção 9 (tabela de custo/performance/segurança, linha "Custo" cita `CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD`); comentário de design já existente em `backend/config/settings.py` linhas 668-679 (a própria setting documenta o comportamento esperado antes desta execução).

## Objetivo
A setting `CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD` (já existe, default 5.0) passa a ser efetivamente aplicada: o custo de cada chamada ao `SummarizationProvider` é estimado e registrado de forma observável, e a ingestão para de chamar o provedor de LLM (caindo no fallback de revisão humana já existente) assim que o gasto acumulado do dia corrente ultrapassa o teto — sem quebrar a ingestão em si.

## Escopo
### Dentro do escopo
- Estimar `custo_estimado_usd` real em `LLMHttpSummarizationProvider` (hoje sempre `None` — decisão em aberto documentada em `providers/summarization.py` linha ~213) a partir de tokens consumidos × preço configurável (nova setting, com default razoável).
- Checar, antes de cada lote de chamadas em `services/ingestao.py::executar_ingestao`, se o gasto acumulado do dia corrente (execuções já persistidas em `RegistroExecucaoIngestao` + o que já foi gasto nesta própria execução) ultrapassa `CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD`; se sim, os itens restantes do lote (e dos lotes seguintes) caem no fallback existente (`_resultado_fallback_erro`, mesmo tratamento já dado a erro de provedor — força `status_revisao=pendente`), sem chamar o provedor.
- Expor o gasto do dia (e se o teto foi excedido) via `metricas` (app já responsável por observabilidade agregada — `backend/metricas/services.py`), reaproveitando o `RegistroExecucaoIngestao` já existente (nenhum modelo novo).
- Testes cobrindo uso normal (não afetado) e uso acima do teto (força fallback no restante do lote).

### Fora do escopo (explicitamente)
- Qualquer mudança na lógica de deduplicação (`services/deduplicacao.py`, `_itens_recentes_persistidos`, `agrupar_itens_brutos`) ou nas checagens de direitos autorais/cópia literal (`_resumo_e_copia_ou_quase_copia`, `_proporcao_do_resumo_copiada_literalmente`) — já passaram por 3 rodadas de revisão fechadas (run `20260902-0727-ingestao-noticias`), não devem ser reabertas nesta execução.
- Escolher o provedor concreto de LLM de produção ou sua tabela de preços real (decisão em aberto registrada em `ARCHITECTURE.md` seção 8, item 3) — esta execução só adiciona uma ESTIMATIVA configurável via setting, não resolve a decisão de provedor.
- Interromper/pausar a task periódica Celery (`tasks.ingerir_noticias`) inteira quando o teto é excedido — o requisito é parar de GASTAR (não chamar o LLM), não parar de ingerir itens (eles continuam sendo persistidos, só sem resumo automático).
- Reset manual/endpoint administrativo para "zerar" o gasto do dia — a virada natural do dia (baseada em `executado_em` das execuções passadas) já resolve isso.

## Suposições assumidas
- Preço por token será uma nova setting simples (`CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS` ou nome equivalente), com um default aproximado de mercado para um modelo econômico (ex.: mesma faixa de `gpt-4o-mini`, já o default de `CATALOGO_NOTICIAS_LLM_MODEL`) — motivo: o BRD/ARCHITECTURE pedem "custo estimado", não um valor exato, e o provedor concreto ainda é decisão em aberto; um número configurável e documentado como estimativa é suficiente e reversível (basta mudar a env var quando o provedor real for escolhido).
- "Gasto acumulado do dia corrente" = soma de `RegistroExecucaoIngestao.custo_estimado_summarization_usd` de execuções cujo `executado_em` cai no dia corrente (fuso do Django, `timezone.now()`), mais o custo já acumulado na execução em andamento antes de cada novo lote — motivo: é o dado que já existe e é persistido por execução; não há necessidade de um registro por chamada individual.
- Quando o teto é excedido no MEIO de uma execução, os lotes restantes daquela mesma execução também são pulados (não só o lote que estourou) — motivo: é a leitura natural de "parar de chamar o provedor" no comentário de design da própria setting em `settings.py`.

## Restrições
- Não pode quebrar/interromper a ingestão de itens quando o teto é excedido — todo item continua sendo persistido, só sem resumo automático (cai em `status_revisao=pendente`, mesmo caminho já usado para erro de provedor).
- Sem migração de schema nova (reaproveitar `RegistroExecucaoIngestao` já existente).
- Seguir a convenção já estabelecida no app `catalogo_noticias` de múltiplos módulos em `services/` (não um único `services.py`, que é a convenção-padrão do projeto mas já foi adaptada neste app especificamente para `services/ingestao.py` + `services/deduplicacao.py`) — a nova lógica de orçamento deve seguir esse mesmo padrão de módulo dedicado dentro de `services/`, não lógica solta em `providers/` ou views.
- Suíte completa (204 testes antes desta mudança) deve continuar passando integralmente: `cd backend && DJANGO_DB_ENGINE=sqlite3 DJANGO_DEBUG=true DJANGO_CACHE_BACKEND=locmem ./.venv/Scripts/python.exe -m pytest -q`.

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | código + implementation-history.md |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked |
| 3 | reviewer (obrigatório — ver `Riscos identificados`) | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. Quando o gasto estimado do dia está abaixo do teto configurado, a ingestão de notícias resume normalmente via LLM, sem nenhuma mudança de comportamento observável.
2. Quando o gasto estimado do dia ultrapassa o teto configurado, nenhuma chamada adicional ao provedor de LLM é feita no restante da execução — os itens correspondentes continuam sendo ingeridos e caem em fila de revisão humana (não travam nem são descartados).
3. O gasto estimado do dia corrente é consultável (via `metricas`, junto do restante do painel de observabilidade do negócio), sem exigir consulta manual ao banco.
4. O teto continua configurável via variável de ambiente, sem alteração de código (mesma convenção já usada pelas demais settings `CATALOGO_NOTICIAS_*`).

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Reabrir, mesmo sem querer, um finding já fechado nas 3 rodadas de revisão de `catalogo_noticias` (dedup/direitos autorais) | Alto | Escopo explicitamente exclui `deduplicacao.py` e as funções de detecção de cópia; reviewer instruído a comparar contra `code-review-contract.md` do run `20260902-0727-ingestao-noticias` |
| Checagem de teto mal posicionada permite estourar o orçamento mesmo assim (ex.: só checa uma vez no início da execução, não por lote) | Alto (é o próprio risco de negócio que esta tarefa mitiga) | Critério de aceite 2 testável explicitamente; revisão obrigatória do ponto exato de checagem em `executar_ingestao` |
| Estimativa de custo por token fica sistematicamente errada (provedor real cobra diferente do estimado) | Médio | Documentado como estimativa configurável, não valor exato; decisão de preço real fica associada à escolha do provedor concreto (ainda em aberto) |
| Falha ao persistir/consultar gasto do dia derruba a ingestão inteira (nova dependência de leitura do banco antes de cada lote) | Médio | Não-objetivo/critério técnico: falha ao calcular o gasto acumulado deve, na dúvida, permitir a chamada (fail-open) e logar warning — nunca lançar exceção que interrompa `executar_ingestao` |

## Dependências
Nenhuma dependência externa pendente. Não depende de nenhuma outra execução em andamento.
