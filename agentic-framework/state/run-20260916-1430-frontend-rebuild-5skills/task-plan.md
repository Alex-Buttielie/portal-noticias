# Task Plan — 20260916-1430-frontend-rebuild-5skills

## Metadados
- **run_id:** 20260916-1430-frontend-rebuild-5skills
- **Data de abertura:** 2026-09-16
- **Solicitado por:** Alex — "jogue tudo que tem hoje fora e refaça usando as 5 skills 100% para a reimplementação do frontend"
- **Spec de origem:** `.claude/skills/frontend-portal/SKILL.md` (consolida 5 skills) + 5 skills originais fetcheadas

## Objetivo
Refazer **100% do `frontend/`** do zero usando as 5 skills em runtime real:
1. **web-design-guidelines** (Vercel) — checklist de conformidade fresco a cada revisão
2. **shadcn-ui-mcp-server** — componentes acessíveis (código-fonte, demos, metadados via MCP)
3. **frontend-design** (Anthropic) — direção de design distintiva em 2 passes (plano + anti-genérico)
4. **21st-dev/magic-mcp** — catálogo 10.000+ componentes React/Tailwind + geração UI por IA
5. **chrome-devtools-mcp** — verificação em browser real (360/768/1024/1440 + dark/light + tab-order + AA)

Stack alvo: **Next.js 14 App Router + React 18 + TypeScript + Tailwind CSS 3.4 + shadcn/ui v4 (Radix)** — migração autorizada explicitamente neste task-plan (conforme §0 da skill frontend-portal).

## Escopo
### Dentro do escopo (tudo será refeito)
- **Setup Tailwind + shadcn:** `tailwind.config.ts`, `postcss.config.js`, `globals.css` com `@tailwind` + `@layer base`, `components.json`, `lib/utils.ts` (`cn`), `tailwindcss-animate`, `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`, `@radix-ui/*` necessários
- **Design system:** tokens `--cor-*`, `--espaco-*`, `--raio-*`, `--sombra-*`, `--z-*` mapeados para `theme.extend` do Tailwind; tipografia `Inter` + `Source_Serif_4` via `next/font`; `darkMode: '[data-theme="dark"]'` casando `layout.tsx` anti-flash
- **Componentes shadcn/21st (ordem de preferência §2):**
  - shadcn/ui v4 via MCP: `Button`, `Card`, `Dialog`, `DropdownMenu`, `Tabs`, `Tooltip`, `Accordion`, `Toast`, `Avatar`, `Label`, `Select`, `Separator`, `Slot`, `ScrollArea`, `Sheet`, `NavigationMenu`, `Breadcrumb`, `Pagination`, `DataTable`, `Form`, `Input`, `Textarea`, `Checkbox`, `RadioGroup`, `Switch`, `Slider`, `Popover`, `HoverCard`, `Menubar`, `ContextMenu`, `Command`, `Calendar`, `DatePicker`, `Alert`, `Badge`, `Skeleton`, `Progress`, `Separator`, `ScrollArea`, `Resizable`, `Sonner` (toast), `Drawer` (vaul)
  - 21st.dev via HTTP MCP (`search`/`get_component`/`search_logo`; `generate` só se `aiGenerationEnabled`): blocos de Hero, Pricing, Dashboard, Newsletter, Footer, Blog/News layouts, Auth forms, Data visualization
- **Shell completo (todas as rotas existentes preservadas):**
  - `app/layout.tsx` (SEO/LGPD/skip-link/anti-flash/JsonLd intactos)
  - `components/Header.tsx` (nav desktop + mobile Sheet + busca + avatar/menu)
  - `components/Rodape.tsx` (links institucionais, RSS, newsletter, LGPD)
  - `components/BottomNav.tsx` (mobile app-like, safe-area, touch 44px)
  - `components/BannerConsentimentoCookies.tsx`
  - `components/PularParaConteudo.tsx`
  - `components/ThemeToggle.tsx`
- **Todas as 26 rotas em `frontend/app/` (rebuild visual apenas, lógica/contratos preservados):**
  - Público: `/`, `/noticia/cluster/[id]`, `/noticia/item/[id]`, `/cadastro`, `/login`, `/verificar-email`, `/recuperar-senha`, `/redefinir-senha`, `/onboarding`, `/planos`, `/lista-de-espera`, `/jornalista/solicitar`, `/jornalista/status`, `/comunidade`, `/comunidade/nova`, `/comunidade/[id]`, `/autor/[id]`, `/radar`, `/empresa`, `/paginas/[slug]`, `/privacidade/politica`, `/privacidade/preferencias-cookies`
  - Admin: `/admin`, `/admin/assinaturas`, `/admin/fila`, `/admin/metricas`, `/admin/moderacao`, `/admin/planos`, `/admin/robos`, `/admin/usuarios`, `/admin/page.tsx`
  - `/minha-conta`, `/cadastro`, `/not-found`
- **Componentes compartilhados em `frontend/components/`:** `Accordion`, `Badge`, `BlocoEditoria`, `BotaoSalvar`, `CartaoEsqueleto`, `Chip`, `CommandPalette`, `DetalheNoticia`, `Dropdown`, `MaisLidas`, `Modal`, `PorQueEstouVendoIsso`, `Tabs`, `Tooltip`, `ToastProvider`, `ReadingProgress`, `ShareButtons`, `SearchBar`, `Data`, `Estados`, `FormField`, `Drawer`, `Cards`, `Button` (UI primitives)

### Fora do escopo (intocáveis)
- `backend/` — diff deve ser vazio
- `frontend/lib/api.ts` — contrato com Django intacto
- URLs/rotas, SEO (`sitemap.ts`, `rss.xml`, `robots.ts`, `JsonLd`), LGPD (banner + `/privacidade/*`)
- Skip-link `#conteudo-principal`, script anti-flash de tema em `app/layout.tsx`
- Novas features de produto; apenas rebuild visual

## Suposições assumidas
- **Migração Tailwind+shadcn autorizada** — nova dependência externa aprovada explicitamente neste task-plan (conforme §0 da skill: "não introduzir Tailwind/shadcn sem aprovação explícita no task-plan.md")
- **Identidade: evolução editorial brasileira** — serifa nos títulos (Source_Serif_4), rio de notícias + sidebar, paleta editorial distinta (não creme/terracota genérico), ousadia no hero (a notícia como protagonista)
- **Validação browser real via chrome-devtools-mcp** — `--slim --headless` nos 4 breakpoints + dark/light + tab-order + contraste AA; se MCP indisponível, fallback estático documentado (precedente `2d8063c`)
- **shadcn-ui-mcp-server** disponível via `npx @jpisnice/shadcn-ui-mcp-server` (com `--github-api-key` se possível)
- **21st.dev** MCP HTTP em `https://21st.dev/api/mcp` com `x-api-key` (`API_KEY_21ST` — chave gratuita em https://21st.dev/mcp); free tier 2 installs/dia, `generate` só se habilitado
- **command.md** fresco fetchado antes de cada revisão (`https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md`)

## Restrições
- `prefers-reduced-motion` global, `:focus-visible` ring visível, AA ≥4.5:1, `color-scheme`, `data-theme` intactos
- `backend/` e `frontend/lib/api.ts` sem diff
- Sem `user-scalable=no`, `onPaste`+`preventDefault`, `transition: all`, `outline-none` sem substituto, `div onClick` sem `<a>`, imagem sem dimensão, input sem label, `...` ASCII em copy
- Diff esperado >300 linhas → revisão obrigatória (`review-triggers.md`)

## Divisão de trabalho
| Etapa | Agente | Entrada | Saída |
|---|---|---|---|
| 1 | executor (6 frentes paralelas) | implementation-contract.md + design-spec.md | código + implementation-history.md |
| 2 | tester | contract + MCPs | test-report.md (tsc 0, build 32/32, command.md 0 blocker/major, MCP screenshots) |
| 3 | reviewer (obrigatório) | diff | code-review-contract.md |
| 4 | remediator | code-review | correções + revalidação |
| 5 | documenter | history | documentation-update.md + README/ARCHITECTURE/SKILL updates |
| 6 | historian | todos | report.md + HISTORY.md |

### Frentes do executor (paralelas, particionamento exclusivo de arquivos)
| Frente | Responsável por | Arquivos (exclusivos) |
|---|---|---|
| A | **Tailwind setup + design tokens** | `tailwind.config.ts`, `postcss.config.js`, `globals.css` (tokens + `@tailwind` + `@layer base`), `components.json`, `lib/utils.ts` (`cn`), `package.json`/`package-lock.json` |
| B | **Shell shadcn/21st** | `components/Header.tsx`, `components/Rodape.tsx`, `components/BottomNav.tsx`, `app/layout.tsx`, `components/ThemeToggle.tsx`, `components/BannerConsentimentoCookies.tsx`, `components/PularParaConteudo.tsx` |
| C | **Componentes UI primitives** | `components/ui/*` (25+ componentes shadcn com `cva`+`cn`+`lucide`+`focus-visible:ring`) |
| D1 | **Páginas núcleo (rio/comunidade/radar/planos)** | `app/page.tsx`, `app/comunidade/*`, `app/radar/*`, `app/planos/*`, `app/noticia/*` |
| D2 | **Páginas auth/onboarding/admin** | `app/cadastro`, `app/login`, `app/onboarding`, `app/minha-conta`, `app/lista-de-espera`, `app/jornalista/*`, `app/admin/*`, `app/autor/*`, `app/empresa`, `app/paginas/[slug]`, `app/privacidade/*`, `app/recuperar-senha`, `app/redefinir-senha`, `app/verificar-email`, `app/not-found` |
| E | **Design spec + 2-pass frontend-design** | `design-spec.md` (paleta 6 hex, 3 ritmos, wireframes ASCII, princípios), revisão anti-genérica documentada |

## Critérios de aceite
1. **5 skills evidenciadas em runtime real:** MCP shadcn demos, 21st catálogo, frontend-design 2-pass, command.md fresco, chrome-devtools screenshots (ou fallback documentado)
2. **Tailwind+shadcn instalados e em uso:** `cn` helper, componentes shadcn via `cva`/`cn`/`lucide`/`focus-visible:ring`, 26 rotas + shell reestilizados só com classes Tailwind/shadcn
3. **`tsc --noEmit` 0 + `next build` 32/32 exit 0**
4. **Checklist `command.md` fresco: 0 blocker/major** (evidência por arquivo em `test-report.md`)
5. **`backend/` e `frontend/lib/api.ts` vazios no diff; nenhuma rota renomeada**
6. **Revisão `approve` ou `approve_with_comments`**
7. **chrome-devtools-mcp executado:** 360/768/1024/1440 + dark/light + tab-order + AA screenshots (ou fallback estático com ressalva)

## Riscos
| Risco | Impacto | Mitigação |
|---|---|---|
| Regressão visual por migração Tailwind (segundo revert) | alto | Mapear tokens `--cor-*` → `theme.extend.colors`, aliases legados, build revalidado a cada frente |
| Conflito de arquivos entre frentes paralelas | alto | Partição exclusiva por arquivo; `globals.css` dono único (Frente A) |
| 21st sem chave / sem créditos IA | médio | Fallback catálogo portado manualmente + `generate` só com `aiGenerationEnabled` |
| Chrome MCP indisponível no CI | médio | `--slim --headless` local + fallback estático documentado |
| Estouro de contexto (26 rotas + 25 componentes) | médio | Frentes paralelas + design-spec compartilhado; páginas seguem padrão, sem reinventar por rota |

## Dependências
- Decisão humana: chave `API_KEY_21ST` para 21st.dev MCP (se não houver, fallback documentado)
- `chrome-devtools-mcp` instalado e Chrome headless disponível para validação final