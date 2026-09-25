<!--
CONTRATO: reconciliação de proveniência (documento auxiliar da fase de planejamento)
DONO: subagente de reconciliação/documentação de proveniência
QUANDO É CRIADO: 2026-09-25, durante o planejamento da run 20260925-1433-go-live-producao
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-20260925-1433-go-live-producao/provenance-reconciliation.md
NATUREZA: SOMENTE LEITURA. Nenhum arquivo de código, contrato, estado ou ref Git foi alterado por este documento.
-->

# Reconciliação de Proveniência — 20260925-1433-go-live-producao

## Metadados

- **Data da reconciliação:** 2026-09-25
- **Run de referência:** `20260925-1433-go-live-producao` (status `planning`, fase `planning` concluída; implementação pendente)
- **Artefato:** `agentic-framework/state/run-20260925-1433-go-live-producao/provenance-reconciliation.md`
- **Escopo:** inventário de proveniência do working tree, das refs Git e das runs abertas, com classificação e registro de conflitos — **sem resolver** os conflitos.
- **Método:** auditoria somente leitura (comandos `git status`, `git log`, `git branch`, `git worktree list`, `git reflog`, leitura de `.git/packed-refs`, leitura de `run-state.json`, `stat` de mtimes e parse de AST dos arquivos Python).
- **Comandos de escrita Git executados:** nenhum. Sem `reset`, `clean`, `stash`, `checkout`, `branch`, `commit`, `push`, `fetch` ou `gc`. Sem acesso à VPS.

## 1. Status da reconciliação

**Status: CONCLUÍDA COMO INVENTÁRIO — CONFLITOS ABERTOS E NÃO RESOLVIDOS.**

O que está reconciliado:

- Todos os arquivos modificados e não rastreados do working tree foram inventariados e associados a uma run.
- A divergência entre `HEAD` local e `origin/develop` foi quantificada.
- A duplicação do commit da run `20260924-1721-react-query-migracao` foi confirmada por identidade de árvore.
- A corrupção de `backend/config/settings.py` foi registrada com estado factual, sem atribuição de reparo.

O que **não** está reconciliado (bloqueios para o go-live):

- Origem do reparo de `backend/config/settings.py` — desconhecida.
- Refs divergentes em `.git/packed-refs` — registradas como conflito, deliberadamente não resolvidas.
- Worktree `wt-merge`/`main` em estado *prunable* (dangling) — não tocado.
- Atribuição de uma parcela das modificações rastreadas (ver §4.4) — pendente de decisão humana.

**Regra de bloqueio em vigor:** nenhum reset, clean, stash ou checkout pode ser executado sobre este working tree sem antes resolver esta reconciliação. O motivo técnico está em §5.1.

## 2. Evidências e paths

### 2.1 Estado do repositório

| Item | Valor observado | Comando/fonte |
|---|---|---|
| Branch atual | `develop` | `git rev-parse --abbrev-ref HEAD` |
| `HEAD` | `645aca3bc0e5f175d6573544aee6ce445a1d4b54` | `git rev-parse HEAD` |
| `origin/develop` efetivo | `d1e04564c4bb01efac6329b1d17e29e1286e1749` | `git rev-parse origin/develop` (ref solta) |
| Relação com o remoto | `develop` **ahead 2** de `origin/develop` | `git branch -vv` |
| Últimos commits | `645aca3` ci(frontend) · `948a5b5` feat(frontend) · `d1e0456` docs(deploy) | `git log --oneline` |
| Worktrees | `/home/alex-buttielie/repositorios/portal-noticias 645aca3 [develop]` · `/tmp/opencode/wt-merge bb63cb3 [main] prunable` | `git worktree list` |

`645aca3` e `948a5b5` existem **apenas localmente** — não foram enviados a `origin/develop`, cujo topo é `d1e0456`.

### 2.2 Refs divergentes (conflito registrado)

| Ref | Valor | Natureza |
|---|---|---|
| `.git/refs/remotes/origin/develop` (solta) | `d1e0456` | **Efetiva** — sombreia a entrada empacotada |
| `.git/packed-refs` → `refs/remotes/origin/develop` | `b671a86a1ca3261d37030e5a5b4520604483c70b` | Divergente e obsoleta (2026-09-19, `fix(api): proxy runtime app/api…`) |
| `.git/refs/remotes/origin/main` (solta) | `bb63cb3` |Efetiva |
| `.git/packed-refs` → `refs/remotes/origin/main` | `cbe161e` | Divergente |
| `.git/packed-refs` → `refs/remotes/origin/homolog-retest` | `7eaa8bb` | Ref remota obsoleta |
| `.git/packed-refs` → `refs/remotes/origin/backup/remote-{develop,homolog-retest,main}-20260904` | `486aef2` / `7eaa8bb` / `ab7a709` | Backpoints históricos de 2026-09-04 |

Existe, portanto, **duas_layer de verdade** para `origin/develop`: a ref solta (recente) e a empacotada (antiga). A leitura de qualquer tooling que use o arquivo `packed-refs` diretamente pode ver `b671a86` e concluir que `develop` diverge de forma incorreta. Isso **não foi corrigido** — ver §6 e §8.

### 2.3 Worktree dangling

- `git worktree list` reporta `/tmp/opencode/wt-merge` (branch `main`, `bb63cb3`) com o marcador **`prunable`**: o diretório administrativo correspondente não existe mais, mas a entrada de worktree persiste.
- Impacto: comandos como `git worktree prune` e algumas rotinas de manutenção podem alterar estado; `git branch -D main` ficaria inconsistente com a entrada órfã.
- **Nenhuma ação foi tomada.** Registrado em §7 como arquivo/estado protegido.

### 2.4 Commits da run `20260924-1721-react-query-migracao`

| SHA | Onde | Estado |
|---|---|---|
| `948a5b5` | `develop` (alcançável, `develop@{1}` via `cherry-pick`) | **Commit canônico** |
| `645aca3` | `develop` (alcançável, `develop@{0}`) | Commit de CI subsequente ao canônico |
| `4c57ff04` | Nenhuma branch (`git branch -a --contains 4c57ff04` → vazio) | **Dangling, preservado por reflog** |

Provas de que `4c57ff04` é duplicata exata de `948a5b5`:

- `git rev-parse 948a5b5^{tree}` = `git rev-parse 4c57ff04^{tree}` = `0c294db73f4d84efb992f0a7661398680127e335` (árvores idênticas).
- Ambos têm autor `Buttielie <63355403+Alex-Buttielie@users.noreply.github.com>` e data `Fri Sep 25 12:04:29 2026 -0300`.
- `git reflog HEAD` mostra `4c57ff0 HEAD@{3}: commit:` ocorrido enquanto o HEAD estava em `observability-20260925-1020` (o par `HEAD@{3}`/`HEAD@{4}` é o checkout develop → observability). Depois, `HEAD@{2}` registra o retorno e `HEAD@{1}` o `cherry-pick` para `develop`.
- `git reflog develop` confirma: `develop@{1}: cherry-pick: feat(frontend): reintroduz cache de cliente com TanStack Query…`.

Conclusão factual: o conteúdo foi commitado primeiro na branch errada (`observability-20260925-1020`) e depois reintegrado por cherry-pick em `develop`. O commit na branch errada foi descartado como referência de branch, mas permanece recuperável por reflog. **Nada foi apagado.**

### 2.5 Working tree — arquivos rastreados modificados

| Path | mtime | Linhas do diff | Run associada |
|---|---|---|---|
| `backend/config/middleware.py` | 2026-09-25 10:27:42 | +158/−? (158 linhas alteradas no diff) | `20260925-1020-observabilidade` |
| `backend/config/settings.py` | 2026-09-25 14:01:00 | +167 linhas no diff | `20260925-1020-observabilidade` **com reparo não atribuído** (§2.7) |

Detalhe crítico de `middleware.py` (linhas 11–12 e 87): importa `from .metrics import record_http` e `from .observability import current_task_id`. Esses dois módulos são **não rastreados**. O arquivo rastreado-modificado depende de arquivos que não existem em nenhum commit.

Demais arquivos rastreados modificados, com mtime anterior à janela da run 1020 — ver §4.4 (atribuição não concluída).

### 2.6 Working tree — arquivos não rastreados

| Path | mtime | Linhas | Run associada |
|---|---|---|---|
| `backend/config/observability.py` | 2026-09-25 10:26:45 | 317 | `20260925-1020-observabilidade` |
| `backend/config/metrics.py` | 2026-09-25 10:26:59 | 236 | `20260925-1020-observabilidade` |
| `backend/config/health.py` | 2026-09-25 10:27:17 | 188 | `20260925-1020-observabilidade` |
| `backend/catalogo_noticias/management/commands/agendar_ingestao.py` | 2026-09-24 22:41:52 | — | **Não classificada** (anterior à run 1020) |
| `agentic-framework/state/run-20260925-1020-observabilidade/` (3 arquivos) | 2026-09-25 10:21–10:22 | — | `20260925-1020-observabilidade` |
| `agentic-framework/state/run-20260924-2136-ingestao-noticias/` | 2026-09-24 23:59 | — | Run anterior (conteúdo não inspecionado) |
| `agentic-framework/state/run-20260925-1433-go-live-producao/` | 2026-09-25 14:35–14:45 | — | Run corrente (este diretório) |

Conteúdo de `agentic-framework/state/run-20260925-1020-observabilidade/`: apenas `task-plan.md`, `implementation-contract.md`, `run-state.json`. **Não existem** `implementation-history.md`, `report.md` nem `code-review-contract.md`.

### 2.7 `backend/config/settings.py` — estado factual

Sequência observada:

1. Durante a implementação da run `20260925-1020-observabilidade` (janela 10:24–10:27), o arquivo recebeu as alterações de observabilidade (blocos `OBSERVABILITY_*`, `ANALYTICS_*`, `CORS_EXPOSE_HEADERS`, `CORS_ALLOW_HEADERS`, `TECHNICAL_TELEMETRY_*`).
2. Por relato da auditoria, o arquivo foi **corrompido às 10:31** e depois **reparado sem atribuição**.
3. O mtime atual do arquivo é **2026-09-25 14:01:00** — ou seja, o conteúdo em disco foi escrito novamente **após** a janela da run 1020, por um fator não registrado nesta reconciliação.
4. Estado atual: o arquivo **parseia sem erro de sintaxe** (verificado com `ast.parse`, sem escrita de `.pyc`) e o diff contra `HEAD` é coerente e legível — apenas aditivo, sem vestígio evidente do trecho corrompido.
5. **Natureza do reparo:** reparado, origem desconhecida, requer validação.

O que **não** se pode afirmar com o estado atual das evidências: qual era o conteúdo corrompido, quem ou o que escreveu o reparo, se o reparo é idêntico ao que a run 1020 pretendia, e se as 167 linhas do diff estão completas. A verificação de integridade é apenas sintática; **nenhum teste funcional, `manage.py check` ou suite foi executado** (fora do escopo somente-leitura deste subagente).

### 2.8 branches locais

| Branch | SHA | Observação |
|---|---|---|
| `develop` | `645aca3` | Branch de trabalho da run 1433 |
| `observability-20260925-1020` | `d1e0456` | Branch da run 1020; **não contém o WIP** (aponta para o mesmo commit de `develop` pré-WIP) |
| `main` | `bb63cb3` | Associada ao worktree prunable |
| `fix/ingestao-timeout-500` | `f2a3ae5` | Anterior a `develop`; sem relação com a run 1020 |
| `perf/custo-performance-p0-p2` | `6e61a97` | Já contida em `develop` |

A branch `observability-20260925-1020` **não contém nenhum** dos arquivos de observabilidade: ela aponta para `d1e0456`, o mesmo commit que era o topo de `develop` antes do cherry-pick. O WIP existe apenas no working tree, sem lastro em nenhuma branch. Isso é o principal risco de perda (§5.2).

## 3. Estado das runs envolvidas

### 3.1 `20260925-1433-go-live-producao` (run corrente)

- `status: planning` · `current_phase: planning` · `iteration_count: 0/3`.
- Fases: `planning` **done**; `implementation`, `testing`, `review`, `remediation`, `documentation`, `closing` todas **pending**.
- Nota da fase de planejamento: *"aguardando aprovação dos lotes e reconciliação da run de observabilidade antes de implementação"*.
- Nota da fase de implementação: *"Não iniciar até haver um contrato de slice aprovado e a run 20260925-1020-observabilidade ser reconciliada."*
- `follow_ups` inclui: *"Reconciliar a run 20260925-1020-observabilidade e os arquivos não rastreados existentes antes de qualquer implementação."*
- Artefatos presentes: `task-plan.md`, `implementation-contract.md`, `backlog.md`, `run-state.json` e **este** `provenance-reconciliation.md`.

### 3.2 `20260925-1020-observabilidade` (WIP isolado)

- `status: in_progress` · `current_phase: implementation` · `iteration_count: 0/3`.
- Fases: `planning` **done**; `implementation` **in_progress** desde 2026-09-25T10:24:00-03:00, `finished_at: null`; demais **pending**.
- `blocked_reason: null` — apesar de a implementação estar parada há mais de 4 horas no registro.
- Artefatos: **3** (`task-plan.md`, `implementation-contract.md`, `run-state.json`). Faltam `implementation-history.md`, `report.md` e `code-review-contract.md`.
- O contrato prevê escopo que **não** aparece no working tree: modelos e migrations de eventos de analytics e de execução de ingestão, além de múltiplos apps (`catalogo_noticias`, `feed`, `metricas`, `newsletter`, `assinatura`, `b2b`). A implementação visível cobre apenas `backend/config/`.
- `follow_ups` que nunca foram executados: acesso à VPS, responsáveis/contatos de alerta, soak de 48 h.
- O contrato da run corrente proíbe misturar suas alterações sem reconciliação explícita (1433 `implementation-contract.md`, linha 193).

### 3.3 `20260924-1721-react-query-migracao` (concluída quanto a código)

- `status: in_progress` · `current_phase: documentation` · `iteration_count: 3/3`.
- Fases `planning`, `implementation`, `testing`, `review` **done**; `documentation` **in_progress**; `remediation` e `closing` **pending**.
- Artefatos completos: `task-plan.md`, `implementation-contract.md`, `code-review-contract.md`, `implementation-history.md`, `report.md`, `run-state.json`.
- Veredito registrado: `approve_with_comments`, 0 blockers, 1 major corrigida no review, 1 minor como follow-up; 15/15 critérios de aceite com evidência.
- `run-state.json` desta run está **modificado e não commitado** (mtime 2026-09-25 14:28:50), ou seja, o avanço da fase `documentation` **não está versionado**.
- `follow_ups` relevante: *"Limpar branches/refs e commits externos somente com decisão humana; esta run não faz push."* — o que **proíbe** que este subagente ou o executor resolvam o conflito de refs por conta própria.

## 4. Classificação por run

### 4.1 `20260925-1020-observabilidade` — WIP isolado, preservado

| Item | Caminho | Situação |
|---|---|---|
| Código não rastreado | `backend/config/observability.py` | WIP não rastreado |
| Código não rastreado | `backend/config/metrics.py` | WIP não rastreado |
| Código não rastreado | `backend/config/health.py` | WIP não rastreado |
| Código rastreado-modificado | `backend/config/middleware.py` | WIP sobre arquivo versionado |
| Código rastreado-modificado | `backend/config/settings.py` | WIP **+ reparo não atribuído** |
| Estado da run | `agentic-framework/state/run-20260925-1020-observabilidade/` (3 arquivos, não rastreados) | WIP não rastreado |
| Branch | `observability-20260925-1020` → `d1e0456` | **Não contém o WIP** |
| Artefatos de fechamento | `implementation-history.md`, `report.md`, `code-review-contract.md` | **Inexistentes** |

Classificação: **incompleta, não verificável, não reaproveitável sem lote próprio.** Não é candidata a merge, cherry-pick ou promoção direta.

### 4.2 `20260924-1721-react-query-migracao` — commitada, com pendência documental

| Item | Caminho/SHA | Situação |
|---|---|---|
| Conteúdo | `948a5b5` | Commitado em `develop` (via cherry-pick de `4c57ff04`) |
| CI | `645aca3` | Commitado em `develop` |
| Duplicata | `4c57ff04` | Commitado na branch errada, descartado como branch, **preservado por reflog**; árvore idêntica a `948a5b5` |
| Documentação viva | `ARCHITECTURE.md`, `PROD_DECISOES.md` modificados e **não commitados** (mtime 2026-09-24 17:00–17:01) | Pendente da fase `documentation` |
| Estado da run | `run-state.json` modificado, não commitado (mtime 2026-09-25 14:28) | Pendente |

Classificação: **código íntegro e íntegro em relação ao remoto (2 commits locais à frente); documentação e estado não versionados.** É o candidato mais próximo de estar pronto para o go-live, mas depende dos commits locais serem formalizados e do `run-state.json` ser fechado.

### 4.3 Demais runs

| Run | Evidência | Situação |
|---|---|---|
| `20260924-1535-arquivar-ingestao` | `run-state.json` (`status: closed`), `implementation-history.md` modificados e não commitados; `code-review-contract.md`, `documentation-update.md`, `report.md` não rastreados | Run **fechada no papel** com artefatos fora do versionamento — divergência entre estado e Git |
| `20260924-2136-ingestao-noticias` | Diretório inteiro não rastreado (mtime 2026-09-24 23:59) | Conteúdo não inspecionado nesta reconciliação |
| Demais runs anteriores | `agentic-framework/state/` | Fora de escopo |

### 4.4 Modificações rastreadas de atribuição não concluída

Não modificadas, apenas registradas. Nenhuma foi tocada.

| Path | mtime | Observação |
|---|---|---|
| `ARCHITECTURE.md` | 2026-09-24 17:01:01 | Provável fase `documentation` da run 1721 (§4.2) — **não confirmado** |
| `PROD_DECISOES.md` | 2026-09-24 17:00:50 | Idem |
| `subir-localhost.sh` | 2026-09-24 23:43:09 | Anterior à run 1020 — origem desconhecida |
| `backend/feed/views.py` | 2026-09-24 16:21:51 | Anterior à run 1020 — origem desconhecida |
| `backend/feed/tests/test_p1_feed_cache_indices.py` | 2026-09-24 16:30:17 | Anterior à run 1020 — origem desconhecida |
| `backend/catalogo_noticias/services/deduplicacao.py` | 2026-09-25 10:05:59 | **15 min antes** do início da implementação da run 1020 — origem desconhecida |
| `backend/catalogo_noticias/management/commands/agendar_ingestao.py` (não rastreado) | 2026-09-24 22:41:52 | Origem desconhecida |
| `agentic-framework/state/run-20260924-1535-arquivar-ingestao/{implementation-history.md,run-state.json}` | 2026-09-24 17:15–17:16 | Run declarada fechada, alterações não commitadas |

**Regra de custódia:** qualquer uma destas alterações, se descartada, pode ser perda irrecuperável de trabalho não versionado e não atribuído. Nenhuma pode ser resetada.

## 5. Conflitos e riscos

### 5.1 Risco crítico — `clean`/`reset` quebraria o backend

`backend/config/middleware.py` é **versionado** e importa `backend/config/metrics.py` e `backend/config/observability.py`, que são **não versionados**. Cenários de falha:

- `git clean -fd` remove `metrics.py` e `observability.py` → o backend deixa de importar e falha no start, com `middleware.py` ainda referenciando módulos ausentes.
- `git checkout -- backend/config/settings.py backend/config/middleware.py` reverte o middleware mas **deixa** `health.py`, `metrics.py` e `observability.py` órfãos no disco, gerando um estado incoerente e não rastreado.
- `git stash` (incluindo `-u`) move o WIP para fora da árvore; sem um stash deliberate e nomeado por run, o resultado é equivalente a perda.

**Classificação: crítico.** Mitigação:gate de integridade de proveniência antes de qualquer operação de limpeza (§8).

### 5.2 Risco crítico — WIP sem lastro em nenhuma branch

Nenhum dos cinco arquivos de `backend/config/` alterados/adicionados pela run 1020 está em qualquer commit ou branch. A branch `observability-20260925-1020` aponta para `d1e0456` e não os contém. Se a árvore for perdida, o WIP é perdido — o reflog do Git não o recupera, porque o Git nunca o viu.

### 5.3 Risco alto — refs com duas camadas de verdade

`packed-refs` e as refs soltas divergem para `origin/develop` (`b671a86` vs `d1e0456`) e `origin/main` (`cbe161e` vs `bb63cb3`). Ferramentas ou agentes que leiam `packed-refs` diretamente (ou que operem sobre um clone empacotado) podem tomar decisões com base em estados obsoletos de 2026-09-19.

### 5.4 Risco alto — `settings.py` reparado sem origem

O arquivo tem escrita posterior à janela da run 1020 (mtime 14:01) e nenhum registro de autoria do reparo. O contrato da run 1433 lista *"Resolver a corrupção local de `backend/config/settings.py`"* como item explícito de escopo — o que confirma que a corrupção é conhecida do solicitante, mas **não** confirma que o reparo atual é o correto. Estado: **reparado, origem desconhecida, requer validação.**

### 5.5 Risco médio — `4c57ff04` alcançável só por reflog

O commit é idêntico em árvore a `948a5b5`, logo não há perda de conteúdo. Ainda assim, `4c57ff04` não é alcançável por nenhuma branch: depende exclusivamente da retenção do reflog. Se o reflog expirar, a origem do cherry-pick é perdida. A run 1721 registra explicitamente que limpeza de refs e commits só com decisão humana.

### 5.6 Risco médio — worktree prunable

A entrada `/tmp/opencode/wt-merge` referencia um diretório inexistente. Comandos de manutenção (`git worktree prune`, remoção da branch `main`) podem produzir estado inconsistente. Não tocado.

### 5.7 Risco médio — estado de run divergente do Git

`20260924-1721-react-query-migracao` está `in_progress`/`documentation` com `run-state.json` não versionado, e `20260924-1535-arquivar-ingestao` está `closed` com artefatos não versionados. O `HISTORY.md` (ledger append-only) não foi verificado quanto a estas linhas nesta reconciliação.

### 5.8 Risco baixo — pipeline de assimetria de push

`develop` está 2 commits à frente de `origin/develop`, e o contrato da run 1433 (§ Critério 4) exige que PR não implante código não aprovado em VPS persistente. O estado atual de `origin/develop` é `d1e0456`, que **não** contém o trabalho da run 1721.

## 6. Decisões explícitas

Decisões já tomadas e aplicadas a este documento:

1. **Run `20260925-1020-observabilidade` = WIP isolado.** Não é adotado no go-live da run `20260925-1433-go-live-producao`. Não será integrado, cherry-picked nem promovido.
2. **Preservar o WIP.** Não apagar, não descartar, não arquivar por deleção, não reaproveitar sem um lote próprio com contrato, testes e revisão próprios. Decisão do solicitante, transcrita aqui.
3. **`settings.py` = "reparado, origem desconhecida, requer validação".** Não se afirma que o arquivo foi corrigido; não se afirma que o reparo está correto; não se atribui autoria ao reparo.
4. **Refs divergentes de `packed-refs` registradas como conflito, sem resolução.** Nenhum `fetch`, `pack-refs` ou reescrita de ref foi executado.
5. **Worktree `wt-merge`/`main` intocado.** Sem prune, sem remoção de branch, sem `checkout`.
6. **`4c57ff04` preservado.** Não será apagado, reescrito ou "limpo". Registrado como duplicata por árvore de `948a5b5`, recuperável por reflog.
7. **Nenhum comando Git de escrita nesta reconciliação.** Auditoria estritamente somente-leitura.
8. **Nenhum acesso à VPS.** O estado do host, DNS, TLS e serviços de produção não foi verificado e não é afirmação deste documento.
9. **Documento é o único artefato alterado.** Somente este arquivo foi criado; nenhum outro foi editado.

## 7. Arquivos e estados protegidos

Nada abaixo pode ser apagado, revertido, movido ou "limpo" sem decisão humana explícita e registrada.

**Código e configuração**

- `backend/config/settings.py` (reparado, origem desconhecida, requer validação)
- `backend/config/middleware.py` (versionado, modificado, depende de módulos não versionados)
- `backend/config/observability.py` (não versionado)
- `backend/config/metrics.py` (não versionado)
- `backend/config/health.py` (não versionado)
- `backend/catalogo_noticias/management/commands/agendar_ingestao.py` (não versionado, atribuição desconhecida)
- `ARCHITECTURE.md`, `PROD_DECISOES.md`, `subir-localhost.sh`
- `backend/feed/views.py`, `backend/feed/tests/test_p1_feed_cache_indices.py`, `backend/catalogo_noticias/services/deduplicacao.py`

**Artefatos de run**

- `agentic-framework/state/run-20260925-1020-observabilidade/` (run WIP, não rastreada)
- `agentic-framework/state/run-20260924-2136-ingestao-noticias/` (não rastreada)
- `agentic-framework/state/run-20260924-1535-arquivar-ingestao/` (artefatos não rastreados)
- `agentic-framework/state/run-20260924-1721-react-query-migracao/run-state.json` (modificado, não commitado)
- `agentic-framework/state/HISTORY.md` (ledger append-only: nunca editar nem remover linha existente)

**Estado Git**

- `.git/refs/**` e `.git/packed-refs` — nenhuma reescrita
- `.git/logs/**` — reflogs de `develop`, `HEAD` e `refs/remotes/origin/develop` são a **única** prova da história do cherry-pick e do commit `4c57ff04`
- Entrada de worktree `/tmp/opencode/wt-merge` (prunable) e branch `main`
- Branch `observability-20260925-1020` (mesmo que a run WIP, ainda que vazia de WIP)

## 8. Próximos gates

Nenhum gate abaixo pode ser pulado. A ordem importa.

**G0 — Preservação física do WIP (bloqueante, antes de qualquer operação de Git)**

- Decidir o mecanismo de backup do WIP não versionado (patch gerado a partir de `HEAD` para os 5 arquivos de `backend/config/`, mais cópia dos artefatos da run 1020).
- Somente após o WIP estar preservado fora da árvore, qualquer discussão de limpeza pode ocorrer.
- Referência: §5.1, §5.2.

**G1 — Validação de `settings.py` (bloqueante para o lote de release/proveniência)**

- Validar o arquivo atual funcionalmente: `manage.py check`, import da aplicação, e testes que cubram as chaves novas (`OBSERVABILITY_*`, `ANALYTICS_*`, `CORS_EXPOSE_HEADERS`, `CORS_ALLOW_HEADERS`, `TECHNICAL_TELEMETRY_*`).
- Determinar se as 167 linhas do diff correspondem ao escopo da run 1020 ou se houve perda/adição não atribuída.
- Registrar o resultado como evidência antes de qualquer commit. Referência: §2.7, §5.4.

**G2 — Formalização dos commits locais da run 1721 (bloqueante para o release)**

- Fechar a fase `documentation` da run `20260924-1721-react-query-migracao` e versionar `run-state.json`.
- Versionar `ARCHITECTURE.md` e `PROD_DECISOES.md` (ou descartá-los com decisão humana registrada).
- Commit e push de `948a5b5` e `645aca3`, bringing `origin/develop` ao estado real. Referência: §2.1, §5.8.

**G3 — Decisão humana sobre refs (bloqueante, sem automação)**

- Resolver a divergência `packed-refs` vs refs soltas para `origin/develop` e `origin/main` **apenas** com autorização humana explícita.
- Decidir o destino de `4c57ff04`, da branch `observability-20260925-1020` e das branches `fix/ingestao-timeout-500` e `perf/custo-performance-p0-p2`.
- A run 1721 registra: limpeza de refs e commits externos somente com decisão humana. Referência: §2.2, §2.4, §5.3, §5.5.

**G4 — Saneamento do worktree dangling (bloqueante, sequencial a G3)**

- Decidir entre `git worktree prune` ou recriação do worktree de `main`, após G3.
- Referência: §2.3, §5.6.

**G5 — Atribuição das modificações pendentes (não bloqueante para release, bloqueante para perda)**

- Atribuir `subir-localhost.sh`, `backend/feed/views.py`, `backend/feed/tests/test_p1_feed_cache_indices.py`, `backend/catalogo_noticias/services/deduplicacao.py`, `agendar_ingestao.py` e os artefatos da run 1535 a uma run, ou declará-los órfãos com decisão registrada.
- Referência: §4.4.

**G6 — Formalização do WIP da run 1020 como lote próprio (posterior ao go-live ou em janela própria)**

- Criar run dedicada com contrato, testes e revisão próprios antes de qualquer reaproveitamento do WIP.
- Se a run 1020 for abandonada, fechar o `run-state.json` com `blocked_reason`/`status` coerente e preservar os artefatos. Referência: §3.2, §6.

**G7 — Critérios de aceite de proveniência do contrato mestre (1433)**

- Critério 1: build de release com working tree sujo é **rejeitado**, listando arquivos e motivo.
- Critério 2: DEV/HOMOLOG/PROD implantam o **mesmo SHA validado**, sem depender de arquivos locais não versionados.
- Backlog: `P0-01` (reconciliar working tree e runs abertas) e `P0-09` (CI de release e provenance) dependem diretamente desta reconciliação.
- Referência: `implementation-contract.md` §"Proveniência e release", §"Critérios de aceite", e `backlog.md` P0-01/P0-09.

## 9. Perguntas humanas pendentes

Nenhuma destas perguntas pode ser respondida por agente sem decisão explícita.

1. **Orçamento de perda:** o WIP da run 1020 deve ser preservado por qual mecanismo — patch, branch dedicada, ou só backup externo — e quem executa antes de qualquer limpeza?
2. **`settings.py`:** o reparo das 14:01 foi feito por quem e a partir de qual referência? Deve-se validar contra o contrato da run 1020, ou o arquivo deve ser regenerado do zero a partir de `d1e0456` mais o escopo da run 1020?
3. **Escopo da run 1020:** manter aberta para continuação, ou encerrar como abandonada preservando artefatos? A decisão "não adotar no go-live" implica qual status final no `run-state.json`?
4. **Refs de `packed-refs`:** autorizar a normalização de `origin/develop` (`b671a86` vs `d1e0456`) e `origin/main` (`cbe161e` vs `bb63cb3`)? Quem executa e com qual janela?
5. **`4c57ff04`:** manter recuperável apenas por reflog, ou criar tag/branch de segurança para blindar a origem do cherry-pick?
6. **Branch `observability-20260925-1020`:** ela deve permanecer (como marcador da run) ou pode ser removida depois que o WIP for preservado?
7. **Worktree `wt-merge`:** autorizar `git worktree prune`, ou recriar o worktree de `main`? A branch `main` ainda é necessária?
8. **Push dos commits locais:** autorizar o push de `948a5b5` e `645aca3` para `origin/develop`? O `main` deve ser atualizado com o merge?
9. **Modificações de origem desconhecida** (§4.4): devem ser atribuídas, versionadas ou descartadas com registro? Quem decide caso a caso?
10. **Run 1535 declarada `closed` com artefatos não versionados:** commitar os artefatos restantes ou considerar a run encerrada com a divergência registrada?
11. **Gate de entrada da implementação da run 1433:** este documento é suficiente para unlocking da fase `implementation`, ou a run permanece bloqueada até G0–G4 concluídos?
12. **Linha no `HISTORY.md`:** quem faz o registro no ledger para a run 1433 e para o desfecho da 1020 — o `historian` desta run ou uma run de fechamento própria?

## 10. Limites desta reconciliação

- Auditoria **somente leitura**. Nenhum arquivo de código, contrato, estado, ref ou worktree foi alterado, além da criação deste documento.
- Nenhum teste, build, `manage.py check` ou verificação funcional foi executado. A validação de `settings.py` é **apenas sintática** (parse de AST).
- Nenhum acesso à VPS, ao GitHub remoto, ao DNS ou a serviços externos. Nada aqui afirma ou nega o estado de produção.
- `packed-refs` e refs soltas foram comparados por leitura direta dos arquivos; nenhuma operação de `fetch` foi feita, então o estado real do servidor remoto **não é conhecido** — apenas o estado local.
- O conteúdo de `agentic-framework/state/run-20260924-2136-ingestao-noticias/` não foi inspecionado.
- Este documento **não** afirma que `settings.py` foi corrigido, que o WIP da run 1020 é aproveitável, nem que o go-live pode prosseguir. Ele registra o que se sabe, o que não se sabe e quem deve decidir.

---

*Documento produced em 2026-09-25 para a run `20260925-1433-go-live-producao`. Único arquivo criado: `agentic-framework/state/run-20260925-1433-go-live-producao/provenance-reconciliation.md`.*

---

# 11. Correção datada — refutação de §2.8 e §5.2 (append-only; nada acima foi alterado)

> **Natureza desta seção:** acréscimo. As §1 a §10 acima permanecem **exatamente
> como a reconciliação de planejamento as escreveu**, inclusive onde a afirmação
> está agora registrada como **refutada**. Este lote **não** reescreveu, não
> removeu e não "corrigiu retroativamente" nenhuma delas: o objetivo é que o
> registro falso continue visível e datado, e que ninguém o reutilize.

- **Data da correção:** 2026-09-25 (execução final do lote P0-1, ramo
  `lote-p0-1-final`, base `origin/develop` = `7715dae8cc1a128e5992245ba636036c8a967f28`)
- **Executor desta seção:** subagente de remediação do lote P0-1
- **Fonte da refutação:** `/tmp/opencode/wip-reconciliation.md` (reconciliação
  completa do WIP, 49 652 B) e medição direta de refs nesta execução
- **O que muda:** duas afirmações da reconciliação de planejamento estavam
  **desatualizadas** quando foram escritas e hoje estão **REFUTADAS** por
  medição. Nenhuma delas deve ser citada adiante sem esta ressalva.

## 11.1 §2.8 está REFUTADA — a branch contém o WIP, e a branch tem 17 commits

A §2.8 afirma, no parágrafo final:

> *"A branch `observability-20260925-1020` **não contém nenhum** dos arquivos de
> observabilidade: ela aponta para `d1e0456`, o mesmo commit que era o topo de
> `develop` antes do cherry-pick. O WIP existe apenas no working tree, sem lastro
> em nenhuma branch."*

**Isso era verdade na janela da reconciliação de planejamento e é falso hoje.**
A medição direta mostra que a branch `observability-20260925-1020` aponta para
`cf2fe02748b7f51fb43286adf58b3cfaf9a9e142` e **contém 17 commits à frente** de
`origin/develop` (`7715dae`), em 162 arquivos, `+44352/−2804` (medido por
`git diff --shortstat`). A paridade é `0 atrás / 17 à frente`.

A atribuição dos 17 commits, segundo `/tmp/opencode/wip-reconciliation.md`:

| Qtde | Commits | Atribuição |
|---|---|---|
| 13 | — | run `20260925-1020-observabilidade` |
| 1 | `672ffba` (prefixo `wip(`) | recuperação de WIP órfão da **mesma** run 1020 |
| 2 | `3a676c7`, `cf2fe02` | run **`20260924-2136-ingestao-noticias`** — commitados na branch errada |

Ou seja: **o WIP foi integralmente commitado** desde a reconciliação de
planejamento, e a branch **não** está mais "2 commits atrás" nem "sem o WIP".
O parágrafo final da §2.8 **não pode ser reutilizado** como afirmação
corrente.

## 11.2 §5.2 está REFUTADA — não há mais "WIP sem lastro em nenhuma branch"

A §5.2 classifica como **crítico** o risco:

> *"Nenhum dos cinco arquivos de `backend/config/` alterados/adicionados pela run
> 1020 está em qualquer commit ou branch. […] Se a árvore for perdida, o WIP é
> perdido — o reflog do Git não o recupera, porque o Git nunca o viu."*

**Também refutada.** A premissa "o Git nunca o viu" é falsa no estado medido: o
Git **vê** o WIP, porque ele está commitado. Consequências que decorrem e que
valem registrar:

- O risco de perda **irrecuperável** descrito em §5.2 **não** se sustenta para o
  WIP commitado. Ele **passa a ser** um risco de **contenção cross-run**: `3a676c7`
  versionou 3 arquivos que o `run-state.json` da run 1020 (linha 89) declara
  *"nunca deve ser commitado nesta branch"* — `backend/catalogo_noticias/services/deduplicacao.py`,
  `backend/catalogo_noticias/management/commands/agendar_ingestao.py` e
  `subir-localhost.sh`. Isso é o bloqueio **A-2** de `/tmp/opencode/wip-reconciliation.md`.
- Os **2** restantes da lista de contenção continuam **não commitados** na
  working tree (`backend/feed/views.py` e
  `backend/feed/tests/test_p1_feed_cache_indices.py`) e **esses** sim são
  trabalho sem lastro — ver **B-6** de `/tmp/opencode/wip-reconciliation.md`.
- O `run-state.json` da run 1433 permanece **exclusivo do orchestrator** e
  **fora do diff do executor** (AC-10). Este lote não o criou nem o editou.

## 11.3 O que **não** mudou com esta correção

- **§5.1 (`clean`/`reset` quebraria o backend) permanece VÁLIDA e crítica.** É
  independente de §5.2: o mecanismo é a combinação de `middleware.py` versionado
  com `metrics.py`/`observability.py` não versionados, e as flags do índice
  continuam sendo a forma correta de detectar o estado. Nada nesta seção
  reduz o risco de §5.1.
- **§5.4 (`settings.py` reparado sem origem) permanece ABERTA.** O lote P0-1 faz
  **verificação, não correção** (P0-02 / gate G1); a origem do reparo das 14:01
  continua sem atribuição e continua sendo pergunta humana (§9, item 2).
- **§5.3 (refs de `packed-refs`), §5.5 (`4c57ff04` por reflog), §5.6 (worktree
  prunable), §5.7 e §5.8 permanecem como registrados.** Esta seção não os toca.
- **A regra de bloqueio da §1 ("nenhum `reset`, `clean`, `stash` ou `checkout`
  pode ser executado sem resolver a reconciliação") permanece de pé.** A refutação
  de §2.8/§5.2 **não** autoriza operação destrutiva alguma. Nenhum comando Git
  de escrita foi executado por esta run.

## 11.4 Onde está a reconciliação completa, para quem precisar do detalhe

Este documento **não** foi reescrito e **não** absorveu a reconciliação completa
do WIP, que é um documento distinto e maior. A fonte é:

- **`/tmp/opencode/wip-reconciliation.md`** (49 652 B) — reconciliação completa
  do WIP `observability-20260925-1020`: inventário dos 17 commits, atribuição
  por run, achados A-1..A-6 e B-1..B-6, e **veredito "NÃO ADOTÁVEL"** como base
  de release. É a fonte das duas refutações acima.
- **`/tmp/opencode/p01-tester-report.md`** (30 258 B) — teste independente do
  commit `df20ad3`, com os achados F-1..F-5.

Ambos são **memória externa** (fora do repositório), preservados para consulta.
Nenhum dos dois é artefato deste lote e nenhum foi criado ou alterado aqui.

## 11.5 Impacto no lote P0-1 (uma linha)

Nenhum. Esta seção é **documental**: a base do lote é `origin/develop` (`7715dae`),
e essa decisão **já** estava correta e **independe** de §2.8/§5.2 — o WIP é
**NÃO ADOTÁVEL** como base (6 blockers em `/tmp/opencode/wip-reconciliation.md`)
e vai em lote próprio, por decisão do solicitante.

*Correção datada acrescentada em 2026-09-25 pelo subagente de remediação do lote
P0-1. Append-only: §1–§10 inalteradas.*
