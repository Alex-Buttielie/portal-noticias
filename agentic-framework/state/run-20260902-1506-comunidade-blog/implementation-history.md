# Implementation History — 20260902-1506-comunidade-blog

## Iteração 1 — 2026-09-02 — orchestrator agindo como executor

App `comunidade/`: `Publicacao` (rascunho→enviado→publicado, checando `credenciamento.services.pode_publicar` na criação E no envio), `Comentario` (exatamente 1 alvo — publicação XOR notícia, constraint de banco; 1 nível de resposta), `Seguidor` (idempotente), 6 endpoints, admin, migration manual, 5 testes.

**Decisões:**
- `services.denunciar` importa `moderacao.services` de forma LOCAL (dentro da função, não no topo do módulo) porque o app `moderacao` ainda não existe nesta sessão — importar no topo quebraria o carregamento de `comunidade` isoladamente. Não é dependência circular real (moderacao vai usar ContentType genérico, não importa `comunidade`).
- Comentário em publicação OU notícia via 2 FKs opcionais + `CheckConstraint` (mais simples que ContentType genérico para só 2 alvos possíveis).
- Credenciamento é reconfirmado tanto na criação do rascunho quanto no envio para publicação — um autor suspenso entre os dois momentos não consegue publicar.

**Status:** 7/7 critérios implementados. Endpoint `denunciar/` funcional apenas depois que `moderacao` (próximo módulo) existir — até lá, chamá-lo resulta em `ModuleNotFoundError` capturado como erro 500 (aceitável temporariamente dentro da mesma sessão de trabalho, será resolvido no próximo run).

**Validação:** não realizada (mesma limitação de sessão).

## Iteração 2 — 2026-09-02 — orchestrator agindo como executor (correção durante construção do frontend)

Ao montar a tela de detalhe de publicação no frontend, descobri que faltava um endpoint de "buscar publicação por id" — só existia listagem (`GET /api/comunidade/publicacoes/`). Adicionado `PublicacaoDetailView` (`GET /api/comunidade/publicacoes/<id>/`): publicada é pública; rascunho/enviado só visível ao próprio autor (nunca vaza conteúdo não publicado). 2 testes novos cobrindo os dois casos.

**Arquivos:** `backend/comunidade/` (novo); `backend/config/settings.py`, `urls.py`.
