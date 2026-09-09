# CSS needs — pages executor (run-20260909-1200-frontend-rebuild)

Nenhuma classe CSS nova necessária.

Classes legadas eliminadas no escopo de páginas (não precisam ser criadas no design system):
- `card-legado` — removida de `frontend/app/page.tsx` (2 ocorrências; `NewsCard` já renderiza
  `cartao-noticia` próprio, o wrapper virou `<article>` sem classe).
- `pagina-editorial` — removida de `frontend/app/paginas/[slug]/page.tsx`, trocada por
  `secao-bloco` + `secao-eyebrow` + `secao-titulo` (existentes).

Todas as demais classes usadas pelas páginas já existem em `globals.css`
(verificado via regex sobre o CSS: `secao-bloco`, `secao-cabecalho`, `secao-eyebrow`,
`secao-titulo`, `grade-noticias`, `grade-cartoes`, `cartao`, `cartao-meta`, `cartao-titulo`,
`formulario`, `portal-layout`, `sidebar`, `newsletter-box`, `lista-compacta`, `seu-rio`,
`controles-feed`, `texto-suave`, `mensagem-erro/sucesso`, `link-nulo`, etc.).
