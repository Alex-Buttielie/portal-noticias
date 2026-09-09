# Implementation history — pages executor (run-20260909-1200-frontend-rebuild)

## Escopo
`frontend/app/page.tsx` + ajustes visuais mínimos em `frontend/app/*/page.tsx`
( + 2 client components co-localizados: `autor/[id]/PerfilAutorConteudo.tsx`,
`privacidade/preferencias-cookies/PreferenciasCookiesConteudo.tsx`).
Nenhuma lógica de dados, hook, chamada `api` ou rota foi alterada — só JSX
estrutural/classes do design system. `globals.css`, `components/`, `lib/` e
`backend/` intocados. Nenhuma dependência adicionada.

## Achado principal
`app/page.tsx` já continha o layout moderno do contrato (hero "Seu rio",
grade + sidebar sticky com `MaisLidas`/`newsletter-box`/salvos, seção "Para você",
"Últimas" em `lista-compacta` + `HorizontalNewsCard`, `BlocoEditoria` por editoria,
teaser comunidade; `useFeed`, paginação por sentinela, newsletter, bookmarks e
filtros intactos). `layout.tsx` já fornece `main.container`, skip-link e tema sem
flash. O trabalho foi, portanto, correção de classes inexistentes + normalização
dos cabeçalhos/seções internas para o design system.

## Arquivos alterados
- `frontend/app/page.tsx` — removida classe inexistente `card-legado` (2×);
  wrappers viraram `<article>` sem classe (`NewsCard` já tem `cartao-noticia`).
- `frontend/app/comunidade/page.tsx` — header `secao-bloco` + eyebrow/título;
  destaques e lista em `grade-noticias`; h2 inline → `secao-cabecalho`/`secao-titulo`.
- `frontend/app/comunidade/[id]/page.tsx` — `article.secao-bloco`, h1 `secao-titulo`,
  comentários com `secao-cabecalho`.
- `frontend/app/planos/page.tsx` — header `secao-bloco`; planos em `grade-cartoes`.
- `frontend/app/radar/page.tsx` — header `secao-bloco`; salvas em `secao-bloco`.
- `frontend/app/minha-conta/page.tsx` — header `secao-bloco`; Assinatura/Pagamentos/
  Newsletter em `section.secao-bloco` com `secao-cabecalho`.
- `frontend/app/empresa/page.tsx` — header `secao-bloco`; Critérios/Membros em
  `section.secao-bloco`.
- `frontend/app/admin/page.tsx` (+ `fila`, `moderacao`, `planos`, `robos`,
  `usuarios`, `assinaturas`, `metricas`) — topo `secao-bloco` + `secao-cabecalho` +
  `secao-titulo`; `admin/planos`: `&` → `&amp;` (render idêntico).
- `frontend/app/autor/[id]/PerfilAutorConteudo.tsx` — header `secao-bloco` + eyebrow;
  publicações em `grade-noticias`.
- `frontend/app/paginas/[slug]/page.tsx` — `pagina-editorial` (inexistente) →
  `article.secao-bloco` + eyebrow + `secao-titulo`.
- `frontend/app/privacidade/politica/page.tsx` — topo `secao-bloco` + eyebrow/título.
- `frontend/app/privacidade/preferencias-cookies/PreferenciasCookiesConteudo.tsx` —
  topo `secao-bloco` + eyebrow/título.
- `frontend/app/lista-de-espera/page.tsx` — topo `secao-bloco` + eyebrow/título.
- `frontend/app/jornalista/status/page.tsx` — bloco perfil: h2 inline → `cartao-titulo`,
  removida margem inline.
- Sem alteração (já conformes: `.formulario` + labels visíveis via `CampoTexto`):
  `login`, `cadastro`, `recuperar-senha`, `redefinir-senha/*`, `verificar-email/*`,
  `onboarding`, `jornalista/solicitar`, `comunidade/nova`, `noticia/item/[id]`,
  `noticia/cluster/[id]` (delegam ao `DetalheNoticia`, dono: components executor).

## Classes em falta
Nenhuma (ver `css-needs-pages.md`).

## Resultado tsc
`npx tsc --noEmit -p tsconfig.json` (em `frontend/`) → exit 0, sem erros.
(Nota: `npx tsc` na raiz do repo não resolve o compilador; rodar a partir de `frontend/`.)

## Pendências
- Validação visual em viewports 360/768/1024/1440 e checagem de `aria-expanded` do
  menu mobile ficam com tester/reviewer (fora do meu escopo).
- `DetalheNoticia`/`BlocoEditoria`/`MaisLidas` e demais `components/*` são do
  components executor — páginas `noticia/*` herdam o visual deles.
