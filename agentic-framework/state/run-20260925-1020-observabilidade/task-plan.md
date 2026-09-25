<!--
CONTRACT: task-plan
DONO: orchestrator
RUN: 20260925-1020-observabilidade
-->

# Task Plan — 20260925-1020-observabilidade

## Metadados
- **run_id:** 20260925-1020-observabilidade
- **Data de abertura:** 2026-09-25
- **Solicitado por:** solicitante, após auditoria e aprovação explícita do escopo
- **Spec de origem:** N/A — auditoria estática de observabilidade realizada antes desta execução

## Objetivo
Implementar observabilidade operacional de ponta a ponta no portal, eliminando falsos verdes e permitindo detectar, correlacionar, diagnosticar e recuperar falhas do frontend, backend, infraestrutura, filas, jobs e dependências externas.

## Escopo

### Dentro do escopo
- Ativar Sentry no Django e integrar Sentry no Next.js com source maps, release e ambiente.
- Implementar error boundaries e códigos de suporte no frontend.
- Propagar `X-Request-ID` do browser até Django, proxy, logs, Sentry e `ApiError`.
- Implementar logs JSON estruturados com ambiente, serviço, release, request ID e task ID quando aplicável.
- Implementar `/livez`, `/readyz` e health detalhado privado.
- Remover fallbacks fictícios de produção; permitir stale real por até 5 minutos com sinalização.
- Implementar degradação explícita e observável de Redis/Celery.
- Migrar ingestão manual de thread daemon para Celery durável, com estado, lock, retry e timeout.
- Adicionar métricas técnicas de HTTP, DB, cache, Celery, filas, jobs, dependências e frontend.
- Integrar Grafana Alloy, Grafana Cloud US (Loki, Mimir/Prometheus, dashboards e alertas).
- Criar dashboards técnicos versionados em JSON e IaC com Terraform quando suportado.
- Configurar Better Stack com checks externos completos.
- Configurar alertas em e-mail, Slack e Telegram, com burn-rate e escalonamento.
- Implementar consentimento técnico separado e consentimento assinado para analytics.
- Restringir payloads de analytics, aplicar redaction e reter dados por 12 meses.
- Implementar rotação e retenção de logs por 30 dias.
- Tornar worker e beat supervisionados por systemd.
- Corrigir o runtime standalone do Next.js no PM2.
- Implementar deploy em releases atômicas com smoke, rollback e versão anterior preservada.
- Auditar e endurecer SSH, secrets, TLS, backup externo e restore.
- Criar backup diário em Cloudflare R2, alerta após 26 horas e restore mensal verificado.
- Atualizar documentação de arquitetura, deploy, operação, privacidade, runbooks e SLOs.
- Adicionar testes unitários, integração, browser/CI e cenários de falha.
- Validar homologação, produção e soak assíncrono de 48 horas.

### Fora do escopo (explicitamente)
- Kubernetes, service mesh ou arquitetura multi-node/HA.
- Session replay, captura de tela ou coleta de PII.
- Reescrita completa do business intelligence existente.
- Mudanças de preço, assinatura, pagamento ou regras de moderação.
- Substituição do banco, do broker ou do modelo de domínio sem necessidade.
- Migração para warehouse ou sistema de analytics dedicado.
- Coleta de conteúdo de usuário, tokens, e-mails, IP completo ou query strings sensíveis.
- Execução de carga destrutiva em produção.

## Suposições assumidas
- A topologia de produção será auditada antes de qualquer alteração; o workflow PM2 versionado será a referência, sem presumir que a VPS já possua worker/beat ou TLS.
- O estado de GitHub, VPS, DNS, certificados e provedores será inventariado antes de modificar qualquer coisa.
- Sentry, Grafana Cloud, Better Stack, Slack e Telegram serão provisionados com contas criadas durante a execução; nenhuma credencial será enviada pelo chat.
- O solicitante e um suplente fornecerão contatos e papéis por canal seguro antes da ativação dos alertas.
- As URLs reais de dev, homolog e prod serão descobertas por inventário ou informadas no acesso seguro.
- A organização pode exigir aprovação humana para textos legais finais; a implementação prepara controles e textos, mas não inventa aprovação jurídica.
- A VPS é de baixo volume; a stack será dimensionada para free/low-cost tiers, respeitando o limite de aproximadamente R$300/mês.
- O estado do Terraform será remoto, privado e criptografado; se o provedor não oferecer integração segura, a parte não aplicável será documentada como follow-up, sem reduzir a cobertura de observabilidade.

## Restrições
- Preservar as alterações não relacionadas já existentes no working tree; não resetar, sobrescrever ou commitar trabalho de outras runs sem rastreabilidade.
- Work em branch dedicada `observability-20260925-1020`.
- Não inserir segredos, tokens ou senhas no repositório, nos logs ou no histórico do Git.
- Telemetria de produto e telemetria técnica devem ser separadas.
- Consentimento explícito é fail-closed; ausência de consentimento não pode gerar envio.
- Dependências de produção devem ser fixadas, revisadas quanto a licença e manutenção, e testadas em CI.
- Não bloquear o portal por indisponibilidade de um cache otimizável sem antes registrar estado degradado e alertar.
- Não usar conteúdo fictício em produção.
- Toda mudança de schema deve passar por backup verificado, homologação e rollback documentado.
- Produção só pode ser alterada em janela coordenada e após smoke de homologação.
- A documentação deve ser atualizada junto com o comportamento entregue.

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | código, configuração, migrations, testes iniciais e implementation-history.md |
| 2 | tester | implementation-contract.md | suítes executadas, evidências e veredito passed/failed/blocked |
| 3 | reviewer | diff e artefatos da implementação | code-review-contract.md com severidade e veredito |
| 4 | remediator | code-review-contract.md | correções, reteste e nova revisão quando necessário |
| 5 | documenter | implementation-history.md e contratos | documentação atualizada e documentation-update.md |
| 6 | historian | todos os artefatos acima | report.md, histórico completo e entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. Uma falha de API não pode deixar a Home com notícias fictícias e HTTP 200 sem sinal.
2. Um erro de frontend deve ser capturado, identificado por release e REQUEST ID, e oferecer recuperação ao usuário.
3. Uma requisição de browser deve poder ser rastreada do browser até o backend e uma resposta de erro deve oferecer um código de suporte.
4. Operadores devem conseguir distinguir liveness, readiness e degradação de Redis/Celery.
5. Uma ingestão manual ou periódica deve ter estado durable, duração, erro, retry e histórico consultável.
6. Operadores devem conseguir detectar filas acumuladas, jobs falhos, freshness de ingestão e falhas de dependências.
7. Logs de aplicação e infraestrutura devem ser pesquisáveis por ambiente, release, serviço e request/task ID.
8. Alertas críticos devem chegar por e-mail, Slack e Telegram, com teste de entrega e escalonamento.
9. Dev, homolog e prod devem ter ambientes e releases separados na telemetria.
10. O sistema deve ter SLOs documentados, dashboards técnicos e burn-rate alerts.
11. Falhas de consentimento ou dados sensíveis não podem ser armazenadas ou enviadas.
12. Eventos de produto devem ser expurgados após 12 meses, inclusive agregados.
13. Um deploy com falha de aplicação não deve promover a release de forma silenciosa.
14. TLS, SSH por chave, secrets fail-closed e backup externo R2 devem estar operacionais.
15. Um restore de backup deve ser demonstrado e repetível mensalmente.
16. O frontend standalone deve iniciar corretamente no PM2 e o deploy deve ser atômico e reversível.
17. A documentação deve permitir que uma pessoa sem contexto audite, diagnostique e recupere o sistema.
18. A produção deve passar por smoke, alertas de teste e soak de 48 horas sem incidente aberto.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Contas externas e MFA não estarem disponíveis | alto | Preparar IaC e checklist antes do deploy; separar progresso de código de provisionamento externo |
| Alterações não relacionadas no working tree | alto | Branch dedicada, inspeção de diff e proibição de reset/overwrite |
| Migração de dados de analytics/ingestão | alto | Backup, migration check, homologação, job de expurgo idempotente e rollback |
| Sentry/Grafana receberem PII | alto | Allowlist, before_send, redaction, testes com payload sensível e revisão obrigatória |
| Alertas ruidosos causarem fadiga | médio | SLOs iniciais, severidade, agrupamento, burn-rate e tuning após soak |
| TLS/SSH/backup exigirem acesso que ainda não existe | alto | Auditar primeiro, não remover caminho antigo antes de validar o novo |
| Standalone/PM2 exigir mudança de assets | médio | Build limpo, smoke de runtime e teste de release em homologação |
| Ingestão longa causar sobreposição | alto | Lock, timeout, estado, métricas de duração e freshness |
| Coleta remover dados além do necessário | alto | Consentimento técnico separado, retenção documentada e agregação controlada |

## Dependências
- Acesso seguro à VPS e ao GitHub para inventário e implantação.
- Contas Sentry, Grafana Cloud, Better Stack, Slack, Telegram e Cloudflare R2.
- MFA e contato do responsável principal e suplente.
- URLs reais de dev, homolog e produção.
- Janela coordenada de produção.
- Validação dos textos legais e do banner de consentimento.
- Capacidade de executar a validação de restore e o soak de 48 horas.
- Limite de custo aprovado para recursos pagos.
