<!--
CONTRACT: report
DONO: historian
QUANDO É CRIADO: no fechamento de cada execução (run).
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/report.md
-->

# Report — 20260903-1211-teto-gasto-diario-llm

## Metadados
- **run_id:** 20260903-1211-teto-gasto-diario-llm
- **Período:** 2026-09-03 12:11 → 2026-09-03 13:15
- **Tarefa:** Enforcement do teto de gasto diário de LLM (CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD)
- **Resultado final:** entregue

## Resumo executivo
A setting `CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD` (default 5.0), que antes existia sem nenhum código lendo-a, passou a ser efetivamente aplicada: o custo por chamada ao provedor de LLM agora é estimado a partir de tokens × preço configurável, o gasto acumulado do dia corrente é checado antes de cada lote de resumo em `executar_ingestao`, e a ingestão para de chamar o provedor (caindo no fallback de revisão humana já existente) assim que o teto é ultrapassado, sem interromper a ingestão em si. O gasto do dia, o teto e se ele foi excedido ficam expostos em `metricas.services.painel()`. Uma revisão de código obrigatória (dado o risco financeiro direto do recurso) encontrou 1 finding major — janela de "dia corrente" calculada em UTC em vez do fuso local do projeto, deslocando o corte em 3h e permitindo gastar até o dobro do teto em um mesmo dia-calendário local — corrigido em uma única iteração de remediação com teste de regressão comprovadamente eficaz (verificado por reversão temporária do fix). Um finding minor (concorrência entre execuções paralelas de `executar_ingestao`, cenário "check-then-act" sem lock) foi aceito como risco residual conhecido, não bloqueante na configuração atual do projeto. A 2ª passada de revisão aprovou o resultado (`approve`). Nenhum desvio relevante do plano original quanto a escopo/critérios de aceite — o único desvio foi operacional, no próprio processo de fechamento (ver "Desvios do plano original").

## Métricas
| Métrica | Valor |
|---|---|
| Iterações (implementação ↔ revisão/remediação) | 1 (dentro do limite de 3 — `iteration_count` no run-state.json) |
| Findings de revisão — abertos | 1 (minor — concorrência entre execuções paralelas, aceito como risco residual conhecido, não bloqueante) |
| Findings de revisão — resolvidos | 1 (major — janela UTC vs. fuso local em `gasto_llm_hoje_usd()`) |
| Arquivos de código/testes alterados | 8 (`backend/config/settings.py`; `backend/catalogo_noticias/providers/summarization.py`; `backend/catalogo_noticias/services/orcamento.py` — novo; `backend/catalogo_noticias/services/ingestao.py`; `backend/catalogo_noticias/tests/test_orcamento.py` — novo; `backend/catalogo_noticias/tests/test_summarization_provider.py`; `backend/metricas/services.py`; `backend/metricas/tests/test_custo_llm.py` — novo) |
| Arquivos de documentação alterados | 2 (`README.md`, `ARCHITECTURE.md` — seções 7, 8, 9) |
| Testes adicionados por esta execução | 42 (41 na implementação inicial — suíte subiu de 204 para 245 — mais 1 teste de regressão na remediação) |
| Suíte completa — resultado no fechamento (2ª passada do reviewer) | 256 passed, 0 failed, 0 errors (245 + 1 teste próprio da remediação + 10 testes de outras sessões paralelas no mesmo repositório, em apps fora de escopo: b2b, comunidade, config, credenciamento, identidade, metricas/test_sanity) |
| Veredito final do tester | passed (245 passed, 0 failed) |
| Veredito final do reviewer | approve (2ª passada, após remediação do Finding 1; 256 passed reexecutados de forma independente) |

## Linha do tempo resumida
- 2026-09-03 12:11 — orchestrator abre o run, produz `task-plan.md` e `implementation-contract.md`; revisão de código marcada obrigatória.
- 2026-09-03 12:12–12:20 — executor implementa os 4 pontos do contrato; autovalidação parcial (catalogo_noticias+metricas: 99 passed).
- 2026-09-03 12:20–12:27 — tester verifica de forma independente, roda suíte completa: 245 passed. Veredito passed.
- 2026-09-03 12:27–12:35 — reviewer (1ª passada): `changes_requested`. Finding 1 (major) — janela UTC vs. fuso local. Finding 2 (minor) — concorrência, não bloqueante.
- 2026-09-03 12:35–12:45 — remediator corrige o Finding 1, adiciona teste de regressão comprovadamente eficaz. Finding 2 mantido como risco residual aceito. Suíte completa: 256 passed.
- 2026-09-03 12:45–12:52 — reviewer (2ª passada): Finding 1 resolved; Finding 2 still-open mas aceito. Suíte reexecutada de forma independente: 256 passed. Veredito final: approve.
- 2026-09-03 12:52–12:58 — documenter atualiza README.md e ARCHITECTURE.md.
- 2026-09-03 12:58 — historian (instância original) inicia fechamento, escreve nota prematura afirmando artefatos ainda não produzidos, e é interrompida por rate-limit da API.
- 2026-09-03 (retomada 1) — historian verifica a inconsistência, acrescenta correção em `implementation-history.md`, tenta produzir `report.md`/`HISTORY.md`/`run-state.json` fechado; ferramenta de escrita do sub-agente bloqueia deterministicamente qualquer arquivo chamado "report.md", conteúdo devolvido como texto.
- 2026-09-03 13:15 — orchestrator (sessão principal, sem essa restrição) persiste `report.md`, acrescenta a linha em `HISTORY.md` e fecha `run-state.json`.

## Desvios do plano original
Nenhum desvio de escopo ou de critério de aceite em relação ao `task-plan.md`/`implementation-contract.md`. O desvio foi puramente operacional no processo de fechamento: duas interrupções distintas (rate-limit da API, depois bloqueio de ferramenta para nome de arquivo "report.md" na sessão do sub-agente historian) atrasaram — mas não comprometeram — a persistência dos 3 artefatos formais de fechamento. O conteúdo técnico da execução estava completo e aprovado desde a 2ª passada do reviewer.

## Follow-ups / pendências
- Concorrência entre execuções paralelas de `executar_ingestao` (Finding 2, minor): checagem "check-then-act" sem lock. Não bloqueante hoje (uma única entrada em `CELERY_BEAT_SCHEDULE`). Se o deploy escalar workers Celery horizontalmente, revisitar com lock distribuído (`select_for_update` ou cache/Redis).
- Preço real de LLM ainda é estimativa configurável (`CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS`, default 0.15), não decisão fechada — escolha do provedor de produção permanece em aberto (`ARCHITECTURE.md` seção 8, item 3).

## Artefatos desta execução
- task-plan.md
- implementation-contract.md
- implementation-history.md (3 iterações + nota de fechamento prematura + 2 correções de registro, todas preservadas por convenção append-only)
- code-review-contract.md (2 passadas: 1ª changes_requested, 2ª approve)
- documentation-update.md
- report.md (este arquivo)
