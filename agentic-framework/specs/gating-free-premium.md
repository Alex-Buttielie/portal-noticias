# Spec: Controle de Acesso e Limites Free x Premium

## Contexto de negócio
BRD seção 7 (Estratégia Free x Premium) — tabela completa de recursos e seus limites por plano. Depende de `assinatura-premium.md` para saber o status/plano do usuário e de `ARCHITECTURE.md` seção 3 (`FeatureLimit`).

## Problema / oportunidade
Sem um mecanismo central e parametrizável de gating, cada feature reimplementaria sua própria lógica de "isso é Free ou Premium", tornando impossível ajustar limites sem alterar código — o que o BRD proíbe explicitamente ("Os limites exatos deverão ser parametrizáveis").

## Histórias de usuário
- Como administrador, eu quero ajustar o limite de um recurso (ex: quantidade de alertas personalizados no Free) sem pedir deploy, para poder experimentar com o produto.
- Como usuário Free, eu quero saber quando estou batendo em um limite do meu plano, para entender o valor de fazer upgrade.
- Como usuário Premium, eu quero ter certeza de que não vejo publicidade e tenho acesso completo aos recursos personalizáveis.

## Requisitos funcionais
1. Tabela `FeatureLimit` (chave, valor, plano) editável via painel admin, cobrindo pelo menos: publicidade (on/off), personalização avançada, alertas personalizados, resumo personalizado, newsletter personalizada, histórico avançado, distribuição personalizada (lista completa: BRD §7).
2. Camada central de verificação de acesso (`has_feature(user, feature_key)` ou equivalente) usada por qualquer módulo que precise checar limite — nenhum módulo deve hardcodar "if premium".
3. Quando um usuário Free atinge um limite, o sistema deve comunicar isso de forma clara (não falhar silenciosamente).
4. Alteração de um `FeatureLimit` pelo admin deve ser auditada (quem, quando, valor anterior/novo — BRD §17).

## Requisitos não-funcionais
- Qualquer novo recurso premium introduzido depois deve poder ser registrado como `FeatureLimit` sem alteração estrutural deste módulo.
- Mudança de limite deve refletir para usuários ativos sem exigir logout/relogin.

## Fora de escopo
- Definição do valor exato de cada limite no lançamento (fica para decisão de produto/experimentação, registrada como dado, não como requisito funcional fixo aqui).
- Cupons e promoções (BRD §6 menciona como possibilidade futura).

## Critérios de sucesso
- Um recurso pode ter seu limite alterado pelo admin e o efeito é visível para o usuário sem deploy.
- Nenhuma verificação de plano está hardcoded fora da camada central de gating.

## Questões em aberto
- Valores iniciais de referência para cada `FeatureLimit` no lançamento (a serem definidos com produto, não bloqueiam a implementação técnica, mas bloqueiam o "conteúdo" default).
