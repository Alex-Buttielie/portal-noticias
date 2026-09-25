<!--
CONTRACT: report
DONO: historian
QUANDO É CRIADO: no fechamento de cada execução (run).
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/report.md
-->

# Report — 20260924-2136-ingestao-noticias

## Metadados
- **run_id:** 20260924-2136-ingestao-noticias
- **Período:** 2026-09-24 21:39 (-03:00) → 2026-09-25 19:47 (-03:00)
- **Tarefa:** Corrigir ingestão de notícias parada — agendamento periódico não roda no modo nativo
- **Resultado final:** entregue

## Resumo executivo
A ingestão de notícias estava parada desde 2026-09-21 23:18 sem gerar erro visível, e a causa raiz não era bug de pipeline: o agendamento é feito por Celery Beat + worker, e o modo nativo (`./subir-localhost.sh` — venv + sqlite + locmem) **nunca iniciou Celery nem Redis**, então a task simplesmente nunca executava. A run entregou um management command `agendar_ingestao` (agendador sem broker, que reaproveita `executar_ingestao()` sem duplicar lógica) integrado ao `subir-localhost.sh`, com verificação de subida, `--stop` que espera a saída e alerta de falha consecutiva. Durante a execução operacional apareceu um segundo problema, mais grave que o primeiro: a primeira rodada não terminava nunca (7h54m para o backlog de 3 dias × 91 fontes), porque o agrupamento de duplicatas é O(n²) com cache que se limpa inteiro; o contrato foi expandido para v2 e entregue uma otimização comportamento-preservante (pré-filtro por limite superior + LRU real + pré-cálculo), medida em 8,6×–10,3× com **grupos de saída idênticos**. O tester deu `passed` nos 10 critérios e a revisão terminou em `approve_with_comments` na 2ª passada, com os 2 major da 1ª passada corrigidos. Houve desvios relevantes: o contrato mudou de versão no meio da run, esta run teve de reparar um `settings.py` corrompido por **outra** run paralela, e duas execuções de subagente morreram por timeout de DNS / HTTP 429 e foram retomadas.

## Métricas
| Métrica | Valor |
|---|---|
| Iterações (implementação ↔ revisão/remediação) | **10 entradas** no `implementation-history.md` (1-9 de execução + 1 de fechamento do historian). Por agente: executor 1-6, tester 1 (Iter. 7), remediator 2 (Iter. 8 integral + Iter. 9 micro-passe), historian 1. `iteration_count` do run-state = **2** (as duas voltas de remediação: 8 e 9, cada uma após uma revisão) |
| Findings de revisão — abertos | **1** (nit de comentário/acoplamento; 0 blocker, 0 major, 0 minor abertos) |
| Findings de revisão — resolvidos | **9** (6 da 1ª passada + 3 da 2ª passada, na micro-passe da Iteração 9) |
| Arquivos alterados | **7** de código/documentação + **7** artefatos de estado = **14**. Código/docs: `agendar_ingestao.py` (novo, 257 linhas), `test_command_agendar_ingestao.py` (novo, 1.036 linhas/30 testes), `deduplicacao.py` (+197/-17), `subir-localhost.sh` (+242/-8), `README.md` (+47/-2), `ARCHITECTURE.md` (+10/-0), `config/settings.py` (reparo cirúrgico, já absorvido e commitado pela run dona do arquivo) |
| Testes adicionados | **30** no arquivo novo (16 do tester interrompido + 8 da Iteração 7 + 6 da Iteração 8); suíte do app `catalogo_noticias` de 147 → **177 passed**, sem nenhum teste existente ajustado |
| Veredito final do tester | **passed** (10/10 critérios de aceite; 177 passed no app, 390 passed nos apps consumidores do dedup; benchmark com grupos idênticos) |
| Veredito final do reviewer | **approve_with_comments** (2ª passada; 1ª passada foi `changes_requested` com 0 blocker / 2 major / 3 minor / 3 nit) |

**Números de resultado (para contexto):** rodada de ingestão com o backlog acumulado: **~7h54m → 1,1-1,5 min** em regime; `agrupar_itens_brutos` em lote de 3.000 itens: **102,12s → 9,96s (10,3×)** sem concorrência e **164,51s → 19,02s (8,6×)** sob carga, com **grupos idênticos** nas duas medições.

## Linha do tempo resumida
A versão detalhada está em implementation-history.md — 10 entradas, com comandos e evidências.
- **2026-09-24 21:39** — planning: diagnóstico fechado (Celery Beat agenda, modo nativo não sobe Celery/Redis; última execução real 21/09 23:18; pipeline saudável). Contrato v1 com 7 critérios.
- **2026-09-24 23:58** — Iteração 1 (executor): command `agendar_ingestao` + bloco do agendador no `subir-localhost.sh` (log, pid file, `--stop`); `bash -n`/`py_compile`/`manage.py check` OK.
- **2026-09-25 07:20** — Iteração 2: a ingestão manual **não termina** (7h23m de elapsed, 1h05m de CPU) e o agendador não é iniciado para não sobrepor rodadas. Diagnóstico do gargalo: `agrupar_itens_brutos` O(n²) sobre o backlog de 3 dias × 91 fontes.
- **2026-09-25 07:47** — a ingestão manual conclui (`registro_id=3`, 5.468 itens, 4.897 grupos, 0 erros de fonte) em **7h54m**. Contrato expandido para **v2** (otimização + benchmark + operação), com 3 critérios novos.
- **2026-09-25 07:51** — Iteração 3: agendador iniciado (pid 129600) usando o comando novo; primeira rodada dispara imediatamente.
- **2026-09-25 07:57** — Iteração 4: 1ª rodada do agendador **conclui** em ~4,5 min (775 itens, `registro_id=4`) — entrega operacional fechada.
- **2026-09-25 12:14** — Iteração 5: benchmark da otimização v2 (102,12s → 9,96s, grupos idênticos). **Restart do agendador bloqueado**: o `settings.py` foi corrompido às 10:31 pela run `20260925-1020-observabilidade` (`IndentationError`, arquivo truncado), o que derrubou também o servidor de dev. Decisão: manter o agendador funcional vivo e **não editar arquivo de outra run**.
- **2026-09-25 15:02** — Iteração 6: reparo cirúrgico do `settings.py` completando a intenção do bloco Sentry (1 hunk, 2 linhas); `py_compile` + `manage.py check` OK; servidor de dev no ar; agendador reiniciado com o dedup otimizado (pid 364572) e rodada fresca concluída (`registro_id=38`) → **critério 10 fechado**. Descoberta: uma segunda instância do agendador (pid 363955) tinha rodado em paralelo e truncado 88 KB de log.
- **2026-09-25 17:50** — Iteração 7 (tester): **passed**. 10/10 critérios, 171 passed, 12 rodadas reais do agendador com intervalo medido de exatamente 15,0 min, mutation check provando não-vacuidade. Registra que a suíte completa do backend tinha 5 falhas **causadas por edição concorrente** da run de observabilidade (`config/metrics.py`).
- **2026-09-25 18:20** — **1ª passada da revisão: `changes_requested`** (0 blocker / 2 major / 3 minor / 3 nit). Os 2 major: janela para 2ª instância no `--stop` e falha do agendador invisível.
- **2026-09-25 18:50** — Iteração 8 (remediator): 6/8 findings corrigidos (espera antes de remover o pid file, escalonamento no 2º sinal, identidade do pid, `flock`, banner verificável, alerta de 3 falhas consecutivas, log em append, validação de `--rodadas`); 177 passed; agendador de produção reiniciado (pid 775406). Findings 4 e 7 **não** tratados por decisão (enhancements).
- **2026-09-25 19:15** — **2ª passada da revisão: `approve_with_comments`**, com os 6 findings da 1ª passada reconfirmados **por medição independente** e 1 minor + 3 nit novos (todos de precisão de mensagem/comentário).
- **2026-09-25 19:46** — Iteração 9 (remediator, micro-passe de 3 itens): redação do 2º sinal (a atomicidade real é **por grupo**, não por rodada), identidade do pid exigindo `*manage.py*agendar_ingestao*` e rechecagem de vivacidade após o banner. 177 passed sem ajustar nenhum teste.
- **2026-09-25 20:05 (carimbo registrado; ~19:37 real)** — documentation: `README.md` (runbook de diagnóstico + subseções do agendador + desempenho do agrupamento), `ARCHITECTURE.md` (parágrafo do modo sem broker) e cabeçalho/`usage()` do `subir-localhost.sh`. Confirmado que o projeto não mantém CHANGELOG e que nenhum outro documento ficou contraditório.
- **2026-09-25 19:44-19:47** — closing (historian): conferência de integridade do histórico, verificação do estado final, `report.md`, linha no `HISTORY.md` e fechamento do `run-state.json`.

## Desvios do plano original
1. **O contrato foi expandido para v2 no meio da run** (Iteração 2 → seção "Versão 2" do `implementation-contract.md`). O plano original tratava só do agendamento; ao executá-lo, a ingestão manual não terminava nunca. A mudança **não foi silenciosa**: está justificada no próprio contrato (causa raiz medida: `agrupar_itens_brutos` O(n²) com cache clear-total, sobre o backlog de 3 dias × 91 fontes) e ganhou 3 critérios de aceite (8-10) e não-objetivos próprios. Sem isso, o objetivo do contrato ("ingestão funcionando") não seria atendido: a rodada nunca terminaria e o registro nunca seria gravado.
2. **Esta run reparou dano de outra run.** Com o `settings.py` corrompido às 10:31 pela run `20260925-1020-observabilidade`, todo comando `manage.py` falhava e o servidor de dev tinha morrido — o restart do agendador (critério 10) estava bloqueado e matar o agendador funcional derrubaria a ingestão. O reparo foi cirúrgico (1 hunk, 2 linhas, completando a `intenção` declarada no próprio comentário do bloco Sentry: init opcional), com `py_compile` e `manage.py check` verdes. **A revisão do bloco cabia à run dona do arquivo** e foi feita por ela depois: commit `5e7fe90`, onde o `pass` do reparo foi trocado por uma chamada real a `reportar_falha_de_init_sentry` (achado MINOR-9 do review de observabilidade). Pendência encerrada por verificação.
3. **Duas execuções de subagente morreram e foram retomadas**: o executor que implementou a otimização v2 (recuperada do código em disco na Iteração 5) e o tester autor dos 16 primeiros testes, interrompido por **HTTP 429** do provedor (recuperado na Iteração 7, que auditou o arquivo herdado e provou que a implementação antiga replicada nele é fiel ao `git HEAD`, 20/20 checagens). Houve também timeout de DNS na mesma janela. Nenhum trabalho foi perdido, mas a run consumiu mais tempo e o reinício do arquivo de testes exigiu auditoria antes de ser aceito.
4. **O servidor Django caiu duas vezes** (10:31 pelo `settings.py` corrompido; novamente ao fim da Iteração 8, não reiniciado por instrução de sessão). Nenhuma das quedas interrompeu a ingestão, porque o agendador é processo próprio e não depende do runserver — o que a run provou em campo.
5. **O ambiente foi compartilhado com outras runs durante toda a execução.** O working tree tinha edições não commitadas de outras runs (`config/*`, `feed/views.py`, `infra/observability/**`, workflows de deploy, `criar_usuario_carga.py`); a documentação e a revisão convergiram para não tocar nelas, e a suíte do backend alternou entre verde e vermelho por causa disso (ver follow-up 6).
6. **O `run-state.json` estava inválido contra o schema ao chegar ao fechamento** (7 chaves fora do schema no objeto `findings`). Reconciliado sem apagar informação: as contagens ficaram em `findings` e todo o detalhe foi para as `notes` da fase `closing`, para `follow_ups` e para este `report.md`. Além disso, os carimbos de tempo de review/remediation/documentation no run-state estão **adiantados** em relação ao relógio real da máquina (evidência: mtime dos arquivos e `git log`); não foram alterados — ver follow-up 7.

## Follow-ups / pendências
Consolidado do `implementation-history.md` (iterações 2, 6, 7, 8, 9) e do `code-review-contract.md` (2ª passada), com o estado de cada item conferido no fechamento.

**Produto / operação (os que importam de verdade)**
1. **As outras 4 tasks periódicas do beat têm exatamente o mesmo gap que a ingestão tinha.** Confirmado por leitura do `CELERY_BEAT_SCHEDULE` (`backend/config/settings.py`, ~linhas 703-731): `assinatura.tasks.processar_vencimentos`, `newsletter.tasks.enviar_newsletters_manha` (crontab 7:00), `newsletter.tasks.enviar_newsletters_noite` (crontab 19:00) e `b2b.tasks.verificar_alertas` **nunca executam no modo nativo** — só a ingestão ganhou um agendador sem broker. Ou todas ganham o mesmo tratamento, ou o modo nativo deve ser declarado oficialmente "sem execução periódica" na documentação. (O `task-plan.md` já lists este item como fora de escopo; é o follow-up mais estrutural que sobrou.)
2. **Decisão de produto pendente sobre `CATALOGO_NOTICIAS_LLM_API_KEY`** (verificada no fechamento: continua **vazia**, `len=0` em `backend/.env`). Com a chave vazia o `SummarizationProvider` usa resumo local derivado de título/fonte e **tudo cai em revisão humana** — ou seja, o custo de operação de um agendador que roda a cada 15 min está sendo pago sem resumo por LLM. Definir a chave (ou assumir explicitamente o modo local como estado desejado) é decisão de produto, não de engenharia.
3. **`ESPERA_PARADA_SEGUNDOS=15` vs. duração de rodada.** Com rodadas de 1,1-1,5 min o limite nunca é atingido; **com o backlog de 7h54m por rodada o `--stop` interrompe a rodada no 2º sinal** (comportamento deliberado e avisado no log). Se a perda da rodada em curso for inaceitável em algum contexto, aumentar o limite ou fazer o 2º sinal só quando o processo estiver no intervalo entre rodadas.

**Melhorias de código (nenhuma bloqueia)**
4. **Enhancement deliberadamente não tratado (Finding 4, 1ª passada):** o pré-filtro do dedup é **0,63×** (mais lento) no caso degenerado em que nada é podado — 120 títulos em 2 templates quase iguais, custo absoluto de 49 ms contra 8,6-10,3× no caso de ganho. Números para quem mexer no limiar: 0,86× / 0,63× / 1,74× / 8,6-10,3×.
5. **Enhancement deliberadamente não tratado (Finding 7, 1ª passada):** a assinatura entrelaçada de `_bound_similaridade` (`... pesos_ordenados_a, peso_uniao_a, pesos_ordenados_b, peso_uniao_b`) torna uma troca parcial silenciosa e catastrófica. Mudança mecânica: agrupar em `dados_item = (pesos_ordenados, peso_uniao)` — a fazer quando o dedup for mexido por outro motivo. `deduplicacao.py` fica intocado e provadamente correto (0 podas indevidas em 1,95M de pares).
6. **Nit residual (único finding em aberto, 2ª passada):** o `grep -F 'Agendador de ingestão iniciado'` amarra o script a uma string exata do log Python (direção de falha segura: aviso, nunca falso sucesso) e a afirmação da Iteração 8 (d)(iii) — de que a verificação do banner fica fora da seção crítica do lock — está **errada** (ela está dentro). Efeito prático benigno; corrigir o comentário e considerar um banner estruturado por quem mexer no lock.
7. **Backoff de falha no agendador** (registrado como follow-up pelo reviewer, não como finding): as 3 falhas que precedem o alerta já pagaram 3 varreduras completas dos 91 feeds. O alerta existe; o backoff (que mudaria o tempo de recuperação) não foi implementado.
8. **`flock` não protege uso manual.** Ele fecha a corrida de dois `./subir-localhost.sh`, mas `manage.py agendar_ingestao` rodado à mão em outro terminal não conhece o lock; proteção contra uso manual ficou fora do escopo. Os pid files de backend/frontend seguem o padrão pré-existente (sem identidade de processo) — o contrato aceitou isso explicitamente.

**Verificados e encerrados no fechamento (registrados para não virarem pendência falsa)**
9. **Revisão do bloco Sentry do `settings.py` — FEITO** pela run `20260925-1020-observabilidade` (commit `5e7fe90`); o `pass` do reparo cirúrgico desta run foi substituído por `reportar_falha_de_init_sentry`. Nada a fazer.
10. **`backend/config/metrics.py` quebrado (5 falhas na suíte `config/`) — SUPERADO**: `MAX_OBSERVATIONS` está de volta; `test_health_checks.py` e `test_observability_redaction.py` passam. Estado real agora: **223 passed / 2 failed**, e as 2 falhas estão em `config/tests/test_exposicao_metricas.py`, arquivo **untracked** da run paralela de observabilidade, ainda em refactoração. Nenhuma falha restante é desta run.
11. **Observação de ambiente (não é pendência desta run):** o frontend em `:3000` respondia **HTTP 500** durante boa parte do fechamento, por alterações não commitadas da run paralela de react-query — fora do escopo desta run, e **`:3000` respondeu 200 na conferência final**.

## Estado final verificado
- **Agendador:** vivo e **único**, pid **775406** (`/tmp/brd-agendador.pid`), log `/tmp/brd-agendador.log`; última rodada confirmada "Rodada 4/infinitas concluída (registro_id=57, 138 itens, 0 erro(s) de fonte)" às 19:34:29, intervalo de 15 min preservado, nenhum alerta de falha consecutiva.
- **Backend:** `http://127.0.0.1:8000/healthz` → **HTTP 200**.
- **Frontend:** `http://127.0.0.1:3000/` → **HTTP 200** (ver observação 11).
- **`CELERY_BEAT_SCHEDULE` e `docker-compose`: intocados** (critério 7 verificado por `git diff` e por igualdade byte a byte da linha do beat entre HEAD e árvore).

## Artefatos desta execução
- `agentic-framework/state/run-20260924-2136-ingestao-noticias/task-plan.md`
- `agentic-framework/state/run-20260924-2136-ingestao-noticias/implementation-contract.md` (v2)
- `agentic-framework/state/run-20260924-2136-ingestao-noticias/implementation-history.md` (10 iterações)
- `agentic-framework/state/run-20260924-2136-ingestao-noticias/code-review-contract.md` (1ª e 2ª passadas — revisão **obrigatória** pelos gatilhos (a) moderação/critérios de publicação e (b) diff acima de ~300 linhas)
- `agentic-framework/state/run-20260924-2136-ingestao-noticias/documentation-update.md`
- `agentic-framework/state/run-20260924-2136-ingestao-noticias/report.md` (este)
- `agentic-framework/state/run-20260924-2136-ingestao-noticias/run-state.json` (fechado, válido contra o schema)
