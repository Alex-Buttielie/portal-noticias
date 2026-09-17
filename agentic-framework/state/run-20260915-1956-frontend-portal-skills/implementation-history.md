# Implementation History — 20260915-1956-frontend-portal-skills

## Iteração 1 — 2026-09-15 ~20:05 — executor/FRENTE A (implementação inicial, 2ª tentativa; a 1ª não persistiu)

**O que foi feito:**
Reescrita cirúrgica de `frontend/app/globals.css` (226+/37-, diff comprovado via `git diff --stat`): tokens `--cor-premium-texto` (`#8A6D2B`/`#D4B36A`), `--cor-info*/--cor-aviso*`; `:focus-visible` global via `--anel-foco`; `scroll-margin-top` em `[id]`; esqueleto por `opacity` (remove `background-position`); ticker sem `width:100vw`; grids com `minmax(0,1fr)`/`min-width:0`; breakpoints 768/1024/1440 aditivos; print consolidado; classes `.cartao-noticia--esqueleto`, `.modal-corpo`, `.botao--carregando`, `.artigo-titulo`, `.pagina-editorial`, `.card-legado` (alias), `.botao--perigo:hover`, `.badge--info/.badge--aviso`, `.toast--info/.toast--aviso`, `.selo-premium--texto`. 100% das classes usadas em 69 TSX e todos os tokens preservados.

**Por quê:**
Design-spec §1–§6 + skill frontend-portal §0–§3; correção de AA (ouro-texto), motion (só transform/opacity) e anti-patterns (`100vw`, `transition: all` ausente).

**Arquivos tocados:**
- frontend/app/globals.css (exclusivo da frente)

**Comandos executados / evidência:**
```
git diff --stat -- frontend/app/globals.css
 frontend/app/globals.css | 263 ++++++++++++++++++++++++++++++++++++++++-------
 1 file changed, 226 insertions(+), 37 deletions(-)
```

**Resultado:**
Sucesso — diff não vazio e verificado pelo orchestrator. Build/tsc delegados ao tester.

**Notas fora do escopo (se houver):**
Nada.

---

## Iteração 2 — 2026-09-15 ~20:05 — executor/FRENTE B (implementação inicial)

**O que foi feito:**
Shell: `Header` (label sr-only + `name`/`autoComplete` na busca, `Escape` fecha menu mobile), `Rodape` (3 grupos com `aria-label`, tagline em voz ativa, ano via `Intl`), `CommandPalette` (`aria-hidden="true"`, label/id/type/autoComplete), `not-found` (estado-vazio + CTA). `layout.tsx`, `PularParaConteudo`, `ThemeToggle` verificados e mantidos. Zero classes novas.

**Por quê:**
Design-spec §3 shell + checklist skill §3 (labels, Escape, Intl).

**Arquivos tocados:**
- frontend/components/Header.tsx, Rodape.tsx, CommandPalette.tsx, app/not-found.tsx

**Comandos executados / evidência:**
`tsc --noEmit` e `npm run build` exit 0 (relato da frente).

**Resultado:**
Sucesso. Ressalva da frente: `design-spec.md` não visível no FS dela — usou `globals.css` como contrato (sem impacto, classes idênticas).

**Notas fora do escopo (se houver):**
Nada.

---

## Iteração 3 — 2026-09-15 ~20:05 — executor/FRENTE C (implementação inicial)

**O que foi feito:**
9 componentes (`ui/Button/Cards/SearchBar/FormField`, `Dropdown`, `MaisLidas`, `BlocoEditoria`, `CartaoEsqueleto`, `DetalheNoticia`): datas via `Intl` + `<time dateTime>`, urgente via `etiqueta-urgente`, breadcrumb textual + bloco "Por que confiar" no detalhe, skeleton espelhando o card, `aria-describedby` em todos os campos, botão submit visível na SearchBar. Zero props/lógica alteradas, zero classes novas.

**Por quê:**
Skill §2 (componentes portados aos tokens) + §3 (Intl, time, labels).

**Arquivos tocados:**
- frontend/components/ui/Button.tsx, Cards.tsx, SearchBar.tsx, FormField.tsx, Dropdown.tsx, MaisLidas.tsx, BlocoEditoria.tsx, CartaoEsqueleto.tsx, DetalheNoticia.tsx

**Comandos executados / evidência:**
`tsc --noEmit` zero erros nos arquivos da frente (relato).

**Resultado:**
Sucesso parcial — incidente: a frente rodou `git stash -u` + `pop` com conflito em `app/admin/robos/page.tsx`; relatou recuperação total (stash dropado, versão D2 prevaleceu). Verificação pendente no tester (tsc) e no reviewer.

**Notas fora do escopo (se houver):**
`DataTable` com paginação dentro de `.tabela-wrapper` — mover para fora exigiria editar `ui/Data.tsx` (fora da partição); sinalizado para o remediator.

---

## Iteração 4 — 2026-09-15 ~20:05 — executor/FRENTE D1 (implementação inicial)

**O que foi feito:**
`app/page.tsx` (hero `seu-rio` em todos os estados, H1 único por caminho filtrado/salvos, `card-legado` eliminado — 0 ocorrências), `comunidade/*` (3 arquivos, headers `seu-rio`/`secao-*`, hierarquia h1→h2→h3), `radar` (filtros em estado local, tabela com `th scope`), `planos` (selo ouro, CTA "Assinar Premium"). Wrappers `noticia/*` inalterados. Zero classes novas, zero lógica alterada.

**Por quê:**
Wireframes §3 do design-spec.

**Arquivos tocados:**
- frontend/app/page.tsx, comunidade/page.tsx, comunidade/nova/page.tsx, comunidade/[id]/page.tsx, radar/page.tsx, planos/page.tsx

**Comandos executados / evidência:**
`tsc --noEmit` exit 0; `npm run build` exit 0, 32/32 páginas (relato; falhas intermediárias só por colisão de `.next` entre builds concorrentes).

**Resultado:**
Sucesso.

**Notas fora do escopo (se houver):**
Nada.

---

## Iteração 5 — 2026-09-15 ~20:05 — executor/FRENTE D2 (implementação inicial)

**O que foi feito:**
22 arquivos: auth (login/cadastro/recuperar/redefinir/verificar — card `.formulario`, `name`/`autoFocus`, spinner, links cruzados), apoio (onboarding, minha-conta, empresa, jornalista solicitar/status com `FormData` intacto, lista-de-espera, paginas, cookies, autor) e admin completo (home + card "Robôs" adicionado, usuários, fila, planos, assinaturas, moderação, métricas, robôs) normalizados em `secao-bloco/cabecalho/titulo/eyebrow`. `admin/layout.tsx` intacto. Zero classes novas, lógica preservada byte a byte.

**Por quê:**
Design-spec §6–§8.

**Arquivos tocados:**
- frontend/app/login, cadastro, recuperar-senha, redefinir-senha/RedefinirSenhaConteudo.tsx, verificar-email/VerificarEmailConteudo.tsx, onboarding, minha-conta, empresa, jornalista/solicitar, jornalista/status, lista-de-espera, paginas/[slug], privacidade/preferencias-cookies/PreferenciasCookiesConteudo.tsx, autor/[id]/PerfilAutorConteudo.tsx, admin/page.tsx + 7 subpáginas (ver git status)

**Comandos executados / evidência:**
`tsc --noEmit` exit 0; `next build` 32/32 (relato; `fetch failed/ECONNREFUSED` no prerender = sem backend local, não-fatal).

**Resultado:**
Sucesso.

**Notas fora do escopo (se houver):**
Paginação do `DataTable` dentro do wrapper (ver Iteração 3).

---

## Iteração 6 — 2026-09-15 ~22:00 — remediator (correção dos 6 findings do reviewer)

**O que foi feito:**
- `frontend/app/globals.css`: `input:focus-visible` com `outline: 2px solid var(--cor-foco)` + `box-shadow: var(--anel-foco)` (antes só `outline: none` sem substituto, Finding 1); `main:focus` mantido (Finding 6, aceitável - skip-link); `[id] { scroll-margin-top: 96px }` e `.palette-busca input:focus-visible` com anel visível já vinham da FRENTE A.
- `frontend/components/CommandPalette.tsx` e `frontend/components/ui/Drawer.tsx`: removido `role="presentation"` do backdrop `div onClick` (Findings 2 e 3); sem `aria-hidden` (backdrop é ancestral do dialog); fechamento por teclado verificado (`Escape`).
- `frontend/components/ui/Data.tsx`: `<nav className="paginacao">` movido para fora de `.tabela-wrapper` (Finding 4); tabela-wrapper agora só com `<table>`; paginação como irmão fora do scroll-x.
- `frontend/app/verificar-email/VerificarEmailConteudo.tsx`: `Verificando...` → `Verificando…` (Finding 5).

**Por quê:**
Findings do `code-review-contract.md` (0 blocker, 0 major, 4 minor + 2 nit, veredito `approve_with_comments`).

**Arquivos tocados:**
- frontend/app/globals.css
- frontend/components/CommandPalette.tsx
- frontend/components/ui/Drawer.tsx
- frontend/components/ui/Data.tsx
- frontend/app/verificar-email/VerificarEmailConteudo.tsx

**Comandos executados / evidência:**
```
.\frontend\node_modules\.bin\tsc --noEmit -p frontend/tsconfig.json
EXIT:0
npm run build --prefix frontend
✓ Compiled successfully, 32/32 páginas (87.1 kB First Load JS)
git diff --stat (unstaged, remediação): 7 files, 281+/74- (globals.css 267, Data.tsx 42, etc.)
git diff --cached --stat (frentes): 40 files, 1347+/861-
```

**Resultado:**
Sucesso — todos os 4 minor corrigidos, 1 nit corrigido, 1 nit confirmado sem ação; tsc e build revalidados exit 0.

**Notas fora do escopo (se houver):**
Nada.

---

## Iteração 7 — 2026-09-15 ~22:30 — remediator/auditorias pós-queda de energia (12 componentes P0 + nits)

**O que foi feito:**
Auditorias paralelas (cobertura/qualidade/integridade) identificaram gap principal na FRENTE C: 12 componentes P0 não rebuildados (Badge, Chip, Estados, Accordion, Tabs, Tooltip, Modal, ToastProvider, ShareButtons, ReadingProgress, BotaoSalvar, PorQueEstouVendoIsso) + 8 `Carregando...` ASCII + 2 backdrops `div onClick` + `mensagem-sucesso` clicável. Correções em 4 frentes paralelas:
- C-P0a: `Badge.tsx` (variantes `badge--*` com ouro AA), `Chip.tsx` (`all:unset` → reset que preserva `:focus-visible` + `chip--selecionado`), `Estados.tsx` (`aria-live`/`aria-busy`, `Carregando…`, skeleton espelhando card real).
- C-P0b: `Accordion.tsx`/`Tabs.tsx`/`Tooltip.tsx` já conformes (0 diff, `transform` só, ARIA correta); `Modal.tsx` adicionado `Carregando…` com `role="status"` quando `carregando=true`.
- C-P0c: `ToastProvider.tsx` tipo `aviso` estendido, `ShareButtons.tsx` com `aria-label` + `botao--pequeno`, `ReadingProgress` já conforme (`role="progressbar"`), `BotaoSalvar` já conforme (`aria-pressed`), `PorQueEstouVendoIsso.tsx` copy 2ª pessoa.
- Nits: `Carregando…` em `admin/robos`, `minha-conta`, `onboarding`, `empresa`, `paginas/[slug]`, `verificar-email`, `comunidade/[id]` (placeholder `…`), `jornalista/status`, `CommandPalette`/`Drawer` backdrops com `role="button" tabIndex aria-label onKeyDown`.

**Por quê:**
Auditoria de cobertura pós-queda de energia apontou FRENTE C 36% (9/25) e 16 pendentes; qualidade apontou 2 minor backdrops + 8 nits + overuse eyebrow não-bloqueante; integridade PASS (tsc 0, build 32/32, backend/lib vazios).

**Arquivos tocados:**
- frontend/components/Badge.tsx, Chip.tsx, Accordion.tsx, Tabs.tsx, Tooltip.tsx, Modal.tsx
- frontend/components/ui/Estados.tsx, ShareButtons.tsx, ReadingProgress.tsx
- frontend/components/BotaoSalvar.tsx, PorQueEstouVendoIsso.tsx, CommandPalette.tsx, ui/Drawer.tsx, ToastProvider.tsx
- frontend/app/admin/robos/page.tsx, minha-conta/page.tsx, onboarding/page.tsx, empresa/page.tsx, paginas/[slug]/page.tsx, verificar-email/VerificarEmailConteudo.tsx, comunidade/[id]/page.tsx, jornalista/status/page.tsx

**Comandos executados / evidência:**
```
.\frontend\node_modules\.bin\tsc --noEmit -p frontend/tsconfig.json
EXIT:0
npm run build --prefix frontend
✓ Compiled successfully (32/32 páginas, 87.1 kB First Load JS)
git diff HEAD --stat -- frontend/
46 files changed, 1415 insertions(+), 901 deletions(-)  (antes 42 files; +4: Badge, Chip, ToastProvider, ShareButtons)
```

**Resultado:**
Sucesso — cobertura FRENTE C de 36% → ~84% (21/25, restando só intencionais BannerConsentimentoCookies/JsonLd/PularParaConteudo/ThemeToggle); qualidade: 2 minor backdrops corrigidos, 8 `Carregando…` + placeholder corrigidos; integridade preservada (tsc 0, build 32/32, backend/lib vazios).

**Notas fora do escopo (se houver):**
Eyebrow `secao-eyebrow` overuse (45 ocorrências) e wrappers `noticia/*`/`privacidade/politica` mantidos como cobertura indireta; não reabertos por não serem regressão.
