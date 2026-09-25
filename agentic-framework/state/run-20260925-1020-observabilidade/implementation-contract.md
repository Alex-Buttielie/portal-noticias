<!--
CONTRACT: implementation-contract
DONO: orchestrator (preenche) / executor, tester, reviewer (leem)
RUN: 20260925-1020-observabilidade
-->

# Implementation Contract — 20260925-1020-observabilidade

## Metadados
- **run_id:** 20260925-1020-observabilidade
- **Deriva de:** task-plan.md (20260925-1020-observabilidade)
- **Versão do contrato:** 2 — incrementada em 2026-09-25 após a revisão completa e o teste independente. A diferença está em "Decisões de escopo da v2" abaixo, e o incremento está declarado, não silencioso.
- **Executor:** subagentes delegados pelo orchestrator
- **Testador:** subagente independente
- **Revisor:** subagentes independentes, obrigatório pelos gatilhos do projeto

## Decisões de escopo da v2 (2026-09-25)
Cinco critérios não foram implementados como escritos. Registrados aqui, com dono, para que a Definition of Done não seja declarada cumprida sobre critérios que ninguém entregou:

| Critério | Situação | Decisão |
|---|---|---|
| **13** — estado durável da ingestão manual (`queued/running/succeeded/failed`, `task_id`, lock, timeout, retry, erro persistido) | não implementado | **Fora do escopo desta run.** A ingestão manual está sendo reimplementada pela run `20260924-2136-ingestao-noticias`, que já tem WIP aberto em `backend/catalogo_noticias/management/commands/agendar_ingestao.py` e `backend/catalogo_noticias/services/deduplicacao.py`. Implementar aqui criaria duas fontes de verdade para o mesmo job. A parte de observabilidade do critério — o canal de métricas de job entregue na remediação (`config/job_state.py`) — fica. |
| **15** — concorrência de ingestão rejeitada ou agrupada pelo lock | não implementado | **Fora do escopo desta run**, mesma razão e mesmo dono. |
| **17** — dependência externa registrando status, duração, resultado e erro sanitizado | parcial | **Dentro do escopo, com limite explícito.** Implementado como helper reutilizável e adotado nos pontos de chamada de menor risco; a adoção em todos os provedores externos é trabalho incremental e não bloqueia o fechamento. |
| **10** — stale de feed real por até 5 min, sinalizado | parcial | O sinal chega ao visitante apenas na janela de revalidação do ISR, porque a Home é página estática. O que é alcançável no App Router foi entregue no Bloco B1; o restante depende de o backend expor a idade do cache, o que exige `backend/feed/views.py` — WIP da run 2136. |
| **29** — standalone sob PM2 com `HOSTNAME`, `PORT`, `static` e `public` | implementado, não verificado | O Bloco C2 trocou o `npm start` por `node .next/standalone/server.js` com as invariantes explícitas. O que falta é execução real na VPS, não decisão de escopo. |

Nenhum desses cinco foi declarado entregue. A run só pode ser fechada com esta tabela ou com a lista de pendências do `test-report.md`, nunca sem uma das duas.

## O que deve ser construído
Uma malha de observabilidade operacional integrada ao portal, com telemetria técnica do frontend e backend, correlação ponta a ponta, health/readiness separados, métricas e logs centralizados no Grafana Cloud US, APM no Sentry, checks externos no Better Stack, alertas multi-canal, jobs Celery duráveis, retenção/privacidade, deploy atômico e hardening da operação. A implementação deve preservar a telemetria de negócio existente, mas eliminá-la como substituta de observabilidade técnica.

## Áreas/arquivos esperados
A lista não é fechada; mudanças adicionais devem ser justificadas no implementation-history.md.

- **Run e documentação:** `agentic-framework/state/run-20260925-1020-observabilidade/`, README, ARCHITECTURE, PROD_DECISOES, CI-CD, runbooks, privacidade/consentimento e documentação de operação.
- **Backend:** `backend/config/`, `backend/catalogo_noticias/`, `backend/feed/`, `backend/metricas/`, `backend/newsletter/`, `backend/assinatura/`, `backend/b2b/`, management commands, testes e migrations.
- **Frontend:** `frontend/next.config.js`, `frontend/package.json`, `frontend/app/error.tsx`, `frontend/app/global-error.tsx`, `frontend/lib/api.ts`, `frontend/lib/analytics.ts`, `frontend/lib/queries.ts`, `frontend/components/AnalyticsTracker.tsx`, `frontend/components/Reporters.tsx`, `frontend/lib/consent*`, `frontend/app/providers.tsx`, `frontend/app/api/[...path]/route.ts`, testes e configuração de build.
- **Infra:** `infra/nginx/`, `infra/systemd/`, `infra/observability/`, `docker-compose.yml`, Dockerfiles, PM2/standalone, Terraform e JSON de dashboards.
- **CI/CD:** `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`, `.github/workflows/rollback.yml`, checks de secrets, testes de integração e source maps.

## Interfaces afetadas
- Endpoints públicos e privados de health/readiness.
- Headers `X-Request-ID`, headers de release e headers de estado degradado.
- Contrato de erro do cliente `ApiError`.
- API de ingestão de analytics e validação de consentimento assinado.
- Modelos e migrations de eventos de analytics e de execução de ingestão.
- Tasks Celery, estados, locks, retry e resultados.
- Configuração de logs, Sentry, Grafana Cloud, Better Stack, Slack, Telegram e R2.
- PM2, systemd, Nginx, Docker e CI/CD.
- Política de retenção e textos de consentimento/privacidade.

## Critérios de aceite (técnicos, testáveis)

### Correlação e frontend
1. Dado um browser sem `X-Request-ID`, quando uma requisição de API é iniciada, então um ID UUID seguro é gerado, enviado no header e aceito pelo Django.
2. Dado um `X-Request-ID` válido, quando a resposta API retorna, então o mesmo ID normalizado aparece no header, no `ApiError` e pode ser exibido como código de suporte.
3. Dado um `X-Request-ID` inválido, longo ou com caracteres de controle, quando a requisição passa pelo middleware, então um UUID seguro é usado sem colisão.
4. Dado um erro de renderização ou exceção client-side, quando o App Router executa no navegador, então o erro é capturado pelo Sentry e uma tela de recuperação com `reset()` é disponível.
5. Dado um evento técnico sem consentimento, quando o tracker é executado, então nenhum payload é enviado ao Sentry, Web Vitals ou endpoint técnico.
6. Dado consentimento técnico aceito, quando ocorre um erro ou Web Vital, então o evento contém ambiente/release e não contém token, e-mail, IP completo, conteúdo ou URL sensível.

### Health e resiliência
7. Dado um processo web vivo com banco indisponível, quando `/livez` é consultado, então o processo responde conforme a semântica de liveness e `/readyz` retorna indisponibilidade sem expor `str(exc)`.
8. Dado PostgreSQL, migrations e dependências obrigatórias disponíveis, quando `/readyz` é consultado, então retorna `200` com resposta pública genérica.
9. Dado Redis ou worker Celery indisponível, quando a aplicação atende tráfego, então o estado degradado é registrado, metricado e alertado, sem esconder a falha; o endpoint privado detalha a causa.
10. Dado feed real indisponível, quando existe cache real válido por até 5 minutos, então a resposta usa conteúdo real, sinaliza degradação e não usa conteúdo fictício.
11. Dado feed real indisponível sem cache válido, quando a Home é solicitada, então retorna `503` e nunca conteúdo `MOCK`.
12. Dado qualquer página de produção que dependa de API, quando a API falhar, então não existe fallback fictício silencioso.

### Jobs e métricas
13. Dado um disparo manual de ingestão, quando a task é criada, então existe registro com `queued/running/succeeded/failed`, task ID, request ID, timestamps, duração, retries e erro final quando aplicável.
14. Dado worker/beat ativos, quando jobs são executados, então métricas de fila, atraso, retry, falha e duração são atualizadas e podem ser consultadas no Grafana.
15. Dado uma segunda tentativa de ingestão concorrente, quando o lock está adquirido, então a nova execução é rejeitada ou agrupada sem duplicar efeitos.
16. Dado worker/beat parados, quando a verificação de saúde privada é executada, então a condição aparece como falha/degradação e gera alerta.
17. Dado uma dependência externa, quando a chamada ocorre, então status, duração, resultado e erro sanitizado são registrados em métrica/log sem segredo.

### Logs, Sentry e Grafana
18. Dado qualquer log de aplicação em dev, homolog ou prod, quando emitido, então contém ambiente, serviço, release e request/task ID quando aplicável.
19. Dado uma exceção de backend, quando o Sentry está configurado, então o ambiente e release corretos são usados e PII padrão é desabilitada.
20. Dado uma exceção frontend, quando o build é executado no CI, então source maps são enviados e a release é identificada pelo SHA.
21. Dado logs JSON, quando ingestados pelo Grafana Alloy, então podem ser pesquisados por request ID, release, serviço e nível.
22. Dado uma regra de alerta, quando a condição é satisfeita, então o alerta é deduplicado, tem severidade, runbook e destino e-p definida.
23. Dado Better Stack, quando uma dependência externa falha, então o check e o alerta corresponding são acionados sem depender da própria VPS.
24. Dado uma retenção de 12 meses, quando o job de expurgo roda, então eventos brutos e agregados anteriores à janela são removidos de forma idempotente e o job é auditável.

### Consentimento e privacidade
25. Dado um payload de analytics com tipo desconhecido, campo excessivo ou token, quando o endpoint público recebe o payload, então ele é rejeitado, redigido ou descartado com sinal técnico.
26. Dado um token de consentimento ausente, inválido ou expirado, quando um evento de analytics é enviado, então o evento não é persistido como dado de produto autorizado.
27. Dado consentimento técnico recusado, quando ocorre uma exceção, quando o conteúdo é técnico, então nenhum envio externo ocorre.
28. Dado uma política de logs, quando uma requisição contém query string sensível, Authorization ou PII, então esses valores são omitidos ou mascarados antes da saída do log.

### Deploy, segurança e continuidade
29. Dado um build standalone, quando o PM2 inicia o frontend, então o processo sobe com a configuração correta de `HOSTNAME`, `PORT`, static e public.
30. Dado um deploy, quando a release nova falha no smoke, então o symlink ativo não muda e a release anterior permanece disponível para rollback.
31. Dado uma configuração com placeholder de secret, quando o bootstrap é executado, então a inicialização falha com mensagem segura e não sobe em modo inseguro.
32. Dado SSH, quando a chave dedicada é configurada, então a conexão funciona e a senha só é removida após teste de fallback/rollback documentado.
33. Dado TLS, quando o domínio é validado externamente, então HTTPS funciona, Renovação está configurada e há alerta de expiração.
34. Dado um backup diário, quando o dump é concluído, então ele é enviado ao Cloudflare R2, o exit code é zero somente após validação e há alerta de atraso.
35. Dado um restore mensal, quando o backup é restaurado, então banco, migrations, contagem de dados e aplicação são verificados em ambiente isolado.
36. Dado uma mudança de migration, quando é aplicada em produção, então backup verificado, homologação, smoke e rollback foram executados antes.
37. Dado documentação ausente, quando a equipe procura uma falha, então existe runbook com diagnóstico, consulta, recuperação, owner e escalonamento.

### Testes e observabilidade do pipeline
38. Dado uma alteração de backend, quando a CI roda, então testes unitários, integração, migration check e coverage gate passam.
39. Dado uma alteração de frontend, quando a CI roda, então typecheck, lint, build e testes de comportamento de erro/consentimento passam.
40. Dado uma alteração de observabilidade, quando a CI roda, então configuração de Nginx/systemd/Compose/Terraform é validada em modo de checagem.
41. Dado um alerta de teste, quando Better Stack, Grafana ou Sentry são acionados, então a entrega é confirmada nos três canais e o teste é encerrado/acknowledged.
42. Dado uma produção implantada, quando a validação de 48 horas termina, então não há incidente aberto, alerta não resolvido ou regressão de SLO.

## Não-objetivos
- Não implementar Kubernetes, multi-node, service mesh ou HA de datacenter.
- Não ativar session replay, recording de tela ou envio de PII.
- Não substituir o painel de business intelligence existente.
- Não alterar regras de assinatura, pagamento, preço ou moderação.
- Não criar um warehouse de analytics.
- Não usar conteúdo fictício como fallback de produção.
- Não remover o acesso operacional antigo antes de validar o novo caminho.
- Não aplicar configuração externa sem inventariar o ambiente real.

## Restrições técnicas
- **Performance:** instrumentação deve ter baixo overhead; sampling de traces em 10%; não fazer polling pesado no frontend; jobs e queries devem ser idempotentes.
- **Segurança/privacidade:** fail-closed para consentimento; redaction obrigatória; sem secrets em logs, fixtures, dashboards ou histórico; token de consentimento assinado e rotacionável.
- **Dependências permitidas:** `@sentry/nextjs`, `sentry-sdk` já existente, cliente/exporter Prometheus ou biblioteca equivalente, `python-json-logger` já suportado, Grafana Alloy e Terraform/provider necessários. Fixar versões, registrar licença e risco.
- **Estilo/convenções:** preservar padrões Django/Next/TypeScript existentes, scripts e runbooks do projeto; não modificar código não relacionado.
- **Deploy:** branch dedicada; sem deploy de produção antes de homologação, backup verificado e janela aprovada.
- **Privacidade legal:** textos finais precisam de validação humana; código não deve fingir aprovação jurídica.
- **Orçamento:** plano inicial free/low-cost, com aviso antes de ultrapassar aproximadamente R$300/mês.

## Definition of Done
- [ ] Todos os critérios de aceite implementados ou bloqueados explicitamente com evidência.
- [ ] Testes automatizados escritos e passando pelo tester independente.
- [ ] Revisão de código aprovada pelo reviewer independente.
- [ ] Findings de remediation resolvidos ou escalados.
- [ ] Documentação de arquitetura, operação, privacidade, dashboards, alertas e runbooks atualizada.
- [ ] Deploy em homologação e smoke aprovados.
- [ ] TLS, SSH, secrets, R2, backup e restore validados.
- [ ] Soak de 48 horas concluído sem incidente aberto.
- [ ] `implementation-history.md`, `documentation-update.md`, `report.md` e `HISTORY.md` atualizados.
