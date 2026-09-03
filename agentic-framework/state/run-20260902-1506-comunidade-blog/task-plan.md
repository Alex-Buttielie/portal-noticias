# Task Plan — 20260902-1506-comunidade-blog

- **Solicitado por:** usuário — continuação da leva "finalizar todo o BRD".
- **Spec:** `agentic-framework/specs/comunidade-blog.md`. Formato conciso (ver nota em `run-20260902-1503-credenciamento-jornalistas/task-plan.md`).

## Objetivo
App `comunidade`: publicações de autores credenciados (rascunho → publicado), comentários (1 nível de resposta), seguir autores, perfis públicos, destaques editoriais. Denúncia fica no endpoint, mas a fila/ação de moderação em si é do próximo módulo (`moderacao-reputacao-governanca`) — endpoint aqui já cria o registro via `moderacao.services` (import tardio, dentro da view, para não gerar dependência circular entre apps).

## Escopo
Dentro: `Publicacao`, `Comentario` (pode ser em publicação OU em `NewsItem`/`NewsCluster` do feed), `Seguidor`, endpoints de CRUD de publicação (autor), comentar/responder, seguir/deixar de seguir, perfil público de autor.
Fora: algoritmo de recomendação, notificação em tempo real, monetização por autor, frontend.

## Suposições assumidas
- `Publicacao.status` segue exatamente rascunho → enviado → publicado (spec, requisito 1) — sem fluxo de aprovação editorial adicional nesta execução (qualquer jornalista credenciado pode publicar diretamente ao enviar; um fluxo de aprovação editorial humana antes de publicar fica como extensão futura, não travado pela spec).
- Comentário genérico via dois FKs opcionais (`publicacao` xor `news_item`) — mais simples que ContentType genérico para este caso concreto (só 2 tipos possíveis de alvo).

## Critérios de aceite (técnicos)
1. Só usuário com `credenciamento.services.pode_publicar(user)=True` consegue criar/enviar publicação.
2. `Publicacao` sempre carrega um `tipo` (opinião/análise) explícito no payload de leitura — nunca omitido/ambíguo.
3. Comentar exige apenas usuário autenticado (não precisa ser jornalista); resposta a um comentário existente é aceita (1 nível — resposta a uma resposta é recusada com erro claro).
4. Seguir/deixar de seguir um autor é idempotente (seguir 2x não duplica).
5. Perfil público de autor lista suas publicações publicadas + selo de credenciado (via `credenciamento`).
6. Destaque editorial: endpoint/admin para marcar `destaque=True`, listagem de destaques.
7. Denunciar comentário/publicação cria um registro consultável (mesmo que a fila de moderação completa só chegue no próximo módulo).

## Riscos
Mesma limitação de execução da sessão. Acoplamento com `credenciamento` (pode_publicar) e `catalogo_noticias` (NewsItem/NewsCluster para associar publicação/comentário a notícia) e `moderacao` (denúncia, criada em módulo seguinte).
