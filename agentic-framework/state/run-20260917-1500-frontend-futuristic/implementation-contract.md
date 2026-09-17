# Implementation Contract — 20260917-1500-frontend-futuristic

## Metadados
- **run_id:** 20260917-1500-frontend-futuristic
- **Deriva de:** task-plan.md (20260917-1500-frontend-futuristic)
- **Versão do contrato:** 1

## O que deve ser construído
Recriar `frontend/` do zero com design futurista paper/ink+signal (HUD/bento/vidro/neon contido, organização reposicionada). Stack Next.js 14 App Router + React 18 + TS + Tailwind 3.4 + shadcn new-york cssVariables (theme.extend mapeando todos var(--cor-*) etc.). Frentes:
- **A tokens/scaffold:** `app/globals.css` com `@tailwind` + `@layer base` definindo `:root` e `[data-theme=dark]` com tokens futuristas (`--cor-primaria:#0A84FF` néon, `--cor-fundo:#FDFBF7` paper, `--cor-fundo-elevado:rgba(255,255,255,0.72)` vidro, `--cor-borda:#E7E7E0`, `--cor-texto:#0B0B1A` ink, `--cor-texto-suave:#6B7280`, `--cor-texto-invertido:#FDFBF7`, `--cor-sucesso:#0A84FF`, `--cor-alerta:#FF9F0A`, `--cor-erro:#FF3B30` signal, `--cor-sinal:#FF2E2E`, `--cor-neon-ciano:#06B6D4`, `--cor-neon-violeta:#7C3AED`, `--cor-sombra` etc. + `--espaco-*`/`--raio-*`/`--sombra-*`/`--z-*`), `tailwind.config.ts` content app/components/lib + darkMode class `[data-theme="dark"]` + extend(colors/spacing/radius/shadow/zIndex→var(...)), `postcss.config.js`, `components.json`, `lib/utils.ts` cn, `next.config.js/tsconfig`. Tokens únicos via var(...); nunca hex hardcoded em componentes.
- **B shell:** `app/layout.tsx` com `next/font` Inter(body) + Source_Serif_4(headings) variable, viewport, metadataBase JsonLd organizationJsonLd, SCRIPT_TEMA_INICIAL beforeInteractive, Providers(ReactQuery+Auth), PularParaConteudo #conteudo-principal, Header(NavigationMenu desktop + Sheet mobile + busca + DropdownMenu avatar + ThemeToggle), Rodape(bento 4 colunas), BottomNav(safe-area), BannerConsentimentoCookies, Toaster sonner; `components/Header.tsx|Rodape.tsx|BottomNav.tsx|ThemeToggle.tsx|BannerConsentimentoCookies.tsx|PularParaConteudo.tsx` futuristas (HUD, vidro, bento).
- **C ui:** 40+ `components/ui/*` (Button/Card/Dialog/Tabs/Toast/Sonner/Sheet/DropdownMenu/NavigationMenu/Breadcrumb/Pagination/DataTable/Form/Input/Textarea/Checkbox/RadioGroup/Switch/Select/Slider/Popover/HoverCard/Calendar/Alert/Badge/Skeleton/Progress/Separator/ScrollArea/Drawer/Avatar/Tooltip/Accordion/Label/Sonner-pricing-table/prose/etc.) via shadcn new-york + cva+cn+Radix+lucide, portados para var(--cor-*), focus-visible:ring, min-h-[44px] touch.
- **D1 núcleo:** `app/page.tsx` hero protagonista bento/HUD + rio, `app/comunidade/**`, `app/radar/**`, `app/planos/**`, `app/noticia/**`, `app/autor/**` + HomeHero/HomeSidebar/BlocoEditoria/MaisLidas/CartaoEsqueleto/DetalheNoticia/PorQueEstouVendoIsso futuristas, consumindo lib/api + lib/queries + Server Components com generateMetadata onde couber.
- **D2 auth/admin/apoio:** `app/cadastro|login|onboarding|minha-conta|lista-de-espera|jornalista/**|admin/**|empresa|paginas/[slug]|privacidade/**|recuperar|redefinir|verificar|not-found` com Form/Zod inline, erro inline + foco 1º erro, autocomplete correto, placeholder ….

## Áreas/arquivos esperados
- `frontend/app/globals.css`, `tailwind.config.ts`, `postcss.config.js`, `components.json`, `lib/utils.ts`, `next.config.js`, `tsconfig.json`
- `frontend/app/layout.tsx`, `providers.tsx`, `robots.ts`, `sitemap.ts`, `rss.xml/route.ts`, `not-found.tsx`, `app/**/page.tsx` (31 rotas)
- `frontend/components/Header.tsx`, `Rodape.tsx`, `BottomNav.tsx`, `ThemeToggle.tsx`, `BannerConsentimentoCookies.tsx`, `PularParaConteudo.tsx`, `HomeHero.tsx`, `HomeSidebar.tsx`, `BlocoEditoria.tsx`, `MaisLidas.tsx`, `CartaoEsqueleto.tsx`, `DetalheNoticia.tsx`, `PorQueEstouVendoIsso.tsx` etc.
- `frontend/components/ui/*` (40+)
- `frontend/lib/api.ts`, `lib/queries.ts`, `lib/auth-context.tsx`, `lib/query-client.ts`, `lib/cookie-consent.ts`, `lib/schema.ts`, `lib/site.ts`, `lib/hooks/*` — preservação (sem diff)

## Interfaces afetadas
- `frontend/lib/api.ts` (121 exports PT, Token + FormData bypass) — contrato preservado, diff vazio
- `frontend/lib/queries.ts` (64 hooks RQ) — apenas consumo
- `frontend/lib/auth-context.tsx`/`query-client.ts`/`cookie-consent.ts`/`site.ts`/`schema.ts` — preservação
- `frontend/app/layout.tsx` SEO/LGPD/skip-link/anti-flash — preservação lógica, visual novo
- `backend/**` — sem diff

## Critérios de aceite (técnicos, testáveis)
1. Dado wipe be6f4e5, quando frontend reconstruído, então `frontend/app/**/page.tsx` (31 rotas) + `robots.ts`/`sitemap.ts`/`rss.xml`/`not-found.tsx`/`providers.tsx` existem e `next build` gera 32/32 rotas sem erro.
2. Dado tokens futuristas em globals.css, quando `tailwind.config.ts` theme.extend referencia var(--cor-*) etc., então nenhuma classe usa hex hardcoded fora de globals.css.
3. Dado stack Next 14, quando `tsc --noEmit -p frontend/tsconfig.json` roda, então EXIT 0.
4. Dado build, quando `npm run build --prefix frontend` roda, então EXIT 0 e 32/32 rotas + shared ~87kB (ECONNREFUSED de prerender com backend offline é pré-existente e não falha build).
5. Dado contratos, quando `git diff --stat -- backend/ frontend/lib/api.ts` roda, então vazio.
6. Dado 5 skills, quando auditoria roda, então `command.md` fresco 0 blocker/major por arquivo (terse), shadcn via MCP/site em componentes/ui, 21st search→get_component portado, frontend-design 2 passes em design-spec.md, chrome-devtools ou fallback documentado.

## Não-objetivos
- Alterar `backend/**` ou `frontend/lib/api.ts`/`queries`/`auth-context`/`cookie-consent`/`site`/`schema`
- Novas features além do BRD/specs existentes; PWA/manifest
- Bloquear paste, `user-scalable=no`, `transition:all`, `outline:none` sem substituto

## Restrições técnicas
- **Performance:** listas >50 virtualizadas ou content-visibility, sem layout reads no render, inputs não-controlados por padrão
- **Segurança/privacidade:** LGPD Banner + /privacidade/* + cookie-consent sync preservados; nenhuma credencial hardcoded
- **Dependências permitidas:** Next 14, React 18, Tailwind 3.4, shadcn Radix v4 new-york, Radix primitives já em package.json, lucide, sonner, embla, next-themes, react-hook-form, @tanstack/query+table
- **Estilo/convenções:** tokens SOMENTE var(--cor-*) etc.; cn(); cva; focus-visible:ring-[var(--cor-foco)]; min-h-[44px] touch-manipulation; motion-reduce:transition-none; text-wrap:balance headings; Intl.* datas; placeholder …

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite 1-6 implementados
- [ ] Testes escritos e passando (tester: tsc + build + command.md)
- [ ] Revisão de código aprovada (reviewer approve/approve_with_comments)
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente
