<!--
ESCOPO DE ENCERRAMENTO
DONO: orchestrator
CONTINUAÇÃO DE: 20260925-1020-observabilidade (fechada como blocked)
-->

# Escopo de encerramento — 20260925-1020-observabilidade

A implementação está completa e verificada; o que falta está nas cinco ondas abaixo. Nenhum item delas é "melhoria": ou desbloqueia o ambiente, ou valida no ambiente, ou depende de decisão humana.

## Decisões tomadas em 2026-09-28

| Decisão | Escolha |
|---|---|
| **Barra de conclusão** | **Produção no ar e monitorando de verdade**: deploy atômico testado, Celery sob systemd, os 19 alertas disparando nos três canais, backup em R2 com restore verificado, TLS e soak de 48 h. Não basta CI verde |
| **Acesso à VPS** | **O solicitante libera acesso por chave SSH dedicada.** Inventário, deploy, systemd, TLS, backup e restore executados por aqui, com tudo registrado. Nunca senha pelo chat |
| **Malha canônica** | **A desta run.** As outras cópias do frontend de observabilidade são arquivadas; `on2-obs` só é lida para trazer o que falta |
| **Destino dos alertas** | **Slack e Telegram agora, e-mail como reserva**, com responsável principal e suplente nomeados |
| **Domínio** | **`portal-noticias.com`**, o canônico do programa. Muda os três callers de deploy e os exemplos de ambiente (era a divergência R-2, agora decidida) |
| **Ordem** | Onda 0 e Onda 1 em paralelo; a 2 espera as duas |
| **Provisionamento das contas** | O solicitante cria, o orchestrator guia passo a passo. Nenhum segredo pelo chat |
| **Revisão da rodada 2** | Auditoria independente quando a delegação voltar |
| **Teto de custo** | Mantido em ~R$300/mês; o desenho usa apenas camada gratuita, e qualquer mudança de plano passa por aviso antes |

## Achado que mudou o plano: sete streams paralelos

Há **sete streams de trabalho** no repositório, todas nascidas de `7715dae`, com 59 a 65 commits e 215 a 243 arquivos cada, e 21% a 26% de sobreposição com este run. `frontend/scripts/verificar-conteudo-ficticio.mjs`, criado por esta run, **existe nas outras seis**. A stream `on2-obs` tem uma malha de observabilidade inteira competindo com a verificada aqui.

Detalhes, comparação do MAJOR-1 e ordem de integração recomendada: `reconciliacao-streams.md`. **Nenhum deploy deve acontecer antes da integração**: release atômica só se prova num repositório que se sabe qual é.

---

## Onda 0 — desbloqueio de repositório

Responsável: orchestrator. Não precisa de ambiente nem de credencial.

| # | Item | Estado |
|---|---|---|
| 0.1 | Isolar o diff órfão da run `20260925-1836` (4 workflows + identidade + gate) em branch dedicada | **feito** — `run-20260925-1836-usuarios-teste` (`1581b50`), worktree próprio, worktree principal limpo |
| 0.2 | `OBSERVABILITY_JOB_STATE_FILE` nas duas pontas do deploy | **feito** — produtor no tuning do worker, consumidor no `backend/.env`, com aviso-e-preserva, comparação das duas pontas no log, e 22 verificações funcionais novas no portão |
| 0.3 | Script `start` do frontend: hoje é `next start`, que o Next rejeita com `output: "standalone"` | **investigado e descartado de propósito** — `npm start` é o escape hatch de produção: `web_runtime: npm` no `deploy.yml` e o `rollback.yml` rodam esse comando para voltar ao caminho in-place. Apontá-lo para o runner standalone transformaria o escape hatch em "standalone sem release", que é pior que o caminho antigo, porque o `next build` reescreveria a árvore sob o processo que a serve. O aviso é esperado e o caminho padrão não o produz. Explicação registrada em `infra/standalone/run-standalone.sh` |
| 0.4 | Domínio `.com` nos três callers, no `rollback.yml` e na documentação de operador | **feito** — e o portão ganhou checagem de coerência que relaciona os hosts, porque a divergência original ficou dias por ninguém conferir |
| 0.5 | Destino da branch `lote-p0-1-proveniencia` (merge, PR ou descarte) | pendente (decisão do solicitante) |
| 0.6 | Auditoria independente de `1a15647` e `e3fe0f0` quando a delegação voltar | pendente |
| 0.7 | `runbook_url` de `exemplo.invalid` para o endereço interno | depende de 1.6 |
| 0.8 | Verificação do critério 4 (error boundary) em browser real | pendente — não há browser conectado nesta sessão |
| 0.9 | Reconciliação das sete streams antes de qualquer deploy | pendente (decisão do solicitante) |

## Onda 1 — provisionamento

Responsável: solicitante, com o orchestrator guiando. Sequência importa porque cada conta alimenta a seguinte.

| # | Item | O que obter |
|---|---|---|
| 1.1 | **Sentry** (org e projeto, plano gratuito) | DSN do backend, DSN público do frontend, token de upload de source map (`SENTRY_AUTH_TOKEN`), slug da org e do projeto |
| 1.2 | **Grafana Cloud** (região US, stack gratuita) | URL de push do Loki, endpoint de remote-write do Mimir, token com permissão de escrita, ID da org, e onde os painéis JSON serão importados |
| 1.3 | **Better Stack** | token de API e token de healthcheck (para os 7 checks de `infra/observability/better-stack/checks.json`) |
| 1.4 | **Cloudflare R2** | nome do bucket, credencial de leitura/escrita, e a regra de lifecycle (JSON já versionado em `infra/observability/r2/lifecycle.json`) |
| 1.5 | **Canais de alerta** | webhook do Slack, bot + chat id do Telegram, e contato de e-mail; **e o responsável principal e o suplente** |
| 1.6 | **Endereço interno do runbook** | o que vai no `runbook_url` das 19 regras |
| 1.7 | **Decisão de domínio** | `.com` × `.com.br` — hoje divergente nos workflows, e o TLS depende disso |

Nenhum destes valores entra no Git. Todos vão para o ambiente da VPS e para os secrets do repositório, e a verificação de que o canal funciona é feita disparando um alerta de teste (item 3.1).

## Onda 2 — carga no ambiente

Responsável: orchestrator, com acesso à VPS e janela coordenada. **Depende das Ondas 0 e 1 inteiras.**

| # | Item | Como se prova que deu certo |
|---|---|---|
| 2.1 | Primeiro deploy da release atômica | release nova em `frontend/releases/`, symlink `current` alternado após smoke, `previous` preservado |
| 2.2 | Rollback real | deploying uma release com falha proposital e confirmando que `current` volta **e** o deploy falha |
| 2.3 | Celery sob systemd | `celery beat` vivo, heartbeat aparecendo, e `celery_beat` saindo de `not_configured` em `/health-detail` |
| 2.4 | Canal de job | arquivo do job state sendo gravado pelo worker e a série `portal_job_task_idle_seconds` aparecendo no scrape |
| 2.5 | TLS | HTTPS respondendo, renovação configurada, alerta de expiração instalado |
| 2.6 | SSH por chave | chave dedicada funcionando; **a senha só é removida depois** do teste de fallback documentado |
| 2.7 | Backup em R2 | dump diário com verificação, marcador `remoto=confirmado` no estado, watchdog sem alarme falso |
| 2.8 | Restore mensal | restauração em ambiente isolado, com contagem de dados e aplicação no ar |

## Onda 3 — verificação em produção

Depende da Onda 2.

| # | Item |
|---|---|
| 3.1 | Teste de entrega nos três canais: e-mail, Slack e Telegram, com o alerta disparado de verdade e depois encerrado |
| 3.2 | Carregar as 19 regras no Mimir e confirmar que cada uma **dispara** — alerta que nunca disparou é hipótese, não verificação |
| 3.3 | Confirmar que os 4 painéis abrem com dado, um por vez |
| 3.4 | Soak de 48 horas, sem incidente aberto |
| 3.5 | Ajustar as linhas de burn-rate com o comportamento real, se os valores iniciais generatesem alerta ruidoso |
| 3.6 | Assinatura do risco R-1 e do go/no-go (run de go-live) |

## Onda 4 — jurídico e produto

Paralela a partir da Onda 1; não depende de ambiente.

| # | Item |
|---|---|
| 4.1 | Validação dos textos de privacidade e do banner pelo responsável — o texto está escrito, **sem aprovação jurídica** |
| 4.2 | Confirmar a base legal da telemetria técnica e o contrato de tratamento com o Sentry (transferência internacional) |
| 4.3 | Confirmar o teto de custo com os planos efetivamente escolhidos |
| 4.4 | Definir quem é o responsável pela operação fora do expediente — sem isso, os 19 alertas não têm destinatário |

## O que não entra em nenhuma onda

- Reposicionar p95 no painel de ingestão: o canal durável publica soma e contagem, não buckets. Um p95 sobre o que não existe seria inventar número.
- Remover o rate limit do compose: o balde único é limitação conhecida de topologia de desenvolvimento, documentada com a correção honesta. A correção "óbvia" reabriria o bypass corrigido.
- Migrar o `next start` para standalone: **não entra**. `npm start` é o escape hatch de produção (`web_runtime: npm` e `rollback.yml`), e trocá-lo por "standalone sem release" seria pior que o caminho que ele substitui. O aviso do Next é o preço de manter um escape hatch que funciona.

## Critério de fim

A run só passa de `blocked` para `closed` quando: as 19 regras tiverem disparado de verdade, o rollback tiver sido exercitado, o restore tiver trazido o banco de volta, o soak de 48 horas tiver terminado sem incidente, e os textos de privacidade tiverem aprovação humana registrada. **Enquanto um desses não acontecer, o estado é `blocked` — e dizer "entregue" seria o mesmo falso verde que a run existe para eliminar.**
