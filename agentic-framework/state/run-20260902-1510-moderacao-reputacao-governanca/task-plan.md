# Task Plan — 20260902-1510-moderacao-reputacao-governanca

Spec: `agentic-framework/specs/moderacao-reputacao-governanca.md`. Formato conciso (ver nota em runs anteriores desta leva).

## Objetivo
App `moderacao`: denúncia (ContentType genérico — aponta para `Comentario`/`Publicacao` de `comunidade` sem `comunidade` precisar ser importado), fila, ações de moderação (aviso/remoção/bloqueio temp/permanente), canal de recurso, modelo de reputação com log de eventos, e página de política editorial pública simples.

## Escopo
Dentro: `Denuncia` (genérica), `AcaoModeracao`, `RecursoModeracao`, `Reputacao`+`ReputacaoEventoLog`, `PaginaEditorial` (conteúdo estático simples). `comunidade.services.denunciar` (já escrito, import tardio) passa a funcionar de verdade a partir deste run.
Fora: detecção automática de abuso por IA, painel de analytics de moderação (fica em `painel-metricas-negocio.md`).

## Critérios de aceite (técnicos)
1. `denunciar(denunciante, motivo, comentario=X ou publicacao=Y)` cria `Denuncia` com `status=pendente`, referenciando o alvo via ContentType.
2. Fila (`Denuncia.objects.filter(status="pendente")`) ordenável/priorizável por reputação do denunciado (menor reputação primeiro, como sinal de prioridade — não único critério).
3. `resolver_denuncia` registra moderador, quando, e se procedente/improcedente — nunca decide sozinha (sempre um `moderador` humano passado explicitamente).
4. `aplicar_acao` registra tipo/motivo/quem aplicou; bloqueio temporário tem `ativo_ate`; qualquer ação gera automaticamente um evento de reputação negativo proporcional à severidade.
5. `criar_recurso` permite ao usuário moderado contestar — fica registrado, sem fluxo de auto-aprovação.
6. Reputação nunca é o ÚNICO critério de uma decisão de moderação — `aplicar_acao` sempre exige um `moderador` humano (não há caminho de auto-decisão só por reputação baixa).
7. `PaginaEditorial` tem ao menos 1 endpoint público de leitura por slug (ex.: `criterios-relevancia`, `politica-moderacao`).

## Suposições assumidas
- Fórmula de reputação: baseline 100 pontos; delta configurável por tipo de ação (aviso -5, remoção -15, bloqueio temporário -30, bloqueio permanente -100); nível calculado por faixa (< 0 = restrito; 0-50 = padrão; > 50 = confiável) — valores de referência, editáveis (constantes de módulo, não hardcoded em múltiplos lugares), não a decisão final de produto (spec já marca isso como questão em aberto).
