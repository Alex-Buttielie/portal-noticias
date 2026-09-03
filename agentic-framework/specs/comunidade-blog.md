# Spec: Comunidade e Blog

## Contexto de negócio
BRD seção 12 (Comunidade e Blog) e seção 14 (Poderes do Autor Credenciado). Depende de `credenciamento-jornalistas.md` (só autor credenciado publica opinião/análise) e de `moderacao-reputacao-governanca.md` (denúncias, moderação, reputação).

## Problema / oportunidade
O BRD define a comunidade como área editorial própria, permitindo discussão sobre fatos/legislação/eleições/economia — sem isso, jornalistas credenciados não têm onde publicar e leitores não têm onde comentar/discutir.

## Histórias de usuário
- Como jornalista credenciado, eu quero criar rascunhos e publicar análises/opiniões associadas a uma notícia/acontecimento, para compartilhar minha perspectiva profissional.
- Como leitor, eu quero comentar em publicações e no feed, seguir autores, e denunciar conteúdo problemático.
- Como leitor, eu quero distinguir claramente notícia de opinião/análise, para não confundir fato com interpretação.

## Requisitos funcionais
1. Publicações de autores credenciados: rascunho → enviado para publicação → publicado, com opinião/análise SEMPRE identificada como tal (nunca misturada visualmente com notícia).
2. Associação de publicação a uma notícia/acontecimento existente (`NewsItem`/`NewsCluster` de `catalogo_noticias`), quando aplicável.
3. Categorias e tags nas publicações.
4. Comentários e respostas (thread simples, 1 nível de resposta é suficiente para o MVP deste módulo).
5. Seguir autores (usuário Free/Premium segue um autor credenciado).
6. Perfis públicos de autor (bio, publicações, selo de credenciado).
7. Denúncia de comentário/publicação (encaminha para fila de moderação — `moderacao-reputacao-governanca.md`).
8. Destaques editoriais (lista de publicações marcadas como destaque pelo admin/editorial).
9. Autor pode editar sua publicação dentro das regras (antes/depois de publicada, com histórico simples de que foi editada).

## Requisitos não-funcionais
- Separação visual e de dado clara entre `NewsItem` (notícia curada) e `Publicacao` (opinião/análise de autor) — nunca no mesmo modelo/tabela.
- Comentários passam pelas mesmas regras de `moderacao-reputacao-governanca.md` (rate limit, denúncia).

## Fora de escopo
- Algoritmo de recomendação de quem seguir.
- Notificação em tempo real de novos comentários (polling/refresh manual é suficiente no MVP).
- Monetização de publicações de autor (ex: assinatura de autor específico).

## Critérios de sucesso
- Um jornalista credenciado consegue publicar uma análise associada a uma notícia em poucos passos.
- Um leitor nunca confunde uma opinião com uma notícia factual ao navegar pelo feed/comunidade.
- A comunidade consegue discutir temas com segurança e respeito (métrica: taxa de denúncias procedentes tratadas).

## Questões em aberto
- Limite de comentários/publicações por dia para usuário Free vs Premium — depende de `gating-free-premium.md` (distribuição/personalização já cobre parte disso, mas comentário/publicação é um recurso novo, precisa de uma chave de `FeatureLimit` própria).
