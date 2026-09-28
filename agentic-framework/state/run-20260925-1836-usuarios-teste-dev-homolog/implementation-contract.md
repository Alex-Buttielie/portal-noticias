<!--
CONTRACT: implementation-contract
DONO: orchestrator (preenche) / executor, tester, reviewer (leem)
QUANDO É CRIADO: logo após o task-plan.md ser aceito.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/implementation-contract.md
-->

# Implementation Contract — 20260925-1836-usuarios-teste-dev-homolog

## Metadados
- **run_id:** 20260925-1836-usuarios-teste-dev-homolog
- **Deriva de:** task-plan.md (20260925-1836-usuarios-teste-dev-homolog)
- **Versão do contrato:** 1

## O que deve ser construído

Um gate de provisionamento de **usuários de teste no deploy**, ativado apenas em DEV e HOMOLOG, que
roda o mesmo comando de carga que o `subir-localhost.sh` já usa
(`backend/identidade/management/commands/criar_usuario_carga.py`) — **um usuário por perfil**
(`free`, `premium`, `admin`).

O que muda em relação ao localhost é **quem entra e como a senha nasce**. Em localhost a senha é
conhecida e impressa no terminal (`admin@local.test` / `LocalAdmin123`). Em DEV/HOMOLOG não pode
ser assim: a senha não existe em lugar nenhum. A conta é criada com **senha inutilizável**
(`set_unusable_password()`), o primeiro acesso é feito pelo fluxo de recuperação de senha que o
produto já tem (`/recuperar-senha` → `/redefinir-senha` → `POST /api/auth/recuperar-senha/` →
`POST /api/auth/redefinir-senha/`), e o **primeiro login já pede a troca de senha**, porque
`deve_trocar_senha=True` faz o `frontend/app/login/page.tsx:18` redirecionar para
`/trocar-senha` e `POST /api/auth/trocar-senha/` limpar a flag.

Isso é coerente por construção com o que já existe:

- `RedefinirSenhaView` (`backend/identidade/views.py:204-205`) grava **só** `password`, então a flag
  `deve_trocar_senha=True` continua de pé depois da recuperação — a troca no primeiro login é
  solicitada, como pedido.
- `User.has_usable_password()` é `False` para essas contas, então nem `check_password` nem o
  `LoginView` abrem porta por senha: **não existe** caminho de acesso sem passar por uma senha que a
  própria pessoa definiu.
- `deve_trocar_senha=True` é a convenção do projeto para "primeiro acesso" (também vale para todo
  cadastro via `/api/auth/cadastro/` — `backend/identidade/serializers.py:73`), então o
  comportamento novo não introduz um estado inédita.

## Áreas/arquivos esperados
Não é lista fechada, mas tudo abaixo está dentro do escopo.

- `backend/identidade/management/commands/criar_usuario_carga.py`
  Nova flag opt-in para criar a conta **sem senha utilizável**. Compatibilidade retroativa
  obrigatória: sem a flag, o comando se comporta exatamente como hoje.
- `backend/identidade/tests/` (arquivo novo, ou adição a `test_primeiro_acesso.py`)
  Testes do comportamento novo + teste de regressão do caminho antigo.
- `.github/workflows/deploy.yml`
  Novo input booleano de gate (default `false`) + bloco de criação das contas por perfil, com
  resumo no log. Nada de segredo.
- `.github/workflows/deploy-dev.yml`, `.github/workflows/deploy-homolog.yml`
  Ligam o gate. `deploy-prod.yml` **não** liga (e isso é o que mantém PROD fail-closed).
- `infra/DEPLOY.md` e/ou `CI-CD.md`
  Documentar o gate, os e-mails gerados e o caminho de entrada. (Fase do `documenter`.)

## Interfaces afetadas

- **Novo argumento de CLI** em `criar_usuario_carga`. É interface humana/operacional, consumida por
  `subir-localhost.sh`, `subir-localhost.bat` e `backend/identidade/migrations/0004_ensure_admin_buttielle.py`
  (que só menciona o comando no docstring) — nenhum desses passa a usar a flag nova.
- **Novo input** `workflow_call` em `deploy.yml` — contrato entre `deploy.yml` e os callers
  `deploy-{dev,homolog,prod}.yml`/`rollback.yml`. Default `false`: quem não declara, não cria conta.
- **Nenhuma mudança em API HTTP**, migration, model ou serializer. Nenhum contrato de dado muda.

## Critérios de aceite (técnicos, testáveis)

1. Dado `criar_usuario_carga --email X --sem-senha --papel free`, quando o comando roda, então
   `User.objects.get(email=X)` tem `has_usable_password() is False`, `deve_trocar_senha is True`,
   `is_active is True` e `email_verificado is True`.
2. Dado `criar_usuario_carga --email X --sem-senha`, quando o comando roda duas vezes (2º deploy),
   então a **senha definida entre os dois deploys não é destruída**: se a conta já tem senha
   utilizável no momento da 2ª execução, ela é preservada. (Idempotência do redeploy.)
3. Dado `criar_usuario_carga --email X --sem-senha --password Y` (senha **e** flag), quando o
   comando roda, então ele falha com `CommandError` explicando a ambiguidade — nunca escolhe um
   dos dois silenciosamente.
4. Dado `criar_usuario_carga --email X --password Y` (sem a flag nova), quando o comando roda, então
   o resultado é idêntico ao de hoje: senha utilizável, `deve_trocar_senha is True`, e
   `Token` do usuário anterior removido. (Regressão: `subir-localhost.sh`, `.bat` e
   `test_primeiro_acesso.py::test_comando_carga_cria_admin_com_troca_obrigatoria` não podem quebrar.)
5. Dado o gate ligado no `deploy.yml` (`usuarios_teste: true`) e `pm_suffix` de DEV ou HOMOLOG,
   quando o job `deploy`Provisiona, então o script invoca o comando **3 vezes**, uma por perfil
   (`free`, `premium`, `admin`), com e-mail no formato
   `teste-<papel>@<pm_suffix>.portal-noticias.com.br`.
6. Dado o gate **não** ligado (default, e o caso de PROD e de `rollback.yml`), quando o job `deploy`
   roda, então o bloco de criação de contas **não executa** e nenhuma conta é criada. Verificável por
   inspeção do `deploy.yml` + `deploy-prod.yml`/`rollback.yml` sem a flag.
7. Dado uma conta de teste criada sem senha utilizável, quando alguém tenta `POST /api/auth/login/`
   com qualquer senha, então a resposta é 401 e **nenhum** `Token` é emitido. (Nenhum acesso sem a
   senha que a pessoa definiu.)
8. Dado uma conta de teste cujo primeiro acesso foi feito por recuperação de senha, quando a pessoa
   faz login, então a resposta traz `deve_trocar_senha: true`; e depois de
   `POST /api/auth/trocar-senha/`, `deve_trocar_senha` é `false` e o login passa a ser normal.
   (Fluxo completo: recuperação → login → troca → uso.)
9. Dado que a criação da conta falha (ex.: `manage.py` sai != 0), quando o job `deploy` roda, então
   o job **não** falha: imprime aviso explícito e o deploy do código termina normalmente. (Mesma
   política já adotada para o Celery no mesmo arquivo.)
10. Dado qualquer valor de `usuarios_teste` diferente de `true`/`false`, quando o job `deploy` roda,
    então ele aborta com mensagem de erro antes de qualquer operação — fail-closed, como já é feito
    com `tls_enabled`, `web_runtime`, `celery_systemd` e `git_mode`.
11. Dado o gate ligado, quando o script roda, então **nenhuma senha** é impressa, passada por argv
    ou gravada em arquivo: a senha da conta de teste não existe no processo. Verificável por
    inspeção: o comando é chamado **sem** `--password` e sem `PROD_SEED_PASSWORD`.
12. Regression: `backend/identidade/tests/test_primeiro_acesso.py` continua passando sem alteração de
    expectativa, e a suíte completa do backend roda verde.

## Não-objetivos
- **Não** criar usuário de teste em PROD, nem com flag, nem por variável de ambiente, nem por
  padrão. Se alguém ligar a flag em PROD, isso é erro de revisão, não comportamento a suportar.
- **Não** alterar o frontend (as telas `/recuperar-senha`, `/redefinir-senha`, `/trocar-senha` e o
  redirecionamento do login já existem e já fazem o fluxo).
- **Não** alterar `RedefinirSenhaView`, `TrocarSenhaView`, `LoginView` ou a semântica de
  `deve_trocar_senha`.
- **Não** mexer no `subir-localhost.sh`/`.bat` (o admin local com senha conhecida continua igual).
- **Não** criar migration nem alterar model.
- **Não** cadastrar secret novo no GitHub — a alternativa era secret de senha, e foi descartada.
- **Não** imprimir a senha de ninguém no log do run.
- **Não** tocar nas alterações já não commitadas no working tree que pertencem a outras runs
  (`.github/workflows/deploy.yml` já tem uma mudança pendente de outra run — o bloco do job state
  do D2; ela deve ser preservada, não revertida).
- **Não** mexer em `scripts/observability/validar-infra.sh` nem nos alerts: não há mudança de
  infra monitorada.

## Restrições técnicas
- **Performance:** 3 chamadas a `manage.py` (uma por perfil). Cada uma paga o boot do Django
  (~1-2 s). Aceitável em DEV/HOMOLOG, que é onde o gate liga; irrelevante em PROD. Se ficar
  incômodo, registrar como follow-up — não otimizar nesta execução.
- **Segurança/privacidade:** é o ponto central desta execução.
  - Nenhuma senha em log, argv, `.env` ou repositório (critério 11).
  - As contas nascem `email_verificado=True` (necessário para `/admin` e Central, e é o que o
    `subir-localhost.sh` já faz) mas **não** são superuser por padrão: só o perfil `admin` leva
    `--superuser`, para não haver trêsstaff accounts.
  - Os e-mails ficam sob o domínio do ambiente, com prefixo `teste-`, para que uma conta de
    homologação nunca seja confundida com conta real em dado de teste.
  - O gate é **fail-closed**: default `false`, validação de valor, e PROD/rollback sem a flag.
- **Dependências permitidas:** nenhuma nova. Só stdlib do shell + o comando Django já existente.
- **Estilo/convenções:** comentários em pt-BR explicando **por quê** (é a convenção observada em
  `deploy.yml`); o script do job roda com `set -e`; comandos que podem falhar de forma prevista
  precisam do tratamento explícito, não do `set -e` acidental.

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Testes escritos e passando (tester)
- [ ] Revisão de código aprovada — **obrigatória**: `review-triggers.md` (autenticação/autorização
      + contrato entre workflows) [reviewer]
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente
