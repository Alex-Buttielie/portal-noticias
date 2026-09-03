# Task Plan — 20260902-1519-b2b-corporativo

Spec: `agentic-framework/specs/b2b-corporativo.md`. Formato conciso.

## Objetivo
App `b2b`: `Organizacao`, membros com permissão (admin da organização vs. membro comum), critérios de monitoramento (empresa/concorrente/setor/palavra-chave) sobre `catalogo_noticias.NewsItem`, painel/resumo executivo, isolamento estrito entre organizações.

## Critérios de aceite (técnicos)
1. `Organizacao` criada com plano corporativo (basic/pro/enterprise) e lista de membros.
2. Admin da organização adiciona/remove membros; membro comum não consegue adicionar outros membros (permissão diferenciada).
3. Critério de monitoramento (`CriterioMonitoramento`) casa com `NewsItem` publicáveis via busca textual (`icontains` em título/resumo/categoria, conforme o tipo).
4. Resumo executivo agrega contagem de itens por critério, só da própria organização.
5. **Isolamento estrito**: usuário de uma organização nunca consegue ler critérios/resumo de outra, mesmo tentando por id direto (checagem de pertencimento em toda view).
6. Reaproveita `assinatura.Plan`/`Subscription` para cobrança do plano corporativo — não duplica modelo de cobrança (uma `Organizacao` pode ter uma `Subscription` associada, plano marcado como corporativo via convenção de nome, já que `Plan` não tem uma dimensão B2C/B2B explícita nesta execução — ver suposição abaixo).

## Suposições assumidas
- `Plan` (de `assinatura/`) não ganhou um campo "é B2B" nesta execução — a distinção fica pelo nome do plano (ex.: "B2B Basic") por enquanto, para não reabrir o módulo `assinatura` com uma migração de schema adicional só para isso. Registrado como possível refinamento futuro (spec já marca "planos corporativos configuráveis" como requisito, atendido de forma simplificada aqui).
- Um usuário pertence a NO MÁXIMO uma organização (`MembroOrganizacao.user` é `OneToOneField`) — suficiente para o critério de isolamento e simples de implementar; múltiplas organizações por usuário fica fora de escopo.
