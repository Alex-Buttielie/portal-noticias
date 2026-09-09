# Implementation History — 20260909-1200-frontend-rebuild (consolidação final)

> Consolidação coerente escrita pelo `historian` em 2026-09-09 a partir dos apêndices por
> agente (`implementation-history-shell/components/pages/responsive.md`), `test-report.md` e
> `code-review-contract.md`. Detalhes por arquivo estão nos apêndices; aqui vai a narrativa
> única do que foi construído, em que ordem e com que resultado.

## 1. Ponto de partida e estratégia
O `frontend/` tinha ~3457 linhas de CSS legado com 3 camadas de header, breakpoints
inconsistentes (400/480/600/720/900/960/1020), `100vw` sem compensação e tokens fora da
escala 4pt. A run dividiu o rebuild em 4 frentes paralelas sob o mesmo contrato
(`implementation-contract.md` v1, 8 critérios): **shell** (`globals.css` + Header/Rodape),
**components** (`ui/*` + BlocoEditoria/MaisLidas/DetalheNoticia), **pages** (`app/page.tsx` +
`app/*`) e **responsive/a11y** (breakpoints, overflow, foco, motion). `lib/api.ts`,
`lib/queries.ts`, `layout.tsx` (SEO/fonts/JsonLd/skip-link/anti-flash) e todo o `backend/`
eram somente-leitura.

## 2. O que cada frente construiu
- **Shell:** reescreveu `globals.css` (design system v2: tokens `--cor-*` light/dark,
  tipografia, escala 4pt, `z-index` por tokens, container `min(1200px, 100% - 2rem)`,
  grade `auto-fill/minmax(min(300px,100%),1fr)`, `portal-layout minmax(0,1fr) 320px` com
  sidebar sticky); rebuild de `Header.tsx` (busca colapsável, hamburger, `aria-current`,
  ThemeToggle, avatar/Entrar+Assine) e `Rodape.tsx` (grid 4→2→1, LGPD/cookies/RSS).
  Classes antigas `.topo*`/`.base*` mantidas como aliases; `overflow-x: hidden` global e
  culpados `100vw` (`.ticker`, `.drawer`) eliminados.
- **Components:** 17 arquivos reescritos/migrados sem mudar nenhuma prop, hook, rota ou
  chamada de API (`Button`, `Cards`, `Estados`, `SearchBar`, `FormField`, `Data`, `Drawer`,
  `ShareButtons`, `ReadingProgress`, `BlocoEditoria`, `MaisLidas`, `DetalheNoticia`,
  `Chip`, `Dropdown`, `BotaoSalvar`, `CartaoEsqueleto`); 8 verificados sem alteração
  (`Accordion`, `Badge`, `Modal`, `Tabs`, `Tooltip`, `ThemeToggle`, `CommandPalette`,
  `PorQueEstouVendoIsso`). Fallbacks inline aplicados onde o CSS ainda não tinha a classe.
- **Pages:** achado principal — `app/page.tsx` já continha o layout do contrato (hero "Seu
  rio", grade + sidebar, "Para você"/"Últimas", `BlocoEditoria`, teaser comunidade); o
  trabalho foi remover classes inexistentes (`card-legado` 2×, `pagina-editorial`) e
  normalizar 15 arquivos para `secao-bloco/secao-titulo`. Login/cadastro/recuperação,
  onboarding, `noticia/*` (delegam ao `DetalheNoticia`): já conformes, intocados.
- **Responsive/a11y:** fez o reparo crítico (seção 3), adicionou as 3 classes pedidas
  (`busca--pill`, `share-sticky`, `detalhe-dropcap`), recriou o sistema `.botao` (40/44/52px)
  e as media queries 480/768/1024/1280, blocos `prefers-reduced-motion` e `@print`, alvos
  ≥40px e `.tabela-wrapper`. Zero mudança em JS.

## 3. Incidente do CSS truncado (achado e reparo)
O agente responsive/a11y encontrou `globals.css` **truncado no disco** (término na linha 575,
marcador literal `...[truncated 20887 chars]`, resto da reescrita perdido — faltavam sistema
`.botao`, `.rodape-grid`, `.tabela-wrapper`, `.lista-compacta`, `.drawer`, todas as media
queries e o bloco a11y). Reparou com **apêndice** ao final do arquivo (cascata preservada,
nenhum token `:root` redefinido, só `:root` aditivo). O remediator confirmou: sem `truncated`
(0 matches), chaves balanceadas (268/268, 271/271 pós-fix), 15 `@media`.

## 4. Revisão e remediação (loop fechado)
- **Reviewer:** diff de 40 arquivos (então 1361+/3636−) amostrado em profundidade;
  guardas OK (`backend/` e `api.ts` vazios, sem dependências novas, rotas e LGPD intactos);
  **0 blocker, 0 major, 4 minor + 2 nit → approve_with_comments**.
- **Remediator final** corrigiu os 6 findings sem redesign nem mudança de dados/rotas:
  (1) `.limitar-linhas-2/3` definidos em `globals.css`; (2) `.share-sticky` com fallback
  sólido em cascata + remoção do `background` inline do TSX; (3) foco move para o campo ao
  abrir a busca (`useRef` + `useEffect`); (4) `Escape` fecha o menu mobile; (5) sociais
  externos com `target="_blank" rel="noopener noreferrer"` (RSS interno sem target);
  (6) Button — finding 6 era pré-existente e mantido por compatibilidade (documentado).
- **Tester (retest pós-remediação, somente leitura):** `tsc` exit 0, `build` exit 0 (2×),
  diff `backend/`+`api.ts` vazio, todos os greps conferem → **PASSED (estático + build)**,
  com ressalva não-bloqueante de runtime em browser (sem harness no ambiente).

## 5. Estado final verificado (historian, 2026-09-09)
- 40 arquivos `frontend/` modificados: **1395 inserções / 3638 deleções** vs HEAD
  (`globals.css` 621+/3290−, hoje com 736 linhas e 15 `@media`); `backend/` + `api.ts`: diff vazio.
- `tsc --noEmit` exit 0 e `next build` exit 0 atestados pelo tester/remediator (3 builds verdes).
- `documentation-update.md` **não produzido** (fase documentation pendente) — ver follow-up 4 do `report.md`.
- **Pendente:** push para `develop` + CI verde; o orchestrator fecha a run após o push
  (`run-state.json` em `in_progress/closing`).

## Dependências
Nenhuma dependência nova em nenhum momento da run (`package.json`/`package-lock.json` intactos).
