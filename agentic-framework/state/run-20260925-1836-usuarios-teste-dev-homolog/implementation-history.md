# Implementation History — 20260925-1836-usuarios-teste-dev-homolog

<!-- Uma seção "## Iteração N" por evento relevante: implementação inicial, cada correção do remediator,
     cada validação do tester. Ordem cronológica, sem lacunas. -->

## Iteração 1 — 2026-09-25 18:36–18:46 — executor (implementação inicial)

**O que foi feito:**

1. `criar_usuario_carga` ganhou a flag opt-in `--sem-senha` (senha inutilizável,
   primeiro acesso por recuperação de senha) e passou a ser **idempotente** nesse
   caminho. O caminho com senha (legado) foi mantido intacto.
2. Arquivo de teste novo `backend/identidade/tests/test_usuarios_teste.py`
   (17 testes), cobrindo os critérios 1, 2, 3, 4, 7, 8 e a parte de log do 11.
3. `.github/workflows/deploy.yml`: input `usuarios_teste` (boolean, default
   `false`), validação de valor, e o bloco `provisionar_usuarios_teste` logo
   depois do `collectstatic`.
4. `deploy-dev.yml` e `deploy-homolog.yml` ligam o gate; `deploy-prod.yml` declara
   `usuarios_teste: false` explicitamente; `rollback.yml` não declara (fica no
   default `false`).

**Por quê:**

O contrato (run 20260925-1836) pede um gate de usuários de teste só em DEV/HOMOLOG
em que **a senha não existe em lugar nenhum**. O mecanismo já existia
(`criar_usuario_carga`, o mesmo do `subir-localhost.sh`); o que faltava era um
caminho que não transporte senha nenhuma e um gate fail-closed na esteira.

**Arquivos tocados:**
- `backend/identidade/management/commands/criar_usuario_carga.py` (novo arg
  `--sem-senha`; `--password` passou a ter `default=None`)
- `backend/identidade/tests/test_usuarios_teste.py` (arquivo novo)
- `.github/workflows/deploy.yml` (input + validação + bloco de provisionamento)
- `.github/workflows/deploy-dev.yml` (`usuarios_teste: true`)
- `.github/workflows/deploy-homolog.yml` (`usuarios_teste: true`)
- `.github/workflows/deploy-prod.yml` (`usuarios_teste: false` explícito)

Nada mais foi tocado. `subir-localhost.sh`/`.bat`, models, serializers, views,
migrations, frontend e `scripts/observability/` intactos.

**Comandos executados / evidência:**

Baseline antes de mexer (suíte já verde, nada quebrado por mim):
```
$ cd backend && .venv/bin/python -m pytest identidade/ -q
59 passed, 56 warnings in 18.05s
```

Suíte nova isolada:
```
$ cd backend && .venv/bin/python -m pytest identidade/tests/test_usuarios_teste.py -q
17 passed, 9 warnings in 7.72s
```

Módulo completo de identidade (critério 12):
```
$ cd backend && .venv/bin/python -m pytest identidade/ -q
76 passed, 64 warnings in 22.90s
```

Suíte completa do backend, exatamente como o CI roda (critério 12):
```
$ cd backend && .venv/bin/python -m pytest -q --cov=. --cov-report=term-missing --cov-fail-under=80
identidade/management/commands/criar_usuario_carga.py    63    3    95%   104, 134, 146
TOTAL                                                   16398  1463    91%
Required test coverage of 80% reached. Total coverage: 91.08%
834 passed, 297 warnings in 117.23s (0:01:57)
```
As 3 linhas descobertas (`104` = e-mail vazio, `134` = prompt `getpass`,
`146` = `--nome`) são caminhos **pré-existentes** e já descobertos antes desta
run; a cobertura do arquivo subiu, não caiu.

**Mutation testing** (prova de que os testes do critério 2 não são vazios). Cada
mutação foi aplicada, a suíte nova rodada, e o arquivo restaurado byte a byte
(`diff` contra o backup: idêntico):
```
MUTAÇÃO 1 — `preserva_senha = False` (o `set_unusable_password()` cego)
  FAILED test_redeploy_preserva_a_senha_que_a_pessoa_definiu_na_recuperacao
  FAILED test_redeploy_preserva_ate_o_token_de_quem_ja_estava_logado
  FAILED test_sem_senha_normaliza_campos_administrativos_sem_destruir_senha
  3 failed, 14 passed

MUTAÇÃO 2 — ordem invertida (`set_unusable_password()` ANTES de perguntar)
  3 failed, 14 passed  (mesmos 3 testes — a ordem é o que o teste trava)

MUTAÇÃO 3 — apagar o `Token` sempre
  FAILED test_redeploy_preserva_ate_o_token_de_quem_ja_estava_logado
  1 failed, 16 passed

MUTAÇÃO 4 — reimpor `deve_trocar_senha=True` no caminho `--sem-senha`
  FAILED test_redeploy_preserva_a_senha_que_a_pessoa_definiu_na_recuperacao
  1 failed, 16 passed
```

Verificação estática do workflow (critérios 5, 6, 10, 11) — **o workflow não foi
executado de verdade**; o script do job `deploy` foi extraído do YAML com
`yaml.safe_load`, as expressões `${{ }}` substituídas por placeholder, e o bloco
do gate executado contra um `manage.py` de mentira que registra o argv:
```
$ python3 -c "yaml.safe_load(...)" nos 5 workflows
OK yaml.safe_load: deploy.yml         jobs=['verify', 'deploy', 'validate']
OK yaml.safe_load: deploy-dev.yml     jobs=['deploy-dev']
OK yaml.safe_load: deploy-homolog.yml  jobs=['deploy-homolog']
OK yaml.safe_load: deploy-prod.yml     jobs=['pre', 'deploy-prod', 'release']
OK yaml.safe_load: rollback.yml        jobs=['prepare', 'rollback']

$ sh -n deploy.sh && bash -n deploy.sh
sintaxe OK (sh/dash)
sintaxe OK (bash)

CENÁRIO A — gate ligado, SUF=dev, os 3 comandos saindo 0:
  manage.py criar_usuario_carga --email teste-free@dev.portal-noticias.com.br --sem-senha --papel free
  manage.py criar_usuario_carga --email teste-premium@dev.portal-noticias.com.br --sem-senha --papel premium
  manage.py criar_usuario_carga --email teste-admin@dev.portal-noticias.com.br --sem-senha --papel admin --superuser
  "Usuários de teste: 3 de 3 contas prontas. Entrada: /recuperar-senha ..."

CENÁRIO C — gate ligado, SUF=homolog: 3 chamadas, mesmo formato de e-mail,
  `--superuser` só no admin.

CENÁRIO B — gate desligado (default false):
  "Usuários de teste: usuarios_teste=false; nenhuma conta criada"
  chamadas ao manage.py: 0

CENÁRIO D — gate ligado e SÓ o perfil admin falhando (exit 3):
  free pronto / premium pronto / AVISO: falha ao criar/atualizar teste-admin@homolog... ; o deploy do código continua
  "Usuários de teste: 2 de 3 contas prontas"
  exit=0   <-- o deploy NÃO falhou (critério 9)

CENÁRIO E — validação de valor (critério 10), `sh` com o `case` real do YAML:
  usuarios_teste='true'  -> exit=0
  usuarios_teste='false' -> exit=0
  usuarios_teste='sim'   -> exit=1  ERRO: usuarios_teste deve ser true ou false
  usuarios_teste='TRUE'  -> exit=1  ERRO: usuarios_teste deve ser true ou false
  usuarios_teste='True'  -> exit=1  ERRO: usuarios_teste deve ser true ou false
  usuarios_teste='1'     -> exit=1  ERRO: usuarios_teste deve ser true ou false
  usuarios_teste=''      -> exit=1  ERRO: usuarios_teste deve ser true ou false
```

Ligação dos callers (inspeção do YAML parseado):
```
deploy.yml  usuarios_teste -> {'type': 'boolean', 'required': False, 'default': False}
deploy-dev.yml     -> deploy-dev: usuarios_teste=True
deploy-homolog.yml -> deploy-homolog: usuarios_teste=True
deploy-prod.yml    -> deploy-prod: usuarios_teste=False
rollback.yml       -> NAO DECLARA (default false do deploy.yml)
```
E a posição do bloco dentro do script do job `deploy`:
```
ordem: collectstatic < gate < pm2 restart: True
o gate está dentro de `cd "$APP_DIR/backend"`: True
venv ativa antes do gate: True
'--password' no script do deploy: 1  (dentro de um COMENTÁRIO meu)
PROD_SEED no script do deploy: 1     (idem, no mesmo comentário)
```

**Resultado:**

Sucesso. 12/12 critérios implementados do ponto de vista do executor, cada um com
evidência acima (pytest para 1/2/3/4/7/8/12; execução do bloco extraído do YAML
para 5/6/9/10/11; 5 e 11 reforçados por teste no comando).

**Notas fora do escopo (se houver):**

1. **Trabalho de outra run desapareceu do working tree durante esta execução.**
   No `git status` inicial (18:36) havia 11 arquivos modificados que já NÃO
   estavam mais modificados no fim (18:46): `.env.production.example`, `CI-CD.md`,
   `backend/.env.example`, `infra/DEPLOY.md`, `infra/nginx/portal-{dev,homolog,prod}.conf`,
   `infra/observability/alerts/{README.md,regras-operacao.yaml}`,
   `scripts/observability/{pendencias-ci.txt,validar-infra.sh}`. Os `mtime` deles
   são 18:27–18:39, **anteriores** a qualquer edição minha (18:42–18:44), e eu
   não escrevi em nenhum deles. Alguma outra sessão as reverteu. Não tentei
   restaurar: isso é git de outra run e a regra é não mexer. O orchestrator
   precisa conferir isso antes de commitar, porque a reversão pode ter sido
   intencional de outro agente.
2. **O bloco pendente do D2 em `deploy.yml` foi preservado** (verificado por
   `grep` dos 5 marcadores dele: `OBSERVABILITY_JOB_STATE_FILE=…jobs-$SUF.json`,
   os dois `assegurar_linha_env`, `canal de job divergente`, `nginx_dump=$(sudo
   nginx -T`). O `git diff` do arquivo foi de 133 linhas antes desta run e é de
   203 agora: os 70 extras são só os meus. Nenhuma linha do D2 mudou.
3. **`rollback.yml` ficou sem declarar o input** (default `false`). Decisão minha,
   não do contrato: um rollback restaura estado, não cria conta nova, e o default
   já cobre o critério 6. Se o `reviewer` preferir simetria com
   `deploy-prod.yml`, é uma linha — mas aí precisa ser o contrato que muda.
4. **`infra/DEPLOY.md` / `CI-CD.md` não foram documentados** — o próprio contrato
   marca essa área como "(Fase do `documenter`.)". Sinalizo aqui o que o
   documenter precisa escrever: o gate `usuarios_teste`, os e-mails
   `teste-<papel>@<pm_suffix>.portal-noticias.com.br` por ambiente, o caminho de
   entrada `/recuperar-senha`, e o fato de que a senha **não** é reimposta no
   redeploy (quem já entrou continua entrando).
5. **`--superuser` só no perfil admin** é decisão minha dentro do que o contrato
   autoriza ("só o perfil `admin` leva `--superuser`"). Três staff accounts dariam
   a qualquer pessoa com o log do run acesso ao `/admin` e à Central. Está
   coberto por `test_sem_senha_com_papel_admin_e_superuser_so_no_admin`.
6. **Critério 9 (aviso de falha por perfil) não tem teste automatizado possível
   no pytest** — é shell. Foi verificado executando o bloco real do YAML contra
   um `manage.py` que falha (Cenário D acima). É a mesma limitação que o `Celery`
   já tem neste arquivo.

---

## Iteração 2 — 2026-09-25 18:52–19:12 — tester (verificação independente)

**Veredito: `passed`** (12/12 critérios atendidos), com 1 ressalva que não é
desta run (ver FALHA/FLY-1 abaixo) e 5 observações registradas em "Observações".

Não corrigi nada: nenhum arquivo de produção foi tocado por mim. A única coisa
que escrevi no repositório é
`backend/identidade/tests/test_usuarios_teste_complemento_tester.py` (arquivo
novo, 7 testes). Contraste por hash para provar que o código de produção está
como o executor deixou:

```
$ sha256sum backend/identidade/management/commands/criar_usuario_carga.py
12acc7f0e512eb84c3342697c015387166cc4d44c063954c13fa19785c8db609  criar_usuario_carga.py
1c4bcfc2c907bcbbed735c684fa5fc02f82a5bfb6bb98c40fff3e84c3c04242f  deploy.yml
ef0384650170623cca9dea393748247301690658c8890265885cdf297e602472  deploy-dev.yml
1cf216f815fdaafc822a52020e272e9b127de4b4c636f1a0004ec402d6a6c782  deploy-homolog.yml
ab0edc0a763a0552e44750a350403a3337effc7ff052b0c30f5c7039dc67d8ba  deploy-prod.yml
676b0297d6c445a3fab22e11cf9295e66d5197d684ef311eb3ad8dcd554de141  rollback.yml
bd85476db88c6eb65559db4186ddbd8becc1cf6ccdceb5b15a32b23c6e3326d4  subir-localhost.sh
```
`criar_usuario_carga.py` tem o mesmo sha da cópia que congelei no sandbox ANTES
de qualquer coisa, e `deploy.yml` mantém os 203+/0- do diff do executor — o
bloco do D2 (de outra run) segue inteiro:
`OBSERVABILITY_JOB_STATE_FILE=…jobs-$SUF.json` (1), `assegurar_linha_env` (4),
`canal de job divergente` (1), `nginx_dump=` (1), `X-Forwarded-For` (4).

---

### Comando executado (o do CI, exatamente)

Descobri o gate em `.github/workflows/ci.yml`, job `backend-tests`
(linha 96): `python -m pytest -q --cov=. --cov-report=term-missing --cov-fail-under=80`,
com `working-directory: backend` e um Postgres 16 como serviço. Havia um
`postgres:16-alpine` disponível na máquina com o MESMO `POSTGRES_DB=brd_portal_noticias`
e `POSTGRES_USER=postgres`, então reproduzi o ambiente do CI de verdade, não
o sqlite de bootstrap:

```
$ cd backend
$ env DJANGO_DEBUG=true DJANGO_DB_ENGINE=postgresql \
      DJANGO_DB_NAME=brd_portal_noticias DJANGO_DB_USER=postgres \
      DJANGO_DB_PASSWORD=postgres DJANGO_DB_HOST=localhost DJANGO_DB_PORT=5432 \
  .venv/bin/python manage.py check
System check identified no issues (0 silenced).

$ env DJANGO_DEBUG=true DJANGO_DB_ENGINE=postgresql \
      DJANGO_DB_NAME=brd_portal_noticias DJANGO_DB_USER=postgres \
      DJANGO_DB_PASSWORD=postgres DJANGO_DB_HOST=localhost DJANGO_DB_PORT=5432 \
  .venv/bin/python -m pytest -q --cov=. --cov-report=term-missing --cov-fail-under=80
...
identidade/management/commands/criar_usuario_carga.py     63      2    97%   104, 146
TOTAL                                                     16517   1462    91%
Required test coverage of 80% reached. Total coverage: 91.15%
841 passed, 301 warnings in 180.18s (0:03:00)
```

**841 passed, 0 failed, cobertura 91,15% (gate 80%).**

Outros recortes, todos reais:

```
$ .venv/bin/python -m pytest identidade/ -q
83 passed, 67 warnings in 28.67s

$ .venv/bin/python -m pytest identidade/tests/test_usuarios_teste.py \
                   identidade/tests/test_usuarios_teste_complemento_tester.py -q
24 passed, 12 warnings in 11.66s

$ .venv/bin/python -m pytest identidade/tests/test_primeiro_acesso.py -v   # critério 12, arquivo INTACTO
5 passed, 5 warnings in 4.27s
```

Cobertura do comando **subiu de 95% para 97%** com os meus 7 testes: a linha
`134` (`getpass.getpass(...)`) deixou de estar descoberta — é exatamente o
caminho legado que nenhum teste do executor exercitava.

### FLY-1 — a suíte completa NÃO é determinística (falha de outra run)

Rodei a suíte completa 3 vezes. A **primeira** deu:

```
1 failed, 833 passed, 297 warnings in 193.90s (0:03:13)
FAILED catalogo_noticias/tests/test_command_agendar_ingestao.py::test_sigterm_em_processo_real_encerra_sem_traceback_e_rapido
```

A segunda e a terceira deram `841 passed`. Isolado,
`…::test_sigterm_em_processo_real_encerra_sem_traceback_e_rapido` passa em
2,40 s. É **flakiness de um teste de outra run** (arquivo **untracked**, de
`run-20260925-2136-ingestao-noticias`, que o teste nem menciona: `grep -c
"20260925-1836"` → `0`; ele spawma um processo real e mede tempo, por isso é
sensível a carga). **Não é desta run e não a atribuo a ela** — mas o critério 12
diz "a suíte completa do backend roda verde", e ela hoje roda verde *por
margem*, não por construção. O orchestrator precisa saber antes de commitar:
se o gate de `ci.yml` for vermelho no push, a causa não é esta run.

### Testes adicionados (7) — e por que cada um existe

`backend/identidade/tests/test_usuarios_teste_complemento_tester.py`. Não são
complemento decorativo: a matriz de mutação abaixo mostra que **3 deles matam
mutações que os 17 testes do executor NÃO matam**.

| # | Teste | Buraco que ele fecha | Mutação que ele mata |
|---|---|---|---|
| 1 | `test_redeploy_apos_recuperar_mas_antes_do_login_mantem_a_troca_pendente` | Estado **intermediário** do critério 2: recuperou a senha, ainda não logou (sem `Token` nenhum), `deve_trocar_senha=True`. A suíte do executor só verifica a flag no estado **já concluído** (`is False`) e, no outro teste, nem olha a flag. | **A** |
| 2 | `test_redeploy_nao_reimpoe_a_troca_nem_apaga_a_senha_apos_o_primeiro_acesso` | O outro lado da mesma regra: primeiro acesso concluído não pode ser obrigado a trocar a cada push. | **A** |
| 3 | `test_tres_redeploysseguidos_preservam_a_senha_e_nao_reimpoem_a_troca` | O gate roda **a cada push**. A suíte do executor prova 1 redeploy; esta prova 3. | **A**, **D**, **G** |
| 4-5 | `test_sem_senha_nunca_chama_getpass[False/True]` (parametrizado) | A razão de o gate poder ser automatizado: no deploy não há terminal, e um `getpass` ali travaria o job para sempre. Afirmado na D3 do executor, **sem nenhum teste**. Monkeypatch que estoura se o prompt rodar, nos dois casos (com e sem `PROD_SEED_PASSWORD` no ambiente). | **B** |
| 6 | `test_caminho_legado_sem_password_e_sem_variavel_ainda_pede_a_senha` | O caminho legado que **ninguém** testava: sem `--password` e sem `PROD_SEED_PASSWORD` tem de continuar pedindo a senha no `getpass`. É a mudança do `default` de `--password` (critério 4) no ponto exato em que ela podia quebrar. | **B** (inverso) |
| 7 | `test_caminho_legado_com_password_vazio_no_argumento_ainda_pede_a_senha` | Caso de borda da distinção nova (`is not None`): `--password ""` explícito precisa continuar caindo no prompt, como antes (`options["password"] or ""`). | **C** |

### Matriz de mutação (rodada no sandbox `/tmp/opencode/muta`, nunca no repo)

Copiei o `backend/` para `/tmp`, apliquei cada mutação **só na cópia**, rodei as
duas suítes e restaurei. `sha256` do arquivo do repo inalterado durante o
processo (ver bloco de integridade acima).

| Mutação | Suíte do executor (17) | Complemento do tester (7) |
|---|---|---|
| **A** — `deve_trocar_senha = False` no ramo que **preserva** a senha | **17 passed — NÃO PEGA** | **2 failed** ✅ |
| **B** — prompt `getpass` incondicional | 12 failed | 6 failed ✅ |
| **C** — `default` de `--password` volta a `os.environ.get("PROD_SEED_PASSWORD", "")` | 13 failed | 5 failed ✅ |
| **D** — `preserva_senha = False` (o `set_unusable_password()` cego) | 3 failed | 3 failed ✅ |
| **E** — apagar o `Token` sempre | 1 failed | 7 passed (coberto pelo executor) |
| **F** — `--sem-senha` + `--password` deixa de dar erro | 1 failed | 7 passed (coberto pelo executor) |
| **G** — ordem invertida (`set_unusable_password()` antes de perguntar) | 3 failed | 3 failed ✅ |

A mutação **A é um buraco real da suíte do executor** e é o achado mais
importante desta verificação: um `deve_trocar_senha = False` no ramo que
preserva a senha **passa os 17 testes** (o
`test_redeploy_preserva_a_senha_que_a_pessoa_definiu_na_recuperacao` já espera
`False`, e o `test_redeploy_preserva_ate_o_token_de_quem_ja_estava_logado` nem
olha a flag) e quebraria o critério 8 em silêncio: o primeiro acesso inteiro
seria pulado para quem acabou de recuperar a senha. Está fechado pelos meus
testes 1 e 3.

### Critério 4 — teste DIFERENCIAL de verdade (o `default` suspeito)

Não confiei em "o docstring diz que continua funcionando". Rodei a **versão
antiga** (`git show HEAD:backend/identidade/management/commands/criar_usuario_carga.py`)
e a **nova** sobre os mesmos 9 cenários do caminho legado, dumpando para JSON
tudo que é observável de fora (estado do user, existência de `Token`, a linha
de `stdout`, a mensagem de `CommandError`, se o `getpass` foi chamado):

1. `--password` explícito em conta existente com senha antiga **e Token**
   (é o caminho do `subir-localhost.sh`, linhas 383 e 492)
2. conta nova com `--password`
3. `PROD_SEED_PASSWORD` no ambiente, sem `--password`
4. sem `--password` e sem variável → `getpass`
5. senha fraca → `CommandError`, sem criar conta
6. sem `--email` e sem `PROD_SEED_EMAIL` → `CommandError`
7. `PROD_SEED_EMAIL` como default do `--email`
8. `--nome` isolado numa conta que já existe
9. e-mail com caixa diferente (`get_or_create(email__iexact=…)`)

```
$ diff -u dif_antigo.jsonl dif_novo.jsonl
>>> IDENTICO: nenhuma diferenca em nenhum dos 9 cenarios do caminho legado <<<
```

O conteúdo dos dumps mostra que os cenários **fizeram trabalho de verdade**
(estado muda, `Token` removido, `CommandError` com as 3 mensagens do
`validate_password`, `getpass` disparado, e-mail normalizado para
`caixa@example.com`). Portanto: **o caminho do `subir-localhost.sh` — o
localhost — não quebra.** Isso vale mais que "os testes do executor passam",
porque os testes do executor só rodam contra a versão nova: um erro de
refatoração que mudasse o comportamento legado **e** adaptasse a expectativa
passaria. O diff não passa.

### Critérios 5, 6, 9, 10, 11 — o shell do workflow, EXECUTADO de verdade

Extraí o bloco do `deploy.yml` com `yaml.safe_load` (o script vive em
`jobs.deploy.steps[0].with.script`, não em `run:`) e **executei** o bloco
literal — `provisionar_usuarios_teste() { … }` + o `if ! provisionar_usuarios_teste; then`
— sob `set -e` (o `set -e` real está em `deploy.yml:248`), num diretório
temporário, contra um `manage.py` falso que registra **argv e ambiente** de
cada chamada.

Posição no script (por linha do script do job, extraída):
```
collectstatic=375 < gate=391 < pm2_state=435
cd "$APP_DIR/backend"=364 < venv ativa=366 < collectstatic=375 < gate=391
gate_dentro_do_cd_backend=True   gate_apos_venv_ativa=True
gate_apos_collectstatic=True     gate_antes_do_pm2=True
$ sh -n gate.sh  -> OK ;  $ bash -n gate.sh -> OK ;  $ sh -n validacao.sh -> OK
```

**CENÁRIO A — gate ligado, SUF=dev (critério 5):** 3 invocações, registradas:
```
argv: manage.py criar_usuario_carga --email teste-free@dev.portal-noticias.com.br    --sem-senha --papel free
argv: manage.py criar_usuario_carga --email teste-premium@dev.portal-noticias.com.br --sem-senha --papel premium
argv: manage.py criar_usuario_carga --email teste-admin@dev.portal-noticias.com.br   --sem-senha --papel admin --superuser
env PROD_SEED_PASSWORD=<AUSENTE>   env PROD_SEED_EMAIL=<AUSENTE>   stdin_isatty=nao
```
3 chamadas, um por perfil, e-mail `teste-<papel>@<pm_suffix>.portal-noticias.com.br`,
`--superuser` só no admin. **CENÁRIO C** com `SUF=homolog`: idêntico, com o
sufixo de homolog.

**CENÁRIO B — gate desligado (critério 6):**
```
Usuários de teste: usuarios_teste=false; nenhuma conta criada
### EXIT=0        invocações ao manage.py: 0
```

**CENÁRIO D — SÓ o `admin` falha, exit 3 (critério 9):**
```
AVISO: falha ao criar/atualizar teste-admin@homolog.portal-noticias.com.br (papel=admin); o deploy do código continua
Usuários de teste: 2 de 3 contas prontas. …
### EXIT=0        invocações: 3
```
**CENÁRIO E — os TRÊS falham:**
```
AVISO: … teste-free@dev…   AVISO: … teste-premium@dev…   AVISO: … teste-admin@dev…
Usuários de teste: 0 de 3 contas prontas. …
### EXIT=0        invocações: 3
```

**CENÁRIO F — validação de valor (critério 10)**, com o `case` **real** do YAML:
```
usuarios_teste='true'   -> exit=0
usuarios_teste='false'  -> exit=0
usuarios_teste='sim'    -> exit=1  ERRO: usuarios_teste deve ser true ou false
usuarios_teste='TRUE'   -> exit=1  ERRO: …
usuarios_teste='True'   -> exit=1  ERRO: …
usuarios_teste='FALSE'  -> exit=1  ERRO: …
usuarios_teste='1'      -> exit=1  ERRO: …
usuarios_teste='0'      -> exit=1  ERRO: …
usuarios_teste=''       -> exit=1  ERRO: …
usuarios_teste=' true'  -> exit=1  ERRO: …
usuarios_teste='true '  -> exit=1  ERRO: …
usuarios_teste='yes'    -> exit=1  ERRO: …
usuarios_teste='on'     -> exit=1  ERRO: …
```
E o `case` está nas **linhas 47-50 do script do job** — antes de qualquer
operação real (as linhas 1-46 são `set -e`, `nvm use 20` e atribuições de
variável), exatamente onde já vivem as validações de `tls_enabled`,
`web_runtime` e `celery_systemd` que o contrato cita.

**Critério 11 — por inspeção E por execução:** removendo os comentários do
script do job `deploy`, `--password` aparece **0 vezes**, `PROD_SEED_PASSWORD`
**0 vezes**, `PROD_SEED_EMAIL` **0 vezes**, `getpass` **0 vezes**. As 2
ocorrências que o `grep` cru acha estão num comentário do próprio executor
(`# SEM \`--password\` e SEM PROD_SEED_PASSWORD: …`), que não executa. E o
registro de argv/env do Cenário A confirma em tempo de execução: nada de senha
no `argv`, `PROD_SEED_PASSWORD` ausente do ambiente, `stdin` não é tty.

**Critério 6 — ligação dos callers (YAML parseado, não `grep`):**
```
deploy.yml       input: {'type': 'boolean', 'required': False, 'default': False}
deploy-dev.yml     job 'deploy-dev'     -> usuarios_teste=True
deploy-homolog.yml job 'deploy-homolog' -> usuarios_teste=True
deploy-prod.yml    job 'deploy-prod'    -> usuarios_teste=False
rollback.yml       job 'rollback'       -> NAO DECLARA (default false do deploy.yml)
```

### Prova de ponta a ponta: gate do YAML → comando real → banco real → views reais

O bloco do gate, com o comando REAL do Django e um banco de verdade
(`/tmp/opencode/muta/backend`, sqlite, 4 deploys):

```
### DEPLOY #1 (gate ligado, SUF=dev)
Usuário teste-free@dev… criado (papel=free, superuser=False) — sem senha utilizável; …
Usuário teste-admin@dev… criado (papel=admin, superuser=True) — sem senha utilizável; …
### DEPLOY #2 (mesmo gate, de novo)
Usuário teste-free@dev… atualizado … — sem senha utilizável; …
### DEPLOY #3 em HOMOLOG (gate ligado)
Usuário teste-free@homolog… criado … — sem senha utilizável; …
### DEPLOY #4 (gate DESLIGADO)
Usuários de teste: usuarios_teste=false; nenhuma conta criada

### ESTADO FINAL NO BANCO
teste-admin@dev.portal-noticias.com.br     papel=admin  superuser=True  staff=True  verificado=True  usa_senha=False deve_trocar=True  tokens=0 prefixo_senha='!'
teste-free@dev.portal-noticias.com.br      papel=free   superuser=False staff=False verificado=True  usa_senha=False deve_trocar=True  tokens=0 prefixo_senha='!'
teste-premium@dev.portal-noticias.com.br   papel=premium …                  verificado=True  usa_senha=False deve_trocar=True  tokens=0 prefixo_senha='!'
teste-admin@homolog.portal-noticias.com.br papel=admin  superuser=True  …      verificado=True  usa_senha=False deve_trocar=True  tokens=0 prefixo_senha='!'
teste-free@homolog…  /  teste-premium@homolog…   (idem, usa_senha=False deve_trocar=True)
```

E o **critério 2 pelo caminho exato do deploy** — gate do YAML, comando real,
banco real, e no meio o primeiro acesso feito pelas **views reais** por HTTP:

```
### 1) DEPLOY #1
    POST /api/auth/recuperar-senha/ -> 200
    POST /api/auth/redefinir-senha/ -> 200 {'detail': 'Senha redefinida com sucesso.'}
    POST /api/auth/login/           -> 200 deve_trocar_senha=True
    POST /api/auth/trocar-senha/     -> 200 Senha atualizada com sucesso.
    teste-free@dev…: usa_senha=True deve_trocar=False superuser=False tokens=1
### 3) DEPLOY #2 — o gate roda de novo sobre quem JA ENTROU
    Usuário teste-free@dev… atualizado … — senha já definida foi preservada (o primeiro acesso já aconteceu).
    teste-free@dev…: usa_senha=True deve_trocar=False superuser=False tokens=1
### 4) a senha definida pela pessoa continua valendo?
    login com 'Definitiva12345': 200 (esperado 200) OK deve_trocar_senha=False
    login com 'PrimeiraVez123' : 401 (esperado 401) OK
### 5) DEPLOY #3 — e a conta que NINGUEM abriu
    teste-admin@dev…: usa_senha=False deve_trocar=True superuser=True tokens=0
```

Ou seja: a senha da pessoa **e** a flag `deve_trocar_senha=False` **e** o
`Token` dela sobrevivem ao redeploy, e a conta que ninguém abriu continua sem
senha utilizável. Critério 2 confirmado de ponta a ponta.

### Critério 8 — o teste atravessa os endpoints de verdade?

Sim, e eu não aceitei isso por leitura do nome do teste. `identidade/urls.py`
declara `auth/recuperar-senha/ → RecuperarSenhaView`, `auth/redefinir-senha/ →
RedefinirSenhaView`, `auth/trocar-senha/ → TrocarSenhaView`; o
`test_fluxo_completo_de_primeiro_acesso_da_conta_de_teste` usa `APIClient()`
contra essas URLs (sem `force_login`, sem atalho de DB) e **lê o `uid`/`token`
do corpo do e-mail** (`mail.outbox`), que é o mesmo caminho da pessoa — um
atalho de teste passaria mesmo com o e-mail quebrado. E a prova acima
(etapas 2 e 4 do e2e) mostra os quatro HTTP 200 reais.

### Cobertura dos 12 critérios de aceite

| # | Critério | Veredito | Evidência real | Trivial ou exercita? |
|---|---|---|---|---|
| 1 | `--sem-senha` cria conta sem senha utilizável, `deve_trocar_senha/is_active/email_verificado` | **ATENDIDO** | `test_comando_sem_senha_cria_conta_sem_senha_utilizavel_em_primeiro_acesso` (asserts `password.startswith("!")` + stdout exato) + e2e com banco real | **Exercita.** Mata B, C, D |
| 2 | Redeploy **não** destrói a senha; inverso (conta nova / já recuperada) | **ATENDIDO** | e2e2 (gate→comando→banco→views, 3 deploys, token preservado) + 5 testes pytest + mutações D e G mortas | **Exercita.** É o critério mais forte da run |
| 3 | `--sem-senha` + `--password` → `CommandError`, sem escolher em silêncio | **ATENDIDO** | `test_sem_senha_com_password_falha_sem_criar_nada`; mutação F mata 1 teste | **Exercita** |
| 4 | Sem a flag, comportamento **idêntico** ao de hoje | **ATENDIDO** | **diff de 9 cenários ANTIGO vs NOVO = vazio** + 2 testes meus de `getpass` legado | **Exercita** — mais forte que os testes do executor |
| 5 | Gate ligado → 3 chamadas, um por perfil, e-mail `teste-<papel>@<sufixo>` | **ATENDIDO** | Cenário A/C: argv registrado, 3 invocações, sufixo dev e homolog | **Exercita** (shell executado) |
| 6 | Gate desligado → bloco não executa; PROD e rollback sem a flag | **ATENDIDO** | Cenário B (0 invocações) + YAML parseado (default `false`, prod `false`, rollback não declara) | **Exercita** |
| 7 | Login com qualquer senha na conta sem senha utilizável → 401, **nenhum** Token | **ATENDIDO** | `test_login_com_qualquer_senha_…` parametrizado (5 senhas), afirma `Token` inexistente | **Exercita o critério, mas a parametrização é fraca** (4 das 5 senhas provam a mesma coisa) |
| 8 | Recuperação → login com `deve_trocar_senha: true` → troca → `false` | **ATENDIDO** | `test_fluxo_completo_…` + e2e2 etapas 2/4 (HTTP 200 reais) | **Exercita.** Teste de fluxo completo, não atalho |
| 9 | Falha na criação não derruba o deploy; aviso explícito | **ATENDIDO** | Cenários D (1 de 3 falha) e E (3 de 3 falham): `EXIT=0`, aviso por perfil, resumo "N de 3" | **Exercita** (shell executado) |
| 10 | Valor fora de `true`/`false` aborta antes de qualquer operação | **ATENDIDO** | Cenário F: 13 valores, `exit=1` nos 11 inválidos; `case` nas linhas 47-50 do script | **Exercita** |
| 11 | Nenhuma senha em log, argv ou arquivo | **ATENDIDO** | Script do job sem comentários: `--password`/`PROD_SEED_PASSWORD`/`getpass` = 0 ocorrências; argv e env registrados nas 3 invocações | **Exercita** (inspeção + execução) |
| 12 | `test_primeiro_acesso.py` passa sem mudar + suíte completa verde | **ATENDIDO COM RESSALVA** | `5 passed` no arquivo (intacto, fora do `git status`); suíte do CI em Postgres: `841 passed`, cobertura 91,15% ≥ 80%. **Ressalva = FLY-1** | **Exercita**, mas a suíte tem flakiness de outra run |

**Nenhum critério "não testável".** Os cinco de shell foram testados executando
o bloco literal do YAML, não por inspeção.

### Trivial vs. real (o que eu não aceitaria sem mutation testing)

**Realmente exercitam o critério** (mataram mutação):
`test_redeploy_preserva_a_senha_que_a_pessoa_definiu_na_recuperacao`,
`test_redeploy_preserva_ate_o_token_de_quem_ja_estava_logado`,
`test_redeploy_reaplica_sem_senha_na_conta_que_ainda_nao_tem_senha`,
`test_sem_senha_normaliza_campos_administrativos_sem_destruir_senha`,
`test_sem_senha_com_password_falha_sem_criar_nada`,
`test_sem_senha_com_prod_seed_password_no_ambiente_avisa_e_nao_imprime_a_senha`,
`test_caminho_com_senha_inalterado_troca_a_senha_e_mata_o_token_anterior`,
`test_caminho_com_senha_continua_lendo_prod_seed_password_do_ambiente`,
`test_fluxo_completo_de_primeiro_acesso_da_conta_de_teste`, e os 7 meus.

**Passam, mas são mais fracos do que parecem — não contam como prova do
critério que o nome delas sugere:**
- `test_sem_senha_com_papel_admin_e_superuser_so_no_admin` testa a **camada
  errada** para a preocupação do seu nome. Ele passa `--superuser` explicitamente
  para o admin, então continua verde mesmo se o gate do shell passar
  `--superuser` para os TRÊS perfis — que é exatamente o que o critério de
  segurança queria evitar. A prova desse critério é o Cenário A (argv real).
- `test_login_com_qualquer_senha_…` parametrizado: 4 das 5 senhas (`"teste"`,
  `"qualquer-coisa-123"`, `"!"`, …) provam a mesma coisa que a primeira. A
  asserção que importa é `has_usable_password() is False`, que o critério 1 já
  cobre. Mantido por ser barato, mas não é o que prova o critério 7.
- `test_caminho_com_senha_rejeita_senha_fraca_e_nao_cria_conta` é quase
  duplicata de `test_primeiro_acesso.py::test_comando_carga_rejeita_senha_fraca`,
  que já existia. É a **única** duplicata que encontrei entre os dois arquivos.

---

### Observações (não bloqueiam o veredito; nenhuma é bug de código desta run)

1. **FLY-1 (a única que o orchestrator precisa agir):** suíte completa tem
   flakiness em `catalogo_noticias/tests/test_command_agendar_ingestao.py::test_sigterm_em_processo_real_encerra_sem_traceback_e_rapido`
   (arquivo untracked de `run-20260925-2136-ingestao-noticias`). 1 falha em 3
   execuções. Se o `ci.yml` ficar vermelho, a causa não é esta run — mas é
   esta run que vai pagar o custo de ser commitada junto.
2. **O caminho de entrada documentado depende de config que ninguém nesta run
   verificou:** `config/settings.py:476` tem
   `EMAIL_BACKEND = os.environ.get("DJANGO_EMAIL_BACKEND", "…console.EmailBackend")`
   e `backend/.env.example:27` traz o console. Se o `.env` de DEV/HOMOLOG não
   apontar para o backend real (Resend), `/recuperar-senha` **não envia
   e-mail**: ele imprime o corpo (com `uid` e `token` de redefinição) no log
   do app, e a pessoa não consegue entrar. O critério 8 está correto no código
   e inatingível no ambiente se isso não estiver configurado. O `documenter`
   precisa escrever isso, e vale o gate checar `DJANGO_EMAIL_BACKEND` junto com
   o de `usuarios_teste`. (É config pré-existente, não escopo desta run.)
3. **Contrato × repo (imprecisão, sem impacto):** a seção "Interfaces afetadas"
   lista `subir-localhost.bat` como consumidor de `criar_usuario_carga`. Ele
   chama `ensure_local_admin.py` (linhas 163, 317, 320), não o comando. Só
   `subir-localhost.sh` (linhas 383 e 492) e a migration `0004` (docstring)
   citam o comando.
4. **`--sem-senha --password ""` agora dá `CommandError`** (porque
   `senha_explicita` é `"" is not None` → `True`), onde uma leitura ingênua
   esperaria o prompt. É fail-closed e defensável, mas é um **delta** em
   relação ao comportamento antigo que o meu teste diferencial não cobre
   (a versão antiga não tinha `--sem-senha`). Registrado para o `reviewer`.
5. **O `if ! provisionar_usuarios_teste; then … fi` é código morto:** a função
   termina em `return 0` em todos os caminhos ( Cenários D e E confirmam
   `EXIT=0` mesmo com 3 falhas). A defesa em profundidade é inofensiva, mas a
   evidência "CENÁRIO D" do executor não prova aquele `if` — prova o `return 0`
   de dentro da função. Nenhum efeito prático.

### O que eu NÃO fiz (por regra)

Não editei código de produção, não commitei, não fiz push/checkout/stash/
reset/branch, e não toquei no bloco do D2 de `deploy.yml`, em
`backend/feed/`, `backend/catalogo_noticias/`, `subir-localhost.sh` nem em
`agentic-framework/state/run-20260924-1535-arquivar-ingestao/`. Todo o
mutation testing e todo o e2e com banco real aconteceram em
`/tmp/opencode/muta` (cópia do `backend/`) e `/tmp/opencode/gate-tester`; o
`backend/db.sqlite3` do repo tem mtime **18:45** (anterior à minha sessão) e
`git status` limpo para ele.

---

## Iteração 3 — 2026-09-25 19:40–20:20 — remediator (correções da review)

**Veredito de entrada:** `changes_requested` — 0 blocker, 1 major, 1 minor, 2 nits.
**Veredito de saída:** os 4 findings **fechados**, com prova executada. Nenhum
ficou em aberto; duas observações fora de escopo foram registradas como nota (N1,
N2 abaixo) para o orchestrator.

**Arquivos tocados nesta iteração (4, todos no escopo do finding):**
- `.github/workflows/deploy.yml` — Finding 1 (selo pós-`.env`), Finding 2 (log
  honesto sobre o e-mail), Finding 3 (`return 1` real)
- `backend/identidade/tests/test_gate_deploy_usuarios_teste.py` (novo) — o
  pytest que roda o harness
- `scripts/verificar-gate-usuarios-teste.sh` (novo) — o harness em dash
- `backend/identidade/tests/test_usuarios_teste_complemento_tester.py` — Finding 4

Nada mais foi tocado. `criar_usuario_carga.py` **não** foi mexido (a revisão
não achou bug nele), e o bloco D2 de outra run em `deploy.yml` está intacto —
prova no final desta seção.

---

### F1 (major, security) — o `.env` da VPS não pode decidir o gate

**O que mudou.** Um bloco novo em `deploy.yml`, imediatamente **depois** de
`set -a; . ./.env; set +a` (que está na linha 618), com 2 linhas Effective:

```sh
USUARIOS_TESTE="${{ inputs.usuarios_teste }}"
case "$USUARIOS_TESTE" in
  true|false) ;;
  *) echo "ERRO: usuarios_teste deve ser true ou false (revalidado após carregar $APP_DIR/backend/.env)"; exit 1 ;;
esac
```

**Por que esta abordagem e não outra.** A revisão sugeriu duas coisas: copiar o
input para outro nome de variável, ou revalidar depois da linha 618. **Trocar o
nome não resolve**, e está escrito no comentário do código por quê: o
`backend/.env` é um arquivo de texto arbitrário em que qualquer chave pode
aparecer, e `set -a` exporta todas — um nome novo (`USUARIOS_TESTE_INPUT`,
`PORTAL_USUARIOS_TESTE`, …) é apenas o próximo nome que alguém pode escrever
lá. O que sobrevive a isso é uma **atribuição literal do input do workflow
depois do source**: o `.env` já falou, e o valor do input volta por cima, sem
que nada mais seja lido de variável até o `if` do gate. Isso vale para
qualquer conteúdo do `.env` — a prova abaixo põe `USUARIOS_TESTE=true` **e mais
5 nomes equivalentes** lá, e mesmo assim o gate não liga.

O `case` foi repetido de propósito e não é redundância: o valor revalidado tem
que ser exatamente o que o gate vai ler (critério 10), e o `exit 1` continua
abortando o job. A validação inicial (L294-297) fica: ela é a que falha cedo,
antes de qualquer operação, que é o que o critério 10 pede.

**O que NÃO foi feito, deliberadamente.** O `.env` é *sourced* com semântica de
shell completa, então um `.env` com `$(...)` executa comando arbitrário. Isso é
RCE no deploy e **já existia** para `DJANGO_SECRET_KEY`/`DJANGO_DB_PASSWORD`; não
é o Finding 1 e mexer nisso é redesenhar o carregamento de ambiente. Fica como
N1.

**Evidência 1 — o exploit é reproduzido, e a prova reprova a versão antiga.**

`scripts/verificar-gate-usuarios-teste.sh` (novo) extrai o `script:` do job
`deploy` com `yaml.safe_load`, renderiza os 17 inputs e executa o script
**inteiro** em `dash` contra um `backend/.env` de verdade, num `APP_DIR`
temporário, com `git`/`npm`/`pip`/`pm2`/`python` stubados localmente (o `manage.py`
grava o argv real). Ele aceita um caminho de workflow como argumento, o que
permite rodá-lo contra a versão anterior sem `git checkout`:

```
$ ./scripts/verificar-gate-usuarios-teste.sh /tmp/.../deploy.yml.baseline   # versão ANTES do fix
  FALHA PROD com USUARIOS_TESTE=true no .env: o gate RODOU (3 invocações). O .env sobrepôs o input do workflow.
       | === Deploy prod portal-noticias ===
       | Usuários de teste: teste-free@prod.portal-noticias.com.br pronto (papel=free)
       | Usuários de teste: teste-premium@prod.portal-noticias.com.br pronto (papel=premium)
       | Usuários de teste: teste-admin@prod.portal-noticias.com.br pronto (papel=admin)
  FALHA DEV + .env com USUARIOS_TESTE=false: exit=0, invocações=0 (esperado 0 e 3)
  FALHA DEV + .env com USUARIOS_TESTE=talvez: exit=0, invocações=0 (esperado 0 e 3)
  ...
== 12/21 asserções passaram ==
RESULTADO: REPROVADO (9)
```

Esse é o Finding 1 exato, reproduzido em `dash` com o input do workflow em
`false`: conta superuser em PROD, sem alteração de repositório. Repare que a
versão antiga também perdia o **sentido inverso** — um `.env` com
`USUARIOS_TESTE=false` desligava o gate em DEV.

**Evidência 2 — depois do fix, o mesmo exploit não funciona.**

```
$ ./scripts/verificar-gate-usuarios-teste.sh
== gate usuarios_teste: prova executada ==
workflow: .../.github/workflows/deploy.yml
shell:    dash
  ok   PROD + .env com USUARIOS_TESTE=true (e 5 nomes equivalentes): 0 invocações — o input do workflow é o único que decide
  ok     …e o log diz que o gate está desligado
  ok   DEV com o gate ligado: 3 invocações de criar_usuario_carga
  ok     free:   --email teste-free@dev… --sem-senha --papel free
  ok     premium: --email teste-premium@dev… --sem-senha --papel premium
  ok     admin:  --superuser só no admin
  ok     --superuser aparece em exatamente 1 das 3 chamadas
  ok     nenhum --password no argv
  ok     PROD_SEED_PASSWORD ausente do ambiente
  ok   HOMOLOG com o gate ligado: 3 invocações
  ok   DEV + .env com USUARIOS_TESTE=false: o gate continua ligado (3 invocações) — o .env não manda em nenhum dos dois sentidos
  ok   usuarios_teste=sim: exit=1 e 0 invocações (falha-closed)
  ok   DEV + .env com USUARIOS_TESTE=talvez: o input válido manda e o deploy segue
  ok   só o admin falhando: exit=0 e as 3 chamadas feitas (o deploy não caiu)
  ok     o AVISO por perfil saiu
  ok     o resumo diz 2 de 3
  ok     a receita manual saiu (o if-not da chamada está vivo)
  ok   console backend: o log avisa que o e-mail não chega e diz onde ele sai (pm2 logs portal-api-dev)
  ok     o log avisa que o uid/token do e-mail é credencial
  ok   backend real: o log diz qual backend está em uso e não inventa o problema
  ok   backend ausente: o log cai no aviso do console (que é o default do Django)

== 21/21 asserções passaram ==
RESULTADO: OK
```

Os critérios 5, 6, 10 e 11 (argv por perfil, `--superuser` só no admin, zero
`--password`, zero `PROD_SEED_PASSWORD`, fail-closed de valor) continuam
cobertos por **execução**, e o `argv` idêntico nas duas versões prova que o fix
**não mudou nada em DEV/HOMOLOG**.

**Evidência 3 — a prova não é enfeite: ela se autoverifica.**
`AUTOMUTACAO=1` faz o harness remover, de uma *cópia* do workflow, o bloco do
selo e exige que o cenário do exploit **reprove**; se o cenário passar sem o
selo, o harness sai com `RESULTADO: REPROVADO` e diz que não serve para nada:

```
$ AUTOMUTACAO=1 ./scripts/verificar-gate-usuarios-teste.sh
== 21/21 asserções passaram ==

== AUTOMUTACAO: removendo o selo e exigindo que o exploit volte ==
  FALHA PROD com USUARIOS_TESTE=true no .env: o gate RODOU (3 invocações). O .env sobrepôs o input do workflow.
  ok     sem o selo, o exploit volta: PROD criaria teste-admin (papel=admin) por .env — o cenário detecta a remoção, a prova tem dente
RESULTADO: OK
```

**Evidência 4 — o harness roda no CI.**
`backend/identidade/tests/test_gate_deploy_usuarios_teste.py` chama o harness
com `AUTOMUTACAO=1` e exige `returncode == 0`. Ele **pula** (com motivo
explícito) onde não há `dash` ou PyYAML — nunca reprova por falta de
infraestrutura, mas onde roda, roda de verdade:

```
$ cd backend && .venv/bin/python -m pytest identidade/tests/test_gate_deploy_usuarios_teste.py -v
identidade/tests/test_gate_deploy_usuarios_teste.py::test_gate_de_usuarios_teste_no_deploy_ignora_o_arquivo_de_ambiente PASSED
============================== 1 passed in 42.27s ==============================
```

E o mesmo teste **reprova** contra a versão anterior do workflow (returncode 2,
porque a mutação não acha o selo que ainda não existe lá): verificado.

---

### F2 (minor, correctness) — o log parou de afirmar um caminho que não existe

**O que mudou.** O `echo` final de `provisionar_usuarios_teste` ganhou um bloco
que decide a mensagem pelo valor **real** de `DJANGO_EMAIL_BACKEND` (que acabou
de ser carregado do `.env` na linha 618, e é o mesmo valor com que o gunicorn
sobe). Com o console backend — o default do Django em
`config/settings.py:476`, e o estado de qualquer VPS que ainda não configura a
credencial de e-mail (HD-E/WS-09) — o log agora diz a verdade e diz onde o
e-mail sai:

```
Usuários de teste: 3 de 3 contas prontas. Entrada: /recuperar-senha com o e-mail acima — a senha é definida por quem acessa, não pelo deploy.
  AVISO: DJANGO_EMAIL_BACKEND ausente ou console em backend/.env — o link de /recuperar-senha NÃO chega em nenhum inbox. O e-mail (com uid/token = credencial da conta) sai no stdout do gunicorn: pm2 logs portal-api-dev --lines 200 --nostream
```

Com um backend real, o log informa qual está em uso e não inventa problema
nenhum. O nome do processo (`portal-api-$SUF`) é o mesmo que o `validate` já usa
em `deploy.yml:1181`.

**Por que não implementei Resend nem `DJANGO_EMAIL_BACKEND`:** é Não-objetivo
do contrato ("não alterar o frontend e em infra de e-mail") e é a run
`run-20260925-1433-go-live-producao` que trata a credencial. `settings.py` não
foi tocado. O que esta run podia fazer — não mentir no log — foi feito. O texto
do `DJANGO_EMAIL_BACKEND` para o `documenter` continua pendente como o
Observação 2 do tester registrou.

**Evidência:** 3 cenários no harness (`email-console`, `email-real`,
`email-ausente`), todos `ok` na versão nova e todos reprovando na antiga.

---

### F3 (nit) — o `if !` deixou de ser código morto

**O que mudou.** A função passou a terminar com `return 1` quando `okados != 3`
(o `return 0` incondicional foi embora), e o comentário do `if !` foi ajustado
para dizer que ele **é** alcançável e por que ele existe. Agora, quando uma das
3 contas não fica, a receita manual realmente sai no log — que é o que o
comentário sempre prometeu e nunca entregou.

Sem risco para o critério 9: quem trata o `return 1` é o `if !` da chamada, e
não o `set -e`. O harness prova as duas coisas ao mesmo tempo, no cenário
`só o admin falhando`: `exit=0`, 3 chamadas feitas, `AVISO:` por perfil, resumo
`2 de 3` **e** a linha `Crie as contas à mão`. Na versão anterior, a última
reprova com a mensagem "a receita manual NÃO saiu — o ramo da chamada é código
morto de novo".

---

### F4 (nit) — lixo de tokenizer no teste do tester

`test_usuarios_teste_complemento_tester.py:22`: "a preservação não pode virar uma
**concessão** implícita" (era `uma赋能 implícita`).

---

### Comandos executados / evidência

```
$ cd backend && .venv/bin/python -m pytest identidade/ -q
84 passed, 67 warnings in 61.55s (0:01:01)
```
(83 antes desta iteração; +1 = o teste do harness. Os 24 testes de identidade da
run continuam verdes, sem alteração de expectativa.)

Sintaxe do script do step, extraído com `yaml.safe_load` e com os `${{ }}`
trocados por `x` (o `sh -n` não entende expressão do GitHub):

```
$ python3 -c "yaml.safe_load(...)" nos 5 workflows
OK yaml.safe_load: deploy.yml / deploy-dev.yml / deploy-homolog.yml /
                  deploy-prod.yml / rollback.yml
$ sh -n   no script do step deploy: rc=0
$ bash -n no script do step deploy: rc=0
$ dash -n no script do step deploy: rc=0

atribuicoes do input no script : 2        (a inicial + o selo)
case "$USUARIOS_TESTE" in      : 2        (a validação inicial + a revalidação)
ordem: source .env < selo < gate : True
$ dash -n && bash -n scripts/verificar-gate-usuarios-teste.sh
sintaxe OK (dash e bash)
```

**Integridade do bloco D2 de outra run** (não-objetivo explícito):

```
$ diff -u deploy.yml.baseline .github/workflows/deploy.yml | grep '^@@'
@@ -616,6 +616,35 @@     (o selo)
@@ -665,12 +694,35 @@    (o gate: log honesto + return 1)
$ ... | grep -E 'OBSERVABILITY|assegurar_linha_env|celery-beat|nginx_dump|heartbeat|X-Forwarded-For'
VAZIO — o bloco D2 está intacto
$ diff <marcadores D2 do baseline> <marcadores D2 de agora>
IDENTICOS (28 marcadores do bloco D2)
```

Também conferi: `/home/apps` **não** foi criado na máquina (o harness intercepta
o `mkdir -p /home/apps` do script), `backend/db.sqlite3` limpo no `git status`,
nada escrito fora de `mktemp -d`, e nenhum comando git destrutivo foi usado
(`git status`/`git diff`/`git show` apenas).

---

### Notas fora do escopo (para o orchestrator, não são pendências desta run)

- **N1 — o `.env` é `source`d com semântica de shell.** `set -a; . ./.env` executa
  o arquivo, então uma linha com `$(...)` ou um comando ali é RCE no deploy.
  Isso é anterior a esta run e vale para `DJANGO_SECRET_KEY` e
  `DJANGO_DB_PASSWORD` também; o Finding 1 era só a ponta visível (uma
  atribuição). Blindar isso é redesenhar o carregamento de ambiente (parse
  seguro, ou `grep` por chave em vez de `source`) e mexe em TODO o resto do
  script. Não fiz.
- **N2 — a mesma classe de bug existe em outros 4 inputs validados antes da
  linha 618 e usados depois dela** (`WEB_RUNTIME`, `CELERY_SYSTEMD`, `TLS_ENABLED`,
  `GIT_MODE`), como a própria review apontou. A correção que fiz é de 1 input
  porque o escopo desta iteração são os findings, e mexer nesses quatro muda o
  comportamento de knobs que não são fronteira de segurança (o pior efeito
  observável é um `TLS_ENABLED` sobrescrito ERRADO no `.env` far o deploy
  abortar, não criar conta em PROD). Se o orchestrator quiser, é a mesma
  técnica em mais 4 pontos — mas isso é decisão de escopo, não correção de
  finding.
- **N3 — `infra/DEPLOY.md` continua sem documentar o gate** (Observação 2 do
  tester, Finding 2 da review, fase do `documenter`). O texto honesto que o
  `documenter` precisa escrever agora está no próprio log do deploy: o caminho
  de entrada depende de `DJANGO_EMAIL_BACKEND` real nos três ambientes e,
  enquanto isso não existir, o e-mail sai no `pm2 logs portal-api-<suf>`.
- **N4 — a suíte completa tem flakiness de outra run** (FLY-1 do tester,
  `catalogo_noticias/tests/test_command_agendar_ingestao.py`). Não toquei; se o
  CI ficar vermelho, a causa não é esta run.

---

<!-- Decisões técnicas (registradas aqui porque são o ponto da run) -->

## Decisões técnicas

### D1. Idempotência do critério 2 — a ordem é "perguntar, depois escrever"

O erro óbvio é chamar `set_unusable_password()` a cada deploy. O gate roda a cada
push, então isso não é caso raro: é o caminho comum, e a 2ª execução apagaria a
senha que a pessoa acabou de definir pelo `/recuperar-senha` — trancando fora
quem já entrou. A ordem correta em `handle()` é:

1. `get_or_create` a conta;
2. normalizar o que **não** é destrutivo e independe da flag (`papel`, `is_active`,
   `email_verificado`, `nome`, e `--superuser` quando pedido) — porque "criar ou
   atualizar" existe justamente para corrigir drift administrativo, e nenhuma
   dessas escritas tira acesso de ninguém;
3. **só então** perguntar `not criado and user.has_usable_password()`;
4. `False` → conta nova (ou ainda sem senha): `set_unusable_password()` +
   `deve_trocar_senha=True`, e o `Token` anterior é apagado;
   `True` → **não escreve em `password` e não mexe em `deve_trocar_senha`**.

`deve_trocar_senha` acompanha a senha de propósito: se a pessoa já concluiu o
primeiro acesso, um redeploy não pode obrigá-la a trocar a senha a cada push. E
o `Token` também é preservado nesse ramo — como a credencial continua valendo,
derrubá-lo só deslogaria quem está usando o ambiente de teste, sem ganho de
segurança. Note que os testes cobrem os dois ramos: há um caso de "conta já
acessada" e um de "conta que ainda não tem senha".

### D2. Por que a falha da criação de contas não derruba o deploy

Mesma política (e o mesmo formato de código) que a função `ativar_celery_systemd`,
que já está no arquivo: `if ! provisionar_usuarios_teste; then echo "AVISO: …"`
na chamada, `return 0` dentro da função, e nenhum caminho de erro sob `set -e`
involuntário (o comando que pode falhar está no `if`, então o `set -e` não
morre nele). O raciocínio é o mesmo do Celery e vale o mesmo: quando este bloco
roda, o código novo **já está no ar** e as migrations **já rodaram** — o que
falhar é um atalho de acesso para quem está testando. Um deploy derrubado por
causa disso seria pior do que um ambiente sem conta de teste.

A diferença para o Celery: lá a degradação é invisível e silenciosa; aqui não.
Então o bloco é **por perfil** — a falha de `free` não esconde a de `admin`, cada
uma vira um `AVISO:` nomeado e o resumo final diz `N de 3 contas prontas`. Um run
verde que esconde quais contas faltaram é o que esta run existe para evitar.

### D3. `--password` com `default=None` (e o que isso NÃO faz)

`--sem-senha` + `--password` tem que falhar (critério 3). Mas o `default` de
`--password` era `os.environ.get("PROD_SEED_PASSWORD", "")`, e aí não dava para
saber se a senha vinha de alguém ou do ambiente. Com `default=None` a distinção
existe: **argumento explícito → `CommandError`; valor herdado do ambiente →
ignorado, com `AVISO`**. A ambiguidade que precisa ser recusada é a de quem
pediu as duas coisas, não a de uma variável que o operador talvez tenha deixado
lá; e o caminho legado fica idêntico ao de antes (sem argumento, sem variável e
sem prompt → continua pedindo a senha no `getpass`). Há teste para os dois lados
(`test_sem_senha_com_password_falha_sem_criar_nada` e
`test_caminho_com_senha_continua_lendo_prod_seed_password_do_ambiente`).

O detalhe que faz o `--sem-senha` poder ser automatizado: o `getpass` **jamais**
pode rodar nesse caminho — no deploy não há terminal, então o comando perguntaria
a senha e esperaria para sempre. O `if not sem_senha:` em volta do prompt é
essencial, não cosmetics.

### D4. Por que o bloco fica depois do `collectstatic` e não depois do PM2

O contrato pede logo após o `collectstatic`, ainda dentro de `cd "$APP_DIR/backend"`
com a venv ativa — e é o lugar certo: o código novo já está no disco e o
`migrate` já rodaram, então a conta pode ser criada. Antes do PM2 significa que o
portal sobe já encontrando o banco pronto. As 3 chamadas pagam o boot do Django
(~1-2 s cada), o que a restrição de performance do contrato aceita
explicitamente em DEV/HOMOLOG.

---

<!-- Repetir bloco "## Iteração N" para cada evento subsequente -->
