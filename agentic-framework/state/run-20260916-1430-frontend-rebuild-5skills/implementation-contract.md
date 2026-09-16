# Implementation Contract — 20260916-1430-frontend-rebuild-5skills

## Metadados
- **run_id:** 20260916-1430-frontend-rebuild-5skills
- **Deriva de:** task-plan.md
- **Versão:** 1

## O que deve ser construído

### FRENTE A — Tailwind Setup + Design Tokens (dono exclusivo de `globals.css`, `tailwind.config.ts`, `postcss.config.js`, `components.json`, `lib/utils.ts`, `package.json`)
- `tailwind.config.ts`: `content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"]`, `darkMode: ['class', '[data-theme="dark"]']`, `theme.extend.colors` mapeando **todos** os tokens `--cor-*` (15+ cores: `primaria`, `primaria-hover`, `primaria-suave`, `secundaria`, `sucesso`, `alerta`, `erro`, `fundo`, `fundo-elevado`, `borda`, `texto`, `texto-suave`, `texto-invertido`, `foco`, `sombra`, `vidro`, `gradiente-marca`), `theme.extend.spacing` mapeando `--espaco-*`, `theme.extend.borderRadius` mapeando `--raio-*`, `theme.extend.boxShadow` mapeando `--sombra-*`, `theme.extend.zIndex` mapeando `--z-*`, `plugins: [require('tailwindcss-animate')]`
- `postcss.config.js`: `plugins: { tailwindcss: {}, autoprefixer: {} }`
- `globals.css`: `@tailwind base; @tailwind components; @tailwind utilities;` + `@layer base { /* tokens --cor-* etc. preservados como fonte da verdade; Tailwind lê via `var(--cor-*)` */ :root { --cor-primaria: ... } [data-theme="dark"] { --cor-primaria: ... } html { scrollbar-gutter: stable; } body { @apply bg-[var(--cor-fundo)] text-[var(--cor-texto)] antialiased; } * { @apply motion-reduce:transition-none; } :focus-visible { @apply outline-none ring-2 ring-[var(--cor-foco)] ring-offset-2; } }` + `@layer components { /* shadcn overrides se necessário */ }`
- `components.json`: `{ "$schema": "https://ui.shadcn.com/schema.json", "style": "new-york", "rsc": true, "tsx": true, "tailwind": { "config": "tailwind.config.ts", "css": "app/globals.css", "baseColor": "neutral", "cssVariables": true }, "aliases": { "components": "@/components", "utils": "@/lib/utils", "ui": "@/components/ui", "lib": "@/lib", "hooks": "@/lib/hooks" } }`
- `lib/utils.ts`: `export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }`
- `package.json`: adicionar `tailwindcss@3.4.17`, `postcss@8.4.49`, `autoprefixer@10.4.20`, `tailwindcss-animate@1.0.7`, `class-variance-authority@0.7.1`, `clsx@2.1.1`, `tailwind-merge@2.6.1`, `lucide-react@0.460.0`, `@radix-ui/react-*` (15+ pacotes), `vaul@0.9.0` (Drawer), `embla-carousel-react@8.0.0` (carrosséis 21st), `sonner@1.4.0` (toast), `next-themes@0.3.0` (tema)

### FRENTE B — Shell shadcn/21st (dono de `Header`, `Rodape`, `BottomNav`, `app/layout`, `ThemeToggle`, `BannerConsentimentoCookies`, `PularParaConteudo`)
- `app/layout.tsx`: preservar SEO (`metadata`, `viewport`, `JsonLd`, `organizationJsonLd`), LGPD (`BannerConsentimentoCookies`), anti-flash script, skip-link `#conteudo-principal`, `Providers` (React Query + Theme), `Header`, `main#conteudo-principal` com `pb-[calc(4rem+env(safe-area-inset-bottom))] sm:pb-6`, `BottomNav` (mobile), `Rodape`, `next/font` `Inter` (corpo) + `Source_Serif_4` (títulos) com `variable: "--fonte-corpo"` / `"--fonte-titulo"`, `className={`${fonteCorpo.variable} ${fonteTitulo.variable} scroll-smooth`}`
- `components/Header.tsx`: **shadcn** `NavigationMenu` (desktop) + `Sheet` (mobile hamburger → `Dialog`/`Sheet` Radix), busca com `Command` (21st) ou `SearchBar` shadcn, avatar/menu com `DropdownMenu`, `ThemeToggle`, `useAuth` para estado logado, `aria-expanded`/`aria-controls` no hamburger, `focus-visible:ring` em todos interativos, `touch-manipulation min-h-[44px]` mobile
- `components/Rodape.tsx`: grid 4→2→1 (xl/lg/md/sm), links institucionais, RSS, newsletter signup, LGPD cookie preferences link, `pb-[env(safe-area-inset-bottom)]` mobile, `focus-visible:ring`
- `components/BottomNav.tsx`: `fixed bottom-0 inset-x-0 z-[var(--z-cabecalho)] sm:hidden`, 5 tabs (`Início`, `Comunidade`, `Radar`, `Planos`, `Conta/Entrar`), `aria-current="page"`, `pb-[env(safe-area-inset-bottom)]`, `min-h-[44px]`, `touch-manipulation`, `focus-visible:ring`, `lucide` icons (`Home`, `Users`, `Compass`, `Crown`, `User`)
- `components/ThemeToggle.tsx`: shadcn `Button` variant `ghost` + `Sun`/`Moon` icons, `next-themes` `useTheme`, `data-theme` toggle
- `components/BannerConsentimentoCookies.tsx`: shadcn `Dialog`/`AlertDialog` com 3 categorias (essenciais/analytics/personalizacao), `localStorage` + sync backend via `api.ts`
- `components/PularParaConteudo.tsx`: skip link `#conteudo-principal` com `focus-visible:ring`

### FRENTE C — Componentes UI Primitives (dono de `components/ui/*` — 25+ componentes)
Cada componente: **shadcn via MCP** → portar para tokens `var(--cor-*)` + `cva` + `cn` + `lucide` + `focus-visible:ring` + `motion-reduce:transition-none` + `touch-manipulation min-h-[44px]` mobile. Props/rotas existentes intactas.
Lista: `Button`, `Card` (`CardHeader`, `CardTitle`, `CardDescription`, `CardContent`, `CardFooter`), `Dialog` (`DialogTrigger`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogDescription`, `DialogFooter`), `DropdownMenu` (`DropdownMenuTrigger`, `DropdownMenuContent`, `DropdownMenuItem`, `DropdownMenuSeparator`, `DropdownMenuLabel`, `DropdownMenuCheckboxItem`, `DropdownMenuRadioGroup`, `DropdownMenuRadioItem`, `DropdownMenuShortcut`), `Tabs` (`TabsList`, `TabsTrigger`, `TabsContent`), `Tooltip` (`TooltipProvider`, `TooltipTrigger`, `TooltipContent`), `Accordion` (`Accordion`, `AccordionItem`, `AccordionTrigger`, `AccordionContent`), `Toast` (`Toaster`, `toast`), `Avatar` (`Avatar`, `AvatarImage`, `AvatarFallback`), `Label`, `Select` (`SelectTrigger`, `SelectValue`, `SelectContent`, `SelectItem`, `SelectGroup`, `SelectLabel`, `SelectSeparator`, `SelectScrollUpButton`, `SelectScrollDownButton`), `Separator`, `Slot`, `ScrollArea`, `Sheet` (`SheetTrigger`, `SheetContent`, `SheetHeader`, `SheetTitle`, `SheetDescription`, `SheetFooter`), `NavigationMenu` (`NavigationMenuList`, `NavigationMenuItem`, `NavigationMenuTrigger`, `NavigationMenuContent`, `NavigationMenuLink`, `NavigationMenuIndicator`, `NavigationMenuViewport`), `Breadcrumb` (`Breadcrumb`, `BreadcrumbList`, `BreadcrumbItem`, `BreadcrumbLink`, `BreadcrumbPage`, `BreadcrumbSeparator`, `BreadcrumbEllipsis`), `Pagination` (`Pagination`, `PaginationContent`, `PaginationItem`, `PaginationPrevious`, `PaginationNext`, `PaginationEllipsis`), `DataTable` (TanStack Table + shadcn `ColumnDef`, sorting, filtering, pagination), `Form` (React Hook Form + Zod + shadcn `FormField`, `FormItem`, `FormLabel`, `FormControl`, `FormDescription`, `FormMessage`), `Input`, `Textarea`, `Checkbox`, `RadioGroup`, `Switch`, `Slider`, `Popover`, `HoverCard`, `Menubar`, `ContextMenu`, `Command`, `Calendar`, `DatePicker`, `Alert`, `Badge`, `Skeleton`, `Progress`, `Resizable`, `Sonner` (toast), `Drawer` (vaul), `Carousel` (embla)

### FRENTE D1 — Páginas Núcleo (dono de `app/page`, `app/comunidade/*`, `app/radar/*`, `app/planos/*`, `app/noticia/*`)
- `app/page.tsx`: Hero editorial (notícia principal em destaque — **ousadia no hero** §1.3), rio de notícias (grid `lg:grid-cols-[minmax(0,1fr)_330px]` sidebar), `BlocoEditoria` carrossel mobile, `MaisLidas` sticky sidebar, `CartaoEsqueleto` skeleton loading, `prefers-reduced-motion` respeitado
- `app/comunidade/page.tsx`: lista publicações com `DataTable` shadcn (filtros, paginação, deep-link query string), `PublicacaoCard` shadcn `Card`
- `app/comunidade/nova/page.tsx`: formulário `Form` shadcn + `Textarea` + `Select` categoria + `Button` submit, validação Zod, erro inline + foco 1º erro
- `app/comunidade/[id]/page.tsx`: `DetalheNoticia` com `ReadingProgress`, `ShareButtons`, `PorQueEstouVendoIsso`, comentários `Accordion`/`Tabs`
- `app/radar/page.tsx`: tendências `Card` grid, evolução histórica `Recharts` (21st chart component), localidades salvas `Tabs` + `Button` add/remove
- `app/planos/page.tsx`: **21st Pricing Table** component adaptado, `Button` CTA "Assinar Premium", `Card` features comparativas, `Badge` "Popular"
- `app/noticia/cluster/[id]` + `item/[id]`: `DetalheNoticia` completo, `JsonLd` `NewsArticle`, `ImageObject`, `BreadcrumbList`, fontes agrupadas `Tabs`

### FRENTE D2 — Páginas Auth/Onboarding/Admin (dono de `app/cadastro`, `app/login`, `app/onboarding`, `app/minha-conta`, `app/lista-de-espera`, `app/jornalista/*`, `app/admin/*`, `app/autor/*`, `app/empresa`, `app/paginas/[slug]`, `app/privacidade/*`, `app/recuperar-senha`, `app/redefinir-senha`, `app/verificar-email`, `app/not-found`)
- Auth: `Form` shadcn + `Input` (email/senha) + `Button` submit + `Link` "Esqueci senha" + `Card` wrapper, `autocomplete`/`type` corretos, placeholder `…`, erro inline + foco 1º erro, `text-[16px]` mobile (anti-zoom iOS)
- Onboarding: `Tabs` interesses + `Select` localidade + `RadioGroup` canal, `Button` "Pular" + "Salvar"
- Minha conta: `Tabs` (Assinatura/Pagamentos/Perfil/Preferências), `DataTable` histórico pagamentos, `Button` cancelar com confirmação
- Admin: `NavigationMenu` lateral (desktop) + `Sheet` (mobile), `DataTable` usuários/assinaturas/planos/robôs/métricas, `Dialog` confirmar ações destrutivas, `Badge` status
- Autor/Empresa: `Card` perfil, `Tabs` publicações/métricas, `Button` seguir/editar
- Privacidade: `Accordion` seções, `Form` preferências cookies (sync backend)
- 404: `Card` amigável + `Link` home + `Button` "Voltar"

### FRENTE E — Design Spec + 2-Pass Frontend-Design (dono de `design-spec.md`)
**Pass 1 — Plano:**
- Paleta base (6 hex nomeados): `--cor-primaria: #1E3A8A` (azul editorial profundo), `--cor-primaria-hover: #1E40AF`, `--cor-primaria-suave: #DBEAFE`, `--cor-secundaria: #0F172A` (near-black texto), `--cor-sucesso: #059669`, `--cor-alerta: #D97706`, `--cor-erro: #DC2626`, `--cor-fundo: #FDFBF7` (off-white papel jornal), `--cor-fundo-elevado: #FFFFFF`, `--cor-borda: #E5E7EB`, `--cor-texto: #111827`, `--cor-texto-suave: #6B7280`, `--cor-texto-invertido: #F9FAFB`, `--cor-foco: #2563EB`, `--cor-sombra: 0 0 0 rgba(0,0,0,0)`, `--cor-vidro: rgba(255,255,255,0.8)`, `--gradiente-marca: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%)` — **não creme/terracota genérico**
- Tipografia: `Source_Serif_4` (títulos — identidade jornalística) + `Inter` (corpo — legibilidade digital), scale: `text-xs/text-sm/text-base/text-lg/text-xl/text-2xl/text-3xl/text-4xl` com `font-normal/font-medium/font-semibold/font-bold`
- Layout concept: "Rio editorial responsivo — hero notícia principal + grid assimétrico 2/1 desktop, carrossel mobile, sidebar sticky `lg:sticky top-24`, breakpoints 360/768/1024/1440"
- Wireframe ASCII (mobile 360 → desktop 1440):
  ```
  MOBILE (360)                    DESKTOP (1440)
  ┌─────────────────────┐         ┌─────────────────────────────────────┐
  │ Header (hamburger)  │         │ Header (logo | nav | busca | avatar)│
  ├─────────────────────┤         ├──────────────────┬─────────────────┤
  │ HERO: Notícia principal     │ Hero: Notícia      │ Mais Lidas      │
  │   (imagem + título)  │         │   principal       │ (sticky)        │
  ├─────────────────────┤         ├──────────────────┼─────────────────┤
  │ Bloco Editoria 1    │         │ Bloco Editoria   │ Sidebar:        │
  │   (carrossel)       │         │   (grid 2 col)   │  - Mais Lidas   │
  ├─────────────────────┤         ├──────────────────┤  - Newsletter   │
  │ Bloco Editoria 2    │         │ Bloco Editoria   │  - Tags         │
  │   (carrossel)       │         │   (grid 2 col)   │  - Anúncio      │
  ├─────────────────────┤         ├──────────────────┴─────────────────┤
  │ Bottom Nav (5 tabs) │         │ Rodapé (grid 4 col)                │
  └─────────────────────┘         └─────────────────────────────────────┘
  ```
- Princípios: (1) Notícia como protagonista — hero abre com conteúdo real, não números; (2) Serifa carrega autoridade — `Source_Serif_4` só em headings; (3) Ousadia contida — um elemento de destaque (hero), resto disciplinado; (4) Mobile-first real — touch 44px, safe-area, carrossel no mobile; (5) Copy ativa 2ª pessoa — "Assine Premium", "Leia agora", "Personalize seu feed"

**Pass 2 — Revisão anti-genérica:**
- Verificar cada eixo contra defaults §1.2: evitar fundo creme `#F4F1EA` + serifada + terracota; evitar near-black + ácido; evitar grid cards idênticos; evitar ALL-CAPS eyebrow; evitar `→` em links; evitar `01/02/03` não-sequencial
- Documentar o que mudou e por quê em `design-spec.md` seção "Revisão anti-genérica"

## Áreas/arquivos
- `frontend/` inteiro (exceto `lib/api.ts` e `lib/hooks/useIsMobile.ts` que podem ser mantidos/adaptados)
- `backend/` — **sem diff**
- `frontend/lib/api.ts` — **sem diff**

## Interfaces
- `lib/api.ts` — contrato inalterado com Django (endpoints, tipos, erros)
- `lib/auth-context.tsx` — `useAuth` preservado
- `lib/site.ts` — `SITE_URL`, `IMAGEM_OG_PADRAO` preservados
- `lib/schema.ts` — `organizationJsonLd`, `newsArticleJsonLd`, etc. preservados
- `lib/cookie-consent.ts` — `permiteCategoria` preservado

## Critérios técnicos
1. `tsc --noEmit -p frontend/tsconfig.json` → exit 0
2. `npm run build --prefix frontend` → exit 0, 32/32 rotas
3. `git diff HEAD --stat -- backend/ frontend/lib/api.ts` → vazio
4. `command.md` fresco → 0 blocker/major (auditoria por arquivo em `test-report.md`)
5. `chrome-devtools-mcp` → screenshots 360/768/1024/1440 + dark/light + tab-order + AA (ou fallback estático documentado)
6. 5 skills runtime evidenciadas: shadcn MCP demos, 21st catálogo/get_component, frontend-design 2-pass documentado, command.md fetch, chrome-devtools workflow

## Não-objetivos
- PWA/manifest/service-worker
- Novas rotas/endpoints
- Mudança de lógica de negócio
- Backend modifications

## Restrições técnicas
- `prefers-reduced-motion` global (CSS `@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }`)
- `:focus-visible` ring sempre visível (`ring-2 ring-[var(--cor-foco)] ring-offset-2`)
- AA contraste ≥4.5:1 (verificar via `command.md` + chrome-devtools)
- `color-scheme: light dark` + `data-theme` no `html`
- Sem `transition: all`, sem `outline: none` sem substituto, sem `div onClick`

## DoD
- [ ] Critérios 1–6
- [ ] Testes passando
- [ ] Revisão aprovada
- [ ] Docs atualizadas
- [ ] History coerente