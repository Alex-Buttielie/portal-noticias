<!--
CONTRATO: implementation-contract (lote P0-1 — versão 3)
DONO: executor do lote P0-1
QUANDO É CRIADO: 2026-09-25, durante a execução do lote P0-1 da run 20260925-1433-go-live-producao
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-20260925-1433-go-live-producao/implementation-history.md
-->

# Implementation History — Lote P0-1 "Proveniência e gate de release (repo-only)"

## 1. O que este lote entregou

| Item de backlog / gate | Entrega | Onde |
|---|---|---|
| **P0-01b** (re-derivação do estado Git) | baseline re-derivada com timestamp, refs, worktree, stash, paridade, `4c57ff04`, com atribuição por run de cada item | `lote-p0-1-evidencias.md` §1 e §2 |
| **P0-02 / G1** (verificação de `settings.py`, sem edição) | `ast.parse` + `compile()` in-memory: **OK**; sem `__pycache__`; arquivo não editado. `manage.py check`: **SKIP com motivo exato** | `lote-p0-1-evidencias.md` §3 |
| **P0-09** (gate determinístico) | `scripts/release/verificar-proveniencia.sh`, read-only, fail-closed, executável, sem rede/segredo/Git de escrita, exit codes `0/1/2` | repositório |
| **AC-6 / R-1** | risco PR → VPS registrado como **aceito, aberto, não mitigado, não coberto pelo gate, não bloqueante**, com exigência de aceite assinado no go/no-go | `CI-CD.md`, `PROD_DECISOES.md`, `infra/DEPLOY.md`, este arquivo |
| **R-2** | divergência de domínio registrada, sem alteração de workflow | idem |
| **AC-7 / AC-8** | uso, contrato, cobertura, não-cobertura e a dependência de branch protection (HD-2) documentados | `CI-CD.md`, `PROD_DECISOES.md`, `infra/DEPLOY.md` |

**Nada mais foi entregue e nada mais foi tocado.** Em especial: nenhum arquivo em
`.github/`, nenhum backend/frontend de aplicação, nenhum `.gitignore`, nenhum
`.env*`, nenhuma migration, nenhum lockfile, nenhuma run anterior, nenhum
`run-state.json`, nenhuma VPS, DNS, credencial, banco, migration ou pipeline.

## 2. Arquivos alterados por este lote

| Caminho | Ação | Tamanho/forma |
|---|---|---|
| `scripts/release/verificar-proveniencia.sh` | criado, `chmod 755` | novo, executável |
| `agentic-framework/state/run-20260925-1433-go-live-producao/lote-p0-1-evidencias.md` | criado | novo |
| `agentic-framework/state/run-20260925-1433-go-live-producao/implementation-history.md` | criado (este arquivo) | novo |
| `CI-CD.md` | acréscimo seccionado ao final | `+110 −0` |
| `PROD_DECISOES.md` | acréscimo seccionado ao final | `+72 −0` |
| `infra/DEPLOY.md` | acréscimo seccionado ao final | `+76 −0` |

Nenhum outro arquivo foi criado, editado, movido ou apagado. Todos os arquivos
não rastreados e modificados que existiam antes do lote continuam existindo, com
o mesmo conteúdo: nada foi descartado, resetado, limpo, stashed ou
"normalizado".

## 3. Decisões tomadas neste lote (com alternativa descartada)

1. **Baseline em `lote-p0-1-evidencias.md`, opção (b) do contrato.**
   Alternativa descartada: extensão aditiva de `provenance-reconciliation.md`
   (opção (a)). Motivo: aquele arquivo é **inventário de fase de planejamento**,
   já tem dono, e a instrução de escopo proíbe editá-lo; além disso, misturar
   snapshot de planejamento com re-derivação executada no mesmo arquivo exigiria
   marcar cada bloco como medição datada, com risco real de leitura como estado
   atual. Escolher (b) mantém o snapshot congelado e a medição executada em
   artefatos separados, ambos referenciados. Nenhum terceiro documento foi
   criado.
2. **`manage.py check` pulado com motivo, não executado.** Alternativa
   descartada: executá-lo mesmo assim (o `.env` seria importado para o processo)
   ou criar um fixture copiando `backend/` para `/tmp`. Ambas violam o lote: a
   primeira acessa segredo; a segunda produziria evidência de um ambiente que
   não é o árbol real, com `BASE_DIR` diferente, e poderia ser lida como
   validação do `settings.py` de produção. Registrado como `SKIP` com o motivo
   exato (`BL-1`) e encaminhado a GP-1b.
3. **Gate como bash + engine python3 por `stdin`.** Alternativas
   descartadas: (a) só bash com `grep`/`git grep` — perderia parse real de
   Python/YAML e o controle de não-vazamento; (b) engine em arquivo separado
   ao lado do script — criaria um arquivo fora da lista de escrita autorizada e
   criaria a impressão de dependência extra. Com o engine embutido, não há
   dependência nova, não há arquivo temporário e não há `__pycache__`.
4. **Sem cor e sem timestamp na saída.** Alternativa descartada: cor quando
   TTY. A saída é sempre idêntica, o que permite diff entre execuções e entre
   agentes; `--json` nunca contém cor nem timestamp.
5. **Regra de conflito restrita a `^={7,}$` (linha inteira).** Medido: a forma
   frouxa (`^={7,}` sem fim de linha) produz falso positivo em saída de pytest
   versionada no próprio repositório. A forma adotada (`^<{7}`, `^>{7}`,
   `^={7,}$`) cobre os três marcadores exigidos pelo contrato e tem **zero**
   falso positivo nos 794 arquivos rastreados.
6. **Filtro de placeholder/shape na regra genérica de segredo, explícito e
   contabilizado.** Sem ele, a regra acusaria 126 candidatos no repositório real
   (senhas de teste, `os.environ.get(...)`, placeholders em documentação) e o
   gate seria inaproveitável. Com ele: **0** falso positivo e **1** detecção
   real em literal sintético. O número de candidatos descartados aparece no
   detalhe da checagem, sem valor — a transparência não custa sigilo.
7. **Checagem extra `sem-ocultacao` (`assume-unchanged`/`skip-worktree`)**
   além dos 7 casos mínimos do contrato: sem ela, o gate seria contornável
   escondendo modificação de arquivo rastreado (vetor de bypass do eixo de
   segurança). Não é bypass: é falha fechada.
8. **Regra genérica aceita com prefixo** (`API_TOKEN`, `DJANGO_SECRET_KEY`,
   `AWS_SECRET_ACCESS_KEY`). Descoberta na própria execução: a primeira versão,
   com `\b` antes de `token`, **não detectava** `API_TOKEN` (o `_` é caractere de
   palavra, logo não há fronteira) — o teste sintético falhou, a regra foi
   corrigida e a medição de falso positivo foi refeita (0). Registrado porque o
   teste_negative provou que a evidência não é decorativa.
9. **`sys.excepthook` no engine** para converter erro inesperado em bloco
   fail-closed (motivo explícito, exit `1`, `--json` válido), em vez de
   traceback. Provado com cópia do script em `/tmp` e exceção injetada (caso O).
10. **Documentação apenas por acréscimo seccionado** (0 linha removida nos três
    arquivos), com o título único exigido pelo contrato, afirmação explícita de
    que nada de CI/CD foi alterado, e R-1 descrito em todos os três documentos
    como aceito/aberto/não mitigado/não coberto/não bloqueante **e** com
    exigência de aceite assinado no go/no-go no mesmo parágrafo.

## 4. Comando do gate entregue (contrato da CLI)

```
scripts/release/verificar-proveniencia.sh [--expected-sha <40-hex>] [--repo <dir>] [--json]
scripts/release/verificar-proveniencia.sh --help
```

| Exit | Significado |
|---|---|
| `0` | aprovado (todas as checagens ok **e** `--expected-sha` informado e igual ao `HEAD`) |
| `1` | reprovado: checagem falhou, não pôde rodar, ou resultado incompleto (inclui `--expected-sha` ausente) |
| `2` | uso incorreto |

Cobertura: repositório/ferramentas; `HEAD` × SHA esperado; árvore rastreada
limpa; ausência de não rastreado (respeitando `.gitignore`); ausência de
`assume-unchanged`/`skip-worktree`; ausência de marcador de conflito; ausência
de segredo aparente; `.py` rastreado faz parse; `.yml`/`.yaml` rastreado faz
parse.

Garantias de construção: não cria/altera/move/apaga arquivo; não usa arquivo
temporário; não executa Git de escrita; não acessa rede nem remoto; não lê
variável de ambiente com credencial; não exige segredo; não imprime valor de
segredo; falha fechada; determinístico.

## 5. Comandos executados (resumo) e resultados

Todas as validações do contrato, seção "Comandos de validação", itens 1 a 6,
foram executadas. Resultado por item:

| Item | O que | Resultado |
|---|---|---|
| 1 | baseline de proveniência (branch, `HEAD`, `origin/*`, paridade, refs, `status -uall`, `diff`, untracked, `log`, `worktree`, stash, `4c57ff04` por `cat-file`/`for-each-ref --contains`/`rev-list`/`reflog`) | feito, 2 medições carimbadas; ver `evidencias` §2 |
| 2 | `ast.parse` + `compile()` de `settings.py`; `manage.py check` se seguro | `SETTINGS_PY_OK`; `manage.py check` **SKIP** (BL-1) |
| 3 | gate: `test -x`, `bash -n`, `--help`, sem SHA, com SHA, SHA divergente, SHA inválido, `--json`, caso negativo no working tree real, prova de read-only, prova de não-vazamento com literal sintético | todos os exit codes como esperado; caso negativo real **reprova (1)**; não-vazamento **0/0/0/0** |
| 4 | ausência de `__pycache__`/`.pyc` | vazio |
| 5 | CI/CD intocado (status, diff, untracked, stash, sha256 de todos os arquivos) | tudo vazio; sha256 idêntico |
| 6 | diff confinado e custódia de `run-state.json` | 9 modificados + 20 não rastreados, todos autorizados ou pré-existentes; `.github/` vazio; `run-state.json` intocado |

Suíte completa do gate em fixture descartável **fora** do portal:
**`PASS=61 FALHA=0`** (`/tmp/opencode/p0-1/testes-gate.sh`, log em
`fixture-testes.log`; fixtures apagados ao final). Casos cobertos: árvore
limpa+SHA ok (0); rastreado modificado; rastreado removido; não rastreado;
ignorado por `.gitignore`; SHA divergente; SHA ausente (incompleto); segredo
sintético rastreado; segredo em não rastreado; conflito; Python inválido;
Python inválido com segredo na mesma linha; YAML inválido; YAML de workflow
com `on:`; sete formas de uso incorreto; `--help`; repositório não-Git;
`skip-worktree`; read-only (status + `.git/index` + conjunto de arquivos);
determinismo (byte a byte); falha fechada por erro interno; SHA em caixa alta.

## 6. Evidência de read-only e de não-mutação

- Nenhum comando Git de escrita: `add`, `commit`, `push`, `merge`, `rebase`,
  `reset`, `clean`, `checkout`, `switch`, `stash`, `restore`, `apply`, `prune`,
  `gc`, `fetch` — **nenhum**. Só `rev-parse`, `status`, `diff`, `log`,
  `for-each-ref`, `cat-file`, `rev-list`, `ls-files`, `stash list`,
  `worktree list`, `reflog`, `show`, `branch -vv`.
- `git status --porcelain=v1 -uall` idêntico antes e depois das 3 execuções do
  gate no portal.
- `.git/index` do portal com mtime e tamanho inalterados
  (`1790362418:99854`); o gate usa `GIT_OPTIONAL_LOCKS=0` para não refrescar o
  índice, e passa ao Git um ambiente enxuto **sem nenhuma variável `GIT_*`
  herdada** (evita injeção de `GIT_DIR`/`GIT_WORK_TREE`/`GIT_INDEX_FILE`) e com
  `--no-ext-diff --no-textconv`.
- Nenhum `__pycache__`/`.pyc` criado; nenhum arquivo temporário criado pelo
  gate; nenhum byte alterado nos arquivos inspecionados.
- `.github/` byte a byte idêntico (6 arquivos, sha256 comparados antes/depois).
- Arquivos protegidos: **nenhum foi editado por este lote**. Digests observados
  (pontuais — ver `evidencias` §6):
  `settings.py` `82a33dd7…` (inalterado de T0 a T2, e igual ao `HEAD`),
  `middleware.py` `bf7aa9c7…` (inalterado), `.gitignore` `b1ddf34e…`,
  `.env.localhost` `5426c804…`, `.env.production.example` `2c352c57…`,
  `backend/.env` (7143 B, mtime 2026-09-21 20:07, **nunca lido** — apenas
  `ls -l`).
  Exceção a registrar com honestidade: `health.py`, `metrics.py` e
  `observability.py` **também não foram editados por este lote**, mas mudaram
  de digest **por ator externo, com o lote em execução** (`evidencias` §1.1,
  finding **F-1b**). Os digests desses três arquivos são observações
  pontuais, não garantia de estado.

## 7. R-1 — risco de supply chain PR → VPS: aceito e aberto

**O que existe hoje e continua existindo:** `.github/workflows/deploy-homolog.yml`
dispara em `pull_request` para `main`, delega ao `deploy.yml` e implanta na VPS
persistente em `/home/apps/portal-homolog` (3102/5102) com `git_mode: pr`,
`pr_number` e `verify_ref` preenchido pelo SHA do head do pull request. Ou
seja: **código de pull request não aprovado pode rodar em uma máquina que tem
segredos**.

- Situação padronizada: **ACEITO** (decisão do solicitante) e, por isso, **NÃO
  BLOQUEANTE para o go-live**; permanece **ABERTO**, **NÃO MITIGADO**, **NÃO
  BLOQUEADO** e **NÃO COBERTO PELO GATE** (o gate inspeciona o repositório local
  e não participa de nenhum pipeline).
- Este lote **não** alterou, **não** mitigou, **não** bloqueou e **não**
  compensou esse caminho. Nenhum arquivo em `.github/` foi editado, criado,
  movido ou removido (sha256 idêntico). Nenhuma sugestão de correção foi feita.
- **Como não bloqueia o go-live, exige aceite explícito e assinado no go/no-go**,
  registrando qual é o caminho afetado, o que está sendo aceito, por quanto
  tempo e quem assinou. O go/no-go lista R-1 como **aceito**, nunca como
  resolvido.
- A decisão futura sobre substituir o caminho (branch de promoção,
  `workflow_dispatch` com SHA explícito, ou desabilitar o deploy por PR) é de
  **lote próprio com revisão de CI/CD** (HD-1) e não é precondição de
  lançamento.
- O gate entregue **não** é apresentação de cobertura desse risco: em nenhum
  documento deste lote R-1 aparece como resolvido, mitigado, bloqueado ou
  coberto.

**R-2 (divergência de domínio):** canônico do programa é
`https://portal-noticias.com/`; os workflows usam `portal-noticias.com.br`
(DEV/HOMOLOG/PROD e `www`). Registrado, **não** corrigido; correção em lote
posterior, sem mudar estrutura, gatilhos ou comportamento. Nenhum valor de
domínio em workflow foi alterado (`git diff HEAD -- .github/workflows/` vazio).

## 8. Limitações declaradas da entrega

- O gate **só bloqueia de fato** com branch protection do GitHub configurada
  (PR obrigatório) **e** registro como required status check. Hoje **nenhum
  pipeline foi alterado**, então nenhuma das duas condições existe: o gate roda
  **somente quando alguém o invoca**. Configurar branch protection sem check
  registrado não torna o gate obrigatório. **HD-2** e **HD-6** são
  pré-requisitos de eficácia, não de entrega; HD-2 não bloqueia o go-live.
- Detecção de segredo é **heurística**: regras específicas (chave privada,
  AWS, GitHub, Slack, Stripe, Google API, webhook) mais uma regra genérica com
  filtro de placeholder. Valor nunca é exibido. Falso positivo e falso negativo
  são possíveis; ampliar a lista é lote de qualidade.
- O gate não valida/pina host key (`known_hosts`) — atribuído a WS-03/GP-2a.
- O gate não compara `develop` × `origin/develop` (paridade remota): isso
  exigiria estado de remoto e está fora do contrato da CLI. A paridade é
  medida na baseline, separadamente.
- `backend/config/settings.py` está **sintaticamente válido** (G1). Isso **não**
  afirma prontidão funcional: `manage.py check`, import da aplicação e testes
  das chaves novas são de **GP-1b / P0-02b**, e dependem de ambiente sem
  `backend/.env`.

## 9. Pendências e findings abertos por este lote

| ID | Pendência | Natureza | Destino |
|---|---|---|---|
| **F-1** | **Evento externo de Git durante o lote**: checkout para `observability-20260925-1020`, fast-forward para `7715dae` e commit `672ffba` versionando o WIP da run 1020 (18:53:32–18:53:38Z). Decisão com efeito de release tomada fora deste lote | finding factual, não revertido (reverter Git é decisão humana) | **orchestrator + HD-5/G0/G2**; registrado em `evidencias` §1 |
| **F-1b** | **Segundo evento externo, com escrita de código de aplicação durante o lote**: `health.py`, `metrics.py` e `observability.py` foram reescritos (18:59:46Z–19:00:37Z, +341/−53 linhas sobre o commit `672ffba`) por ator externo. Como o commit versionou a versão **anterior**, o trabalho novo está fora de qualquer commit — WIP sem lastro, o risco §5.2 da reconciliação. `settings.py` e `middleware.py` **não** foram afetados e G1 foi reexecutado com o mesmo resultado | finding factual; não revertido; digests destes 3 arquivos são observações pontuais | **orchestrator + HD-5/G0**; registrado em `evidencias` §1.1 |
| **F-1c** | O working tree **mudou duas vezes sob os pés deste lote** (HEAD e código de aplicação). Qualquer medição de proveniência neste repositório é válida apenas com timestamp | risco de prova; a baseline T0 e o estado T2 estão ambos registrados | **orchestrator**: nenhum gate de proveniência deve ser considerado válido sem re-derivação no momento da decisão |
| **F-2** | `settings.py`: reparo de origem não atribuída (mtime 14:01, posterior à janela da run 1020) | finding factual | **HD-5**; o G1 sintático passa, a validação funcional é de **GP-1b** |
| **F-3** | `manage.py check` não executado (BL-1) | bloqueio honesto, sem bypass | **GP-1b** em ambiente sem `backend/.env` |
| **F-4** | Itens com "origem não determinada" na baseline: `deduplicacao.py`, `agendar_ingestao.py`, `backend/feed/views.py`, `backend/feed/tests/test_p1_feed_cache_indices.py`, `subir-localhost.sh` | atribuição impossível sem decisão humana | **HD-5** |
| **F-5** | Divergência ref solta × `.git/packed-refs` (`origin/develop`, `origin/main`, `homolog-retest`) segue aberta | registrada, **não** normalizada | **G3/D-08** |
| **F-6** | Worktree `/tmp/opencode/wt-merge` segue `prunable` | intocado | **G4** |
| **F-7** | Snapshot da reconciliação de planejamento divergiu do estado real (citava `ARCHITECTURE.md` e `run-state.json` da run 1721 como modificados; não estão) | lesson learned: não usar snapshot como estado Git | registrado em `evidencias` §2.3 |
| **F-8** | Diretório de estado da run é não rastreado e reprova o gate por isso | leitura esperada e correta | **G5/D-08**; `.gitignore` **não** editado |
| **F-9** | Cobertura de testes do próprio script é evidência manual (`PASS=61` em driver fora do repositório), não suíte versionada | follow-up 12 do contrato | lote de qualidade |

Nenhum finding foi marcado como resolvido por este lote.

## 10. O que este lote explicitamente não fez

- Não tocou em `.github/` (byte a byte idêntico), não criou/modificou
  workflow, gatilho, job, `if`, `needs`, matriz, `environment` ou `secrets`.
- Não registrou o gate em nenhum pipeline e não documentou que ele roda
  automaticamente.
- Não fez commit, push, merge, reset, clean, stash, checkout, switch, restore,
  branch, prune, gc nem fetch; não editou `.gitignore`, `.env*`, migrations,
  lockfiles, frontend de aplicação ou runs anteriores.
- Não acessou VPS, DNS, credencial, banco, migration, `known_hosts` nem
  pipeline; não executou `ssh`/`scp`/`rsync`/`pm2`/`manage.py migrate`.
- Não corrigiu `settings.py` nem qualquer outro arquivo de aplicação.
- Não escreveu nem editou
  `agentic-framework/state/run-20260925-1433-go-live-producao/run-state.json`
  (custódia do orchestrator, AC-10) nem qualquer outro arquivo de estado da run.
- Não fez validação/pinning de host key (WS-03/GP-2a) nem alterou domínio em
  workflow (R-2).
- Não fez revisão de qualidade do que entregou: essa revisão é do reviewer
  independente (segurança, CI/CD não-regressão, veracidade documental,
  custódia de `run-state.json`).

## 11. Estado do arquivo para o orchestrator

- Diff do executor: 6 arquivos, todos na lista de escrita autorizada (§2).
- `run-state.json`: **intocado**; o orchestrator o atualiza **depois** deste
  lote, com base em `lote-p0-1-evidencias.md`, no veredito do tester e no
  `code-review-contract.md`.
- Veredito do executor: **entrega concluída dentro do escopo**, com bloqueios e
  findings honestos registrados (BL-1, F-1, F-1b, F-1c, F-4) e **sem nenhuma
  alegação** de que R-1 foi resolvido, mitigado, bloqueado ou coberto pelo
  gate, nem de que o gate já é barreira efetiva.
- **Ressalva operacional relevante para o orchestrator:** o repositório foi
  alterado por ator externo **duas vezes durante** este lote (§1 e §1.1). O
  working tree nunca esteve estável. As medições T0 (18:50:15Z) e T2
  (19:00:39Z) estão ambas registradas com timestamp; qualquer decisão de
  release precisa de **nova re-derivação** no momento da decisão, porque o
  estado observado aqui já pode ter mudado.

*Executor do lote P0-1, 2026-09-25.*

---

# Iteração 1 — Remediação de T-D1, T-D2 e T-D4 (append-only; nada acima foi alterado)

> **Dono:** subagente remediator, contratado **exclusivamente** para corrigir o
> defeito de gate encontrado pelo testador (**T-D1**), propagar a correção para as
> afirmações documentais (**T-D2**) e fechar a lacuna de cobertura de teste
> (**T-D4**). **Janela:** 2026-09-25T19:19:17Z → 2026-09-25T20:50Z (UTC).
> **Escopo de escrita:** `scripts/release/verificar-proveniencia.sh`,
> `lote-p0-1-evidencias.md` (§10), este rodapé e o rodapé datado do contrato do
> lote. **Nada mais foi tocado** — nenhum arquivo de WIP, nenhum
> `backend/config/**`, nenhuma migration, nenhum lockfile, nenhum frontend,
> `.github/`, `.env*`, `run-state.json`, `settings.py`, nenhuma run anterior e
> **`test-report.md`**. **Nenhum comando Git de escrita no portal**; nenhum acesso
> a VPS, DNS, banco, credencial, `known_hosts` ou pipeline. **Nenhuma revisão de
> qualidade** (é do reviewer independente).

## I1.1 O defeito, reproduzido por mim antes de corrigir

`test-report.md` §5.1 (T-D1): em `scripts/release/verificar-proveniencia.sh:393`,
`if tag.upper() != "H":` neutraliza a tag **minúscula** `h` que o Git emite para
`assume-unchanged`. Reproduzi em fixture descartável **fora do portal** (comandos
Git de escrita só dentro da fixture):

```
git ls-files -v : h app.py | H leia-me.txt
git status     : (vazio)      <- não vê a alteração
git diff HEAD  : (vazio)      <- não vê a alteração
disco          : ALTERADO-COM-SEGREDO-SINTETICO-PRE-FIX
>>> gate exit = 0 — APROVADO
[ok] 4 arvore-limpa — nenhum arquivo rastreado modificado, removido ou renomeado
[ok] 6 sem-ocultacao — nenhum assume-unchanged / skip-worktree
[ok] 8 sem-segredos — 0 achado(s) de segredo aparente
```

Contraste medido no mesmo instante: com `update-index --skip-worktree` a tag é
`S` e o gate sai `1`. Logo `skip-worktree` era detectado e `assume-unchanged`
não — exatamente T-D1.

## I1.2 Decisões tomadas nesta iteração (com alternativa descartada)

| ID | Decisão | Alternativa descartada | Motivo |
|---|---|---|---|
| **D1** | corrigir a comparação para **sensível ao caso**, aceitando só a tag `H` exato, e nomear a constante `TAG_CACHEADO_NORMAL = "H"` | (a) `tag not in ("H", "h", "S", "s")`; (b) `git ls-files -t`; (c) acrescentar um segundo `git status` | (a) fixa a lista de tags e quebra se o Git emitir outra tag especial — a checagem é de **estado do índice**, não de uma lista de Flags conhecidas; (b) `git ls-files -t` **não** distingue maiúscula de minúscula (medido: devolve `H` para `assume-unchanged`), ou seja, é justamente a informação que faltava; (c) `git status` não vê a alteração sob as flags — usar isso seria **a burla**, não a correção |
| **D2** | a detecção vem dos **bits do índice** (`git ls-files -v`), e a checagem falha fechada na **presença da flag**, exista ou não divergência de conteúdo | reprovar só quando o conteúdo sob a flag difere do `HEAD` | exigiria comparar conteúdo×blob, o que é caro e ainda assim **aprovaria** um repositório cujo índice tem flag oculta — o que o texto da própria checagem promete não aprovar. Falha fechada na flag é mais forte, mais simples e mais barato |
| **D3** | o achado passa a **nomear o mecanismo** (`assume-unchanged`, `skip-worktree`, `skip-worktree+assume-unchanged`) e o detalhe lista os mecanismos presentes | manter a mensagem genérica `%d arquivo(s) com assume-unchanged/skip-worktree` | a mensagem anterior era a alegação falsa de T-D2: prometia os dois mecanismos sem distinguir. Nomear o mecanismo é verificável pelo operador e sobrevive a uma tag nova do Git (vira `estado especial do indice`) |
| **D4** | o detalhe de `arvore-limpa`, quando há flag, ganha a ressalva de que **`git diff` é cego** sob essas flags e remete à checagem 6 | (a) marcar `arvore-limpa` como `incompleto`; (b) deixar como está | (a) mudaria o **status** de uma checagem e, portanto, o formato da saída e as contagens do resumo — mudança de contrato desnecessária para corrigir T-D1, com risco de quebrar asserções de outros agentes; (b) deixaria um "ok" de árvore limpa ao lado de um "1 arquivo com estado especial no índice", o que é a mesma classe de veracidade que T-D2 apontou. Optei pela ressalva textual: **nenhum** status, exit code, chave de JSON ou ordem de achados mudou |
| **D5** | `VERSAO_GATE` continua `"1"` | subir para `"2"` | o gate ainda **não** está registrado em pipeline nenhum (HD-2/HD-6 abertas), não há consumidor do número de versão e o lote não foi encerrado; uma mudança de versão sem contrato que a versione é ruído. A mudança de comportamento está registrada nesta iteração e na §10 das evidências |
| **D6** | não editar `CI-CD.md`, `PROD_DECISOES.md` e `infra/DEPLOY.md` | restaurar/reescrever a seção do lote P0-1 nos três | eu só podia editar os três para remover afirmação falsa sobre `assume-unchanged`/`skip-worktree`, e **nenhuma existe mais**: o ator externo sobrescreveu as seções (§I1.4). Restaurar a seção é reescrever trabalho de outro ator, está fora da lista de escrita e competiria com escritas concorrentes em segundo |
| **D7** | deixar `lote-p0-1-evidencias.md` §4.2 e este arquivo §3.7 **intactos** e registrar a correção por acréscimo | reescrever a linha do caso `M` e o §3.7 | instrução de append-only para estes dois arquivos nesta remediação, e o programa exige preservar o histórico: a afirmação anterior estava correta **quando escrita** e o defeito está registrado com reprodução |

## I1.3 O que mudou no gate (6 pontos, todos mínimos)

Digest **antes** `ce06eaa1d8a6c5019ebd65e7ea8572d0a403586a9a03cd1626d973784981a5e4`
(757 linhas) → **depois** `133408e55076f4c71fa439ee2588d94b55f540e4d29da3296d0858bd592a9541`
(807 linhas), `mode 755`, `bash -n` com `exit 0`.

| # | Onde | Mudança |
|---|---|---|
| C1 | cabeçalho, item 5 | declara que as flags são lidas do índice e que `git status`/`git diff` não veem alteração escondida |
| C2 | `--help` (`sem-ocultacao` + "LIMITES CONHECIDOS") | declara origem (flags do índice), case-sensitive (`H`/`h`/`S`/`s`) e reprovação pela presença da flag |
| C3 | engine, `TAG_CACHEADO_NORMAL = "H"` (linha 364) | constante nomeada |
| C4 | engine, **linha 421** — era `if tag.upper() != "H":` | **`if tag != TAG_CACHEADO_NORMAL:`** + comentário de regressão de 15 linhas no ponto do defeito |
| C5 | engine, `mecanismo_indice()` (linha 475) e achado/detalhe da checagem 6 | o mecanismo é nomeado na saída |
| C6 | engine, linha 458 | `arvore-limpa` "ok" ganha ressalva quando há flag |

**Semântica das tags medida em `git 2.53.0`** (`ls-files -v` + `ls-files --debug`):
`H`/flags `0` = normal; **`h`**/flags `8000` = assume-unchanged;
**`S`**/flags `40004000` = skip-worktree; **`s`**/flags `4000c000` = as duas flags
(aplicadas em chamadas separadas). Em chamada única
`--assume-unchanged --skip-worktree`, **só** a assume-unchanged é gravada
(flags `8000`) — medição que contraria a intuição e por isso vale estar escrita.

**Não** mudou: CLI, exit codes `0/1/2`, as 10 checagens, a ordem dos achados, o
formato do JSON, as regras de segredo, a forma dos marcadores de conflito e o
filtro de placeholder.

## I1.4 Testes: `PASS=125 FALHA=0`

Driver `/tmp/opencode/p0-1-remed/suite.sh`, log `/tmp/opencode/p0-1-remed/testes.log`,
fixtures em `/tmp/opencode/p0-1-remed/fixtures/` — **tudo fora do portal**.

**Os dois fixtures exigidos (T-D4 fechado):**

| Fixture | `ls-files -v` | gate | achado | segredo na saída |
|---|---|---|---|---|
| `Q-assume-unchanged` (conteúdo alterado **e** flag) | `h` | **`1`** | `assume-unchanged: tag git ls-files -v = h` | literal completo `0`, prefixo 20 `0`, prefixo 6 `0` em `stdout`, `stderr` e `--json` |
| `S-skip-worktree` (conteúdo alterado **e** flag) | `S` | **`1`** | `skip-worktree: tag git ls-files -v = S` | literal completo `0`, prefixo 6 `0` |
| `R-assume-unchanged-puro` (só a flag) | `h` | **`1`** | `assume-unchanged: tag git ls-files -v = h` | — |
| `T-ambas-flags` | `s` (flags `4000c000`) | **`1`** | `skip-worktree+assume-unchanged: tag git ls-files -v = s` | — |
| `U-varias-flags` (2 arquivos) | `h` + `S` | **`1`** | `2 arquivo(s) com estado especial no indice (assume-unchanged, skip-worktree)` | — |

Cobertura reexecutada da suíte P0-1 completa, toda em fixture descartável fora
do portal (detalhe asserção a asserção na §10.6 das evidências): árvore limpa +
SHA ok `0`; `--json` `0`; SHA em caixa alta `0`; **sem** `--expected-sha` `1`
(incompleto, e `sha_esperado: null` em `--json`); modificado `1`; removido `1`;
renomeado `1`; untracked `1`; ignorado por `.gitignore` `0`; SHA divergente `1`;
três marcadores de conflito `1`/`1`/`1`; segredo rastreado `1` com controle
positivo `1` e não-vazamento `0/0/0`; segredo + erro de sintaxe `1` sem eco da
linha; segredo em não rastreado `1`; segredo em ignorado `0`; `.py` inválido `1`;
`.yml` inválido `1`; `--help` `0`; oito formas de uso incorreto `2`;
`python3` ausente `1`; `git` ausente `1`; PyYAML ausente com `.yml` `1` e sem
`.yml` `0`; determinismo byte a byte em texto e `--json` e sem timestamp; flag de
exceção inexistente `2`; read-only com `.git/index`, `git status` e sha256 de
todos os arquivos idênticos antes/depois, inclusive na fixture com flag.

No portal, somente leitura: caso negativo real `exit 1` com `arvore-limpa` e
`sem-untracked` falhando; sem `--expected-sha` `1`; `--json` `1` e JSON válido;
**`.git/index` do portal idêntico antes e depois** (`17:32:05.093719930 -0300:105471`);
`HEAD` idêntico antes e depois; `git status` idêntico em três medições
consecutivas; calibragem `sem-segredos`/`sem-conflito`/`sem-ocultacao` com `0`
achados, `133 candidato(s) descartado(s)` pelo filtro de placeholder e
`10 arquivo(s) .yml/.yaml validado(s)`.

Nota de honestidade sobre o harness: minhas `git status` usam
`GIT_OPTIONAL_LOCKS=0` para não refrescar o índice — sem isso o índice mudaria por
causa do harness, não do gate (foi o que o testador isolou no caso F27).

## I1.5 Correção das afirmações documentais (T-D2)

| Alegação de T-D2 | Onde | Estado agora |
|---|---|---|
| `--help`: `sem-ocultacao nenhum assume-unchanged / skip-worktree` | `verificar-proveniencia.sh` | **verdadeira** — o `--help` foi atualizado (C2) e a detecção foi implementada (C4), nesta ordem |
| saída do gate: `nenhum assume-unchanged nem skip-worktree` | `verificar-proveniencia.sh` | **verdadeira** |
| `scripts/…:445`: `%d arquivo(s) com assume-unchanged/skip-worktree` | `verificar-proveniencia.sh` | **substituída** por mensagem que nomeia os mecanismos presentes (C5) |
| §3.7: "sem ela, o gate seria contornável escondendo modificação de arquivo rastreado" | este arquivo | **corrigida por acréscimo**: o bypass existe, era real e foi fechado; o §3.7, como está escrito, descrevia a **intenção** e não a realidade medida |
| §5, lista de casos: `skip-worktree` | este arquivo | **corrigida por acréscimo**: a lista era honesta para o que foi testado; a cobertura real de `assume-unchanged` está na §10.6 das evidências e acima |
| `CI-CD.md`: "`skip-worktree`/`assume-unchanged` é achado próprio" e "Não é `.gitignore` permissivo nem `skip-worktree` que burlam" | `CI-CD.md` | **a alegação não existe mais no arquivo** — o ator externo sobrescreveu a seção do lote (ver I1.6) |
| `infra/DEPLOY.md`: lista do que reprova | `infra/DEPLOY.md` | **idem**: a seção não existe mais no arquivo |

Verificação: `grep -c 'verificar-proveniencia' CI-CD.md PROD_DECISOES.md
infra/DEPLOY.md` → `1`, `0`, `0`; `grep -c 'R-1'` → `1`, `0`, `0`. O único
supervivente em `CI-CD.md` (§554–560, seção do ator externo) é o bullet de **R-1**,
que é verdadeiro e **não** afirma cobertura de `assume-unchanged`.

`action-plan.md`, `task-plan.md`, `implementation-contract.md` e `backlog.md` foram
lidos e **não** foram editados: nenhum dos quatro afirma cobertura de
`assume-unchanged`/`skip-worktree`, logo não havia afirmação falsa a corrigir.
`lote-p0-1-proveniencia.md` recebeu apenas um rodapé datado, no padrão dos
rodapés "Acabamento documental" já existentes, **sem** tocar na versão (**3**),
na revisão 2, nos AC, gates, HD, R-1, R-2 nem no addendum da revisão 3.

## I1.6 Regressão externa observada na janela (registro; não corrigi nada)

| ID | Fato | Efeito |
|---|---|---|
| **T-E3** | `HEAD` foi de `672ffba` para `0c45cf0` com **6 commits novos** (`1b97836`, `ca3ae4d`, `2bf82c0`, `b0e196b`, `a340b17`, `0c45cf0`), todos de conteúdo de observabilidade/infra da run externa; `origin/develop` segue em `7715dae`, sem push | baseline de proveniência do lote **desatualizada**; `settings.py` e os demais protegidos podem ter mudado de novo |
| **T-E4** | **`.github/` foi reescrito em tempo real** durante a janela: os 6 sha256 originais mudaram, e `deploy-dev.yml`, `deploy-homolog.yml`, `deploy-prod.yml`, `deploy.yml` e `rollback.yml` mudaram **outra vez** 12 s depois da primeira medição, sem nenhum comando meu entre elas. `git diff --stat HEAD -- .github/` → `576 insertions(+), 4 deletions(-)` em 4 arquivos | **AC-6(a) e AC-9 (`.github/` byte a byte idêntico) não são mais verificáveis** e, no estado atual, são **falsos**. Não reverti, não normalizei, não commitei |
| **T-E5** | as seções do lote P0-1 em `PROD_DECISOES.md` e `infra/DEPLOY.md` foram **sobrescritas** e a de `CI-CD.md` reduzida a um bullet | a evidência documental de **AC-7** e **AC-8** deixou de existir nesses arquivos |
| **T-E6** | o gate reprovou `yaml-valido` no portal uma vez (`arquivo .yml/.yaml rastreado nao faz parse`) enquanto o ator externo escrevia um `.yml` rastreado; na medição seguinte: `10 arquivo(s) .yml/.yaml validado(s)`, `ok` | reprovação transitória por leitura em arquivo em escrita; evidência de que o gate **fecha** nesse caso |
| **T-E7** | working tree de 45 entradas (17 `M`, 28 `??`) às 19:19Z para 73 (39 `M`, 34 `??`) às 20:47Z | reforça F-1c: nenhuma decisão de release pode usar medição sem re-derivação |

**R-1 permanece ACEITO, ABERTO, não mitigado, não coberto pelo gate e não
bloqueante**, com aceite assinado exigido no go/no-go: verifiquei por leitura que
`deploy-homolog.yml` mantém `on: pull_request`, `app_dir:
/home/apps/portal-homolog`, `git_mode: pr`, `pr_number` e `verify_ref:
${{ github.event.pull_request.head.sha }}`. Nenhum artefato meu afirma resolução,
mitigação, bloqueio ou cobertura desse risco. **R-2** segue **ABERTO**: nenhum
valor de domínio em workflow foi alterado por mim.

## I1.7 Pendências que esta remediação **não** fecha

- **Reexecução do tester independente.** `test-report.md` **não** foi tocado e
  **precisa** ser reexecutado: o veredito `failed` de **AC-4** que motivou esta
  correção é anterior a ela.
- **AC-6(a) e AC-9 (`.github/` byte a byte idêntico).** Bloqueadas por T-E4;
  resolução é humana (parar o ator externo, re-derivar, G0/G2/HD-5).
- **AC-7 e AC-8 (documentação do lote nos três documentos).** Bloqueadas por
  T-E5; restauração é decisão humana e conflita com escritas concorrentes.
- **AC-1, AC-2, AC-3** continuam bloqueados por T-E3/T-E7: a baseline, a prova de
  não-mutação e a verificação de `settings.py` foram medidas contra árvores que se
  moveram depois.
- **Cobertura de testes versionada** continua sendo evidência manual: o driver
  desta itração está em `/tmp`, fora do repositório (follow-up 12 do contrato).

*Remediação 1 do lote P0-1, 2026-09-25. Este rodapé é acréscimo: §1 a §11 acima
permanecem como o executor os escreveu, inclusive onde a afirmação agora é
corrigida aqui. Revisão de qualidade: reviewer independente.*

---

# 12. Remediação final do lote — decisões D1–D5 e refixação do entregável (append-only; nada acima foi alterado)

> **Natureza desta seção:** acréscimo. As §1 a §11 e a "Iteração 1" acima
> permanecem **exatamente** como foram escritas, inclusive onde medem um estado
> que já mudou. Esta seção registra **o que a remediação final decidiu e por quê**.

- **Data:** 2026-09-25
- **Executor:** subagente de remediação final do lote P0-1 (delegado pelo orchestrator)
- **Worktree:** `/tmp/opencode/p01-final`, branch `lote-p0-1-final`
- **Base:** `origin/develop` = `7715dae8cc1a128e5992245ba636036c8a967f28`
- **Comandos Git de escrita executados:** **nenhum**. Sem `add`, `commit`, `push`,
  `merge`, `rebase`, `reset`, `clean`, `checkout`, `switch`, `stash` ou `restore`.
  Sem rede, sem VPS, sem credencial, sem `gc`/`prune`. **A árvore principal do
  portal não foi escrita** (ver §12.6, prova de não-mutação).

## 12.1 Os 8 caminhos do lote, e nada mais

O contrato (versão 3, "Escrita autorizada — lista fechada") autoriza exatamente
estes 8 caminhos. Todos e apenas eles existem nesta entrega:

| # | Caminho | Modo |
|---|---|---|
| 1 | `agentic-framework/state/run-20260925-1433-go-live-producao/lote-p0-1-proveniencia.md` | 644 |
| 2 | `agentic-framework/state/run-20260925-1433-go-live-producao/provenance-reconciliation.md` (aditivo) | 644 |
| 3 | `agentic-framework/state/run-20260925-1433-go-live-producao/implementation-history.md` | 644 |
| 4 | `agentic-framework/state/run-20260925-1433-go-live-producao/lote-p0-1-evidencias.md` | 644 |
| 5 | `scripts/release/verificar-proveniencia.sh` | **755** |
| 6 | `CI-CD.md` | 644 |
| 7 | `PROD_DECISOES.md` | 644 |
| 8 | `infra/DEPLOY.md` | 644 |

Nenhum outro arquivo foi criado ou modificado. Em particular **não** existem
nesta entrega `run-state.json`, `test-report.md`, `action-plan.md`,
`backlog.md`, `implementation-contract.md`, `task-plan.md` nem
`sessoes-pausadas-e-freeze.md`. Nada sob `.github/`, `backend/`, `frontend/`,
`infra/nginx/`, `infra/backup/`, lockfile, migration ou `.env*` foi tocado.

## 12.2 D1 — o gate canônico é `133408e5…`, não a cópia de `df20ad3`

**Decisão.** O gate instalado neste lote é
`scripts/release/verificar-proveniencia.sh`, sha256
`133408e55076f4c71fa439ee2588d94b55f540e4d29da3296d0858bd592a9541`
(33 784 B, 807 linhas, modo 755). A versão do commit `df20ad3`
(sha256 `cd0cddd585f81ab4c7a49e655f01873b7662c0362d46e1c03dd285ff7d27d390`,
804 linhas) **não** é a instalada.

**Medição que embasa a decisão** (detalhe completo em
`lote-p0-1-evidencias.md` §12):

- `git ls-files -v` é **case-sensitive** e o caso `s` **existe**: com
  `assume-unchanged` a tag é `h` (flags `0x8000`); com `skip-worktree` é `S`
  (flags `0x4000`); com **as duas** é `s` (flags **`0xc000`**). Medido em git
  2.53.0.
- **Nenhuma das duas versões tem bypass.** A comparação da checagem 6 é
  `if tag != TAG_CACHEADO_NORMAL` (`"H"`) nas **duas**, e **ambas reprovam com
  `exit 1`** em `h`, `S` e `s`. `grep` confirma **ausência de `upper()`/`lower()`
  na comparação** em ambas (as menções a `upper()` são comentários de
  advertência, não código).
- O que de fato difere é **rótulo e comentário**: só `133408e5…` nomeia
  corretamente o caso `s` como `skip-worktree+assume-unchanged` e **corrige** o
  comentário que afirmava erroneamente que a tag seria `S`. A `cd0cddd5…` rotula
  o arquivo como `estado especial do indice` e tem o `--help` incompleto.

**Alternativa descartada:** entregar a versão de `df20ad3` por ser "a que está
commitada". Descartada porque ela documenta errado um caso de flag que ela mesma
detecta, e o `--help` descreve a semântica de forma incorreta.

**Registra-se também** que o commit `df20ad3` é um **snapshot pré-remediação** e
está **superado** por este lote: ele não contém a §10 de
`lote-p0-1-evidencias.md` nem a "Iteração 1" deste arquivo, ambos os quais
passaram a existir com esta remediação (achado **F-1**, ver §12.5).

## 12.3 D2 — `run-state.json` fica FORA do lote

`run-state.json` é **exclusivo do orchestrator**, atualizado **após** o lote e
**fora** do diff do executor (**AC-10**). Ele **não** foi criado, **não** foi
editado e **não** aparece em nenhuma evidência de diff. Nenhum `run-state.json`
de nenhuma run foi tocado. Isso resolve o achado **F-2** (o commit `df20ad3`
o carregava como arquivo adicionado, contrariando AC-10).

## 12.4 D3 — os artefatos de planejamento do programa não entram no lote

`action-plan.md`, `backlog.md`, `implementation-contract.md`, `task-plan.md`,
`test-report.md` e `sessoes-pausadas-e-freeze.md` **não constam** da lista
fechada, e o backlog declara o diretório de estado da run como **não rastreado e
fora de release**. Nenhum deles foi criado nesta entrega. Isso resolve o achado
**F-3**.

**Memória externa** (preservada, fora do repositório, **não** é artefato do lote
e não é diff):

| Caminho | Bytes | O que é |
|---|---|---|
| `/tmp/opencode/preservacao-20260925/` | — | custódia completa: `prioritarios/` (gate `133408e5…` e a cópia `_df20ad3/` com `cd0cddd5…`), `untracked/agentic-framework/state/run-20260925-1433-go-live-producao/` (**os 4 artefatos de estado usados aqui**, além de `run-state.json` e dos 6 artefatos de planejamento) |
| `/tmp/opencode/wip-reconciliation.md` | 49 652 | reconciliação do WIP: achados A-1..A-6, B-1..B-6, veredito **NÃO ADOTÁVEL** |
| `/tmp/opencode/p01-tester-report.md` | 30 258 | teste independente de `df20ad3`: achados F-1..F-5 |
| `/tmp/opencode/gate-cmp/workingtree.sh` | 33 784 | cópia do gate canônico, sha idêntico ao instalado |

Estes caminhos são registrados aqui **como memória externa**, para que nada
deles se perca. **Nenhum arquivo foi criado no repositório** por causa deles.

## 12.5 D4 e D5 — base do lote e refutação

**D4 — a base é `origin/develop` (`7715dae`), não a branch de WIP
`observability-20260925-1020`.** Motivo: a reconciliação
(`/tmp/opencode/wip-reconciliation.md`) vereditou o WIP como **NÃO ADOTÁVEL**
como base de release (6 blockers: B-1..B-6), e o solicitante confirmou
`origin/develop` + P0-1 como base do go-live, com o WIP em **lote próprio**. A
medição confirma a forma: a branch de WIP tem **17 commits à frente** de
`origin/develop`, em 162 arquivos, `+44352/−2804`, sendo **13** da run
`20260925-1020-observabilidade`, **1** recuperação de WIP órfão da mesma run
(`672ffba`) e **2** (`3a676c7`, `cf2fe02`) da run
`20260924-2136-ingestao-noticias`, commitados na branch errada.
`git merge-base origin/develop observability-20260925-1020` = `7715dae` ⇒ merge
limpo do ponto de vista do Git e, portanto, **sem nenhum aviso**: a colisão é
inteiramente semântica.

**D5 — refutação de B-3 registrada.** O achado B-3
(`/tmp/opencode/wip-reconciliation.md:302`) afirma que *"a versão defeituosa do
gate ficou na working tree; um `git add -A` reproduziria o bug do
`tag.upper()`"*. Isso é **REFUTADO por medição direta** (medida nesta run,
registrada em `lote-p0-1-evidencias.md` §12):

- tags medidas: `h` (só `assume-unchanged`, flags `0x8000`), `S` (só
  `skip-worktree`, flags `0x4000`), **`s`** (as duas, flags **`0xc000`**);
- `exit 1` em **h** `h`, `S` **e** `s` na fixture, **nas duas versões** —
  **nenhuma tem bypass**;
- a comparação é `if tag != "H"` **idêntica** nas duas (L421 em ambas), e
  **não há `upper()` nem `lower()`** aplicado a `tag` em nenhuma.

A única diferença real é de **rótulo e comentário**. Registrado para que
ninguém reintroduza o achado errado: o `tag.upper()` **nunca esteve presente**
em nenhuma das duas versões. O risco **real** e subsistente de B-3 — duas
verdades sobre o próprio entregável — está resolvido por **D1**.

**Achados e status** (detalhe e status completo em
`lote-p0-1-evidencias.md` §11): **F-1** RESOLVIDO (D1 + artefatos
pós-remediação); **F-2** RESOLVIDO (D2); **F-3** RESOLVIDO (D3); **F-4**
RESOLVIDO (`133408e5…` corrige comentário e `--help`); **F-5** RESOLVIDO (D1,
o lote fixa `133408e5…`); **B-3** **REFUTADO** (D5). **A-2/B-4** (violação de
contenção cross-run em `3a676c7`) e **B-2** (~4 000 linhas não rastreadas sem
lastro) seguem **ABERTOS** e são **decisão humana**, fora do escopo do P0-1.

**Refutações na reconciliação.** `provenance-reconciliation.md` §2.8
(*"a branch aponta para `d1e0456` e não contém o WIP"*) e §5.2 (*"WIP sem
lastro em nenhuma branch"*) estão **REFUTADAS** e isso foi registrado em uma
**seção de correção datada e aditiva** (§11), sem reescrever nem apagar nada do
que existia. §5.1 (`clean`/`reset` quebraria o backend) e §5.4
(`settings.py` reparado sem origem) **permanecem válidas e abertas**.

## 12.6 Os três documentos vivos: por que a versão de `df20ad3`, e não a working tree

Os três documentos vivos foram extraídos do commit **`df20ad3`**
(`git show df20ad3:<caminho>`), e **não** copiados da working tree principal.
A comparação mostra que a working tree principal **não serve** como fonte,
pelo motivo mais forte possível: ela **não contém** a documentação do P0-1.

| Documento | sha256 de `df20ad3` (escolhido) | sha256 da WT principal (descartado) | `Lote P0-1` na WT | `Lote P0-1` em `df20ad3` |
|---|---|---|---|---|
| `CI-CD.md` | `16f7ae5458b274db…` | `5d39447a1ec2990b…` | **0** | 1 |
| `PROD_DECISOES.md` | `5240a41de2e42201…` | `fe6c0f780c8677ae…` | **0** | 1 |
| `infra/DEPLOY.md` | `cac51f9963e99ba9…` | `0985212449fa5ce5…` | **0** | 1 |

Contagens de menção a `verificar-proveniencia`: `CI-CD.md` 2 (escolhido) vs 1
(descartado); `PROD_DECISOES.md` 1 vs 1; `infra/DEPLOY.md` **4 vs 0**.

**O que difere e por quê.** O diff working tree principal ↔ `df20ad3` é de
`+483/−123` em `CI-CD.md`, `+74/−72` em `PROD_DECISOES.md` e `+478/−64` em
`infra/DEPLOY.md` (contra `HEAD` = `cf2fe02`: `+115/−5`, `+0/−0` e `+198/−0`).
A WT principal carrega conteúdo de **outra run** — seções `§P1-6`, "Decisões do
Bloco C2", "Operação da topologia ATIVA depois do deploy (C2)" — e, ao mesmo
tempo, a **seção do lote P0-1 foi sobrescrita** (é exatamente o que o teste
independente registrou como **B-5**).

**Consequência:** usar a WT principal **perderia** a seção do lote em los três
documentos, e ainda assim **acrescentaria** material de run alheia. A versão de
`df20ad3` é a **única** que contém a documentação do P0-1 íntegra. Por isso
`df20ad3` foi escolhido **apenas** como fonte dos **três documentos vivos** — os
4 artefatos de estado vêm da cópia pós-remediação (que **inclui** a §10 e a
"Iteração 1") e o gate vem de `133408e5…`. É uma escolha **por arquivo**, não
uma confiança no commit: `df20ad3` como **entregável** está superado (D1/F-1),
mas como **fonte de texto** dos três documentos vivos é o que existe.

## 12.7 Prova de não-mutação da árvore principal

Todas as medições abaixo foram tomadas na árvore principal
`/home/alex-buttielie/repositorios/portal-noticias`, em modo somente leitura:

| Item | Esperado | Medido | Resultado |
|---|---|---|---|
| `git rev-parse HEAD` | `cf2fe02748b7f51fb43286adf58b3cfaf9a9e142` | idem | ✅ |
| `git status --porcelain=v1 -uall \| wc -l` | `70` | `70` | ✅ |
| `sha256sum backend/config/settings.py` | `2031e7c7e18c2c5a50458720e405cdc99d2f8d70e2bdcb2845c688e0a045b0ea` | idem | ✅ |

A árvore principal **não foi escrita**. Nenhum `run-state.json` de nenhuma run
foi tocado. O gate foi executado **contra** ela apenas com `--repo`, que é
read-only por contrato.

## 12.8 Achado novo, encontrado nesta remediação, que exige decisão

**O gate reprova a própria cópia limpa do lote, com 1 achado, e o achado está
no `lote-p0-1-evidencias.md` — material pré-existente, não escrito por mim.**

`sem-segredos` (checagem 8) reprova a linha **839** de
`lote-p0-1-evidencias.md`, regra `segredo-stripe-live`. A linha é o comando
gerador do literal sintético do teste AC-5, que **contém o prefixo do padrão** e
é auto-referencial: o gate detecta, corretamente, um "segredo aparente" no
documento que documenta o teste de segredo. O **valor** do literal não está
transcrito no artefato, e a seção diz isso explicitamente.

Medições que isolam a causa:

| Cenário |exit | Achados |
|---|---|---|
| Cópia limpa com os **8** caminhos, `--expected-sha` correto | `1` | 1 (só `sem-segredos`, linha 839) |
| Cópia limpa com **7** dos 8 caminhos (sem `lote-p0-1-evidencias.md`), `--expected-sha` correto | **`0`** | **0** |
| Mesma cópia de 7 caminhos, `--expected-sha` errado (controle) | `1` | 2 |

Ou seja: **o `exit 0` é alcançável** e foi provado; o único bloqueador na cópia
completa é a linha 839, **pré-existente** (§10, Bloco "Segredo (AC-5)").

**Não corrigi**, deliberadamente: (a) reescrever ou remover essa linha seria
violar o caráter **append-only** do artefato e apagar evidência do teste AC-5;
(b) a correção pode ser o redator do artefato tornando o exemplo **não
auto-referencial** (por exemplo citando o prefixo como `sk-…-SINTÉTICO` sem
montar o padrão completo, ou movendo a linha para um bloco cercado de
`IGNORAR`), e essa é uma decisão de **conteúdo**, não de execução. Fica
registrado para o **reviewer** e para o **orchestrator**.

## 12.9 Execuções do gate nesta remediação

| # | Alvo | `--expected-sha` | exit | Achados |
|---|---|---|---|---|
| 1 | árvore principal congelada | `cf2fe02…` (correto) | **`1`** | **70** |
| 2 | a própria worktree `p01-final` | `7715dae…` (correto) | **`1`** | **8** |
| 3 | cópia limpa, 8 caminhos | correto | **`1`** | **1** (linha 839, ver §12.8) |
| 4 | cópia limpa, 7 caminhos (diagnóstico) | correto | **`0`** | **0** |

A execução 1 é a prova de que o gate **reprova estado sujo** (falha em
`arvore-limpa` e `sem-untracked`) e de que **não escreve** (a árvore principal
seguiu com os mesmos 70 itens e os mesmos sha depois das quatro execuções).
A execução 2 é o resultado **esperado**: a worktree tem 3 documentos
rastreados modificados e 5 caminhos não rastreados, porque **o commit é do
orchestrator** — o executor não faz commit. Detalhe completo em
`lote-p0-1-evidencias.md` §12 e nesta seção.

*Remediação final do lote P0-1, 2026-09-25. Este rodapé é acréscimo: §1 a §11 e a
"Iteração 1" permanecem como foram escritas, inclusive onde a afirmação agora é
corrigida aqui. O commit é do orchestrator.*

## 12.10 Como a lista de 8 foi verificada (e uma ressalva honesta)

A lista fechada foi conferida por **duas** leituras independentes:

| Leitura | Resultado |
|---|---|
| `git status --porcelain=v1 -uall` | **8** caminhos: 3 ` M` (`CI-CD.md`, `PROD_DECISOES.md`, `infra/DEPLOY.md`) + 5 `??` (4 artefatos de estado + o gate) |
| união de `git diff --name-only origin/develop` (3) **+** `git ls-files --others --exclude-standard` (5) | **8**, `diff` **idêntico** à lista autorizada |

**Ressalva sobre a segunda leitura, para não haver dúvida:** a forma
`git diff --name-only origin/develop` **por si só** devolve apenas as **3**
mudanças **rastreadas** — ela **não** lista arquivos não rastreados, por
construção do Git, e `git add` (que tornaria os 8 visíveis ali) está
**proibido** ao executor. Por isso a conferência dos 8 foi feita pela **união**
das duas leituras acima, que é o que de fato compara o diff do lote contra a
lista fechada. O commit é do orchestrator; depois do commit, `git diff` e
`git status` passarão a concordar.

`.github/` foi verificado **byte a byte**: os **6** blobs de
`origin/develop:.github/` comparados por `sha256` com os 6 arquivos em disco —
**todos idênticos** —, `git diff origin/develop -- .github/` **vazio** e
**zero** arquivos não rastreados sob `.github/`.

# 13. F-5 — o gate reprovava a própria evidência do lote · **RESOLVIDO no documento**

> Append-only: §1 a §12 e a "Iteração 1" permanecem exatamente como foram
> escritas. Esta seção não reescreve o §12.8 — ela **resolve** o achado que ele
> deixou em aberto para o reviewer.

## 13.1 O que era

O §12.8 mediu e **não corrigiu**. O achado era
`agentic-framework/state/run-20260925-1433-go-live-producao/lote-p0-1-evidencias.md:839`
— a transcrição do comando gerador do literal sintético do teste AC-5, dentro de
"§10.6 → Segredo (AC-5), com literal sintético real gerado na execução". O
prefixo de chave live do Stripe aparecia colado a um corpo alfanumérico de 14
caracteres, o que casa com `segredo-stripe-live`
(`scripts/release/verificar-proveniencia.sh:549`,
`\b(?:sk|rk)[-_](?:live|test)[-_][0-9A-Za-z]{10,}`).

## 13.2 Reverificação: o estado que o §12.8 deixou em aberto

| Cenário | exit | Achados |
|---|---|---|
| cópia limpa dos **8** caminhos, `--expected-sha` correto, **antes** | `1` | **1** (`segredo-stripe-live`, `lote-p0-1-evidencias.md:839`) |
| **a mesma cópia, depois** | **`0`** | **`0`** — 10/10 checagens `ok`, `resultado: APROVADO` |

Reproduzido **fora** do repositório, em `/tmp/opencode/verificacao-f5` (`git init`
próprio, os 8 caminhos copiados, `--expected-sha` igual ao `HEAD` da cópia), e
nos dois modos: texto e `--json` (`exit 0`, `"resultado": "aprovado"`, 0 achados).

## 13.3 Por que a correção foi no documento e **não** no gate

O gate estava **correto**. Um arquivo **rastreado** não deve conter padrão de
credencial — nem em documentação, nem num exemplo, nem num registro de prova.
Enfraquecer a regra teria trocado "o artefato do lote se auto-aprovava" por
"a regra de segredo foi rebaixada para o artefato passar", que é exatamente o
burla que a checagem 8 existe para fechar. Portanto, nesta ordem:

1. `scripts/release/verificar-proveniencia.sh` **não foi tocado** — sem
   allowlist, sem carve-out, sem relaxamento de `segredo-stripe-live`; `bash -n`
   segue `0` e o `sha256` é **o mesmo de antes e de depois**:
   `133408e55076f4c71fa439ee2588d94b55f540e4d29da3296d0858bd592a9541`.
2. `lote-p0-1-evidencias.md:839-841` foi reescrito para **descrever** o teste
   com fidelidade (literal sintético **real**, montado em tempo de execução, com
   o prefixo de chave live do Stripe e sufixo de 12 bytes hexadecimais de
   `/dev/urandom`, gravado em `app.py` de fixture rastreada fora do portal) sem
   conter nenhuma sequência que case com a regra — o prefixo é citado **por
   descrição** e nunca montado ao lado de 10+ alfanuméricos. Uma nota na própria
   seção explica o porquê, para que a linha não pareça removida por zelo.
3. **O registro do teste AC-5 continua inteiro**: a tabela T26–T43 acima da nota
   e a afirmação "**o valor não é transcrito aqui**" foram preservadas. O que
   saiu do documento foi só a transcrição do comando.

## 13.4 Varredura do lote inteiro e teste negativo de não-regressão

A regra foi varrida nos **8** caminhos do lote, com a **mesma** regex da fonte da
verdade: **1** ocorrência no total — a linha 839, corrigida. **Zero** restantes.
(`lote-p0-1-evidencias.md:392` e `lote-p0-1-proveniencia.md:374` trazem o mesmo
gerador com um marcador de 9 caracteres, **um a menos** que o mínimo de 10 da
regra: **não casam**, foram verificados e deixados como estão.)

**Não-regressão:** num arquivo rastreado temporário da cópia limpa, gravada uma
credencial Stripe real — `sk_live_` + corpo alfanumérico, em `config_neg.py:1` —
o gate **continuou reprovando**: `exit 1`, `achados: 1`, achado
`[8 sem-segredos] config_neg.py:1 :: segredo-stripe-live`. O literal completo e o
prefixo de 20 caracteres tiveram contagem `0` na saída (o valor não vaza).
Arquivo removido; a mesma cópia voltou a `exit 0`. O conserto foi no texto e
**não** derrubou a segurança.

*Nenhum commit, `add` ou `push`: o commit é do orchestrator.*
