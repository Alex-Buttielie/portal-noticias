<!--
CONTRACT: documentation-update
DONO: documenter
QUANDO É CRIADO: depois que testes passam e a revisão (se exigida) está aprovada.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/documentation-update.md
-->

# Documentation Update — 20260925-1836-usuarios-teste-dev-homolog

## Metadados
- **run_id:** 20260925-1836-usuarios-teste-dev-homolog
- **Baseado em:** implementation-history.md (iterações 1 = executor, 2 = tester, 3 = remediator), implementation-contract.md v1 e code-review-contract.md (veredito de entrada `changes_requested`: 0 blocker, 1 major, 1 minor, 2 nits — os 4 findings fechados na iteração 3)
- **Escopo documentado:** o gate `usuarios_teste` do `.github/workflows/deploy.yml` — as contas de teste de DEV/HOMOLOG, o caminho de entrada (`/recuperar-senha` → `/redefinir-senha` → troca no primeiro login), a ausência de senha em lugar nenhum, a idempotência no redeploy, o PROD fail-closed, e **a dependência honesta de `DJANGO_EMAIL_BACKEND`**
- **Estado do código documentado:** gate executado de verdade (21/21 asserções do harness, reconferidas nesta fase), e-mail de recuperação **não entregue** em nenhum ambiente (console backend), `--superuser` só no `admin`, `PASSWORD_RESET_TIMEOUT` = 1 h
- **Fora do escopo (não documentado por não ter sido implementado):** backend de e-mail real (credencial do Resend), qualquer token/secret novo, a semântica de `deve_trocar_senha`, o frontend

## Documentos afetados
| Documento | Tipo de mudança | Resumo |
|---|---|---|
| `infra/DEPLOY.md` | **nova seção §9.7** com 4 subseções (§9.7.1 "Como entrar (passo a passo)", §9.7.2 "O e-mail de recuperação sai no log da API", §9.7.3 "Se o link se perdeu", §9.7.4 "O que um redeploy faz") + 4 blocos de comando | Runbook do operador da VPS: tabela com as 6 contas (e-mail exato, papel, staff) de DEV e HOMOLOG, o passo a passo de entrada, onde o e-mail de recuperação sai de verdade, como recuperar o link se o log perdeu, o que o redeploy preserva, e por que PROD não tem conta de teste. Numeração `9.7` escolhida porque é a seção "o que o deploy deixa na VPS depois de rodar" (§9) e **nenhuma seção existente foi renumerada** |
| `CI-CD.md` | 4 edições pontuais | (1) parágrafo novo **"Contas de teste por ambiente"** logo depois da tabela "Ambientes na VPS"; (2) coluna `Trigger / gate` da tabela "Workflows" passa a trazer o valor do input por caller; (3) nova subseção **"O gate `usuarios_teste`: contas de teste sem senha em DEV/HOMOLOG"** dentro da §P1-6, ao lado das subseções de `web_runtime` e `celery_systemd`, com a tabela de quem liga e as três propriedades que importam para quem opera; (4) novo item em "Pendências que continuam abertas": `DJANGO_EMAIL_BACKEND` ausente nos três ambientes |
| `agentic-framework/state/run-20260925-1836-usuarios-teste-dev-homolog/documentation-update.md` | novo artefato de fase | Este contrato |
| `README.md` | **nenhuma mudança** | Ver "Sem impacto em documentação?" logo abaixo — nada ficou contraditório e não havia encaixe natural |
| CHANGELOG | **não existe no projeto** | Nenhum arquivo foi criado; ver "Entrada de changelog" |

## Sem impacto em documentação?
- [x] `README.md` **não** foi alterado, e a decisão foi checada linha a linha antes de decidir. A seção "Deploy e infraestrutura" (linhas 16-46) é um resumo da topologia ativa que já aponta para `CI-CD.md` e `infra/DEPLOY.md` como runbooks; ela não enumera ambientes com contas, não afirma nada sobre contas de teste e não ficaria contraditória com o gate. A tabela de endpoints de `identidade` (linha 119, `/api/auth/recuperar-senha/`) descreve o contrato da API — a view **chama** `send_mail` — e o README já diz a verdade maior na linha 88: "em desenvolvimento, o padrão é imprimir os e-mails … no console em vez de enviá-los de verdade — não há integração com um provedor de e-mail transacional real ainda". Acrescentar uma frase sobre as contas de teste ali seria duplicar o runbook em vez de referenciá-lo, e foi exatamente isso que a instrução da fase mandou não fazer.
- [x] `ARCHITECTURE.md` **não** foi alterado (e está fora da lista de arquivos desta fase): conferido por `grep`, o documento **não menciona** `criar_usuario_carga` nem o gate, então não há nada contraditório. O arquivo tem edições não commitadas de outra run.
- [x] Nenhum outro documento do repositório ficou contraditório: `PROD_DECISOES.md` continua sendo a fonte da pendência de e-mail (item 2, citado a partir das duas docs novas) e `subir-localhost.sh` continua criando o admin local com senha conhecida, que é o outro caminho do mesmo comando, com o comportamento intacto (critério 4 da implementação).

## Exemplos/snippets novos ou atualizados

**`infra/DEPLOY.md` §9.7 — como pegar o link de redefinição (o e-mail vai para o log, não para um inbox):**
```bash
# O corpo do e-mail é impresso em texto puro; o assunto sai codificado
# (RFC 2047), por isso o grep é pelo link e não pelo assunto.
pm2 logs portal-api-dev --lines 200 --nostream | grep -A8 'redefinir-senha?uid='
# Ou direto no arquivo que o PM2 mantém (o `pm2 logs` é só uma visão dele):
grep -A8 'redefinir-senha?uid=' ~/.pm2/logs/portal-api-dev-out.log
# Troque `dev` por `homolog` no ambiente de homologação.
```

**`infra/DEPLOY.md` §9.7 — conferir as contas sem alterar nada:**
```bash
SUF=dev            # ou homolog
cd "/home/apps/portal-$SUF/backend"
. .venv/bin/activate
set -a; . ./.env; set +a
python manage.py shell -c "
from django.contrib.auth import get_user_model
U = get_user_model()
for p in ('free', 'premium', 'admin'):
    u = U.objects.filter(email='teste-%s@$SUF.portal-noticias.com.br' % p).first()
    print(p, 'inexistente' if not u else 'papel=%s superuser=%s tem_senha=%s deve_trocar=%s'
          % (u.papel, u.is_superuser, u.has_usable_password(), u.deve_trocar_senha))
"
```

**`infra/DEPLOY.md` §9.7 — sem e-mail e sem log, definir a senha direto na VPS:**
```bash
SUF=dev            # ou homolog
cd "/home/apps/portal-$SUF/backend"
. .venv/bin/activate
set -a; . ./.env; set +a
python manage.py changepassword "teste-free@$SUF.portal-noticias.com.br"
```

**`infra/DEPLOY.md` §9.7 — criar uma conta à mão quando o log disser `N de 3`:**
```bash
SUF=dev            # ou homolog
cd "/home/apps/portal-$SUF/backend"
. .venv/bin/activate
set -a; . ./.env; set +a
python manage.py criar_usuario_carga \
  --email "teste-free@$SUF.portal-noticias.com.br" --sem-senha --papel free
# Troque `free` por `premium` ou `admin` nas outras duas. O sufixo de PROD
# (`prod`) não usa essas contas — ver o início desta seção.
```

**`CI-CD.md` §P1-6 — como rodar a prova do gate fora do CI:**
```bash
scripts/verificar-gate-usuarios-teste.sh                 # ~40 s
AUTOMUTACAO=1 scripts/verificar-gate-usuarios-teste.sh   # ~80 s, com a automutação
```

## Entrada de changelog
**O projeto não mantém CHANGELOG.** Verificado nesta fase: nenhum arquivo `CHANGELOG*`/`CHANGES*`/`HISTORY*` de produto na raiz nem em subdiretório — o único `HISTORY.md` é `agentic-framework/state/HISTORY.md`, que é o registro de execuções do framework de agentes, não um changelog do software. As 5 documentation-update.md anteriores do repositório registram a mesma conclusão. **Nenhum arquivo de changelog foi criado**, porque inventar um histórico de versões num projeto que não o mantém seria um registro falso. Se o projeto adotar um CHANGELOG no futuro, esta mudança entra como algo como: *"DEV e HOMOLOG passam a receber, a cada deploy, uma conta de teste por perfil (`teste-free@`, `teste-premium@`, `teste-admin@`) sem senha utilizável; o primeiro acesso é pelo fluxo de recuperação de senha e o redeploy não apaga a senha já definida. PROD nunca recebe essas contas."*

## Verificação
- [x] **Nenhum exemplo/trecho de documentação existente ficou contraditório** — o `git diff` toca só o que está na tabela acima: `infra/DEPLOY.md` é **100 % aditivo** (170 linhas novas, 0 removidas) e `CI-CD.md` remove 4 linhas, que são exatamente as 4 células da coluna `Trigger / gate` reescritas. Nenhuma seção foi renumerada, nenhum texto de outra run foi editado dentro dos dois arquivos (conferido com `git diff -U1` linha a linha).
- [x] **Build/lint de documentação** — o projeto **não tem** linter de markdown (sem `markdownlint`, `vale`, `remark` ou `.pre-commit-config.yaml`; `ci.yml` não roda nenhum). A verificação foi: contagem de fences balanceada nos dois arquivos (`infra/DEPLOY.md` 92, `CI-CD.md` 10, ambos pares) e leitura do diff inteiro.
- [x] **Todo fato citado nas docs foi conferido contra o código, não de memória:**
  - e-mails e `--superuser` só no `admin`: lido no bloco do gate em `.github/workflows/deploy.yml:667-728`; `deploy-prod.yml:61` (`false` explícito), `deploy-dev.yml:35` e `deploy-homolog.yml:34` (`true`), `rollback.yml` sem o input;
  - "o `.env` da VPS não decide o gate": o bloco do selo **depois** do `set -a; . ./.env` (`deploy.yml:619-647`);
  - `DJANGO_EMAIL_BACKEND` ausente do bootstrap: o `printf` que cria `backend/.env` (`deploy.yml:547`) não tem a chave, e `backend/config/settings.py:476` cai no console backend; a lista de "todo e-mail transacional" do item de pendência do `CI-CD.md` saiu de `grep -rn "send_mail\|EmailMessage"` (só `identidade/emails.py`, `newsletter/services.py` e `b2b/services.py` — o `allauth` do Google não entra por `send_mail`);
  - **formato real da saída do console backend**: rodado um `send_mail` de teste no venv local — o assunto sai codificado em RFC 2047 e o corpo sai em texto puro, por isso o `grep` dos docs é pelo link (`redefinir-senha?uid=`), e não pelo assunto;
  - validade do link: `config/settings.py:626` (`PASSWORD_RESET_TIMEOUT` = 3600 s, `PASSWORD_RESET_TIMEOUT_SECONDS`); o gerador é o `PasswordResetTokenGenerator` padrão (Django 5.2, sem `identify_hasher`, que é o que permite o token de uma conta com senha inutilizável);
  - `FRONTEND_BASE_URL` do link vem do bootstrap (`FRONTEND_BASE_URL=$WEB_ORIGIN`), ou seja o domínio do próprio ambiente;
  - redirecionamento para `/trocar-senha` no primeiro login: `frontend/app/login/page.tsx:19`; campos `senha_atual`/`nova_senha` em `identidade/serializers.py:103`;
  - `changepassword` existe de verdade: `django/contrib/auth/management/commands/changepassword.py` no venv, com `django.contrib.auth` em `INSTALLED_APPS` e `USERNAME_FIELD = "email"`;
  - os **do snippets** com `manage.py shell -c` foram **executados** (variante com `$SUF` inclusive) e produzem a saída documentada;
  - a afirmação "21 asserções" e os tempos `~40 s` / `~80 s` do harness: o harness foi **rodado nesta fase** (`RESULTADO: OK`, 21/21, `real 0m40,591s`).
- [x] **Nenhuma alteração de outra run foi sobrescrita.** Só três arquivos de fora do diretório de estado foram escritos: `infra/DEPLOY.md`, `CI-CD.md` e este contrato. `git status` final mostra intactos os arquivos de outras runs (`ARCHITECTURE.md`, `README.md`, `subir-localhost.sh`, `backend/**`, `infra/observability/**`, `scripts/observability/validar-infra.sh`, `agentic-framework/state/HISTORY.md`, o bloco do D2 em `deploy.yml`). Nenhum comando git destrutivo foi usado — só `status`, `diff`, `diff --numstat` e `check-ignore`.

## O que ficou de fora, de propósito
- **Não documentado como se fosse verdade: o e-mail de recuperação chegando.** O texto das duas docs diz, explicitamente, que **hoje nada chega em nenhum inbox** e que o e-mail sai no stdout do gunicorn (`pm2 logs portal-api-<env>`), com o `uid`/`token` tratado como credencial. A pendência é nomeada e apontada (`PROD_DECISOES.md` item 2; dependência humana HD-E da run de go-live), não descrita como resolvida. Isso fecha o Finding 2 da revisão ("o log parou de afirmar um caminho que não existe") na parte da documentação.
- **Nada foi inventado sobre recuperar o link.** A pergunta era se existe algo no código; a resposta honeta, verificada no código, é: **não existe comando de management que emita o link** — ele só nasce de `POST /api/auth/recuperar-senha/` (`identidade/views.py:160-173` → `emails.py:37`). As três saídas que *existem de fato* foram documentadas (pedir um link novo; o link antigo continua válido até 1 h, porque o token é derivado do estado da conta; e `changepassword`, com os dois avisos honestos: não mexe em `deve_trocar_senha` e quebra a premissa "senha não existe" daquela conta, já que o redeploy a preserva).
- **Nenhuma seção nova foi criada em documento cuja estrutura não a comportasse.** `infra/DEPLOY.md` tem uma seção exatamente para "o que o deploy deixa na VPS depois de rodar" (§9) e foi nela que a §9.7 entrou; `CI-CD.md` tem a §P1-6 como o registro do contrato do `deploy.yml` (é onde `web_runtime` e `celery_systemd` estão documentados) e foi nela que a subseção do gate entrou. Não foi inventada uma seção "Contas de teste" solta no topo de nenhum dos dois.
- **Não documentado (é evidência de verificação, não operação):** a matriz de mutação, o `AUTOMUTACAO=1`, os 17+7+1 testes e o diff diferencial do caminho legado. Só a **existência** do harness e como rodá-lo entraram no `CI-CD.md`, porque quem mantém a esteira precisa saber que ele existe.
- **Fora do escopo desta fase e por quê:** o `backend/.env.example` traz `DJANGO_EMAIL_BACKEND=…console.EmailBackend` como exemplo local — correto para dev local e não contraditório; o bootstrap do `deploy.yml` que **não** escreve a chave é que faz o e-mail ir para o log, e isso está documentado como pendência, não "corrigido" com um default no repo (default no repo seria afirmar entrega real, que não existe).

## Pendência que a documentação expõe (e que só o humano fecha)
A entrada nas contas de teste de DEV/HOMOLOG depende inteiramente de
`DJANGO_EMAIL_BACKEND` + `RESEND_API_KEY` no `backend/.env` de cada ambiente. O
código do Resend já existe (`backend/config/email_resend.py`) e o gate já avisa
no log qual backend está em uso; o que falta é a credencial, registrada como
**HD-E** na run de go-live e como item 2 de `PROD_DECISOES.md`. Documentado como
dependência, não como problema desta mudança.
