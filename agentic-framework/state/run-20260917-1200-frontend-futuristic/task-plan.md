# Task Plan — 20260917-1200-frontend-futuristic

## Metadados
- **run_id:** 20260917-1200-frontend-futuristic
- **Data de abertura:** 2026-09-17
- **Solicitado por:** Alex — rebuild total do design (estrutura funcional preservada, organização e componentes 100% futuristas) com 5 skills
- **Spec de origem:** BRD_portal_noticias_versao_1.docx + agentic-framework/specs/* (13 specs) + .claude/skills/frontend-portal/SKILL.md

## Objetivo
Recriar `frontend/` do zero com design completamente novo e futurista (bento-grid/HUD, vidro/neon, papel escuro), mantendo 100% da estrutura funcional (31 rotas app/**/page.tsx + contratos lib/api.ts + SEO/LGPD/skip-link/anti-flash) e evidenciando as 5 skills em runtime.

## Escopo
### Dentro do escopo
- Scaffold futurista: `tailwind.config.ts` theme.extend mapeando tokens futuristas `--cor-*`, `--espaco-*`, `--raio-*`, `--sombra-*`, `--z-*` para `var(--cor-*)`; `postcss.config.js`; `components.json` new-york rsc tsx cssVariables; `lib/utils.ts` cn; `app/globals.css` com `@tailwind` + `@layer base` (tokens futuristas + Inter/Source_Serif_4 via next/font + data-theme + prefers-reduced-motion)
- Shell futurista: `app/layout.tsx` (SEO metadataBase/JsonLd/organizationJsonLd + SCRIPT_TEMA_INICIAL beforeInteractive + Providers + PularParaConteudo + BannerConsentimentoCookies + Toaster), `components/Header.tsx` (NavigationMenu desktop + Sheet mobile + CommandPalette + DropdownMenu avatar), `components/Rodape.tsx` (bento 4 colunas + RSS/newsletter/LGPD), `components/BottomNav.tsx` (safe-area, touch 44px), `components/ThemeToggle.tsx`, `BannerConsentimentoCookies.tsx`, `PularParaConteudo.tsx`
- UI primitives futuristas: 40+ `components/ui/*` via shadcn-ui-mcp-server/new-york (Button/Card/Dialog/Tabs/Toast/Sheet/DropdownMenu/NavigationMenu/Breadcrumb/Pagination/DataTable/Form/Input/Textarea/Checkbox/RadioGroup/Switch/Slider/Popover/HoverCard/Calendar/Alert/Badge/Skeleton/Progress/Separator/ScrollArea/Drawer-Sonner etc.) + blocos 21st.dev (Hero/Pricing/Charts) via search→get_component, portar para var(--cor-*)
- Páginas núcleo (D1): `app/page.tsx` (hero protagonista + rio bento-grid/HUD + HomeHero/HomeSidebar/BlocoEditoria/MaisLidas/CartaoEsqueleto), `app/comunidade/**` (feed/nova/[id]), `app/radar/**`, `app/planos/**`, `app/noticia/cluster|item/[id]`, `app/autor/[id]`
- Páginas auth/admin/apoio (D2): `app/cadastro|login|onboarding|minha-conta|lista-de-espera|jornalista/**|admin/**|empresa|paginas/[slug]|privacidade/**|recuperar|redefinir|verificar|not-found` (31 rotas preservadas, visual novo)
- Design-spec futurista 2 passes (paper #FDFBF7 / ink #0B0B1A / signal #FF2E2E + néon ciano/violeta, bento-grid, vidro)

### Fora do escopo (explicitamente)
- `backend/**` — diff vazio
- `frontend/lib/api.ts`, `frontend/lib/queries.ts`, `lib/auth-context.tsx`, `lib/query-client.ts`, `lib/cookie-consent.ts`, `lib/schema.ts`, `lib/site.ts` — contratos preservados (diff vazio), apenas consumo
- Novas features de produto além do BRD/specs existentes
- `user-scalable=no`, `onPaste+preventDefault`, `transition:all`, `outline:none` sem substituto, `div onClick` sem <a>

## Suposições assumidas
- Direção paper/ink+signal aprovada (paper #FDFBF7, ink #0B0B1A, signal, HUD) — motivo: contraste editorial + sinal urgente sem cair no creme/terracota genérico
- Futurista = HUD/bento/vidro/neon contido, não cyberpunk carregado — 1 elemento ousado (hero), resto disciplinado
- 21st generate só se aiGenerationEnabled — motivo: evitar custo sem créditos; fallback catálogo
- MCPs runtime quando disponíveis, fallback documentado (precedente 2d8063c) — motivo: sem MCP no CI

## Restrições
- Stack: Next.js 14 App Router + React 18 + TypeScript + Tailwind 3.4 + shadcn v4 Radix (intocável)
- Tokens SOMENTE var(--cor-*) etc. via tailwind theme.extend; nunca hex hardcoded
- SEO intocável: metadataBase, sitemap.ts, rss.xml/route.ts, robots.ts, JsonLd, organizationJsonLd
- LGPD intocável: BannerConsentimentoCookies + /privacidade/* + cookie-consent sync
- A11y intocável: skip-link #conteudo-principal + SCRIPT_TEMA_INICIAL anti-flash em layout.tsx
- Verificação mínima: frontend/node_modules/.bin/tsc --noEmit + npm run build --prefix frontend exit 0; backend/lib/api.ts diff vazio; command.md fresco 0 blocker/major; chrome-devtools 360/768/1024/1440 + dark/light + tab-order + AA ou fallback com ressalva

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor (5 frentes) | implementation-contract.md | código + implementation-history.md |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked |
| 3 | reviewer (review-triggers.md) | diff do executor | code-review-contract.md |
| 4 | remediator | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. Design 100% novo futurista evidenciado (bento/HUD/vidro/neon contido) e não-genérico (revisão anti-genérico registrada)
2. Estrutura funcional 100% preservada: 31 rotas app/**/page.tsx + layouts/sistema (robots/sitemap/rss/not-found/providers) renderizam e navegam; contratos lib/api.ts intactos
3. 5 skills evidenciadas em runtime: shadcn via MCP/site + 21st search/get_component + frontend-design 2 passes + command.md fresco + chrome-devtools ou fallback documentado
4. tsc --noEmit 0 + next build 32/32 exit 0; backend/ + lib/api.ts diff vazio; nenhuma rota renomeada
5. A11y/SEO/LGPD intocáveis preservados: skip-link, anti-flash, JsonLd, Banner, privacidade/*
6. Revisão approve/approve_with_comments e docs atualizadas (README/SKILL sem contradição)

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Token drift (hex hardcoded vs var(--cor-*)) | alto | Mapear tudo em tailwind theme.extend; grep var(--cor-*) |
| Conflito de frentes paralelas | alto | Partição exclusiva por arquivo; globals.css dono único |
| 21st sem chave/créditos | médio | Fallback catálogo portado; generate só com aiGenerationEnabled |
| Chrome MCP indisponível | médio | Fallback tsc+build+checagem estática com ressalva (2d8063c) |
| Scope creep (31 rotas + 40 ui) | médio | Templates por domínio (auth/admin/comunidade) + lib/queries reutilizada |

## Dependências
- API_KEY_21ST opcional (https://21st.dev/mcp) para 21st MCP; sem ela, fallback site
- chrome-devtools-mcp opcional (--slim --headless) para verificação browser
