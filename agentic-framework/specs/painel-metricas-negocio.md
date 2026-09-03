# Spec: Painel de Métricas de Negócio

## Contexto de negócio
BRD seção 21 (Métricas de Negócio) — usuários cadastrados/ativos, conversão Free→Premium, receita, churn, etc. Consumida pela operação (BRD §29) para decisão.

## Problema / oportunidade
Sem métricas agregadas, a operação não tem como avaliar se o produto está funcionando (BRD §32: "o negócio possui métricas suficientes para tomar decisões").

## Histórias de usuário
- Como administrador/operação, eu quero ver usuários ativos (diário/mensal), conversão Free→Premium, churn e receita recorrente num painel, sem precisar consultar o banco diretamente.

## Requisitos funcionais
1. Painel (Django admin customizado ou endpoint dedicado) com: usuários cadastrados, ativos diários/mensais (baseado em login/uso), conversão Free→Premium, receita recorrente, receita média por assinante, churn, taxa de renovação, número de empresas B2B, ticket médio B2B.
2. Métricas calculadas a partir dos dados já existentes (`identidade.User`, `assinatura.Subscription`/`HistoricoPagamento`, `b2b.Organizacao` quando existir) — não duplica dado, só agrega.
3. Filtro por período (últimos 7/30/90 dias).

## Requisitos não-funcionais
- Cálculo eficiente (agregação no banco via ORM, não trazer todos os registros para Python) — atenção a performance conforme a base cresce.

## Fora de escopo
- CAC (custo de aquisição) — depende de dado de marketing/canal que não existe no sistema hoje.
- Dashboards de terceiros (Google Analytics, Mixpanel) — métricas nesta execução vêm só do banco interno.

## Critérios de sucesso
- Um administrador consegue responder "quantos usuários converteram para Premium no último mês" sem consulta manual ao banco.

## Questões em aberto
- Nenhuma bloqueante — depende apenas dos módulos que já existem (`identidade`, `assinatura`) mais os que serão implementados nesta rodada (`b2b`).
