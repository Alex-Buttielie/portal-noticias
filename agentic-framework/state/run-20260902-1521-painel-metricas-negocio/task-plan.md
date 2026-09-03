# Task Plan — 20260902-1521-painel-metricas-negocio

Spec: `agentic-framework/specs/painel-metricas-negocio.md`. Último módulo desta leva — formato conciso.

## Objetivo
App `metricas`: agregação (via ORM, sem trazer registros para Python) de usuários cadastrados/ativos, conversão Free→Premium, receita recorrente, churn, número de organizações B2B — endpoint único, só admin.

## Critérios de aceite (técnicos)
1. `GET /api/metricas/painel/?dias=30` retorna: usuários cadastrados (total e no período), assinaturas ativas, conversão Free→Premium (assinaturas ativas / usuários cadastrados), receita recorrente (soma de `HistoricoPagamento.status=aprovado` no período), churn (canceladas+expiradas no período / ativas no início do período), organizações B2B ativas.
2. Só `papel=admin` acessa o painel (outros usuários recebem 403).
3. Todas as métricas calculadas por agregação no banco (`Count`/`Sum`/`Avg` do ORM), nunca por iterar querysets inteiros em Python.
