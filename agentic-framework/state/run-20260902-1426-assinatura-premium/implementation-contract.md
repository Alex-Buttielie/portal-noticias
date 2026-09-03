# Implementation Contract — 20260902-1426-assinatura-premium

## Metadados
- **run_id:** 20260902-1426-assinatura-premium
- **Deriva de:** task-plan.md (20260902-1426-assinatura-premium)
- **Versão do contrato:** 1

## O que deve ser construído
App Django `assinatura` com o domínio completo de assinatura Premium: `Plan`, `Subscription` (7 estados exatos do BRD §9), `HistoricoPagamento`, `AssinaturaMudancaEstadoLog`, `ConfiguracaoAssinatura` (singleton), `PaymentGatewayProvider` (interface) + `ManualPaymentGatewayProvider` (placeholder), serviço de domínio, task periódica de vencimento/grace period, admin, e endpoints de autoatendimento (listar planos, assinar, cancelar, ver status, ver histórico).

## Áreas/arquivos esperados
- `backend/assinatura/`
  - `models.py` — `Plan`, `Subscription`, `HistoricoPagamento`, `AssinaturaMudancaEstadoLog`, `ConfiguracaoAssinatura`
  - `providers/payment.py` — `PaymentGatewayProvider` (ABC), `ResultadoCobranca`, `ManualPaymentGatewayProvider`
  - `services.py` — `assinar_plano`, `processar_confirmacao_pagamento`, `processar_pagamento_recusado`, `cancelar_assinatura`, `_sincronizar_papel_usuario`, `_registrar_mudanca_estado`
  - `tasks.py` — task periódica (`processar_vencimentos_e_grace_periods`)
  - `admin.py`, `serializers.py`, `views.py`, `urls.py`
  - `migrations/0001_initial.py` (escrita à mão, seguindo o padrão já usado em `gating`/`catalogo_noticias`)
  - `tests/`
- `backend/config/settings.py` — `INSTALLED_APPS`; `CELERY_BEAT_SCHEDULE` (adicionar a nova task); `backend/config/urls.py`

## Interfaces afetadas
- `Plan(nome, preco: Decimal, duracao_dias: int, ativo: bool)`.
- `Subscription(user FK, plan FK PROTECT, status [teste|ativa|pagamento_pendente|inadimplente|cancelada|expirada|encerrada], preco_cobrado: Decimal, duracao_dias_no_momento: int, inicio, vencimento, renovacao_automatica: bool, grace_period_termina_em, gateway_referencia)`.
- `HistoricoPagamento(subscription FK, valor, status [aprovado|recusado|pendente|estornado], referencia_gateway, criado_em)`.
- `AssinaturaMudancaEstadoLog(subscription FK, estado_anterior, estado_novo, motivo, criado_em)`.
- `ConfiguracaoAssinatura(grace_period_dias: int default 7, periodo_teste_dias: int default 0, periodo_teste_ativo: bool default False)` — singleton (`pk=1`).
- `PaymentGatewayProvider.criar_cobranca(subscription, valor) -> ResultadoCobranca`, `.consultar_status(referencia) -> str`, `.cancelar(referencia) -> None`.
- Endpoints: `GET /api/assinatura/planos/` (públicos, só ativos), `POST /api/assinatura/assinar/` (autenticado), `POST /api/assinatura/cancelar/` (autenticado, cancela a própria), `GET /api/assinatura/minha/` (autenticado, status atual), `GET /api/assinatura/historico-pagamentos/` (autenticado, só do próprio usuário).

## Critérios de aceite (técnicos, testáveis)
1. Dado um `Plan(ativo=True)`, quando `GET /api/assinatura/planos/`, então aparece na lista; dado `ativo=False`, então NÃO aparece.
2. Dado um usuário autenticado sem assinatura, quando `POST /api/assinatura/assinar/` com um plano válido, então uma `Subscription` é criada com `status=pagamento_pendente`, e `services.assinar_plano` chama `PaymentGatewayProvider.criar_cobranca`.
3. Dado que `PaymentGatewayProvider.criar_cobranca` retorna status `aprovado` (caso do `ManualPaymentGatewayProvider`), então a `Subscription` transiciona automaticamente para `ativa`, `inicio`/`vencimento` são preenchidos (`vencimento = inicio + duracao_dias`), e `User.papel` vira `premium` — tudo sem intervenção do admin.
4. Dado `processar_pagamento_recusado(subscription)`, então `status` vira `inadimplente`, `grace_period_termina_em = now + ConfiguracaoAssinatura.grace_period_dias`, e `User.papel` PERMANECE `premium` (não derruba na hora — critério de sucesso da spec).
5. Dado uma `Subscription` `inadimplente` com `grace_period_termina_em` no passado, quando a task periódica roda, então `status` vira `expirada` e `User.papel` vira `free`.
6. Dado uma `Subscription` `inadimplente` com `grace_period_termina_em` no futuro, quando a task periódica roda, então NADA muda (ainda dentro do grace period).
7. Dado um usuário com `Subscription` `ativa`, quando `POST /api/assinatura/cancelar/`, então `status` vira `cancelada`, `renovacao_automatica=False`, mas `User.papel` PERMANECE `premium` até `vencimento`.
8. Dado uma `Subscription` `cancelada` com `vencimento` no passado, quando a task periódica roda, então `status` vira `encerrada` e `User.papel` vira `free`.
9. Toda transição de estado (itens 3-8 acima) cria um `AssinaturaMudancaEstadoLog` com estado_anterior/novo e motivo — nenhuma transição é silenciosa.
10. `GET /api/assinatura/historico-pagamentos/` só retorna pagamentos do usuário autenticado (nunca de outro usuário) — 401/403 para requisição anônima.
11. Cancelar ou expirar uma assinatura nunca deleta o `User` nem seus dados de onboarding/identidade — só afeta `Subscription.status`/`User.papel`.
12. `POST /api/assinatura/assinar/` para um usuário que já tem uma `Subscription` `ativa`/`teste`/`pagamento_pendente` retorna erro claro (400), não cria uma segunda assinatura concorrente.

## Não-objetivos
- Não integrar um gateway de pagamento real.
- Não implementar cupons/promoções, planos B2B.
- Não enviar e-mail/notificação real de aviso — só registrar o evento (log/auditoria já cobre "rastreável").
- Não construir frontend/checkout.
- Não ativar período de teste por padrão.

## Restrições técnicas
- **Performance:** N/A para meta definida.
- **Segurança/privacidade:** `HistoricoPagamento`/`Subscription` de um usuário nunca acessível por outro usuário via API (isolamento por `request.user`, nunca por id na URL sem checagem de dono). Preço/duração do plano cobrado fica CONGELADO em `Subscription.preco_cobrado`/`duracao_dias_no_momento` no momento da assinatura — mudar o `Plan` depois não retroage sobre assinaturas já criadas.
- **Dependências permitidas:** nenhuma nova biblioteca externa esperada (Celery/Redis já configurados desde `catalogo_noticias`).
- **Estilo/convenções:** mesmas já registradas nos runs anteriores; `PaymentGatewayProvider` segue o mesmo padrão de interface abstrata + provider concreto já usado para `SummarizationProvider`/`NewsSourceProvider`.

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Testes escritos e passando (tester) — **incluindo validação por execução real** (módulo financeiro — não deve ir para produção sem isso, ver task-plan.md)
- [ ] Revisão de código — **obrigatória** por `review-triggers.md` (cobrança/pagamento/assinatura; migração de schema de banco)
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente
