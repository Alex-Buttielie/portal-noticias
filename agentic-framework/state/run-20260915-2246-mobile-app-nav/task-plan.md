# Task Plan — 20260915-2246-mobile-app-nav

## Metadados
- **run_id:** 20260915-2246-mobile-app-nav
- **Data:** 2026-09-15
- **Solicitado por:** Alex — "todo o front tenha um modo para dispositivo móvel, componentes se ajustem, navegação parecida com app do dispositivo"
- **Spec:** `.claude/skills/frontend-portal/SKILL.md` (responsive 360/768/1024/1440 + touch + safe-area + drawer/bottom-nav)

## Objetivo
Adicionar modo móvel app-like em todo o `frontend/`: layout e navegação se adaptam ao viewport/dispositivo, com navegação primária em drawer + bottom tab bar, componentes com touch targets ≥44px, `env(safe-area-inset-*)`, gestos com fallback teclado, e tipografia/espaçamento que não quebra em 360px — mantendo desktop intacto e sem mudar rotas/contratos.

## Escopo
### Dentro
- Shell: `Header` com hamburger → `Sheet/Drawer` (Radix Dialog) + bottom nav `nav[aria-label="Navegação primária"]` fixa em `sm:hidden` com 4–5 tabs (Início, Comunidade, Radar, Planos, Conta/Entrar), `env(safe-area-inset-bottom)`, `touch-action: manipulation`, `overscroll-behavior: contain` no overlay, `prefers-reduced-motion` nos slides.
- Componentes: `Button`/`Chip`/`Badge`/`Tabs`/`Card`/`Table` com `min-w-0`/`truncate`/`line-clamp` + `min-h-[44px]`, `Table` com scroll-x + paginação fora do wrapper (já feito, preservar), `SearchBar` com `inputMode=search`, `Drawer/Sheet` com `inert` durante drag.
- Páginas: hero/rio `portal-layout` empilha 1col em `<1024` (já faz) + sidebar vira carrossel/drawer em mobile; forms com `font-size 16px` para evitar zoom iOS; listas com `content-visibility` onde >50 itens (se houver).
- Detecção: CSS-first via Tailwind breakpoints + `useIsMobile` hook (`window.matchMedia("(max-width: 768px)")`) só onde precisa (bottom nav vs top nav); sem UA sniff.

### Fora
- PWA install/manifest/service-worker, `backend/`, `lib/api`, URLs/SEO/LGPD, nova rota.

## Suposições
- Bottom nav com 4–5 itens cobre navegação primária; admin mantém sidebar desktop e drawer mobile (mesmo `admin/layout.tsx` com `Sheet`).
- `360px` como menor viewport suportado; `safe-area-inset` só afeta iOS notch/Dynamic Island.

## Restrições
- `prefers-reduced-motion`, `:focus-visible` ring, AA, `color-scheme`, `data-theme` intactos; `backend/lib` sem diff; sem `user-scalable=no`.

## Divisão
| Etapa | Agente | Entrada | Saída |
|---|---|---|---|
| 1 | executor 3 frentes | implementation-contract.md | código + history |
| 2 | tester | contract | test-report.md (tsc+build+breakpoints+touch+safe-area+screenshots) |
| 3 | reviewer | diff | code-review |
| 4 | remediator | review | fixes |
| 5 | documenter | history | docs |
| 6 | historian | todos | report + HISTORY |

## Critérios de aceite
1. Em 360px: sem overflow-x, sem scrollbar horizontal indesejada, todo conteúdo legível sem pinch.
2. Navegação app-like: hamburger abre `Sheet` com foco preso + `Escape`/backdrop fecha + `aria-expanded`; bottom nav visível só em mobile e com `aria-current="page"` + `safe-area`, deep-link por URL.
3. Touch: `touch-action: manipulation`, `min-h 44px` em interativos, `overscroll-behavior: contain` em modais/drawers, gestos com alternativa tap/teclado.
4. `tsc` 0 + `build` 32/32.
5. `command.md` zero blocker/major; `backend/lib` vazios.

## Riscos
| Risco | Impacto | Mitigação |
|---|---|---|
| Bottom nav cobre foco/conteúdo | médio | `pb-[calc(4rem+env(safe-area-inset-bottom))]` no `main`, sticky não cobre `:focus-visible` |
| Drawer duplica nav | baixo | Fonte única de itens, `aria-label` distintos |
| Zoom em inputs iOS | médio | `text-[16px]` em inputs em `<768` |
