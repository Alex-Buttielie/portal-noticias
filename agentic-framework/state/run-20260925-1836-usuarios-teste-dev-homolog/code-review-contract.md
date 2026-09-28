<!--
CONTRACT: code-review-contract
DONO: reviewer
QUANDO É CRIADO: sempre que review-triggers.md indicar revisão obrigatória, ou sob demanda (skill agentic-review).
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/code-review-contract.md
-->

# Code Review Contract — 20260925-1836-usuarios-teste-dev-homolog

> **Revisão 2 (revalidação, pós Iteração 3 do remediator).** A revisão 1 (4 findings:
> 1 major / 1 minor / 2 nits, veredito `changes_requested`) está rebaixada a
> "status dos findings anteriores", abaixo. O veredito desta revisão é
> **`approve_with_comments`**: nenhum `blocker`, nenhum `major`; 3 `minor` novos,
> todos com correção de 1 linha ou uma melhoria de comentário, nenhum deles
> reintroduzindo a falha que a Iteração 3 existiu para fechar.

## Metadados
- **run_id:** 20260925-1836-usuarios-teste-dev-homolog
- **Escopo desta revalidação (não a review inteira):** o que a Iteração 3 do
  remediator tocou, e só isso.
  - `.github/workflows/deploy.yml`: bloco do selo (L619-647, logo depois do
    `set -a; . ./.env; set +a` da L617), função `provisionar_usuarios_teste`
    (L667-720) com a nova mensagem de e-mail (L698-712), o `return 1` real
    (L717-718) e o `if !` da chamada (L726-728).
  - `scripts/verificar-gate-usuarios-teste.sh` (novo, 22 KB).
  - `backend/identidade/tests/test_gate_deploy_usuarios_teste.py` (novo).
  - `backend/identidade/tests/test_usuarios_teste_complemento_tester.py` (só o
    comentário do Finding 4).
- **Fora do escopo, não re-revisado:** `criar_usuario_carga.py` (conferi por
  hash, ver abaixo), o bloco `OBSERVABILITY_JOB_STATE_FILE` /
  `assegurar_linha_env` / `nginx -T` (run D2, de outra run) e os demais
  arquivos já modificados de outras runs no working tree.
- **Contrato de referência:** implementation-contract.md, v1 (critérios 5, 6, 9,
  10 e 11; Não-objetivos "não criar usuário de teste em PROD, nem com flag, nem
  por variável de ambiente"; "o gate é fail-closed").
- **Gatilhos:** os mesmos da revisão 1 (autenticação/autorização; escrita em
  produção a cada deploy; contrato entre workflows). O gatilho de **segurança**
  reentra agora em segundo plano, porque a correção escolhida (um `case`
  repetido) é exatamente o tipo de coisa que um teste por string "provaria"
  sem provar.

## Verificações executadas nesta revalidação

| # | Verificação | Resultado |
|---|---|---|
| 1 | `git diff -- .github/workflows/deploy.yml` lido hunk a hunk | selo, mensagem de e-mail, `return 1` e `if !` como descrito; o resto do hunk é o bloco D2 de outra run, intacto |
| 2 | Extração do script do job `deploy` com `yaml.safe_load` → 902 linhas; `set -a; . ./.env; set +a` está na **linha 371** | serve de base para auditar "o que é lido depois do source" |
| 3 | `grep` de **todas** as leituras de `$USUARIOS_TESTE` (L15, L47, L396-397, L422) | nada entre o selo (L396) e o `if` da função (L479) reatribui ou relê a partir de `.env` |
| 4 | **Experimento de bypass em `dash`** com 5 `.env` maliciosos (`return 0`, `readonly USUARIOS_TESTE=true`, `exit 0`, `exit 1`, `set +e`) contra o padrão `set -a; . f; set +a` + atribuição literal | `return`/`exit` param o source ou matam o script; **`readonly` faz a atribuição literal falhar e o script MORRE (rc=2) antes do gate** — todos fail-closed para a fronteira do gate. Nenhum transforma `false` em "gate roda" |
| 5 | `./scripts/verificar-gate-usuarios-teste.sh` | **21/21, `RESULTADO: OK`** (o exploit de PROD com 6 nomes de chave no `.env` não liga o gate; o `.env` também não desliga em DEV) |
| 6 | `AUTOMUTACAO=1` no mesmo harness | o exploit volta sem o selo e o cenário detecta — a prova tem dente (confirmado) |
| 7 | **Experimento de falso positivo**: copiei o `deploy.yml` para `/tmp` e troquei o selo por uma proteção **equivalentemente correta** (`set_gate_usuarios_teste "${{ inputs.usuarios_teste }}"` — o input entra por *parâmetro de função* depois do source, que nenhum `.env` alcança) | sem AUTOMUTACAO: **21/21 OK** (as asserções são agnósticas à implementação); com AUTOMUTACAO: **rc=2, "não achei o selo para remover"** → ver Finding R2 |
| 8 | **Experimento do `SUF`**: copiei o harness e pus `SUF=prod` no `backend/.env` do cenário DEV | o gate imprime `teste-free/premium/admin@prod.portal-noticias.com.br pronto` e o deploy segue para `portal-web-prod` → ver Finding R3 |
| 9 | `shutil.which("python3")` / `import yaml` no venv do backend, no python do sistema e nos 3 arquivos de requirements | `backend/.venv` **não tem** PyYAML; o sistema tem (`/usr/lib/python3/dist-packages`); **PyYAML não está em `requirements.txt`, `requirements-lock.txt` nem `requirements-dev.txt`** → ver Finding R1 |
| 10 | `env PATH=<shim sem yaml> .venv/bin/python -m pytest identidade/tests/test_gate_deploy_usuarios_teste.py -q -rs` | **`1 skipped in 0.06s` — `SKIPPED … nenhum interpretador Python com PyYAML`** (é exatamente o que o CI vai ver) |
| 11 | `cd backend && .venv/bin/python -m pytest identidade/ -q` | **84 passed** (83 + o teste novo) — sem regressão |
| 12 | `sha256sum criar_usuario_carga.py` | `12acc7f0e512eb84c3342697c015387166cc4d44c063954c13fa19785c8db609` — **idêntico** ao hash que o tester congelou na Iteração 2 (L213). O remediator não tocou no arquivo: `--sem-senha` e a idempotência (`preserva_senha` decidido antes de qualquer escrita) estão byte a byte como a revisão 1 aprovou |
| 13 | `config/settings.py:476`, `config/email_resend.py`, `deploy.yml:903-904` e `:1233` | default do `EMAIL_BACKEND`, o comportamento do Resend e o nome do processo PM2 conferem com o texto da nova mensagem |
| 14 | `grep -nP '[\x{4e00}-\x{9fff}]'` no teste do tester | nenhum caractere CJK — Finding 4 conferido |
| 15 | Marcadores do bloco D2 em `deploy.yml` | 20 ocorrências de `OBSERVABILITY_JOB_STATE_FILE`/`assegurar_linha_env`/`nginx_dump=`/`X-Forwarded-For` — o bloco de outra run segue inteiro, o selo e o gate estão em hunks separados |

---

# Parte 1 — Status dos findings da revisão 1

| # | Sev. | Status | Como verifiquei |
|---|---|---|---|
| 1 | major (security) | **RESOLVIDO** | §3, §4, §5, §6 acima. A atribuição literal depois do source é a única forma que sobrevive a um `.env` arbitrário, e a justificativa do remediator ("trocar o nome da variável não resolve, porque `set -a` exporta tudo e o arquivo é arbitrário quanto a chaves") está **correta** — testei. Resíduo honesto em R3 (o selo cobre o *liga/desliga*, não as outras variáveis lidas pela função) |
| 2 | minor (correctness) | **RESOLVIDO** | §13. O texto decide pelo valor **real** de `DJANGO_EMAIL_BACKEND`, o fallback do `case` é **idêntico** ao default de `settings.py:476`, o nome do processo (`portal-api-$SUF`) é o mesmo que o `validate` já usa, e o gunicorn herda a variável exportada pelo mesmo `set -a`. A afirmação negativa ("NÃO chega em nenhum inbox") é **verdadeira** para o console backend, e o ramo de backend real **não afirma que o e-mail chega** — só nomeia qual está em uso, então não há cenário em que a mensagem minta. Detalhe que fecha a última dúvida do chamador: `ResendEmailBackend.__init__` **levanta** `ValueError` sem `RESEND_API_KEY` ("nunca engole envio"), então "backend configurado mas token não enviado" não é um cenário silencioso. O gate não envia e-mail nenhum, logo não há o que "não ser idempotente" |
| 3 | nit (maintainability) | **RESOLVIDO** | `if [ "$okados" -eq 3 ]; then return 0; fi; return 1` (L717-718) + o comentário ajustado. O harness afirma as duas metades ao mesmo tempo no cenário "só o admin falhando": `exit=0` **e** a linha `Crie as contas à mão` presente. **E o critério 9 continua intacto**: a chamada está em `if ! provisionar_usuarios_teste` (L726), então (a) o `set -e` do script (L1) não incide sobre o status da chamada, e (b) por semântica POSIX o `errexit` é suspenso em **todo** o corpo da função quando ela é chamada em condição — o que aqui é inofensivo porque o corpo só tem `[ ]`, `echo` e aritmética, e o único comando que pode falhar (`python manage.py …`) já é testado por perfil. O bloco continua antes do `restart_or_start` do PM2 (L611-657), então o código entra no ar de qualquer forma |
| 4 | nit (style) | **RESOLVIDO** | §14 |

**Nenhum dos 4 ficou aberto.** Nenhum item de severidade major/blocker reintroduzido.

---

# Parte 2 — Findings novos (introduzidos ou expostos pela remediação)

### Finding R1 — o teste novo é **pulado** no CI real: a prova do Finding 1 não roda onde se diz que roda
- **Arquivo:** `backend/identidade/tests/test_gate_deploy_usuarios_teste.py:74-75`
  (skip) + `backend/requirements-dev.txt` / `requirements-lock.txt` (o que falta)
- **Categoria:** test-coverage
- **Severidade:** minor
- **Resumo:** o teste é **coletado** pelo comando do `ci.yml:96` (nome `test_*.py`,
  app com `tests/`, `pytest.ini` só define `python_files = test_*.py`, sem
  `testpaths`/`norecursedirs`) — mas ele é marcado com
  `@pytest.mark.skipif(_python_com_yaml() is None, …)`, e **PyYAML não está em
  nenhum dos três arquivos de requirements do projeto**. No runner do GitHub o
  `python3` do PATH é o interpretador do `actions/setup-python`, que só tem o
  que `ci.yml` instala (`requirements-lock.txt` + `requirements-dev.txt`) — e
  lá não há PyYAML. Resultado: **`1 skipped`, em 0,06 s**, exatamente como
  reproduzi (§10). Localmente o teste passa porque o `/usr/bin/python3` desta
  máquina tem PyYAML de apt — o que mascarou o problema.
- **Cenário de falha:** alguém reintroduz o bug do Finding 1 (apaga o selo, ou
  religa a leitura do `.env`) e abre um PR. O job `backend-tests` fica **verde**,
  e o único teste que pegaria isso aparece no log como `s skipped`. A proteção
  do major corrigido continua dependendo de
  `./scripts/verificar-gate-usuarios-teste.sh` na mão. Note que isto **não**
  contradiz o critério 12 (a suíte roda verde — 84 passed) e **não** reintroduz
  a vulnerabilidade: o selo está no código. O que é falso é a afirmação da
  Iteração 3 ("Evidência 4 — **o harness roda no CI**"), que precisa ser
  corrigida no `implementation-history.md` ou tornada verdade.
- **Sugestão (1 linha):** `pyyaml` em `requirements-dev.txt` (é ferramenta de
  teste, e o próprio projeto já faz isso no job do validador de observabilidade,
  `ci.yml:296`). Com isso, o `skipif` continua honesto para ambientes sem
  infraestrutura e o CI passa a executar a prova de verdade.

### Finding R2 — a auto-mutação do harness é acoplada à **forma** do fix: um fix correto e diferente deixa o CI vermelho
- **Arquivo:** `scripts/verificar-gate-usuarios-teste.sh:426-449` (o bloco
  `AUTOMUTACAO`) + `test_gate_deploy_usuarios_teste.py:84-104`
- **Categoria:** test-coverage / maintainability
- **Severidade:** minor
- **Resumo:** as **21 asserções** são comportamentais e agnósticas à
  implementação (§7: um fix alternativo e correto passa 21/21). A
  auto-mutação, não: ela procura a **string literal**
  `USUARIOS_TESTE="${{ inputs.usuarios_teste }}"` e, se não achar, sai com
  `rc=2`. O pytest roda o harness com `AUTOMUTACAO=1` e exige
  `returncode == 0`.
- **Cenário de falha:** alguém reforça a proteção — por exemplo, passa o
  input por **parâmetro de função** depois do source
  (`set_gate_usuarios_teste "${{ inputs.usuarios_teste }}"`), que nenhum `.env`
  consegue alcançar porque o literal é resolvido em tempo de parse do script, não
  em tempo de execução. A proteção continua correta; o comportamento do gate é
  idêntico. Mas o CI fica **vermelho** com `ERRO: não achei o selo para
  remover (substring not found)`. Verificado, não especulado (§7).
  Agravante menor: a mutação remove por substring, então um refactor innocente
  como `GATE_USUARIOS_TESTE="${{ inputs.usuarios_teste }}"; USUARIOS_TESTE="$GATE_USUARIOS_TESTE"`
  também casa e remove o bloco errado.
- **Mitigações já presentes (por isso é minor, não major):** a falha é **barulhenta
  e autoexplicativa** — a mensagem diz exatamente o que fazer ("O formato do
  bloco mudou: atualize a mutação antes de confiar nesta prova") e o pytest
  embute a saída do harness na mensagem de assert. Ou seja, é um falso positivo
  *acionável*, do tipo que se vê e se corrige em 2 minutos; não é um falso
  positivo silencioso que treina a equipe a ignorar o teste.
- **Sugestão:** a mutação deveria ser tolerante — se o selo não existir, o
  harness deveria reportar `MUTAÇÃO: não aplicável (o formato do bloco mudou)`
  e sair **0**, deixando a proteção de regressão por conta das 21 asserções; ou
  aceitar qualquer revalidação pós-source como alvo (`awk` entre
  `set -a; . ./.env` e o `if` da função procurando `case "$*USUARIOS_TESTE*"`).
  Se preferirem manter o `exit 2`, ao menos o pytest deveria distinguir
  "reprovou o comportamento" de "a mutação não encontrou o alvo" e dar nome ao
  segundo caso.

### Finding R3 — o selo cobre o *liga/desliga*, mas o comentário afirma uma invariante mais forte do que o código entrega (`$SUF` continua vindo do `.env`)
- **Arquivo:** `.github/workflows/deploy.yml:640-642` (o comentário do selo) e
  `:427` / `:462` (as leituras de `$SUF` dentro/ao lado do gate)
- **Categoria:** correctness (com leitura de segurança)
- **Severidade:** minor
- **Resumo:** o comentário do selo diz, em linha literal: *"Validade: para
  QUALQUER conteúdo de `backend/.env`, o gate segue o input do workflow, porque
  **nada mais é lido de variável nenhuma** entre este ponto e o `if` da
  função."* A segunda metade é **falsa**: entre o selo (L396) e o `if` (L479) a
  função lê `$SUF` (L427, o domínio do e-mail das contas) e
  `$DJANGO_EMAIL_BACKEND` (L462), e as duas podem ser definidas no `.env` da
  VPS. A primeira metade — a que é o Finding 1 — é verdadeira e é a que importa
  para a fronteira de segurança.
- **Cenário de falha (reproduzido, §8):** `.env` da VPS de **DEV** com uma
  linha `SUF=prod`. O gate liga (input `true`, correto) e cria
  `teste-free@prod.portal-noticias.com.br`, `teste-premium@prod.…`,
  `teste-admin@prod…` — os **mesmos endereços do ambiente de produção** — dentro
  do banco de DEV, e o próprio log passa a mandar o operador para
  `pm2 logs portal-api-prod`. Nenhuma conta de PROD é criada (lá o gate está
  desligado, e o selo é quem garante isso), nenhuma senha existe, nenhum privilégio
  sobe: o efeito é conta de teste com domínio errado, num banco de teste. Por
  isso **minor** e não major — mas é exatamente a mesma forma do Finding 1, a
  **30 linhas** do código que a Iteração 3 acabou de fechar, e o comentário
  afirma que ela foi fechada em geral.
- **Nota (pré-existente, **fora** do diff desta run — para o orchestrator
  registrar como follow-up, não como finding desta run):** o mesmo `SUF`
 controlado pelo `.env` tem um efeito **bem mais grave** no bloco de PM2, que é
  anterior a esta run: com `SUF=prod` no `.env` de DEV, o deploy chega a
  `restart_or_start "portal-web-prod"` e `"portal-api-prod"` (L611, L640, L656),
  ou seja, **reinicia o processo de produção com o código de DEV**. No meu
  harness isso parou em `portal-web-prod não ficou online` porque o stub de PM2
  responde pelo `GATE_PM_SUF`; na VPS real não pararia. Também exige escrita em
  `backend/.env` (ou seja, N1: quem escreve ali já executa código arbitrário
  como o usuário de deploy), então não é fronteira de privilégio — mas é um
  perigo de ambiente cruzado com raio de impacto bem maior que o Finding 1 e
  merece a própria run.
- **Sugestão:** (a) ajustar o comentário do selo para o que ele de fato garante
  ("o valor que **liga** o gate vem do input do workflow e nada mais") e
  mencionar explicitamente que `SUF`/`DJANGO_EMAIL_BACKEND` ainda vêm do `.env`;
  (b) se quiser o gate inteiro imune ao `.env`, lacrar também o `SUF` da mesma
  forma (`SUF="${{ inputs.pm_suffix }}"` depois do source) — 1 linha, sem mudar
  DEV/HOMOLOG. O follow-up do PM2 é assunto da run que dona aquele bloco.

---

# Parte 3 — Julgamento das decisões de escopo do remediator (N1-N4)

Chamador pediu julgamento honesto, "se for major, é major, mesmo que preexistente".
Faço o julgamento nos dois sentidos: o que é escopo, o que é número, e o que é
a justificativa escrita.

### N1 (`.env` é `source`d com semântica de shell → RCE) — **decisão correta, escopo correto**
Confirmei a mecânica: com `set -a; . ./.env; set +a`, um `.env` com `$(…)`/
comando executa, e um `exit 0` faz o script do job sair **0** ali mesmo (medido
em `dash`: `rc=0`, o "CHEGOU AO SELO" nunca é impresso) — ou seja, um `.env`
pode até **fingir um deploy verde**. É grave, mas é **anterior a esta run**,
vale igualmente para `DJANGO_SECRET_KEY`/`DJANGO_DB_PASSWORD`, e a correção é
redesenhar o carregamento de ambiente no script inteiro (parse seguro, ou
`grep` por chave). Blindar isso **não** era o Finding 1 e mexer nisso violaria
"não mexer no resto do script". **Não é major desta run.** É major de um
follow-up próprio.

### N2 (a mesma classe em `WEB_RUNTIME`, `CELERY_SYSTEMD`, `TLS_ENABLED`, `GIT_MODE`) — **decisão de não mexer: defensável. Justificativa escrita: parcialmente errada.**
"Não são fronteira de segurança" **se sustenta** para o que está de fato
exposto (medido no script extraído; o `source` do `.env` é a linha **371**):

| Variável | leituras **antes** do source | leituras **depois** | exposta? |
|---|---|---|---|
| `TLS_ENABLED` | 34, 35, 204, 220, 317, 320 | — | **não** |
| `GIT_MODE` | 54, 56, 58, 209, 210, 228, 260, 265, 270 | — | **não** |
| `WEB_RUNTIME` | 39, 41, 340 | **585, 896** | sim, não é fronteira de segurança |
| `CELERY_SYSTEMD` | 43 | **675** | sim, não é fronteira de segurança |
| `SUF` | 5, 246 | **427, 462, 480, 611+** | sim — **e não estava na lista** |

Ou seja: **`TLS_ENABLED` e `GIT_MODE` não têm o bug** (o `deploy.yml` é
inclusive modelar em `TLS_ENABLED` — as L317-320 são um assert pós-escrita que
compara o valor **do input** com o que está no `.env`, exatamente o padrão que
falta ao gate antes do fix). Os dois que estão expostos não criam conta em
PROD, não mexem em credencial e não mudam o que é servido: são knob de
infraestrutura, e a consequência é o tier web não ser construído do jeito
esperado (WEB_RUNTIME) ou o worker não subir (CELERY_SYSTEMD) — degradação
visível em `/health-detail`, não fronteira de segurança. **A decisão de não
mexer é defensável; a frase "o pior efeito observável é um `TLS_ENABLED`
sobrescrito ERRADO no `.env` far o deploy abortar" está errada** — não há
nenhum uso de `TLS_ENABLED` depois do source para abortar. E a lista de 4 knobs
**esqueceu o `SUF`**, que é o que expõe o gate (Finding R3) e o PM2. Isso não
muda o veredito desta run; muda o que o orchestrator deve registrar no
follow-up.

### N3 (`infra/DEPLOY.md` sem documentar) — **dentro do contrato, fora do escopo da Iteração 3**
O contrato lista `infra/DEPLOY.md` na "Áreas/arquivos esperados" e o
`definition of done` tem "Documentação atualizada [documenter]" como caixa
separada. A Iteração 3 é a de remediação da review; o documento é fase do
`documenter`. **Não é finding de código** e a decisão está correta. O que a
Iteração 3 fez bem foi **transferir para o log** o que era o pedido do Finding 2
(quando a credencial de e-mail não existe, o log diz que o link não chega e
onde ele sai) — o texto que o `documenter` precisa escrever agora é o que já
está em `deploy.yml:699-712`.

### N4 (flakiness de `test_command_agendar_ingestao.py`, de outra run) — **corretamente não tocada**
Arquivo untracked de `run-20260925-2136-ingestao-noticias`, `grep
"20260925-1836"` → 0, mede tempo de processo real. Não é desta run e mexer
seria violar "não tocar em mudanças de outra run". A suíte que importa
(`identidade/`) é **84 passed** e determinística.

### Observação de registro (não é finding)
Os `mtime` dos arquivos tocados na Iteração 3 (`19:05`–`19:19`) são
**anteriores** à janela que a própria Iteração 3 declara (`19:40`–`20:20`). O
conteúdo confere com o que a seção descreve (selo, mensagem, `return 1`, F4), mas
a trilha de auditoria da run está com horário inconsistente — vale corrigir o
horário no `implementation-history.md` para não confundir quem auditar depois.

---

# Resumo quantitativo (revisão 2)

| Severidade | Revisão 1 | Revisão 2 (revalidação) |
|---|---|---|
| blocker | 0 | **0** |
| major | 1 (Finding 1) | **0** — resolvido e com bypass testado em `dash` |
| minor | 1 (Finding 2) | **3** (R1, R2, R3) — o F2 fechou; os 3 são da remediação, 1 linha cada |
| nit | 2 (F3, F4) | **0** — ambos resolvidos |

# Veredito

**`approve_with_comments`**

O Finding 1 — o único que barrava — está **realmente fechado**, e não por
soma de palavras-chave: a correção escolhida é a única que sobrevive a um
`backend/.env` arbitrário, a justificativa do remediator sobre trocar o nome da variável está
correta, e eu testei em `dash` as cinco contra-variantes que o chamador propôs
(`return`, `readonly`, `exit 0`, `exit 1`, `set +e`): nenhuma transforma
`usuarios_teste=false` em "gate roda"; as que alcançam o shell abortam o deploy
antes do gate, que é fail-closed. O Finding 2 fechou honestamente (a mensagem
decide pelo valor real, casa com o default do Django, nomeia o processo certo e
não afirma entrega que não pode garantir). O Finding 3 fechou sem custo: o
`return 1` é tratado pelo `if !`, o `set -e` não o alcança, o bloco continua
antes do PM2, e o critério 9 resiste (exit=0 com 1 de 3 falhando). O Finding 4
fechou. `criar_usuario_carga.py` está **byte a byte** igual ao que a revisão 1
aprovou (hash conferido) — `--sem-senha` e a idempotência não foram tocados. Os
84 testes de identidade passam. O bloco de outra run em `deploy.yml` está
intacto.

Os três `minor` não bloqueiam o merge e nenhum deles reabre o Finding 1: (R1) o
teste novo **é pulado no CI** porque PyYAML não está em nenhum requirements —
a afirmação "o harness roda no CI" da Iteração 3 é falsa e o guard do major
corrigido precisa de `pyyaml` em `requirements-dev.txt` para existir de fato;
(R2) a auto-mutação do harness reprovaria um fix **igualmente correto** de
forma diferente — falso positivo barulhento e acionável, não silencioso;
(R3) o comentário do selo afirma uma invariante mais forte do que o código
entrega (`$SUF` continua vindo do `.env`, e eu reproduzi o efeito), o que é a
mesma forma do Finding 1 a 30 linhas de distância, com impacto de correção
(conta de teste com domínio errado em banco de teste), não de segurança.

Fora do diff, e para o orchestrator registrar como follow-up próprio, não como
pendência desta run: **N1** (o `.env` é executado com semântica de shell, e um
`exit 0` ali finge um deploy verde) e o perigo de ambiente cruzado do `SUF` no
bloco de PM2 (`SUF=prod` no `.env` de DEV reinicia `portal-web-prod` com o
código de DEV) — este último tem raio de impacto maior que o Finding 1 corrigido
e merece a própria run, com owner do bloco de PM2.
