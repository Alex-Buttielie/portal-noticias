# PLANO DE ARREGAR TUDO — 2026-10-08

Derivado da síntese de 2026-10-08. Cada fase valida antes de integrar; **nada
junta tudo e só depois mede**. `develop` é alvo móvel — houve 6 dias em que a
outra sessão não publicou nada, o que muda o custo de re-merge para perto de
zero neste momento.

## Decisões do solicitante (2026-10-08)

| # | Decisão |
|---|---|
| 1 | Migration `0004` do double opt-in **AUTORIZADA** para aplicação |
| 2 | DNS: apontar **só** `portal-noticias.com` e `www` para `108.174.147.50`. DEV e HOMOLOG por **IP + Host header** |
| 3 | **Fechar `8080` e `8443`** (Caddy do `plataforma-educacao`) |
| 4 | **Rotacionar a senha do root** e desligar `passwordauthentication`/`permitrootlogin` **depois** que um deploy por chave passar no CI |
| 5 | Alcance: o que bloqueia PROD · publicar `develop`→`main` · levantar DEV para navegação · **os 6 itens de P2/observabilidade**. **Revisão jurídica da LGPD fora** (registrada como pendência) |

---

## FASE 1 — Destravar o repositório (risco datado)

**1.1 Fix do backup.** O script corrigido está **não commitado na VPS** (`M` em
PROD e HOMOLOG) e ausente de `develop`. O `deploy.yml` faz `git reset --hard`
(linhas 289, 291, 294, 304, 307), então **qualquer deploy reverte o backup para
a versão quebrada**. O fix entra por arquivo, não por merge do branch: o branch
`backup-pm2-6-quebras` diverge em 10 arquivos que são só a base antiga dele.

Critério: sha de `infra/backup/pg_backup_pm2.sh` em `develop` = `93edff7e…`,
igual ao que roda na VPS. Depois disso, `git reset --hard` na VPS traz a
versão **certa** de volta.

**1.2 Defeito do revisor.** `settings.py:671` tem 3 backends,
`email_entrega.py:82` tem 5 — faltam `filebased` e `""`, e não existe o teste
que prende as duas listas. O par pior possível: `verificar_canal_email()`
recusa e o boot cala.

**Não** é merge do branch `revisor-final`: ele branchou antes do picsum, então
mergear faria o `develop` perder `frontend/lib/placeholder.ts` e
`frontend/testes/placeholder.test.mjs`. Reaplicar por cima do `develop` atual.

---

## FASE 2 — Migration `0004` (autorizada)

Dump antes em DEV e HOMOLOG → aplicar → verificar colunas e job → publicar o
double opt-in em `develop` → suíte + gate.

Medido: **0 inscrições nos três ambientes**, então a consequência de desligar o
envio de quem já estava inscrito não atinge ninguém. PROD aplica `0003` + `0004`
juntas, dentro do deploy.

Ordem obrigatória: **aplicar a migration ANTES de publicar o código**, porque
o código novo morre com `column token_confirmacao does not exist`.

---

## FASE 3 — `develop` → `main`

`main` recebe `develop` com suíte e gate verdes. `main` **não** dispara deploy
de PROD: `deploy-prod.yml` só dispara em tags `v*`.

---

## FASE 4 — Fechar `8080`/`8443` na VPS

Backup das regras do UFW e do `DOCKER-USER` antes. Verificar depois: portal
responde em 80/443, `plataforma-educacao` **pode cair** — o solicitante foi
avisado e autorizou mesmo assim. Se o outro sistema reagir, há como reverter.

---

## FASE 5 — DEV para o solicitante navegar

DEV já roda `develop`. Levantar e entregar acesso. Funciona por IP + Host
header (`dev.portal-noticias.com.br`), sem depender de DNS.

---

## FASE 6 — SSH

6.1 Rotacionar a senha do root (a atual está no histórico do chat).
6.2 Provador um deploy por chave no CI. Enquanto isso, **senha fica ligada**.
6.3 Só então desligar `passwordauthentication` e `permitrootlogin`, com
**rollback automático em 10 min**: se o CI não conseguir conectar, o servidor
volta sozinho ao estado anterior e oCoordinate avisa.

Sequência invertida quebra o pipeline. Ordem correta: chave primeiro, senha
depois.

---

## FASE 7 — P2 / observabilidade (6 itens)

**`observability-20260925-1020` NÃO É MERGEÁVEL.** Ele tentaria apagar
`scripts/release/verificar-proveniencia.sh` (851 linhas, sha256 congelado em
`32ed34b3…b57b59`) e `scripts/verificar-gate-usuarios-teste.sh` (673 linhas):
400 arquivos, +42.204/−66.999. Branchou de uma base muito antiga.

Método: cherry-pick de commits soltos, nunca merge. Cada item P2 entra medido
e sozinho.

---

## Depende exclusivamente do solicitante

- **DNS**: `portal-noticias.com` e `www` → `108.174.147.50`. Sem isso não há
  TLS, e sem TLS PROD não é PROD.
- **`RESEND_API_KEY`**: cadastro em **503 medido** nos três ambientes.
- **`VPS_SSH_KEY`**: `cat /root/.ssh/deploy_ci` na VPS → secret do GitHub.
  Pré-requisito da Fase 6.3.
- **Credencial do R2**: hoje o backup só existe nesta VPS, e o próprio script
  avisa isso no log a cada execução.
- **Assinatura do R-1** → libera a tag `v*` → PROD.

## Registrado sem solução, por decisão

- Revisão jurídica da LGPD (política de privacidade é rascunho).
- PROD em `v1.0.29` (`290a7b7`), 8 dias, sem nenhum dos 11 itens da Onda 1:
  o oráculo de enumeração e a mentira de entrega continuam no ar até a tag.