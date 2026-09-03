<!--
CONTRACT: implementation-history
DONO: executor (cria e adiciona entradas) / tester, remediator, historian (adicionam entradas)
QUANDO É CRIADO: junto com a primeira ação do executor sobre o implementation-contract.md.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/implementation-history.md
NATUREZA: append-only durante a execução — cada entrada é uma iteração, nunca se edita uma entrada anterior.
-->

# Implementation History — 20260902-1426-assinatura-premium

## Iteração 1 — 2026-09-02 — orchestrator agindo como executor (ferramentas de execução/subagente ainda indisponíveis)

**Quem implementou e por quê:** mesma situação dos 3 runs anteriores nesta sessão. Este é o módulo de MAIOR risco (envolve estado financeiro, mesmo que via gateway placeholder) implementado sem nenhuma validação por execução — o usuário confirmou explicitamente que queria prosseguir mesmo assim.

**O que foi feito:** app Django `assinatura/` completo — `Plan`, `Subscription` (7 estados exatos do BRD §9), `HistoricoPagamento`, `AssinaturaMudancaEstadoLog` (auditoria), `ConfiguracaoAssinatura` (singleton), `PaymentGatewayProvider` (interface) + `ManualPaymentGatewayProvider` (placeholder), `services.py` (máquina de estados completa), task periódica Celery, admin, e 5 endpoints de autoatendimento.

### Decisões técnicas (dentro da liberdade deixada pelo contrato)

1. **`Subscription.STATUS_COM_ACESSO_PREMIUM = {teste, ativa, cancelada}`** — a decisão mais consequente desta execução: `cancelada` MANTÉM acesso Premium (até `vencimento`). Já registrada como suposição no `task-plan.md`, mas repetida aqui por ser central: sem isso, cancelar seria punitivo (cortaria acesso já pago), o que contradiz "sem práticas de retenção abusivas" (BRD §8) — mas por não estar explícito na spec, é uma INTERPRETAÇÃO, sinalizada para o `reviewer`/produto confirmarem.
2. **`_sincronizar_papel_usuario` é o ÚNICO lugar do sistema que escreve `User.papel`** — nunca rebaixa `papel=admin`. `gating/` (run anterior) só LÊ esse campo; a suposição que aquele módulo fez ("assinatura vai manter isso atualizado") está agora cumprida.
3. **Congelamento de preço/duração na assinatura** (`preco_cobrado`/`duracao_dias_no_momento`) — mudar `Plan.preco` depois de um usuário já ter assinado não altera o valor da assinatura em andamento (só afeta novas assinaturas). Implementado copiando os valores do `Plan` no momento de `assinar_plano`, nunca lendo `plan.preco` depois disso para cálculos de cobrança.
4. **Confirmação de pagamento síncrona** (`assinar_plano` já chama `processar_confirmacao_pagamento`/`processar_pagamento_recusado` imediatamente se o gateway responder `aprovado`/`recusado` na hora — caso do `ManualPaymentGatewayProvider`) — um gateway real com confirmação assíncrona (webhook) chamaria essas mesmas funções a partir de uma view de webhook separada, NÃO implementada nesta execução (não-objetivo explícito, já que não há provedor real escolhido).
5. **Task periódica processa 3 categorias por execução** (inadimplente→expirada; cancelada→encerrada; ativa vencida→renovar ou expirar) — todas usando a MESMA função `_transicionar`, garantindo que nenhuma transição escape da auditoria/sincronização de papel.
6. **Migration `0001_initial.py` escrita à mão** (5 modelos, 3 FKs) — MAIOR risco técnico desta iteração, mesma ressalva do run `gating-free-premium`, mas amplificada pelo número de campos/relações. Segui rigorosamente o formato de referência (`catalogo_noticias`/`gating`), incluindo `on_delete=PROTECT` para `Subscription.plan` (não `SET_NULL`/`CASCADE` — perder o vínculo com o plano de uma assinatura já paga seria inaceitável).

### Status dos critérios de aceite técnicos (implementation-contract.md)

| # | Critério | Status | Evidência |
|---|---|---|---|
| 1 | Plan ativo/inativo na listagem pública | ✅ Implementado | `test_plano_ativo_aparece_na_listagem_publica` |
| 2-3 | Assinar cria pagamento_pendente, gateway aprova → ativa + papel=premium | ✅ Implementado | `test_assinar_com_gateway_aprovando_ativa_na_hora_e_promove_usuario` |
| 4 | Pagamento recusado → inadimplente, grace period, Premium NÃO derrubado na hora | ✅ Implementado | `test_assinar_com_gateway_recusando_nao_promove_usuario_mas_inicia_grace_period`, `test_pagamento_recusado_nao_derruba_acesso_premium_ja_ativo` |
| 5 | Grace period expirado → expirada, papel=free | ✅ Implementado | `test_grace_period_expirado_derruba_para_free` |
| 6 | Grace period não vencido → nada muda | ✅ Implementado | `test_grace_period_ainda_nao_vencido_nao_muda_nada` |
| 7 | Cancelar → cancelada, mantém Premium até vencimento | ✅ Implementado | `test_cancelar_mantem_acesso_premium_ate_vencimento` |
| 8 | Cancelada + vencimento passado → encerrada, papel=free | ✅ Implementado | `test_cancelada_com_vencimento_passado_e_encerrada_e_derruba_para_free` |
| 9 | Toda transição gera log de auditoria | ✅ Implementado | `test_toda_transicao_gera_log_de_auditoria` |
| 10 | Histórico de pagamentos isolado por usuário | ✅ Implementado | `test_endpoint_historico_pagamentos_isola_por_usuario` |
| 11 | Cancelar/expirar nunca apaga o usuário | ✅ Implementado | `test_cancelar_ou_expirar_nunca_apaga_o_usuario` |
| 12 | Não permite segunda assinatura concorrente | ✅ Implementado | `test_nao_permite_segunda_assinatura_concorrente` |

**Resumo:** 12 de 12 critérios implementados, 14 testes de sanidade escritos (incluindo 3 via `APIClient`).

### Lacunas de cobertura conhecidas (sinalizadas para o `tester`)

1. Nenhum teste exercita a task Celery (`tasks.processar_vencimentos`) diretamente como task — só a função de serviço que ela chama (`processar_vencimentos_e_grace_periods`). Mesma limitação estrutural já registrada para `catalogo_noticias` (sem broker Redis real no ambiente).
2. Renovação automática (`renovacao_automatica=True`, vencimento passado, gateway aprova de novo) não tem teste de sanidade dedicado — só o caminho de expiração por falta de renovação automática está coberto indiretamente pelos testes de grace period. Recomendo ao `tester` adicionar um teste explícito desse caminho.
3. Nenhum teste do fluxo `POST /api/assinatura/cancelar/` com sucesso via `APIClient` (só o caso de erro 401/403 sem autenticação) — a lógica de cancelamento em si é testada diretamente via `services.cancelar_assinatura`, não ponta a ponta pela view.

### Validação por execução: **NÃO REALIZADA nesta iteração**

Mesma limitação dos 3 runs anteriores. **Este é o módulo onde essa lacuna é mais grave** — envolve uma máquina de estados financeira com várias transições encadeadas (`assinar → confirmar/recusar → grace period → expirar/renovar`, `cancelar → encerrar`), e uma migration manual de 5 modelos. Recomendo fortemente que este `run_id` seja o PRIMEIRO a ser validado por execução assim que as ferramentas voltarem, antes de qualquer um dos outros 3 runs desta sessão, dado o risco financeiro (mesmo que hoje só simulado via `ManualPaymentGatewayProvider`).

**Ação necessária:**
```
cd C:\alex\brd_portal_noticias\backend && DJANGO_DB_ENGINE=sqlite3 .venv/Scripts/python.exe manage.py makemigrations --check --dry-run
cd C:\alex\brd_portal_noticias\backend && DJANGO_DB_ENGINE=sqlite3 .venv/Scripts/python.exe -m pytest -q
```

**Arquivos tocados:**
- `backend/assinatura/__init__.py`, `apps.py`, `models.py`, `services.py`, `admin.py`, `serializers.py`, `views.py`, `urls.py`, `tasks.py` (novos)
- `backend/assinatura/providers/__init__.py`, `payment.py` (novos)
- `backend/assinatura/migrations/__init__.py`, `0001_initial.py` (novos)
- `backend/assinatura/tests/__init__.py`, `test_sanity.py` (novos)
- `backend/config/settings.py` (modificado — `INSTALLED_APPS += "assinatura"`, `CELERY_BEAT_SCHEDULE` + nova entrada)
- `backend/config/urls.py` (modificado — `path("api/assinatura/", include("assinatura.urls"))`)
