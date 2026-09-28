<!--
CONTRACT: task-plan
DONO: orchestrator
QUANDO É CRIADO: no início de toda execução (agentic-run), antes de qualquer implementação.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/task-plan.md
-->

# Task Plan — 20260925-1836-usuarios-teste-dev-homolog

## Metadados
- **run_id:** 20260925-1836-usuarios-teste-dev-homolog
- **Data de abertura:** 2026-09-25
- **Solicitado por:** humano (sessão de chat)
- **Spec de origem:** nenhuma — pedido conversacional. Referência de comportamento: `subir-localhost.sh` (linhas 250-263 e 359-378) e `backend/identidade/management/commands/criar_usuario_carga.py`.

## Objetivo
Ao final desta execução, o deploy de **DEV** e de **HOMOLOG** deve provisionar automaticamente
**um usuário de teste por perfil** (`free`, `premium`, `admin`), com o mesmo mecanismo de carga
que o `subir-localhost.sh` já usa, e **PROD nunca** deve criar conta de teste alguma.

## Escopo
### Dentro do escopo
- Um usuário de teste por perfil (`free`, `premium`, `admin`) criado/atualizado a cada deploy de
  DEV e de HOMOLOG, de forma **idempotente** (redeploy não reseta senha já trocada).
- Suporte no comando `criar_usuario_carga` para criar a conta **sem senha utilizável**, porque o
  primeiro acesso é feito pelo fluxo "Esqueci minha senha" já existente no produto
  (`POST /api/auth/recuperar-senha/` → `POST /api/auth/redefinir-senha/`).
- Gate explícito e **fail-closed** no `deploy.yml` para que só DEV e HOMOLOG criem contas, e
  PROD/rollback nunca.
- Resumo no log do run com os e-mails criados e a instrução de como entrar.
- Testes automatizados do comportamento novo do comando de carga.

### Fora do escopo (explicitamente)
- **PROD não cria usuário de teste** em nenhuma hipótese (nem opcional, nem por variável).
- Não gravar senha, token ou segredo no repositório, no `.env` da VPS ou no log do run.
- Não mexer no frontend (telas de login, "esqueci minha senha" já existem).
- Não alterar `RedefinirSenhaView`/`TrocarSenhaView` nem a semântica de `deve_trocar_senha`.
- Não alterar o comportamento de `subir-localhost.sh` (o admin `admin@local.test` local continua
  igual, com senha conhecida).
- Não tocar nos já muitas alterações não commitadas no working tree que pertencem a outras runs.

## Suposições assumidas
- **E-mail dos usuários de teste** = `teste-<papel>@<sufixo-ambiente>.portal-noticias.com.br`
  (ex.: `teste-admin@homolog.portal-noticias.com.br`), derivado do `pm_suffix` já existente e não
  de `$HOST` — o que também desvia da divergência `.com` × `.com.br` registrada como R-2 em
  `CI-CD.md`. Motivo: o solicitante não fixou o formato do e-mail e cada ambiente tem banco próprio,
  então o prefixo por ambiente é redundante mas inofensivo e torna óbvio, num log, em qual ambiente
  a conta está.
- **Senha inicial**: inexistente por construção (`set_unusable_password()`). A conta fica
  inacessível até alguém usar "Esqueci minha senha". Motivo: o solicitante escolheu o fluxo de
  recuperação explicitamente depois de saber que `trocar-senha` exige a senha atual.
- **Senha de quem já trocou não é resetada em redeploy.** O comando só aplica a política
  "sem senha utilizável" quando a conta ainda não tem senha utilizável. Motivo: sem isso, todo
  deploy quebraria a sessão de quem está testando.
- **Falha ao criar a conta não derruba o deploy** (aviso, não erro), seguindo o precedente já
  documentado do Celery no mesmo arquivo. Motivo: web e API já provisionados; uma conveniência não
  pode custar o deploy do código.

## Restrições
- Segurar a fronteira de segurança do projeto: PROD é fail-closed e não deve ganhar caminho
  opcional para criar contas de teste.
- Manter a invariante do `deploy.yml`: nada de credencial em log, argv ou arquivo versionado.
- Compatibilidade retroativa: `criar_usuario_carga` sem a nova flag precisa se comportar exatamente
  como hoje (usado por `subir-localhost.sh`, `.bat`, migration de carga e testes existentes).
- Não introduzir dependência externa nova.

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | código + implementation-history.md |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked |
| 3 | reviewer (OBRIGATÓRIO — `review-triggers.md`) | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. Um deploy de DEV deixa existindo 3 contas de teste, uma por perfil (`free`, `premium`, `admin`),
   aptas a entrar.
2. Um deploy de HOMOLOG deixa existindo as mesmas 3 contas, em banco distinto do de DEV.
3. Nenhum deploy de PROD cria conta de teste, mesmo que alguém adicione a flag por engano.
4. Um redeploy do mesmo ambiente **não** invalida a senha que a pessoa já definiu pelo fluxo de
   recuperação.
5. Nenhuma senha, token ou segredo novo aparece no repositório, no log do run ou no `.env` da VPS.
6. O operador descobre, no log do run, quais e-mails existem e como entrar neles.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Flag `usuarios_teste` ser ligada por engano em PROD | alto | `deploy-prod.yml` não declara a flag e o `deploy.yml` valida o valor; o gate é default `false` e PROD é fail-closed por construção |
| Senha impressa no log do run | alto | não existe senha: a conta nasce com senha inutilizável; o segredo do primeiro acesso é gerado pela pessoa no navegador |
| Conta de teste usada em homologação com dado real confundindo QA | médio | e-mail com prefixo `teste-` e sufixo do ambiente; `email_verificado=True` explícito (necessário para a Central/admin) |
| `manage.py criar_usuario_carga` falhar e derrubar o deploy inteiro | médio | mesma política do Celery: aviso, não erro; o código continua no ar |
| Redploy resetar a senha de quem já testava | médio | a política "sem senha" só é aplicada a conta que ainda não tem senha utilizável |
| Alterar o comando quebrar `subir-localhost.sh`/migration/testes | alto | a nova flag é opt-in; sem ela o comportamento é byte-a-byte o de hoje; teste de regressão explícito |

## Dependências
- `review-triggers.md` dispara revisão obrigatória (autenticação + API/contrato).
- Nenhuma dependência externa. Não é preciso cadastrar secret novo no GitHub (essa era a
  alternativa, e foi descartada pelo solicitante).
- O `email_verificado=True` das contas de teste é o que permite o acesso ao `/admin` e à Central,
  coerente com o que `subir-localhost.sh` já faz.
- A entrega em HOMOLOG depende de a mudança chegar a `develop` e de haver PR `develop` → `main`
  (é esse PR que dispara o `deploy-homolog.yml`).
