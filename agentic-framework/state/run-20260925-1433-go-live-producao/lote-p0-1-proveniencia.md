<!--
CONTRACT: implementation-contract (lote)
DONO: orchestrator (preenche) / executor, tester, reviewer (leem)
QUANDO É CRIADO: após aprovação do contrato mestre, antes de qualquer implementação do lote
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-20260925-1433-go-live-producao/lote-p0-1-proveniencia.md
-->

# Implementation Contract — Lote P0-1 "Proveniência e gate de release (repo-only)"

## Metadados

- **run_id:** 20260925-1433-go-live-producao
- **lote:** P0-1 — Baseline de proveniência, gate determinístico de release e documentação
- **Itens de backlog cobertos:** P0-01 (parcial — reconciliação/atribuição é de **WS-00/GP-0**), **P0-01b** (re-derivação detalhada do estado Git e baseline de release), P0-02 (apenas verificação — gate G1), P0-09 (parcial — sem integração ao CI/CD)
- **Deriva de:** `task-plan.md`, `implementation-contract.md` e `backlog.md` da run 20260925-1433-go-live-producao
- **Entradas adicionais:** proposta do explorador para o P0-1, consolidada nas restrições deste contrato
- **Domínio canônico:** `https://portal-noticias.com/` (único valor de domínio adotado neste programa; valores de domínio dentro de workflow ficam para lote posterior, sem alterar estrutura nem gatilhos — ver "Divergência de domínio" abaixo)
- **Versão do contrato:** **3**
- **Revisão 2 (decisão do solicitante, mantida):** **NÃO alterar o CI/CD existente.** Nenhum workflow, gatilho, job ou comportamento em `.github/` pode ser editado neste lote. O caminho PR → VPS persistente permanece **ativo** e passa a ser **risco de supply chain ACEITO, ABERTO e NÃO BLOQUEANTE**, sem alegação de resolução nem de mitigação. Ver **AC-6** e "Riscos aceitos / pendentes registrados" (**R-1**).
- **Revisão 3 (addendum datado 2026-09-25, aplicada a partir da revisão de planejamento):** esta revisão **não** amplia o escopo do lote. Ela (a) padroniza o tratamento de **R-1** como risco **aceito, aberto, não bloqueante para o go-live e assinado no go/no-go**; (b) **remove a circularidade de gate** — GP-0 fecha apenas com **G0, G2, G3, G4, G5**, e a validação **G1** (`settings.py`) é executada **neste lote**, depois de GP-0, alimentando **GP-1 e GP-1b**; (c) declara **`run-state.json` como arquivo exclusivo do orchestrator**, fora do diff do executor (**AC-10**); (d) registra a divergência de **domínio** entre o canônico `.com` e o `portal-noticias.com.br` presente nos workflows existentes, sem editar workflow; (e) atribui a **validação/pinning de host key (`known_hosts`)** a **WS-03**, fora deste lote; (f) corrige IDs inexistentes e texto corrompido. Ver §"Addendum da revisão 3".
- **Precondição de gate (não circular):** GP-0 fecha com **G0, G2, G3, G4, G5** (custódia e decisões humanas). **G1 não faz parte de GP-0**: G1 é executada aqui, como item **P0-02 (verificação)** deste lote, e seu resultado alimenta **GP-1** (lote) e **GP-1b** (integridade funcional). Um GP-0 que dependesse de G1 seria circular, porque este lote só pode ser delegado depois de GP-0.
- **SHA de release:** não fixado neste contrato. É **re-derivado** no início do lote por `git rev-parse HEAD` e confirmado com o solicitante (**HD-3**). **Estado re-derivado em 2026-09-25T18:32:47Z (snapshot datado, não premissa; leitura apenas):** `develop` e `origin/develop` **iguais** em `7715dae8cc1a128e5992245ba636036c8a967f28`, paridade `0` atrás / `0` à frente, e `948a5b5`/`645aca3` **já contidos no remoto** — **não há push pendente**; o `645aca3` citado em outros artefatos desta run é um **snapshot datado** da reconciliação e **não** é o `HEAD` observado; `4c57ff04` é ***dangling*** (existe como objeto, **nenhuma ref o contém e o reflog não o menciona** ⇒ recuperável **por SHA**, não por reflog). **Nenhum artefato deste lote pode tratar qualquer um desses valores como SHA de release**, e o lote **re-deriva** o estado no início (§"Comandos de validação", item 1).
- **Executor:** subagente delegado, execução restrita ao repositório local
- **Testador:** subagente independente do executor
- **Revisor:** subagente independente — revisão **obrigatória** de segurança e de CI/CD no sentido de *não-regressão* (ver seção "Revisão obrigatória")
- **Natureza do lote:** `repo-only`, sem qualquer efeito em CI/CD, VPS, DNS, backup, banco ou aplicação
- **Estado:** planejamento. Este documento **não** autoriza, sozinho, alteração de VPS, DNS, backup, banco, migration, aplicação, credencial ou pipeline.

### Limite de escopo deste lote (leitura obrigatória)

Este lote é deliberadamente pequeno e **sem efeito observável em produção**. Ele:

- **SIM** cria baseline de proveniência, um gate determinístico read-only e a documentação correspondente;
- **NÃO** altera **nenhum** arquivo em `.github/` — workflows, gatilhos, jobs, secrets e comportamento atual são preservados exatamente como estão;
- **NÃO** fecha, mitiga nem examina o caminho que leva código de pull request à VPS que hospeda HOMOLOG; esse caminho **permanece ativo** e é registrado como **risco aceito, aberto e não bloqueante**, com assinatura explícita no go/no-go (**R-1**);
- **NÃO** altera **nenhum** valor de domínio dentro de workflow: o único valor de domínio adotado no programa é o canônico `https://portal-noticias.com/`, e qualquer valor de domínio em workflow fica para **lote posterior**, **sem** mudar estrutura, gatilhos ou comportamento;
- **NÃO** faz validação nem pinning de host key / `known_hosts`: essa atribuição é de **WS-03** (F1), com contrato, evidência e gate próprios (GP-2a e linha no go/no-go);
- **NÃO** escreve `run-state.json` nem qualquer outro arquivo de estado da run: ver **AC-10** e "Escrita autorizada";
- **NÃO** toca em código de aplicação, dados, infraestrutura de execução, DNS, TLS, firewall, backup ou ambiente;
- **NÃO** corrige `backend/config/settings.py` — apenas verifica e reporta;
- **NÃO** exige nem presume acesso à VPS, ao DNS ou a credenciais de produção.
- **NÃO** edita `.gitignore`: o diretório de estado das runs, inclusive o artefato **não rastreado** desta run, declarado **fora de release**, é tratado por **inventário e ownership** (G5/D-08).

Qualquer necessidade de tocar a VPS, o banco, uma migration, um segredo, o runtime da aplicação ou **os pipelines existentes** **invalida o lote** e deve ser devolvida ao orchestrator como novo lote.

## Objetivo

1. **Baseline de proveniência (P0-01):** registrar, de forma atribuída e reproduzível, o estado atual do working tree —branch, SHA, arquivos modificados, arquivos não rastreados— com atribuição explícita de cada item à run que o criou, sem tocar em nenhum arquivo protegido e sem executar nenhum comando Git de escrita.
2. **Verificação, não correção, de `settings.py` (P0-02 / gate G1):** comprovar com métodos determinísticos e read-only (`ast.parse`/`compile()` e, se o ambiente permitir, `manage.py check`) que `backend/config/settings.py` é sintaticamente válido no estado atual, e reportar o resultado sem editar o arquivo. **G1 é executada neste lote, depois de GP-0** (GP-0 fecha apenas com G0, G2, G3, G4, G5), e o resultado alimenta **GP-1** e **GP-1b**.
3. **Gate determinístico de release (P0-09):** entregar um script read-only, sem dependência de rede e sem depender de segredo, que reprove de forma determinística quando o release não é reproduzível: working tree sujo ou com untracked, SHA divergente do esperado, marcadores de conflito de merge, segredos aparentes em arquivos rastreados, Python inválido ou YAML inválido.
4. **Registrar R-1 como risco aceito, aberto e não bloqueante:** documentar explicitamente que existe um caminho de deploy que leva o head de um pull request não aprovado à VPS persistente que hospeda HOMOLOG, que este lote **não** o altera, **não** o mitiga e **não** o cobre pelo gate, e que ele está **aceito por decisão do solicitante** — logo, **não bloqueia o go-live** — mas permanece **ABERTO** e **exige registro e aceite explícito, assinados, no go/no-go**. **Nenhuma documentação deste lote pode afirmar ou sugerir que esse risco foi resolvido, mitigado, bloqueado ou coberto pelo gate.**
5. **Documentar somente as decisões deste lote**, com registro explícito de que o gate **só bloqueia de fato quando a branch protection do GitHub estiver configurada** — e de que, mesmo com branch protection, ele **não cobre** o caminho PR → VPS.

## Escopo do lote

### P0-01 — Inventário atribuído por run (read-only)

- Capturar, com comandos Git **somente de leitura**, o inventário do working tree: branch, `HEAD` completo, `origin/*` e a paridade `develop` × `origin/develop`, **todas** as refs locais e remotas, arquivos modificados rastreados, arquivos não rastreados, presença do objeto `4c57ff04` (por SHA) e `.gitignore` aplicável — com **timestamp** da medição e o comando exato de cada linha. Este inventário é a **re-derivação detalhada** do estado Git (backlog **P0-01b**); a **reconciliação/atribuição** e a **re-verificação fresca de G0–G5** que fecham **GP-0** são de **WS-00** e **não** dependem deste artefato.
- **Reuso obrigatório do artefato existente:** o inventário de fase de planejamento já existe em `agentic-framework/state/run-20260925-1433-go-live-producao/provenance-reconciliation.md`. O executor **não** cria um documento paralelo. Escolhe **uma** das duas saídas, sem criar um terceiro:
  - **(a)** estender `provenance-reconciliation.md` de forma **aditiva**, acrescentando a baseline re-derivada no início do lote, a atribuição por run de cada item e os comandos de reprodução — sem reescrever nem remover seções existentes, sem resolver os conflitos que ele registra como abertos; ou
  - **(b)** registrar a baseline re-derivada do lote exclusivamente em `lote-p0-1-evidencias.md`, referenciando `provenance-reconciliation.md` como inventário de origem, e não alterar aquele arquivo.
  - A escolha deve ser justificada no `implementation-history.md`. Em ambos os casos, atribuição por run de cada item é obrigatória.
- **Proibido:** `git add`, `commit`, `push`, `merge`, `rebase`, `reset`, `clean`, `checkout`, `switch`, `stash`, `restore`, `apply`, `am`, `filter-branch`, `gc`, `prune`; proibido mover, apagar ou sobrescrever qualquer arquivo do working tree.
- **Proibido:** tocar `backend/config/settings.py`, `backend/config/middleware.py`, `backend/config/health.py`, `backend/config/metrics.py`, `backend/config/observability.py`, os diretórios das runs `20260925-1020-observabilidade` e `20260924-2136-ingestao-noticias`, o frontend de aplicação, lockfiles, migrations e segredos.
- **Atribuição por run (obrigatória em qualquer das duas saídas):** cada item modificado/não rastreado recebe uma destas origens — run `20260925-1020-observabilidade`, run `20260924-2136-ingestao-noticias`, run `20260924-1535-arquivar-ingestao`, `20260924-1721-react-query-migracao`, este lote, ou **"origem não determinada — exige decisão humana"**. Itens sem atribuição possível **não** são inventados nem descartados: ficam registrados como pendência de **HD-5**.
- **Diretório de estado desta run:** `agentic-framework/state/run-20260925-1433-go-live-producao/` é **artefato não rastreado de planejamento desta run**, **fora de qualquer release**, com **ownership desta run** e **re-derivado** a cada execução. O inventário o declara explicitamente como tal. **Editar `.gitignore` é proibido neste lote** (e neste programa): a exclusão do diretório de estado do release é resolvida por **inventário e decisão de ownership** em **G5/D-08**, nunca por regra de ignore. Ele continua sendo **untracked** — logo, motivo de reprovação do gate (P0-09, caso 2), e essa é a leitura esperada e correta.

### P0-02 — Verificação de `settings.py` (sem edição) — corresponde ao gate **G1**

- **Onde este item vive:** G1 é executado **neste lote** (WS-01), **depois** de GP-0. GP-0 fecha apenas com **G0, G2, G3, G4, G5**. O resultado de G1 alimenta **GP-1** (este lote) e **GP-1b** (integridade funcional, WS-02).
- Verificar `backend/config/settings.py` por método determinístico e **sem escrita em disco**:
  - `ast.parse` do conteúdo lido em memória;
  - `compile()` do mesmo conteúdo (equivalente a `py_compile`, sem gerar `__pycache__`);
  - `manage.py check` **apenas se** o ambiente local permitir sem rede, sem banco e sem segredo; caso contrário registrar `SKIP` com o motivo exato.
- **Proibido:** editar, formatar, reordenar, "corrigir" ou regenerar `settings.py`. A correção de conteúdo é o lote de correção de `settings.py` (**P0-02b** no `backlog.md`, gate **GP-1b**), não este.
- Se a verificação falhar: registrar finding (severidade a definir pelo reviewer), Reprovar o lote e devolver ao orchestrator. **Não** corrigir neste lote.
- Nenhum comando de verificação pode criar `__pycache__`, `.pyc` ou qualquer outro artefato; usar `PYTHONDONTWRITEBYTECODE=1` quando invocar Python.

### P0-09 — Gate determinístico de release

- Criar `scripts/release/verificar-proveniencia.sh`: script **read-only**, POSIX-friendly, executável, sem rede, sem segredo, sem escrita em disco e sem qualquer comando Git que altere o repositório.
- O script **reprova** (fail-closed) em, no mínimo, estes casos:
  1. **working tree sujo** — arquivo rastreado modificado, removido ou renomeado;
  2. **untracked** — arquivo não rastreado presente (respeitando `.gitignore`), incluindo o diretório de estado das runs, declarado **fora de release** por ownership (G5/D-08) e **não** resolvido por edição de `.gitignore`;
  3. **SHA divergente** — `HEAD` diferente do SHA de release esperado;
  4. **marcadores de conflito** — `<<<<<<<`, `>>>>>>>`, `=======` (7+ caracteres) em arquivos rastreados;
  5. **segredos aparentes** — padrões de chave/ token/ senha em arquivos **rastreados**;
  6. **Python inválido** — arquivo `.py` rastreado que não faz parse;
  7. **YAML inválido** — arquivo `.yml`/`.yaml` rastreado que não faz parse.
- **A saída nunca imprime valor de segredo.** O finding de segredo informa apenas: identificador da regra, caminho do arquivo, número da linha e o fato de que o valor foi omitido. Nenhuma linha de conteúdo é ecoada, nem parcialmente, nem com mascaramento parcial.
- Falha fechada (fail-closed): se uma verificação não puder ser executada (Python ausente, PyYAML ausente, `git` indisponível), o script **falha** com motivo explícito. Não existe bypass silencioso; qualquer exceção exige flag explícita, documentada e registrada como finding.
- Saída determinística e estável para diff: sem timestamp, sem cor quando não for TTY, findings ordenados por (checagem, caminho, linha).

### Fora de escopo — caminho PR → VPS persistente (risco **aceito, aberto, não bloqueante**; **não** resolvido aqui)

**Decisão do solicitante (revisões 2 e 3 deste contrato): o CI/CD existente não é alterado neste lote nem no programa nesta fase.** Esta seção existe para deixar o risco **explícito, rastreável e assinado**, não para tratá-lo.

- Estado atual, mantido inalterado por decisão: `.github/workflows/deploy-homolog.yml` dispara em `pull_request` para `main`, delega a `.github/workflows/deploy.yml` e implanta na VPS persistente em `/home/apps/portal-homolog` (3102/5102) com `git_mode: pr`, `pr_number` e `verify_ref` preenchido pela expressão de SHA do head do pull request (`github.event.pull_request.head.sha`). Ou seja: **o head do PR, não aprovado, pode chegar à máquina que hospeda ambiente e segredos**.
- **Este lote não altera, não mitiga, não bloqueia e não compensa esse caminho.** Nenhum arquivo em `.github/` pode ser editado, criado ou removido — incluindo `deploy-homolog.yml`, `deploy.yml`, `ci.yml`, `deploy-prod.yml`, `deploy-dev.yml` e `rollback.yml`.
- O gate entregue por P0-09 **não** cobre esse caminho: ele inspeciona o repositório local e não participa de nenhum pipeline. Documentação deste lote que apresente o gate como proteção contra deploy de PR é **incorreta** e deve ser rejeitada na revisão.
- O risco é classificado como **supply chain / caminho de deploy não aprovado para a VPS persistente**. Situação padronizada: **ACEITO** (decisão do solicitante), **ABERTO**, **NÃO MITIGADO**, **NÃO COBERTO PELO GATE**, **NÃO BLOQUEANTE para o go-live**, **COM ASSINATURA OBRIGATÓRIA no go/no-go** (ver **R-1**).
- **Regra de veracidade:** nenhum artefato deste lote — nem `CI-CD.md`, nem `PROD_DECISOES.md`, nem `implementation-history.md`, nem o relatório de revisão — pode marcar R-1 como **resolvido**, **mitigado**, **fechado** ou **coberto pelo gate**. O go/no-go lista R-1 como **aceito**, nunca como resolvido.
- **HD-1 muda de natureza:** deixa de ser bloqueio de go-live e passa a exigir apenas **registro e aceite explícito** do risco (assinatura no go/no-go). A decisão sobre *quando e como* substituir o caminho PR → VPS continua sendo uma **decisão futura** (lote próprio com revisão de CI/CD), não uma precondição de lançamento.

### Fora de escopo — divergência de domínio e host key (registradas, não corrigidas aqui)

- **Domínio:** o único valor de domínio adotado no programa é o canônico `https://portal-noticias.com/`. Os workflows existentes usam hoje `portal-noticias.com.br` (`host` de DEV/HOMOLOG/PROD e `allowed_hosts_extra` de `www`). Essa divergência é **registrada** e **não** é corrigida neste lote: alterar qualquer valor de domínio em workflow exige **lote posterior**, e mesmo lá **sem** mudar estrutura, gatilhos, jobs ou comportamento. O go/no-go registra a divergência e o lote que a resolve.
- **Host key / `known_hosts`:** a validação e o *pinning* da host key da VPS (`known_hosts`) são atribuídos a **WS-03** (F1), com passo, evidência e gate **GP-2a** e linha no go/no-go. Este lote **não** acessa a VPS, **não** gera nem valida host key e **não** altera `known_hosts`.

### Documentação (somente decisões deste lote)

- `CI-CD.md`, `PROD_DECISOES.md` e `infra/DEPLOY.md` recebem **apenas** o conteúdo deste lote:
  - o que o gate de proveniência verifica e como invocá-lo;
  - o contrato do script (uso, exit codes, o que ele **não** faz);
  - o registro de que o gate só é efetivo com branch protection do GitHub configurada;
  - o registro de que **o caminho PR → VPS permanece ativo**, que este lote **não** o alterou e que o risco está **aceito, aberto, não mitigado, não coberto pelo gate e não bloqueante**, com assinatura exigida no go/no-go (**R-1**);
  - o registro de que o gate **não** é executado automaticamente por nenhum workflow, já que **nenhum pipeline foi alterado**;
  - o registro da **divergência de domínio** (canônico `.com` × `portal-noticias.com.br` nos workflows) como pendência de lote posterior, sem alteração de workflow.
- **Proibido:** reescrever, reorganizar ou "melhorar" seções existentes desses documentos; documentar decisões de outros lotes; prometer deploy, go-live ou infraestrutura não entregue; afirmar que o risco PR → VPS foi tratado, resolvido, mitigado ou coberto.

## Áreas/arquivos esperados

### Escrita autorizada (lista fechada)

| Caminho | Natureza | Observação |
|---|---|---|
| `agentic-framework/state/run-20260925-1433-go-live-producao/lote-p0-1-proveniencia.md` | já criado (este contrato) | contrato do lote |
| `agentic-framework/state/run-20260925-1433-go-live-producao/provenance-reconciliation.md` | **aditivo ou nenhuma** | inventário de P0-01 já existente (fase de planejamento, read-only). **Não criar `proveniencia-inventario.md`**: evita artefato sobreposto. Ver "P0-01" abaixo |
| `agentic-framework/state/run-20260925-1433-go-live-producao/implementation-history.md` | novo | histórico do lote, decisões e comandos |
| `agentic-framework/state/run-20260925-1433-go-live-producao/lote-p0-1-evidencias.md` | novo | saída dos comandos de validação e do caso negativo esperado |
| `scripts/release/verificar-proveniencia.sh` | novo, executável | saída de P0-09 |
| `CI-CD.md` | acréscimo seccionado | apenas decisões deste lote |
| `PROD_DECISOES.md` | acréscimo seccionado | apenas decisões deste lote |
| `infra/DEPLOY.md` | acréscimo seccionado | apenas decisões deste lote |

Qualquer arquivo fora desta lista exige **aprovação do orchestrator** e justificativa no `implementation-history.md`.

**`run-state.json` é explicitamente EXCLUÍDO desta lista (revisão 3, achado M1).** O arquivo `agentic-framework/state/run-20260925-1433-go-live-producao/run-state.json` é **exclusivamente do orchestrator**, atualizado **após** o término do lote e **fora do diff do executor**. O executor **não** o cria, **não** o edita e **não** o inclui em nenhuma evidência de diff. Antes da revisão 3, o `Definition of Done` exigia que o executor atualizasse `run-state.json`, o que era **incompatível com AC-9** (diff confinado à lista de escrita): a contradição está resolvida em favor do diff confinado. Ver **AC-10**.

**`.github/` é inteiramente proibido.** Nenhum arquivo em `.github/` — `ci.yml`, `deploy.yml`, `deploy-homolog.yml`, `deploy-dev.yml`, `deploy-prod.yml`, `rollback.yml` ou qualquer outro, inclusive **novo** — pode ser editado, criado, movido ou removido neste lote. Nenhum gatilho, job, `if`, `needs`, matriz, `environment` ou `secrets` pode mudar. Nenhum **valor de domínio** em workflow pode mudar (`.com` × `.com.br` permanece como divergência registrada). Também são proibidos: `backend/`, `frontend/`, `infra/nginx/`, `infra/backup/`, `docker-compose*.yml`, `.env*`, `known_hosts` e migrations.

### Arquivos protegidos (proibido tocar, ler para verificação ok; alterar, nunca)

- `backend/config/settings.py` — P0-02 é **verificação**, não correção.
- `backend/config/middleware.py`, `backend/config/health.py`, `backend/config/metrics.py`, `backend/config/observability.py` — pertencem a outras execuções.
- **`.github/`** — todo o CI/CD existente é intocado por decisão do solicitante (revisões 2 e 3 deste contrato). Inclui `ci.yml`, `deploy.yml`, `deploy-homolog.yml`, `deploy-dev.yml`, `deploy-prod.yml` e `rollback.yml`. Nenhuma referência a arquivo de workflow pode ser adicionada, removida ou alterada, e **nenhum valor de domínio** em workflow pode mudar.
- `agentic-framework/state/run-20260925-1433-go-live-producao/run-state.json` — **exclusivo do orchestrator**, fora do diff do executor (**AC-10**).
- `agentic-framework/state/run-20260925-1020-observabilidade/` — WIP **isolado** desta run; run aberta, artefato separado. Este lote **não** adota, não aproveita e não fecha esse WIP.
- `agentic-framework/state/run-20260924-2136-ingestao-noticias/` — run aberta, artefato separado.
- `frontend/` (aplicação, componentes, `package.json`, `package-lock.json`).
- Migrations (`backend/**/migrations/`) e qualquer lockfile.
- Segredos: `.env*`, chaves, arquivos de credencial, valores de `secrets` do GitHub, variáveis de ambiente com credencial.

## Interfaces afetadas

### Interface 1 — CLI do gate (nova, contrato estável)

```
scripts/release/verificar-proveniencia.sh [--expected-sha <40-hex>] [--repo <dir>] [--json]
```

- `--expected-sha`: SHA de release **obrigatório** para o gate de release. **Ausência da flag ⇒ exit `1` (resultado incompleto):** o script registra que a checagem de SHA foi **não solicitada**, marca o resultado overall como **incompleto** e **reprova**. Ausência da flag **nunca** é aprovação automática nem aprovação por omissão. Os três exit codes permanecem `0`/`1`/`2`: SHA em formato inválido é **uso incorreto** (`2`), não SHA ausente.
- `--repo`: diretório do repositório a inspecionar (default: raiz do repositório do script).
- `--json`: saída estruturada para CI, **sem** incluir valor de segredo em nenhum campo.
- `--help`: uso e exit codes, sem executar checagem.
- **Exit codes:** `0` aprovado; `1` reprovado — uma ou mais checagens falharam, não puderam ser executadas, **ou o resultado ficou incompleto (inclui `--expected-sha` ausente)**; `2` uso incorreto.
- Contrato de read-only: o script **não** cria, altera, move ou apaga arquivo algum; **não** executa `git add/commit/push/merge/rebase/reset/clean/checkout/switch/stash/restore/apply`; **não** faz rede; **não** lê variável de ambiente que possa conter segredo; não exige privilégio elevado; não gera `__pycache__`.
- Compatibilidade: `bash`/`sh` conforme `#!/usr/bin/env bash`, sem depender de `jq`, `actionlint` ou `shellcheck` em tempo de execução. `python3` é usado apenas para parse in-memory; ausência de `python3` ou de PyYAML ⇒ falha fechada com motivo, sem fallback silencioso.

### Interface 2 — CI/CD existente (explicitamente NÃO alterada)

- Nenhuma interface de pipeline é criada, alterada ou removida. `.github/workflows/deploy-homolog.yml` **continua** disparando em `pull_request` e implantando o head do PR na VPS de HOMOLOG; `.github/workflows/deploy.yml` (reutilizável, com `git_mode: pr`) **continua** como está.
- O gate deste lote **não é registrado em nenhum workflow** e **não roda automaticamente**. Ele só é executado quando alguém o invoca manualmente, local ou externamente.
- Consequência: o gate **não** participa de nenhum required status check hoje. Mesmo após **HD-2** (branch protection), ele não será exigido automaticamente enquanto não for registrado como check — o que **não** pode ser feito neste lote, por decisão de não tocar em CI/CD.
- Nenhuma interface de aplicação, API, banco, fila, cache, cookie ou sessão é alterada.

### Interface 3 — documentação (consumida por humano e por operador)

- `CI-CD.md`, `PROD_DECISOES.md` e `infra/DEPLOY.md` passam a conter a seção única e delimitada "Lote P0-1 — Baseline de proveniência e gate de release", com: uso do script, exit codes, o que o gate **não** cobre, a nota de que o gate não roda em nenhum pipeline, o **risco aceito e aberto** do caminho PR → VPS (**R-1**, com assinatura exigida no go/no-go), a **divergência de domínio** registrada (canônico `.com` × `portal-noticias.com.br` dos workflows) e a dependência de branch protection (**HD-2**).

## Critérios de aceite (AC-1..AC-10)

Formato: **Dado** X, **quando** Y, **então** Z.

### AC-1 — Inventário de proveniência atribuído por run

**Dado** um working tree com arquivos modificados rastreados e arquivos não rastreados, **quando** o executor captura o inventário com comandos Git somente de leitura, **então** o inventário re-derivado existe em **um** dos dois destinos previstos (extensão aditiva de `provenance-reconciliation.md` **ou** `lote-p0-1-evidencias.md`, sem criar documento paralelo) contendo branch, `HEAD` completo, lista de rastreados modificados, lista de não rastreados e, para **cada** item, a run de origem ou a marcação "origem não determinada — exige decisão humana", junto do comando exato que reproduz cada seção.

### AC-2 — Inventário sem mutação e sem tocar arquivos protegidos

**Dado** o inventário antes e depois da execução do lote, **quando** se comparam `git status --porcelain`, a lista de não rastreados e o `HEAD`, **então** a única diferença em relação ao estado inicial são os arquivos da lista de escrita autorizada, `HEAD` não mudou, nenhum arquivo protegido aparece como alterado e nenhum comando Git de escrita foi executado.

### AC-3 — `settings.py` verificado, não corrigido

**Dado** `backend/config/settings.py` no estado atual, **quando** o lote executa `ast.parse`, `compile()` em memória e — se o ambiente permitir sem rede, sem banco e sem segredo — `manage.py check`, **então** o resultado de cada verificação é registrado em `lote-p0-1-evidencias.md` com comando, exit code e saída, nenhum `__pycache__`/`.pyc` é criado, o arquivo **não** é editado e, se alguma verificação falhar, o lote é reprovado e a correção é devolvida ao orchestrator em vez de executada.

### AC-4 — Gate read-only, determinístico e fail-closed

**Dado** `scripts/release/verificar-proveniencia.sh` executável, **quando** ele roda em um repositório de teste, **então** ele reprova com exit code `1` em cada um dos casos da seção P0-09, aprova com `0` quando o repositório está limpo e o SHA bate, retorna `2` em uso incorreto, **falha com `1` marcando resultado incompleto quando `--expected-sha` não é fornecido** (nunca `0` por omissão da flag), não altera nenhum arquivo do repositório inspecionado, não acessa a rede, não exige segredo e falha fechada — com motivo explícito — quando uma checagem não pode ser executada.

### AC-5 — Achados sem vazamento de segredo

**Dado** um arquivo **rastreado** contendo um segredo aparente, **quando** o gate roda, **então** o achado informa apenas identificador da regra, caminho e número da linha, com a declaração explícita de que o valor foi omitido, e a saída completa do script **não contém** o valor do segredo nem qualquer trecho dele — inclusive no modo `--json`. **Dado** um segredo apenas em arquivo não rastreado ou ignorado, **quando** o gate roda, **então** o valor não é analisado nem impresso. **A prova é não tautológica:** o teste usa um **literal sintético real**, gerado na execução, em **arquivo rastreado de um repositório de fixture descartável fora do repositório do portal**, e exige **três** resultados — (a) o literal **está** no arquivo rastreado (controle positivo), (b) o gate **detecta** o achado com regra/caminho/linha e sai com `1` (prova de detecção), (c) o literal **não** aparece em `stdout`, `stderr` nem em `--json` (prova de não-vazamento). Fixture sem detecção é **blocker**, não sucesso. Comandos em §"Comandos de validação", item 3.

### AC-6 — Caminho PR → VPS: fora de escopo, preservado e registrado como aceito e aberto

**Dado** um repositório cujo CI/CD existente implanta o head de pull request na VPS persistente de HOMOLOG, **quando** o lote P0-1 é implementado, **então** (a) **nenhum** arquivo em `.github/` é editado, criado ou removido e o diff do lote é vazio em `.github/`; (b) o comportamento atual do deploy por PR permanece **inalterado e ativo**; (c) o risco é registrado em `PROD_DECISOES.md`, em `CI-CD.md` e no `implementation-history.md` como **aceito, aberto, não mitigado, não coberto pelo gate e não bloqueante para o go-live** (**R-1**), com a descrição do caminho afetado e a exigência de **assinatura no go/no-go**; (d) **nenhum** artefato do lote afirma, sugere ou deixa implícito que esse risco foi resolvido, mitigado, bloqueado ou coberto pelo gate; e (e) **nenhum** valor de domínio em workflow foi alterado.

### AC-7 — Documentação restrita às decisões do lote

**Dado** `CI-CD.md`, `PROD_DECISOES.md` e `infra/DEPLOY.md`, **quando** o lote é implementado, **então** cada arquivo recebeu apenas a seção do lote P0-1 (uso e exit codes do gate, cobertura e não-cobertura, o fato de o gate não rodar em nenhum pipeline, o registro de que **o caminho PR → VPS permanece ativo e pendente de decisão**, e o registro de que o gate só é efetivo com branch protection do GitHub configurada — **HD-2**), sem reescrita de seções existentes, sem afirmar decisão de outro lote e sem afirmar mitigação do risco PR → VPS.

### AC-8 — O gate só bloqueia de fato com branch protection do GitHub

**Dado** um repositório no GitHub **sem** branch protection configurada, **quando** alguém faz push direto ou um PR é mergeado sem verificação, **então** o gate **não impede** nada por si só; e, dado o mesmo repositório **com** branch protection e o gate registrado como required status check, **quando** esse cenário ocorrer, **então** o merge é bloqueado. O contrato **registra explicitamente** essa limitação, em `CI-CD.md`, `PROD_DECISOES.md` e neste arquivo, e trata a configuração da branch protection como dependência humana (**HD-2**) e como gate de go-live — não como entregue por este lote.

### AC-9 — Diff confinado ao lote

**Dado** o diff final do lote, **quando** comparado à lista de escrita autorizada, **então** nenhum arquivo fora dela foi alterado, **`.github/` está byte a byte idêntico ao estado inicial**, nenhum lockfile, migration, arquivo de frontend de aplicação, segredo ou run foi tocado, `HEAD` permaneceu inalterado e não há comando de escrita Git no histórico do lote. `run-state.json` **não** faz parte do diff do executor — ver **AC-10**.

### AC-10 — `run-state.json` é do orchestrator, fora do diff do executor

**Dado** o diff final do lote, **quando** o executor compara `git status`/`git diff` com a lista de escrita autorizada, **então** `agentic-framework/state/run-20260925-1433-go-live-producao/run-state.json` **não** aparece como criado ou modificado por ele, e o estado da run (fase, findings, `blocked_reason`, follow-ups) é atualizado **pelo orchestrator depois** que o lote for encerrado, com base em `lote-p0-1-evidencias.md`, no `code-review-contract.md` e no veredito do tester. O executor **não** inventa estado de run e **não** fecha fase.

## Não-objetivos

- **Não** acessar, alterar, reiniciar ou inspecionar a VPS; **não** executar `ssh`, `scp`, `rsync` ou `pm2`; **não** alterar DNS, TLS, firewall, usuário, chave ou porta. Em particular, **não** validar nem fixar (pinning) host key / `known_hosts` — isso é de **WS-03** (GP-2a).
- **Não** executar migration, seed, `manage.py migrate`, backup, restore ou qualquer escrita em banco.
- **Não** corrigir `backend/config/settings.py` — apenas verificar e reportar (a correção de conteúdo é **P0-02b**/GP-1b; aqui é a verificação **G1**, que alimenta GP-1/GP-1b).
- **Não** alterar código de aplicação: backend, frontend, componentes, rotas, páginas, estilos, `package.json` ou lockfiles.
- **Não** alterar **nenhum** arquivo em `.github/` — `ci.yml`, `deploy.yml`, `deploy-homolog.yml`, `deploy-dev.yml`, `deploy-prod.yml`, `rollback.yml` ou qualquer outro. Gatilhos, jobs, condições, matriz, permissões, `environment` e `secrets` permanecem **exatamente** como estão. Esta é uma decisão do solicitante e vale acima de qualquer otimização de escopo.
- **Não** adicionar, remover ou "corrigir" qualquer workflow; **não** criar workflow novo; **não** registrar o gate como step de nenhum job; **não** alterar branch protection, rulesets, secrets ou environments por API ou UI.
- **Não** alterar **nenhum valor de domínio** em workflow (`.com` × `.com.br`): a divergência é registrada e fica para lote posterior, sem alterar estrutura nem gatilhos.
- **Não** escrever, criar ou editar `run-state.json` nem qualquer outro arquivo de estado da run — é do **orchestrator**, após o lote (**AC-10**).
- **Não** editar `.gitignore` nem qualquer regra de ignore: a exclusão do diretório de estado das runs (inclusive o artefato não rastreado desta run) do release é resolvida por **inventário e ownership** em **G5/D-08**, e ele permanece **untracked** — logo, motivo de reprovação do gate, que é a leitura correta.
- **Não** fechar, bloquear, condicionar nem recompensar o caminho PR → VPS dentro deste lote. Ele permanece **ativo** e registrado como **R-1** (risco **aceito, aberto, não mitigado, não coberto pelo gate, não bloqueante**). Alegar que ele foi resolvido é **blocker**.
- **Não** inventar estratégia de deploy de HOMOLOG (branch de promoção, `workflow_dispatch`, `git_mode: branch`, nome de branch, promoção automática).
- **Não** implementar bind loopback de Gunicorn/Next em `127.0.0.1`/rede privada. É **separável**, pertence ao lote de host/rede (P0-04) e está **bloqueado por decisão humana** sobre a topologia de execução e o impacto em homologação.
- **Não** remover o modo `git_mode: pr` do workflow reutilizável `deploy.yml`.
- **Não** criar branch protection, regras de repositório, secrets, environments ou hooks por API — é configuração humana/admin (**HD-2**).
- **Não** rodá-lo em `PYTHONDONTWRITEBYTECODE=0`; **não** gerar `__pycache__`, coverage ou artefato de build.
- **Não** normalizar, formatar, reordenar imports ou "limpar" arquivos existentes durante a execução do lote.
- **Não** declarar o lote como "provenance resolvida" para toda a run: este lote entrega **baseline + gate**, não a reconciliação completa das runs abertas.

## Restrições técnicas

- **Read-only por construção:** todo comando de validação e todo o script são de leitura. Qualquer necessidade de escrita fora da lista autorizada é blocker.
- **Fail-closed:** ausência de ferramenta ou de contexto ⇒ falha, nunca aprovação implícita.
- **Determinismo:** mesma entrada ⇒ mesma saída, ordenação estável, sem timestamp no corpo do resultado, para permitir diff entre execuções e entre agentes.
- **Performance:** o gate deve concluir em segundos sobre o repositório; sem varredura recursiva cega de `node_modules`/`.git`/ambientes virtuais.
- **Segurança/privacidade:** o gate é uma ferramenta de segurança; ele próprio não pode vazar segredo, não pode imprimir valor, não pode exigir segredo e não pode ser usado como vetor de exfiltração. Nenhum valor de credencial pode aparecer em artefatos, logs, `implementation-history.md` ou documentação — apenas referência de existência.
- **Escopo de leitura do script:** apenas arquivos **rastreados** (`git ls-files`) para as checagens de conteúdo; untracked é motivo de reprovação por si, não material de análise de conteúdo.
- **Idempotência:** reexecutar o lote não deve produzir mudança adicional no working tree.
- **Estilo:** scripts e runbooks existentes do projeto; comentários em português; sem introdução de dependência nova (nenhum pacote, nenhum binário obrigatório).
- **Portabilidade:** o script não pode depender de `jq`, `actionlint` ou `shellcheck` em execução; `python3` e PyYAML são usados quando presentes e sua ausência é falha fechada.
- **Atribuição:** mudanças de arquivos pré-existentes de outra run são proibidas neste lote; a autoria de qualquer arquivo novo é deste lote e da run 20260925-1433.

## Revisão obrigatória

Revisão de código **obrigatória**, por dois eixos, por reviewer independente do executor:

1. **Eixo CI/CD — não-regressão:** nenhum arquivo em `.github/` alterado; **nenhum valor de domínio** em workflow alterado; comportamento atual de deploy preservado; o gate não foi registrado em pipeline nenhum e a documentação **não** afirma que ele roda automaticamente; fail-closed real do gate; ausência de bypass; determinismo; exit codes; comportamento do gate quando a árvore está suja.
2. **Eixo security/segurança:** o gate não vaza segredo em nenhum modo (inclusive `--json` e stderr); cobertura de segredos aparentes sem falsos positivos que tornem o gate inútil; o gate não é contornável por arquivo ignorado, `.gitignore` permissivo ou `skip-worktree`; nenhum arquivo protegido tocado; nenhum segredo em artefato; e **o risco PR → VPS (R-1) está registrado como aceito, aberto, não mitigado e não coberto pelo gate**, sem alegação falsa de resolução.
3. **Eixo de veracidade documental:** nenhum artefato do lote afirma que o caminho PR → VPS foi resolvido, mitigado ou coberto pelo gate; nenhum documento promete deploy, go-live ou pipeline que não existe; nenhum documento diz que R-1 "não bloqueia" sem dizer, no mesmo parágrafo, que ele **exige aceite assinado no go/no-go**.
4. **Eixo de custódia de estado (AC-10):** `run-state.json` **não** aparece no diff do executor e nenhum artefato do lote afirma que o executor atualizou o estado da run; nenhum comando Git de escrita foi usado para isso.

**Gatilhos de `review-triggers.md` aplicáveis:** introdução de comportamento de segurança (o gate), contrato novo usado por outros sistemas (a CLI do script) e volume de diff. A revisão é pré-requisito de fechamento do lote.

## Dependências humanas (bloqueantes quando marcadas como gate)

| ID | Dependência | Natureza | Bloqueia |
|---|---|---|---|
| **HD-1** | **Não bloqueia mais o go-live (revisão 3).** O que é exigido agora é **registro e aceite explícito do risco R-1**, assinados no go/no-go: qual é o caminho PR → VPS ativo, o que está sendo aceito, por quanto tempo e quem assinou. A **decisão sobre a futura substituição** desse caminho (gatilho, branch, `verify_ref` aprovado, ou desabilitar o deploy por PR) continua decisão futura, de lote próprio com revisão de CI/CD. **Nenhuma implementação deste lote.** | registro/aceite + decisão futura | **não** bloqueia este lote **e não bloqueia o go-live**; bloqueia apenas a alegação de que "supply chain está fechada" e o encerramento de P0-09 com esse título |
| **HD-2** | Configurar **branch protection** no GitHub para a branch protegida, com PR obrigatório. Como o gate **não** foi registrado em workflow nenhum, mesmo com branch protection ele não vira required status check automaticamente: exigiria um workflow, o que está fora de escopo por decisão. | configuração | eficácia do gate; **não** é entregue por este lote; **não** bloqueia o go-live (limitação registrada, ver R-11 no `action-plan.md`) |
| **HD-3** | Definir o SHA/branch de release e a política de promoção entre `develop`, `main` e HOMOLOG, incluindo quem aprova. **No estado re-derivado em 2026-09-25T18:32:47Z, `develop` e `origin/develop` estão em paridade (`0/0`) e `948a5b5`/`645aca3` já constam do remoto — não há push pendente; o `645aca3` citado em outros artefatos desta run é um snapshot datado e não é o `HEAD` observado. O SHA de release é re-derivado no início do lote (`git rev-parse HEAD`) e confirmado aqui.** | decisão | uso de `--expected-sha` em promoção real |
| **HD-4** | Topologia de execução para bind loopback (Gunicorn/Next em `127.0.0.1` vs rede privada) e impacto em HOMOLOG. | decisão | lote de host/rede; **fora** deste lote e explicitamente separável |
| **HD-5** | Reconciliação formal das runs abertas `20260925-1020-observabilidade` (WIP **isolado** desta run) e `20260924-2136-ingestao-noticias` e dos arquivos não rastreados: quem é dono de cada arquivo. | decisão/orquestração | saída do critério de parada da run mestre; este lote apenas **documenta** |
| **HD-6** | Onde e como o gate será executado de forma recorrente, já que **nenhum workflow pode ser alterado** neste lote: runner local, hook externo, job de outro projeto ou nenhum. | decisão futura | eficácia operacional do gate; **não** bloqueia a entrega do script |
| **HD-7** | **Validação e pinning da host key da VPS** (`known_hosts`) no caminho de acesso do operador e do usuário de deploy, com evidência de que uma chave divergente é rejeitada. Atribuída a **WS-03** (gate **GP-2a**), **não** a este lote. | decisão/ação de infraestrutura | gate GP-2a e linha do go/no-go |

## Riscos aceitos / pendentes registrados

| ID | Risco | Situação neste lote |
|---|---|---|
| **R-1** | **Supply chain:** o head de um pull request não aprovado pode ser implantado na VPS persistente que hospeda HOMOLOG (`.github/workflows/deploy-homolog.yml` → `deploy.yml` com `git_mode: pr`). Código não aprovado pode rodar em uma máquina que tem segredos. | **ACEITO** por decisão do solicitante (revisão 3 deste contrato) e, por isso, **NÃO BLOQUEANTE para o go-live**. Permanece **ABERTO**: **não** alterado, **não** mitigado, **não** bloqueado, **não** coberto pelo gate. Nenhum artefato pode marcá-lo como **resolvido**. Exige **registro e aceite explícito, assinados, no go/no-go**; a decisão futura sobre a substituição do caminho segue em **HD-1**, em lote próprio. O gate entregue **não** cobre este risco. |
| **R-2** | **Divergência de domínio:** o canônico do programa é `https://portal-noticias.com/`, enquanto os workflows existentes usam `portal-noticias.com.br` (hosts de DEV/HOMOLOG/PROD e `www`). | **ABERTO e registrado.** Este lote **não** altera valor de domínio em workflow. Correção em **lote posterior**, sem mudar estrutura nem gatilhos, com linha no go/no-go. |

## Comandos de validação (somente leitura)

Todos os comandos abaixo são **não destrutivos** e de **leitura**. Nenhum deles altera estado, e nenhum toca em `.github/`. Executar sempre a partir da raiz do repositório.

### 1. Baseline de proveniência (P0-01)

```bash
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git rev-parse origin/develop
git rev-list --left-right --count origin/develop...develop      # esperado: 0<TAB>0 enquanto em paridade
git for-each-ref --format='%(refname) %(objectname)' refs/heads refs/remotes
git status --porcelain=v1 -uall
git diff --name-only HEAD
git diff --name-status HEAD
git ls-files --others --exclude-standard
git log -1 --format='%H %ci %s'
git worktree list                                             # leitura: worktrees registrados (ex.: wt-merge prunable)
git cat-file -t 4c57ff04 2>/dev/null || echo 'AUSENTE: objeto 4c57ff04 nao existe mais'
git for-each-ref --contains 4c57ff04 --format='%(refname)' 2>/dev/null   # esperado: vazio (dangling)
git rev-list --all | grep -c '^4c57ff04'                     # esperado: 0 (ninguma ref o alcanca)
git reflog --all | grep -c '4c57ff04' || true                # esperado: 0 nesta observacao
git stash list            # leitura: apenas para provar que nada foi stashed
```

**Regras de leitura deste inventário (re-derivação, nunca snapshot herdado):**

1. Todo o bloco é **carimbado com timestamp** no momento da execução, e nenhum valor é copiado de `provenance-reconciliation.md` nem de qualquer outro artefato — aquele arquivo é **snapshot de planejamento** e vale como inventário de arquivos e atribuição, não como estado Git atual.
2. Se `develop` e `origin/develop` **não** estiverem em paridade, o gate reprova por SHA divergente e o lote **reprova** — a decisão de push é humana (**G2/D-08**), não do executor.
3. Se `4c57ff04` **não** existir mais, isso é **finding de perda de objeto** (a árvore é idêntica à de `948a5b5` e a origem do cherry-pick deixa de ser recuperável) e o lote reprova até decisão humana de **G3/D-08**.
4. A divergência **ref solta × `.git/packed-refs`** observada na última medição (`origin/develop` `7715dae8` × `b671a86`; `origin/main` `bb63cb3d` × `cbe161e`) é **pendência de G3/D-08**, não fato resolvido: o lote **registra**, não normaliza.

### 2. Verificação de `settings.py` (P0-02) — sem escrita

```bash
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import ast, pathlib, sys
p = pathlib.Path('backend/config/settings.py')
src = p.read_text(encoding='utf-8')
try:
    ast.parse(src)
    compile(src, str(p), 'exec')
    print('SETTINGS_PY_OK')
except SyntaxError as exc:
    print('SETTINGS_PY_FAIL', exc)
    sys.exit(1)
PY
```

Comando opcional (somente se o ambiente local permitir **sem rede, sem banco e sem segredo**; caso contrário registrar `SKIP` com o motivo):

```bash
PYTHONDONTWRITEBYTECODE=1 DJANGO_SETTINGS_MODULE=config.settings \
  python3 manage.py check --fail-level ERROR
```

### 3. Gate de proveniência (P0-09)

```bash
test -x scripts/release/verificar-proveniencia.sh
bash -n scripts/release/verificar-proveniencia.sh
scripts/release/verificar-proveniencia.sh --help
scripts/release/verificar-proveniencia.sh; echo "exit=$?"   # sem --expected-sha: esperado exit=1 (incompleto)
scripts/release/verificar-proveniencia.sh --expected-sha "$(git rev-parse HEAD)"; echo "exit=$?"
scripts/release/verificar-proveniencia.sh --expected-sha 0000000000000000000000000000000000000000; echo "exit=$?"
scripts/release/verificar-proveniencia.sh --expected-sha nao-e-sha; echo "exit=$?"   # formato inválido: esperado exit=2
scripts/release/verificar-proveniencia.sh --json | head -40
```

**Caso negativo obrigatório (evidência):** no working tree atual, com untracked e modificados, o gate **deve falhar** com exit `1` e listar as razões. Registrar a saída em `lote-p0-1-evidencias.md`. Um gate que passe neste estado é um **blocker**.

**Prova de read-only:** o gate não pode alterar o repositório inspecionado. Verificar com

```bash
git status --porcelain=v1 > /tmp/p0-1-antes.txt
scripts/release/verificar-proveniencia.sh --repo . >/dev/null 2>&1
git status --porcelain=v1 > /tmp/p0-1-depois.txt
diff /tmp/p0-1-antes.txt /tmp/p0-1-depois.txt && echo "READONLY_OK"
```

**Prova de não-vazamento (não tautológica — exige literal sintético real, arquivo rastreado e detecção comprovada):**

O teste **não** pode consistir em buscar um literal que existe em lugar nenhum. O executor **gera um literal sintético** (valor falso, sem relação com qualquer credencial), grava-o em um **arquivo rastreado** de um **repositório de fixture descartável, criado fora do repositório do portal** (nenhum comando Git de escrita é executado dentro do repositório do portal), roda o gate contra esse fixture e registra **três** resultados: (a) **controle positivo** — o literal **está** no arquivo rastreado; (b) **prova de detecção** — o gate **reporta** o achado, com identificador de regra, caminho e linha, e sai com `1`; (c) **prova de não-vazamento** — o valor **não** aparece em `stdout`, nem em `stderr`, nem em `--json`, em nenhum dos modos, nem parcialmente.

```bash
FIXTURE_DIR="$(mktemp -d /tmp/p0-1-gate-fixture-XXXXXX)"
LITERAL="sk-live-SINTETICO-$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')"
printf 'API_TOKEN = "%s"\n' "$LITERAL" > "$FIXTURE_DIR/config_exemplo.py"

# Fixture descartável FORA do repositório do portal (nada é escrito no portal).
git -C "$FIXTURE_DIR" init -q
git -C "$FIXTURE_DIR" add config_exemplo.py
git -C "$FIXTURE_DIR" -c user.name=fixture -c user.email=fixture@localhost commit -qm fixture
SHA_FIXTURE="$(git -C "$FIXTURE_DIR" rev-parse HEAD)"

# (a) CONTROLE POSITIVO: o literal existe no arquivo rastreado -> esperado: 1
grep -F -c "$LITERAL" "$FIXTURE_DIR/config_exemplo.py"

# (b)+(c) O gate reprova (1) e não imprime o valor
scripts/release/verificar-proveniencia.sh --repo "$FIXTURE_DIR" --expected-sha "$SHA_FIXTURE" \
  > "$FIXTURE_DIR/out.txt" 2> "$FIXTURE_DIR/err.txt"; echo "exit=$?"   # esperado: 1
scripts/release/verificar-proveniencia.sh --repo "$FIXTURE_DIR" --expected-sha "$SHA_FIXTURE" --json \
  > "$FIXTURE_DIR/out.json.txt" 2> "$FIXTURE_DIR/err.json.txt"; echo "exit=$?"  # esperado: 1

# (b) PROVA DE DETECCAO: o achado existe e traz regra/caminho/linha, sem o valor
grep -E 'config_exemplo\.py' "$FIXTURE_DIR/out.txt"   # esperado: >= 1 linha de finding
grep -F -c "$LITERAL" "$FIXTURE_DIR/out.txt"           # esperado: 0  <- o achado existe mas nao vaza o valor

# (c) PROVA DE NAO-VAZAMENTO em stdout, stderr e --json -> esperado: 0 em todos
grep -F -c "$LITERAL" "$FIXTURE_DIR/out.txt" "$FIXTURE_DIR/err.txt" \
                           "$FIXTURE_DIR/out.json.txt" "$FIXTURE_DIR/err.json.txt"
```

**Leitura do resultado:** (a) `0` ⇒ fixture mal construído, repetir; (b) **sem linha de finding** ⇒ o gate **não** detecta segredo e o teste é vazio — **blocker**; (c) qualquer contagem **≠ 0** ⇒ **vazamento**, **blocker**. Registrar os quatro arquivos de saída em `lote-p0-1-evidencias.md` e **apagar a fixture ao final** (`rm -rf` no diretório temporário, fora do portal). **Nenhum placeholder de texto substitui o literal.**

### 4. Ausência de escrita em disco pelo Python

```bash
find . -name '__pycache__' -newermt '-10 minutes' -not -path './.git/*' | head   # esperado: vazio
```

### 5. CI/CD intocado (AC-6, AC-9)

Prova de que **nada** em `.github/` mudou, por conteúdo e por status Git:

```bash
git status --porcelain=v1 -- .github/            # esperado: vazio
git diff --stat HEAD -- .github/                 # esperado: vazio
git diff --name-only HEAD -- .github/            # esperado: vazio
git ls-files --others --exclude-standard -- .github/   # esperado: vazio
git stash list -- .github/                       # esperado: vazio
```

Impressões digitais dos workflows, para comparar antes/depois sem depender de diff:

```bash
find .github -type f -print0 | sort -z | xargs -0 sha256sum    # esperado: idêntico ao início do lote
```

**Leitura esperada (e desejada):** o caminho PR → VPS **continua presente**. Isto é o comportamento **aceito e aberto** de **R-1**, não uma falha do lote. O executor **não** deve tentar corrigi-lo, nem propor patch, nem registrar o item como resolvido.

**Valores de domínio nos workflows (leitura, sem alteração — R-2):** o lote registra, sem editar, os hostnames que hoje existem nos workflows, para que a divergência com o canônico `https://portal-noticias.com/` fique em evidência:

```bash
grep -rn 'portal-noticias' .github/workflows/    # esperado: valores atuais, inalterados
git diff HEAD -- .github/workflows/               # esperado: vazio (nenhum valor de domínio alterado)
```

### 6. Confirmação de diff confinado (AC-9) e custódia de `run-state.json` (AC-10)

```bash
git status --porcelain=v1
git diff --name-only HEAD
git ls-files --others --exclude-standard
git diff --stat HEAD -- .github/
git status --porcelain=v1 -- agentic-framework/state/run-20260925-1433-go-live-producao/run-state.json
```

Nenhum arquivo fora da lista de "Escrita autorizada" pode aparecer como alterado, e nada sob `.github/` pode aparecer. O último comando deve retornar **vazio** para o diff produzido por este lote: `run-state.json` é do **orchestrator**, atualizado depois, **fora** do diff do executor (**AC-10**).

## Definition of Done

> Critérios **AC-1 a AC-10**. Itens marcados *(orchestrator)* **não** pertencem ao diff do executor.

- [ ] Inventário de proveniência re-derivado, com atribuição por run de cada item e comandos de reprodução, em **um** dos dois destinos previstos (AC-1).
- [ ] Inventário de estado Git **re-derivado neste lote**, com **timestamp** e comando por linha: branch, `HEAD`, `origin/*`, paridade `develop` × `origin/develop`, todas as refs, `status -uall`, presença de `4c57ff04` por SHA (`cat-file`, `for-each-ref --contains`, `rev-list --all`, `reflog`), `worktree list` e `stash list` — **sem copiar valor de `provenance-reconciliation.md` ou de qualquer snapshot**; diretório de estado desta run declarado **não rastreado, fora de release, com ownership e sem edição de `.gitignore`**.
- [ ] Nenhum arquivo protegido tocado; `HEAD` inalterado; nenhum comando Git de escrita executado (AC-2, AC-9).
- [ ] **G1 executada neste lote, depois de GP-0:** verificação de `settings.py` registrada em `lote-p0-1-evidencias.md`, com `ast.parse`/`compile()` bem-sucedidos, sem `__pycache__` e sem edição do arquivo (AC-3); resultado repassado a **GP-1** e **GP-1b**.
- [ ] `scripts/release/verificar-proveniencia.sh` existe, é executável, é read-only e reprova os 7 casos previstos, com exit codes `0/1/2`; **sem `--expected-sha` ele falha com `1` e resultado incompleto**, e SHA em formato inválido retorna `2` (AC-4).
- [ ] Saída do gate nunca contém valor de segredo, em texto nem em `--json` (AC-5), provado com **literal sintético real** em arquivo rastreado de fixture descartável **fora** do repositório do portal, com **controle positivo**, **prova de detecção** (achado presente, gate sai `1`) e **prova de não-vazamento** em `stdout`/`stderr`/`--json`; fixture apagada ao final.
- [ ] Caso negativo demonstrado e registrado: gate falha no working tree atual com as razões esperadas.
- [ ] **`.github/` byte a byte idêntico ao estado inicial**; nenhum workflow, gatilho ou job alterado; **nenhum valor de domínio** em workflow alterado; o deploy por PR continua ativo (AC-6, AC-9).
- [ ] Risco **R-1** (supply chain PR → VPS) registrado como **ACEITO, ABERTO, não mitigado, não coberto pelo gate e NÃO BLOQUEANTE para o go-live**, com exigência de **assinatura no go/no-go**, em `PROD_DECISOES.md`, `CI-CD.md` e `implementation-history.md`, **sem** qualquer alegação de resolução ou cobertura pelo gate (AC-6).
- [ ] Divergência de domínio (canônico `.com` × `portal-noticias.com.br` dos workflows) registrada como pendência de lote posterior (AC-6 e R-2).
- [ ] Documentação do lote afirma explicitamente que o gate **não roda em nenhum pipeline** e que só é efetivo com branch protection **e** registro como required status check — o que este lote não faz (AC-7, AC-8).
- [ ] Revisão independente (segurança, CI/CD não-regressão, veracidade documental) concluída, com findings major/blocker remediados ou explicitamente aceitos.
- [ ] `implementation-history.md` do lote completo: comandos executados, decisões, alternativas descartadas, evidência de read-only e registro de R-1.
- [ ] `run-state.json` **não** aparece no diff do lote (AC-10).
- [ ] Nenhum acesso a VPS, DNS, banco, segredo, migration, `known_hosts` ou pipeline.
- [ ] *(orchestrator)* `run-state.json` atualizado **após** o lote, com o estado, `blocked_reason` se **HD-2** estiver aberta, e follow-ups — **fora** do diff do executor (AC-10).

## Registro de limitação (obrigatório, não opcional)

### O gate é condicionalmente eficaz

- Como **script read-only**, ele reprova localmente quando executado — mas **não tem poder de veto por si só**.
- Ele **só bloqueia de fato** quando (a) é executado no pipeline, (b) a **branch protection do GitHub** está configurada com PR obrigatório **e** (c) o gate está registrado como **required status check** naquela branch.
- Neste lote, **apenas a ferramenta** é entregue. Nenhum pipeline foi alterado, então **(a) e (c) não existem hoje**: o gate roda **somente quando alguém o invoca manualmente**. Configurar branch protection sem um check registrado **não** torna o gate obrigatório.
- Portanto: **HD-2 e HD-6 são pré-requisitos de eficácia, não de entrega.** São decisão e ação humanas. **HD-2 não bloqueia o go-live**; a limitação é registrada como risco R-11 no `action-plan.md` e no go/no-go.

### O risco de supply chain é aceito, permanece aberto e não é coberto pelo gate

- O caminho PR → VPS **não** foi alterado, por decisão do solicitante. Ele **continua ativo**: código de pull request não aprovado pode ser implantado na VPS persistente que hospeda HOMOLOG.
- O gate **não** cobre, não compensa e não substitui esse controle, porque não participa de nenhum pipeline.
- **Este lote não resolve R-1.** Situação padronizada: **ACEITO** (por isso **não bloqueia o go-live**) e **ABERTO** (**não** mitigado, **não** coberto pelo gate). O aceite é **registrado e assinado no go/no-go**, e a decisão futura sobre substituir o caminho continua em **HD-1**, em lote próprio.
- Qualquer leitura de que a supply chain foi fechada, resolvida ou mitigada a partir deste lote é **incorreta** e deve ser tratada como finding na revisão. O go/no-go lista R-1 como **aceito**, nunca como resolvido.

## Follow-ups (não fazer neste lote)

1. **R-1 / HD-1 — substituir o caminho PR → VPS (risco aceito, aberto, não bloqueante).** Decisão futura, em lote próprio com revisão de CI/CD: substituir o deploy por PR por um caminho que só aceite código aprovado (branch de promoção, `workflow_dispatch` com SHA explícito, ou desabilitar o deploy por PR). Requer projeto/decisão de como homologação continua funcionando; **não** é executável sem alterar CI/CD, o que está proibido neste lote. **Até lá:** o aceite está assinado no go/no-go.
2. **HD-2** — configurar branch protection com PR obrigatório na branch protegida; registrar evidência (printout das regras) em `PROD_DECISOES.md`. Observar a limitação: sem check registrado, o gate não passa a ser exigido. Não bloqueia o go-live.
3. **HD-6** — definir onde o gate rodará de forma recorrente, já que nenhum workflow pode ser alterado aqui (runner local, hook externo, ou decisão por não executar recorrentemente).
4. **HD-3** — definir SHA de release e política de promoção; documentar o comando canônico `verificar-proveniencia.sh --expected-sha <sha>`. O `645aca3` dos outros artefatos é **snapshot datado**, não SHA de release; no estado re-derivado de 2026-09-25T18:32:47Z `develop` e `origin/develop` já estavam **em paridade** e `948a5b5`/`645aca3` **já estavam no remoto** (sem push pendente).
5. Lote próprio para **registrar o gate em pipeline** (assim que houver decisão de alterar CI/CD), incluindo remoção do modo `git_mode: pr` do workflow reutilizável `deploy.yml`.
6. Lote de correção de **`settings.py`** (**P0-02b** / gate **GP-1b**), condicionado ao resultado de G1/AC-3; se a verificação já passar, o item pode ser encerrado como resolvido por evidência.
7. **HD-5** — reconciliação formal das runs `20260925-1020-observabilidade` (WIP **isolado** desta run) e `20260924-2136-ingestao-noticias` e dos arquivos não rastreados; este lote apenas registra a atribuição tentativa.
8. **HD-4 / P0-04** — bind loopback de Gunicorn/Next; **separável** e **bloqueado por decisão humana** sobre topologia de execução.
9. **HD-7 / WS-03 (GP-2a)** — validação e pinning da host key (`known_hosts`) no acesso do operador e do usuário de deploy, com evidência de rejeição de chave divergente, e registro da divergência de que o caminho de CI usa senha sem fingerprint (que só um lote de CI/CD altera).
10. Lote de **divergência de domínio (R-2)** — alinhar `portal-noticias.com.br` dos workflows ao canônico `https://portal-noticias.com/`, **sem** mudar estrutura, gatilhos ou comportamento, com decisão do solicitante sobre os nomes de ambiente.
11. Lote de host/SSH/rotação root (P0-03), domínio/DNS/TLS (P0-05), backup/restore (P0-06) e isolamento de ambientes (P0-07) — todos fora deste lote, todos repo+infra, todos com contrato próprio.
12. Testes automatizados do próprio script — hoje a cobertura é evidência manual em `lote-p0-1-evidencias.md`; promover a testes versionados é lote de qualidade.
13. Ampliar o conjunto de regras de segredo com allowlist de falsos positivos conhecida, após observar falsos positivos reais em uso.

---

## Addendum da revisão 3 — 2026-09-25

Aplicado a partir da revisão de planejamento. Nenhum escopo foi ampliado; nenhum item do **Histórico** abaixo foi apagado.

| # | Achado | O que mudou nesta revisão 3 |
|---|---|---|
| B1 | Gate circular: GP-0 exigia **G1**, que só pode ser executado **depois** de GP-0 | GP-0 passou a fechar apenas com **G0, G2, G3, G4, G5** (custódia e decisões). **G1** virou item executado **neste lote** (P0-02), **depois** de GP-0, alimentando **GP-1** e **GP-1b**. Registrado em "Precondição de gate" e em §P0-02. |
| B2 | R-1 tratado de forma divergente entre os artefatos e **capaz de bloquear** o go-live | Situação **padronizada**: **ACEITO**, **ABERTO**, **NÃO MITIGADO**, **NÃO COBERTO PELO GATE**, **NÃO BLOQUEANTE**, **COM ASSINATURA NO GO/NO-GO**. **HD-1** deixou de bloquear o go-live e passou a exigir **registro e aceite explícito**. AC-6, AC-7, DoD, "Registro de limitação" e follow-up 1 reescritos. |
| M1 | Conflito **AC-9 × `run-state.json`**: o DoD exigia que o executor atualizasse o `run-state.json`, que não está na lista de escrita autorizada | `run-state.json` passou a ser **exclusivo do orchestrator**, atualizado **após** o lote e **fora** do diff do executor. Novo **AC-10**. AC-9 reescrito sem ambiguidade. `run-state.json` entrou na lista de **arquivos protegidos** para o executor. **Não** foi adicionado à lista de escrita autorizada. |
| M2 | Validação/pinning de host key sem dono | Atribuída a **WS-03** (gate **GP-2a**, linha no go/no-go), com nova dependência **HD-7** e follow-up 9. Este lote declara explicitamente que **não** faz pinning. |
| M3 | Caminho crítico com convergência mal desenhada (no `action-plan.md` §2.2) | Corrigido no `action-plan.md` §2.2/§3.1/§15.1, com as dependências explícitas de cada gate. |
| m1 | Mapa **G6/G7** incorreto no plano | G6 = formalização do WIP da run 1020 como lote próprio (com o desfecho: manter aberta ou encerrar preservando artefatos); G7 = critérios de aceite de proveniência do contrato mestre (satisfeitos por GP-1/GP-1b, **não** é gate de decisão humana). Corrigido no `action-plan.md` §4.2. |
| m2 | IDs inexistentes (**D-HD3**) e ID de outro documento (**HD-3**) | `D-HD3` → **D-08** (`action-plan.md` §15.2). Referência a **HD-3** mantida apenas onde é válida (este contrato) e marcada como pertencente a este contrato. |
| m3 | **Subdomínios** de ambiente tratados como **decididos** | Nenhum nome de subdomínio é **afirmado** sem decisão. O único valor de domínio do programa é o canônico `https://portal-noticias.com/`; os hostnames de DEV/HOMOLOG/PROD ficam para o lote que permite valores de domínio (**R-2**), e a divergência com `portal-noticias.com.br` é registrada. |
| m4 | Ambiguidade "nesta fase" | Onde era ambíguo, trocado por **"no lote P0-1/F0"** ou "nesta fase do programa", conforme o escopo real. |
| m5 | Soak sem ambiente definido | Soak definido em **HOMOLOG** (ambiente de pré-produção), não em "pré-produção" genérico (`action-plan.md` §12.2). |
| m6 | Cobertura de **P2-05, P2-06 e P2-07** ausente | Cobertura declarada no `action-plan.md` §3.1 (WS-14) e §12.2, e no `backlog.md`. |
| m7 | Snapshot **`645aca3`** tratado como atual | Marcado como **snapshot datado** em todos os artefatos; o SHA de release é **re-derivado** no início do lote (`git rev-parse HEAD`) e confirmado por **HD-3**. |
| m8 | Sete corrupções de texto | Corrigidas: `HttpOnly`/`hosts`, `banner`/`GA4`, `backup do soak`/`Restore testado`, `reconciliação`/`queued`, **D-13** (`Janela e responsáveis`), `usuário see` → **usuário vê**, `desligamento manual operable` → **acionável**. Extras da mesma classe: `email eLGPD` e `eRENOVAR`. |
| m9 | Placeholder de template aparente (chaves duplas) | A expressão do workflow foi reescrita em prosa (`github.event.pull_request.head.sha`), preservando o fato e eliminando o token de placeholder. Nenhum placeholder não substituído permanece neste contrato. |

**Histórico preservado:** a revisão 2 permanece válida e explícita — o CI/CD existente **não** é alterado neste lote nem nesta fase do programa. A revisão 3 **não** reescreve essa decisão; apenas padroniza o tratamento do risco R-1, remove a circularidade de gate, define a custódia de `run-state.json` e atribui host key a WS-03.

*Acabamento documental pós-revisão independente (2026-09-25): aplicadas as ressalvas **R1–R11** do reviewer a este contrato **sem mudar escopo, AC, gate, dependência ou decisão** — neste arquivo: exit code explícito para ausência de `--expected-sha` (Interface 1, AC-4, comandos e DoD) e correções de texto (`Código não aprovado`, `decididos`, `afirmado`, `capaz de bloquear`). A **versão do contrato permanece 3** e a revisão 2 continua válida; nenhum código, workflow, VPS, `settings.py`, run anterior ou `run-state.json` foi tocado; nenhum comando Git de escrita; nenhum `implementation-history.md` criado.*

*Acabamento documental — segunda rodada de remediação de planejamento (2026-09-25):* a **versão do contrato permanece 3** e a revisão 2 continua válida; **nenhum escopo, AC, gate, dependência ou decisão mudou**. Alterações, todas documentais: (1) **estado Git re-derivado** registrado, com **timestamp** (2026-09-25T18:32:47Z, leitura apenas) nos metadados, no **HD-3** e no follow-up 4 — `develop` e `origin/develop` **iguais** em `7715dae8`, paridade `0/0`, `948a5b5`/`645aca3` **já no remoto** (sem push pendente), `4c57ff04` ***dangling*, ausente do reflog, recuperável só por SHA**, divergência ref solta × `packed-refs` **ainda aberta**; (2) §P0-01 passou a exigir inventário de refs/paridade/`4c57ff04`/`worktree`/`stash` com timestamp, separando a **re-derivação detalhada** (backlog **P0-01b**, WS-01/GP-1) da reconciliação e da **re-verificação fresca de G0–G5** que fecha **GP-0** (WS-00) — **sem gate circular e sem GP-0 depender de artefato de WS-01**; (3) §"Comandos de validação" item 1 passou a conter o conjunto completo de re-derivação, com as 4 regras de leitura; (4) **prova de não-vazamento de segredo deixou de ser tautológica**: literal sintético real, arquivo rastreado em **fixture descartável fora do repositório do portal**, controle positivo + prova de detecção + prova de não-vazamento em `stdout`/`stderr`/`--json`, e **nenhum placeholder de texto** no lugar do literal — refletido em AC-5, no item 3 dos comandos e no DoD; (5) o diretório de estado desta run foi declarado **não rastreado, fora de release, com ownership, re-derivado a cada execução, sem edição de `.gitignore`** (§P0-01, P0-09 caso 2, DoD). `run-state.json` **não** foi editado nesta rodada — o **orchestrator** o atualizará **após a revisão final**, com timestamp posterior; `provenance-reconciliation.md`, runs 1020/2136, `settings.py`, `.github/`, `.gitignore`, código, workflows e VPS intocados; nenhum comando Git de escrita; nenhum `implementation-history.md` criado.

*Acabamento documental — remediação 1 (2026-09-25T20:50Z):* a **versão do contrato permanece 3** e a revisão 2 continua válida; **nenhum escopo, AC, gate, dependência humana, decisão, R-1 ou R-2 mudou**, e nenhuma seção deste arquivo foi reescrita ou removida. Alterações, **exclusivamente documentais e por acréscimo** (nenhuma linha deste arquivo foi reescrita ou removida, e o texto da "Revisão obrigatória" foi **preservado como está**): (1) registro de que o vetor de burla citado no **eixo de segurança** da "Revisão obrigatória" (`skip-worktree`) **e também `assume-unchanged`**, hoje não citado naquele texto, estão **cobertos e provados por fixture explícito** — `git update-index --assume-unchanged` em arquivo rastreado com conteúdo alterado ⇒ `exit 1` com achado `assume-unchanged: tag git ls-files -v = h`, e nenhum valor de segredo na saída; o caso `skip-worktree` também tem fixture próprio (`exit 1`, `tag = S`); (2) registro de que a detecção é feita pelos **bits do índice** com `git ls-files -v` (case-sensitive: `H` normal, `h` assume-unchanged, `S` skip-worktree, `s` as duas), porque **`git status` e `git diff` não veem alteração escondida por essas flags**, e de que o gate reprova **pela presença da flag**, exista ou não divergência de conteúdo; (3) registro de que o defeito **existiu** entre a entrega e o teste independente (o gate aprovava com `exit 0` sob `assume-unchanged`, por `tag.upper() != "H"`), de que foi **corrigido**, e de que a cobertura **`assume-unchanged` não existia** na suíte original (`PASS=61` era honesto para o que foi testado, mas o rótulo do driver a superdeclarava); (4) a remediação executou **125 asserções** com `FALHA=0` em fixtures descartáveis **fora do portal**, incluindo read-only, determinismo, falha fechada e os 7 casos de P0-09. Evidência completa em `lote-p0-1-evidencias.md` §10 e em `implementation-history.md` "Iteração 1". **Nenhum arquivo de código, workflow, VPS, `settings.py`, run anterior, `.gitignore` ou `run-state.json` foi tocado**; `.github/` passou a ser reescrito por ator externo durante a janela (registrado em `lote-p0-1-evidencias.md` §10.8 e §10.9), o que **não** é revertido aqui e mantém **AC-6(a)/AC-9** pendentes de decisão humana; **R-1** e **R-2** seguem exatamente como registrados, e nenhum comando Git de escrita foi executado.
