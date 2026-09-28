# Report — 20260925-1836-usuarios-teste-dev-homolog

## Metadados
- **run_id:** 20260925-1836-usuarios-teste-dev-homolog
- **Período:** 2026-09-25 18:36 → 2026-09-28 19:35 (as fases da run consularam
  2026-09-25; o código só foi para o `develop` em 2026-09-28 — ver "Linha do tempo")
- **Tarefa:** Usuários de teste (um por perfil) criados no deploy de DEV e HOMOLOG
- **Resultado final:** `entregue`

## Resumo executivo
O pedido era simples de descrever e difícil de fazer direito: o deploy de DEV e de
HOMOLOG não criava conta nenhuma, e não pode criar com senha conhecida (o
`subir-localhost.sh` faz isso localmente, mas a senha não pode estar no repositório
de um ambiente com domínio real). A solução foi um input booleano `usuarios_teste`
no `deploy.yml` com **default `false`**, ligado apenas em `deploy-dev.yml` e
`deploy-homolog.yml`, explícito `false` em `deploy-prod.yml` e **ausente** em
`rollback.yml`; ligado, ele cria 3 contas por deploy
(`teste-{free,premium,admin}@<sufixo>.portal-noticias.com.br`, só o `admin` é
superuser) através da flag nova `--sem-senha` do `criar_usuario_carga`, que faz a
conta nascer com `set_unusable_password()` — a senha não existe em log, `argv`,
ambiente, arquivo nem banco, e o primeiro acesso é pelo fluxo que o produto já
tinha (`/recuperar-senha` → `/redefinir-senha`), com troca de senha obrigatória no
primeiro login porque `deve_trocar_senha=True` faz o login redirecionar para
`/trocar-senha`. O desvio relevante do plano não foi de escopo de produto, foi de
método: a **primeira revisão achou um major de segurança que nenhum teste de
string revelaria** — o `set -a; . ./.env` do deploy (o `backend/.env` da VPS,
`chmod 600`, nunca sobrescrito) roda **depois** da validação do input e **antes**
de o gate ler o valor, então uma linha `USUARIOS_TESTE=true` nesse arquivo ligava
o gate **em PROD**, criando `teste-admin@prod…` como superuser, sem alteração de
repositório e sem aviso. A correção (reatribuir o input **depois** do source, com
revalidação) só é crível se for executada, e por isso a run entregou também
`scripts/verificar-gate-usuarios-teste.sh`: ele extrai o `script:` do workflow com
PyYAML e roda o shell **inteiro** em `dash` contra um `.env` de verdade — 25
asserções, das quais 21 cobriam o major e 4 cobrem o `SUF`; e o modo
`AUTOMUTACAO=1` remove o selo de uma cópia do workflow e exige que o cenário do
exploit **reprobe**, ou seja, a prova se autoverifica. Veredito final: tester
`passed` (12/12 critérios, 841 testes na suíte completa em Postgres 16), reviewer
`approve_with_comments` na segunda revisão, com os 3 `minor` dessa segunda
revisão também fechados. O que ficou de fora é o que a run não podia resolver: sem
`DJANGO_EMAIL_BACKEND` configurado na VPS o e-mail de recuperação não chega em
nenhum inbox.

## Métricas
| Métrica | Valor |
|---|---|
| Iterações (implementação ↔ revisão/remediação) | 2 laços de remediação, de um máximo de 3 (`iteration_count: 2`). 1º laço fechou os 4 findings da revisão 1; 2º fechou os 3 `minor` da revisão 2. São 3 seções "Iteração N" no `implementation-history.md` (executor, tester, remediator) + uma 2ª passagem do remediator que **não** foi registrada lá — ver "Inconsistências de registro" |
| Findings de revisão — abertos | **0** |
| Findings de revisão — resolvidos | **7** — 4 da revisão 1 (1 `major` de segurança, 1 `minor`, 2 `nit`) e 3 `minor` da revisão 2 (R1, R2, R3) |
| Arquivos alterados | **12** fora do diretório de estado: 4 workflows (`deploy.yml`, `deploy-dev.yml`, `deploy-homolog.yml`, `deploy-prod.yml`), 1 comando de management, 3 arquivos de teste, 1 dependência de teste (`backend/requirements-dev.txt`), 1 harness (`scripts/verificar-gate-usuarios-teste.sh`), 2 documentos (`infra/DEPLOY.md`, `CI-CD.md`). Mais 7 artefatos de estado. **`rollback.yml` não foi tocado** — o fail-closed de lá é por omissão |
| Testes adicionados | **25 casos**: 17 (`test_usuarios_teste.py`, executor) + 7 (`test_usuarios_teste_complemento_tester.py`, tester) + 1 (`test_gate_deploy_usuarios_teste.py`). 6 deles foram depois ajustados ao P1-04 do `develop` (fixture `canal_entregando`) |
| Veredito final do tester | **`passed`** — 12/12 critérios; 841 passed na suíte completa com Postgres 16 e cobertura 91,15% (gate 80%) |
| Veredito final do reviewer | **`approve_with_comments`** (revisão 2). Revisão 1 foi `changes_requested` — 0 blocker / 1 major / 1 minor / 2 nit |

## Linha do tempo resumida
A versão detalhada está em `implementation-history.md`; os horários abaixo são os do
`run-state.json`, que é o registro canônico da run.
- 2026-09-25 18:36 — run aberta (`created_at`); planejamento começa.
- 2026-09-25 18:36–18:52 — **planning** (orchestrator): 3 decisões confirmadas com o solicitante (sem senha fixa no repo; um usuário por perfil; `feature → develop → PR para main`) e contrato com **12 critérios de aceite**.
- 2026-09-25 18:41–19:05 — **implementation** (executor): flag `--sem-senha` no `criar_usuario_carga` (idempotente), 17 testes, input + validação + função `provisionar_usuarios_teste` no `deploy.yml`, gate ligado em DEV/HOMOLOG e desligado em PROD.
- 2026-09-25 19:06–19:48 — **testing** (tester): `passed` 12/12, com o gate do CI reproduzido de verdade (Postgres 16, 841 passed). **Ache um buraco na suíte do executor**: a mutação `deve_trocar_senha=False` no ramo que preserva a senha passa os 17 testes dele. Registrou FLY-1 (teste flaky de outra run).
- 2026-09-25 19:06–19:52 — **review** (reviewer): `changes_requested`, 0 blocker / 1 major / 1 minor / 2 nit. O `major` é o `.env` da VPS virando a chave do gate. O orchestrator reproduziu o exploit em `dash` antes de aceitar o relato.
- 2026-09-25 19:55 em diante — **remediation, 1ª passagem**: os 4 findings fechados (selo pós-`.env`, log honesto sobre o e-mail, `return 1` real, lixo de tokenizer) + o harness de prova executada.
- sem horário registrado — **remediation, 2ª passagem**: fecha R1 (`pyyaml` em `requirements-dev.txt`, e o teste passa a falhar em vez de pular), R2 (mutação do harness passa a ser estrutural, com desfecho "NÃO APLICÁVEL" distinguível) e R3 (`SUF` lacrado depois do source, `deploy.yml:663`, + 4 asserções novas no harness + reescrita do comentário do selo).
- sem horário registrado — **documentation** (documenter): seção nova em `infra/DEPLOY.md` e 4 edições em `CI-CD.md`, incluindo o registro explícito de que o e-mail de recuperação **não** chega a nenhum inbox.
- 2026-09-28 19:07 — commit `1581b50` na branch `run-20260925-1836-usuarios-teste`: o código foi escrito sobre a branch de observabilidade e estava órfão no worktree; foi isolado ali para liberar os 4 workflows que a run de observabilidade precisava alterar.
- 2026-09-28 19:09 — merge `dd604be` sobre `develop`. **Apareceram 6 testes falhando**: o P1-04, que o `develop` trouxe depois, fez `recuperar-senha` recusar o caminho de sucesso quando não há canal de entrega real — e em teste o backend é `locmem`, então `mail.outbox` ficava vazio. Os 6 passaram a pedir a fixture `canal_entregando`, que já existia no `conftest.py` do `develop` para exatamente isso.
- 2026-09-28 19:30 — commit `1ba4c97`: a documentação que ficara presa na branch de observabilidade é portada, e a seção de `infra/DEPLOY.md` é reinserida renumerada.
- 2026-09-28 19:35 — **closing** (historian): este report, uma linha no `HISTORY.md` e o `run-state.json` corrigido.

## Desvios do plano original
1. **`rollback.yml` ficou sem declarar o input** em vez de `usuarios_teste: false`
   explícito como no `deploy-prod.yml`. Decisão do executor, registrada na
   `implementation-history.md` (Iteração 1, nota 3) e mantida pela revisão. O
   fail-closed de lá é por omissão, e funciona: sem declarar, vale o `default:
   false` do `deploy.yml` (`deploy.yml:150-154`). Confirmado por `grep` nesta base.
2. **O escopo de verificação cresceu muito além dos 12 critérios.** O plano previa
   testes do comando Django; a revisão provou que o que precisava ser provado era o
   *shell do workflow*, e aí nasceu `scripts/verificar-gate-usuarios-teste.sh`
   (659 linhas), o pytest que o roda e a dependência de teste `pyyaml`. É o desvio
   que valeu a run: sem ele, o `major` corrigido não teria prova de regressão.
3. **Documentação portada e renumerada.** O `documentation-update.md` descreve uma
   seção **§9.7** de `infra/DEPLOY.md`; ao ser portada para o `develop` ela virou
   seção de topo `## As contas de teste de DEV e HOMOLOG` (`infra/DEPLOY.md:961`),
   porque o pai "## 9. topologia ATIVA" só existe na branch de observabilidade.
   O conteúdo é o que o documenter escreveu; a numeração é da base de destino.
4. **Base de entrega e prazo.** O código foi escrito sobre a branch
   `observability-20260925-1020` e precisou de `1581b50` (2026-09-28) para ser
   isolado, e a documentação só entrou no `develop` em `1ba4c97`. A entrega
   Welshou: work → branch da observabilidade → develop. Três dias entre a run e o
   código no `develop`.
5. **6 testes da run quebraram ao chegar na base de destino** (P1-04 × `locmem`),
   corrigidos com uma fixture que já existia no `conftest.py` do `develop`.
   **Esta é a lição da run**: só rodar na base de destino mostra que a suíte
   desta run conversava com a suíte do `develop`. Sem essa correção, o gate de CI
   ficaria vermelho e o deploy de HOMOLOG não chegaria a acontecer.
6. **`run-state.json` estava fora de sincronia** ao chegar ao fechamento
   (`status: in_progress`, `current_phase: planning`, `planning`/`remediation` em
   `in_progress`, `documentation` `pending`). Corrigido nesta fase, sem apagar os
   `notes` que já registravam o trabalho — ver "Inconsistências de registro".
7. **Imprecisão do contrato que sobrou**: a seção "Interfaces afetadas" do
   `implementation-contract.md` lista `subir-localhost.bat` como consumidor de
   `criar_usuario_carga`; ele chama `ensure_local_admin.py`, não o comando. Só
   `subir-localhost.sh` (linhas 383 e 492) e a migration `0004` (docstring) citam
   o comando. Registrado pelo tester (Iteração 2, Observação 3); sem impacto.

## Follow-ups / pendências
- **Provedor de e-mail de verdade (bloqueia o uso real das contas).**
  `DJANGO_EMAIL_BACKEND` não está configurado em nenhum ambiente: o default do
  Django é o console backend (`backend/config/settings.py:627-629`) e o `printf`
  que cria o `backend/.env` no primeiro deploy não escreve a chave. Resultado: o
  e-mail de recuperação de senha **não chega em nenhum inbox** — ele sai no stdout
  do gunicorn (`pm2 logs portal-api-<suf>`), e o `uid`/`token` que ele carrega é
  credencial da conta. O código do Resend já existe
  (`backend/config/email_resend.py`); falta a credencial, que é humana (HD-E da run
  `20260925-1433-go-live-producao`, `PROD_DECISOES.md` item 2). O gate já avisa no
  log qual backend está em uso (`deploy.yml:723-727`) e a documentação registra a
  pendência como pendência, sem afirmar entrega. **Enquanto isso não existir, o
  caminho de entrada documentado funciona só por log.**
- **`SUF` controlado pelo `.env` no bloco de PM2 (preexistente, não revisado).**
  `SUF=prod` no `backend/.env` de DEV faz o deploy chegar a
  `restart_or_start portal-web-prod` / `portal-api-prod` — ou seja, reiniciar o
  processo de produção com o código de DEV. Na 2ª passagem de remediação isso foi
  **fechado por consequência** para o gate (`SUF="${{ inputs.pm_suffix }}"` em
  `deploy.yml:663`, logo depois do source) e coberto por 4 asserções do harness,
  mas **o bloco de PM2 não passou por revisão própria** e é anterior a esta run.
  O reviewer classificou de "perigo de ambiente cruzado com raio de impacto bem
  maior que o Finding 1" e propôs que tenha a própria run, com o dono daquele bloco.
- **N1 — o `backend/.env` é executado como shell.** `set -a; . ./.env` executa o
  arquivo: uma linha com `$(…)` roda comando arbitrário no deploy, e um `exit 0`
  ali faz o script do job sair 0 ali mesmo (medido em `dash` pelo reviewer), ou
  seja, um `.env` pode até **fingir um deploy verde**. Vale igualmente para
  `DJANGO_SECRET_KEY` e `DJANGO_DB_PASSWORD`, é anterior a esta run, e corrigir é
  redesenhar o carregamento de ambiente no script inteiro (parse seguro, ou `grep`
  por chave em vez de `source`).
- **N2 — a mesma classe em outros inputs.** `WEB_RUNTIME` e `CELERY_SYSTEMD` são
  lidos depois do source e são sobrescrevíveis pelo `.env`; `TLS_ENABLED` e
  `GIT_MODE` **não** são (o `deploy.yml` é modelar em `TLS_ENABLED`: valida o
  valor do input contra o que está no `.env` depois de escrever, que é exatamente
  o padrão que faltava ao gate). A decisão de não mexer nos dois expostos é
  defensável — não criam conta em PROD nem mexem em credencial — mas precisa virar
  item de backlog, não anotação.
- **R2 residual: as 4 camadas de fail-closed de PROD não têm teste de CI.** São
  (1) `deploy-prod.yml:61` com `false` explícito, (2) `rollback.yml` sem declarar
  o input, (3) o `default: false` do input, (4) o selo pós-source de
  `deploy.yml:658-663`. Hoje a suíte de Python não enxerga YAML nenhum. Fix
  candidato, não aplicado por escopo: um `scripts/verificar-yaml.sh` com `grep`
  sobre os 5 workflows (1 passo de pipeline, zero dependência) ou uma asserção de
  parse com o PyYAML que já está declarado.
- **FLY-1 — a suíte completa não é determinística.**
  `catalogo_noticias/tests/test_command_agendar_ingestao.py::test_sigterm_em_processo_real_encerra_sem_traceback_e_rapido`
  falhou em 1 de 3 execuções do tester. É arquivo **untracked** da run
  `20260924-2136-ingestao-noticias`, não menciona esta run (`grep "20260925-1836"`
  → 0) e mede tempo de processo real. Hoje o critério 12 fica verde **por
  margem**, não por construção.
- **A run de observabilidade segue fora do `develop`.** 24 commits em
  `observability-20260925-1020` ainda não estão no `develop` (verificado nesta
  base), e a mesclagem foi relatada com 54 conflitos. Não é escopo desta run; fica
  registrado porque a base de entrega desta run passou por essa branch.

## Artefatos desta execução
- task-plan.md
- implementation-contract.md
- implementation-history.md
- code-review-contract.md
- documentation-update.md
- run-state.json

---

<!-- As duas seções abaixo são uma ADIÇÃO do historian ao template de
     `contracts/report.md` (que não as tem). Elas existem porque a regra do
     `historian.md` exige que eu sinalize, e não esconda, o que está fora de
     sincronia no registro. -->

## Inconsistências de registro encontradas no fechamento
1. **A 2ª passagem da remediação não tem seção no `implementation-history.md`.** O
   arquivo tem "Iteração 1" (executor), "Iteração 2" (tester) e "Iteração 3"
   (remediator, que fechou os 4 findings da revisão 1) e **acaba aí**. O
   `run-state.json` agora diz `remediation: done` com `iteration_count: 2`, e o
   `code-review-contract.md` documenta R1/R2/R3 como fechados — mas a passagem que
   os fechou não foi registrada no diário. **Não corrigi**: o `historian` não edita
   o diário de outro agente. O conteúdo dos três fixes é verificável no código
   (`pyyaml` em `backend/requirements-dev.txt`; mutação estrutural com desfecho
   "NÃO APLICÁVEL" em `scripts/verificar-gate-usuarios-teste.sh:533-560` e os dois
   desfechos distinguíveis no pytest; `SUF="${{ inputs.pm_suffix }}"` em
   `deploy.yml:663`), e nenhum dos três foi revisado depois.
2. **Os horários do `implementation-history.md` divergem do `run-state.json`.** A
   Iteração 1 do diário declara 18:36–18:46 e o `run-state.json` registra
   implementation 18:41–19:05; a Iteração 2 do diário declara 18:52–19:12 e o
   `run-state.json` registra testing 19:06–19:48. O próprio reviewer sinalizou
   isso na revisão 2 (Observação de registro: os `mtime` da Iteração 3, 19:05–19:19,
   são anteriores à janela que a seção declara, 19:40–20:20). Usei o
   `run-state.json` como canônico na linha do tempo acima; a correção do diário é
   do remediator.
3. **`run-state.json` chegou ao fechamento fora de sincronia** — `status:
   in_progress`, `current_phase: planning`, `planning` e `remediation` em
   `in_progress`, `documentation` em `pending`, `finished_at` nulo e `findings` todo
   zerado. **Corrigido nesta fase**, com os `notes` existentes preservados e as
   correções acrescentadas, nunca substituídas.
4. **O `HISTORY.md` desta branch está 2 entradas atrás do `develop`** — faltam
   `20260924-2136-ingestao-noticias` e `20260925-1020-observabilidade`, que existem
   no `develop`. É consequência de a branch de entrega ter sido cortada de uma base
   mais antiga. **Não acrescentei as duas linhas**: o ledger é append-only e as
   entradas das outras runs não são minha para registrar. O próximo a mexer no
   `HISTORY.md` no `develop` deve reconciliar antes de acrescentar a linha nova.
5. **Numeração divergente de "iteração".** O diário numera por evento
   (1=executor, 2=tester, 3=remediator), a revisão fala em "Iteração 3 do
   remediator" (= a Iteração 3 do diário) e o `run-state.json` conta laços de
   remediação (`iteration_count: 2`). Nas métricas acima usei a contagem do
   `run-state.json` e explicitei as outras duas.

## Verificações que eu mesmo fiz no fechamento (historian, somente leitura)
Nada aqui é citação de outro agente: foi checado contra o código nesta base.
- `./scripts/verificar-gate-usuarios-teste.sh` → **25/25, `RESULTADO: OK`**, e o
  `/home/apps` não foi criado e nada fora de `mktemp` foi escrito.
- `pytest identidade/tests/test_gate_deploy_usuarios_teste.py` → **1 passed** (47 s;
  é o teste que roda o harness com `AUTOMUTACAO=1`).
- `pytest --collect-only` dos 3 arquivos de teste da run → **25 casos** (17 + 7 + 1).
- `sha256sum criar_usuario_carga.py` = `12acc7f0e512eb84…` — **idêntico** ao hash que
  o tester congelou na Iteração 2 do diário e que o reviewer reconferiu na revisão 2
  (§12). O comando de management não foi tocado desde a implementação.
- `rollback.yml` não menciona `usuarios_teste`; `deploy-prod.yml:61` = `false`;
  `deploy-dev.yml:35` e `deploy-homolog.yml:34` = `true`; input em
  `deploy.yml:150-154` com `default: false`; selo pós-source em `deploy.yml:658-663`;
  função em `deploy.yml:683-744`, chamada em `if !` na 742.
- Commits `1581b50` (2026-09-28 19:07), `dd604be` (19:09) e `1ba4c97` (19:30),
  com o conteúdo descrito acima — incluindo os 6 testes que passaram a pedir
  `canal_entregando` (3 em cada arquivo de teste) e o `pyyaml==6.0.3` em
  `backend/requirements-dev.txt`.
- `git rev-list --count develop..observability-20260925-1020` → **24**.
