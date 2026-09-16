# Task Plan - Frente D1: Páginas Núcleo

## Objetivo
Reescrever 7 páginas principais em `frontend/app/` usando **Tailwind + shadcn/ui + 21st.dev patterns** com tokens `var(--cor-*)`.

## Páginas a Implementar

### 1. `app/page.tsx` (Home - Hero editorial + Rio de notícias)
- [ ] Hero: Notícia principal em destaque (imagem + título + lead + "Leia mais") — ousadia no hero
- [ ] Rio: Grid assimétrico `lg:grid-cols-[minmax(0,1fr)_330px]` — principal (2/3) + sidebar (1/3)
- [ ] Sidebar: `MaisLidas` (sticky `lg:sticky top-24`), `BlocoEditoria` carrossel mobile (`scroll-snap-x`), `CartaoEsqueleto` skeleton loading
- [ ] Mobile: carrossel horizontal editorias (`BlocoEditoria` com `overflow-x-auto scroll-snap-x`), single col
- [ ] Breakpoints: 360/768/1024/1440
- [ ] `prefers-reduced-motion` respeitado

### 2. `app/comunidade/page.tsx` (Lista publicações)
- [ ] `DataTable` shadcn (TanStack Table) com: colunas (Título, Autor, Categoria, Status, Data), sorting, filtering, paginação, deep-link query string
- [ ] `PublicacaoCard` shadcn `Card` com badge status (rascunho/publicado/destaque)
- [ ] Filtros: busca, categoria, autor, status
- [ ] Ações: criar nova (link `/comunidade/nova`), editar (próprio autor)

### 3. `app/comunidade/nova/page.tsx` (Criar publicação)
- [ ] `Form` shadcn + React Hook Form + Zod
- [ ] Campos: `Input` título, `Select` categoria, `Textarea` conteúdo, `Checkbox` destaque, `Button` submit
- [ ] Validação Zod: título obrigatório (min 5), conteúdo min 100 chars
- [ ] Erro inline + foco no 1º erro (`form:invalid:first`)
- [ ] `text-[16px]` mobile (anti-zoom iOS)

### 4. `app/comunidade/[id]/page.tsx` (Detalhe publicação)
- [ ] `DetalheNoticia` com: título, autor (link `/autor/[id]`), data, `ReadingProgress`, `ShareButtons`, `PorQueEstouVendoIsso`
- [ ] Conteúdo com tipografia editorial (`prose` style customizado tokens)
- [ ] Comentários: `Accordion` shadcn por thread, `Form` resposta, paginação
- [ ] `Badge` "Premium" se aplicável

### 5. `app/radar/page.tsx` (Tendências + Evolução + Localidades)
- [ ] **Tendências**: Grid `Card` shadcn (categoria, nº notícias, nº fontes, sparkline)
- [ ] **Evolução histórica**: `Recharts` (21st chart component) — linha temporal por categoria/localidade
- [ ] **Localidades salvas**: `Tabs` shadcn + `Button` add/remove, `Input` busca CEP/cidade
- [ ] `Badge` "Premium" em evolução histórica (recurso pago)

### 6. `app/planos/page.tsx` (Pricing - 21st Pricing Table)
- [ ] **21st Pricing Table** adaptado: 2 colunas (Semestral R$30/180d, Anual R$50/365d)
- [ ] `Card` features comparativas (checklist icons `lucide-check`)
- [ ] `Badge` "Mais popular" no Anual
- [ ] `Button` CTA "Assinar Premium" (variant `premium`) → `/api/assinatura/assinar`
- [ ] FAQ `Accordion` shadcn

### 7. `app/noticia/cluster/[id]/page.tsx` + `app/noticia/item/[id]/page.tsx`
- [ ] `DetalheNoticia` completo: hero imagem, título, lead, fontes agrupadas (`Tabs` shadcn), `JsonLd` `NewsArticle` + `ImageObject` + `BreadcrumbList`
- [ ] `ReadingProgress` topo, `ShareButtons` flutuante, `PorQueEstouVendoIsso`
- [ ] Fontes: cards com link original, badge fonte, timestamp

## Regras Técnicas
- [ ] Server Components onde possível (SEO, data fetching via `lib/api.ts`)
- [ ] Client Components só onde há interatividade (forms, tabs, carrossel, accordion)
- [ ] `generateMetadata` em cada rota (SEO técnico preservado)
- [ ] `lib/api.ts` **inalterado** - usar contratos existentes
- [ ] `prefers-reduced-motion` + `focus-visible` + AA contrast
- [ ] Touch 44px mobile, `env(safe-area-inset-*)`
- [ ] `text-wrap: balance` headings, `truncate`/`line-clamp` cards

## Validação
- [ ] `tsc --noEmit` passa
- [ ] `npm run build` 32/32 páginas

## Ordem de Execução
1. Home (app/page.tsx) - maior complexidade visual
2. Comunidade list (app/comunidade/page.tsx) - DataTable TanStack
3. Comunidade nova (app/comunidade/nova/page.tsx) - RHF + Zod
4. Comunidade detalhe (app/comunidade/[id]/page.tsx)
5. Radar (app/radar/page.tsx) - Recharts
6. Planos (app/planos/page.tsx) - Pricing Table
7. Notícia cluster/item (app/noticia/cluster/[id]/page.tsx + app/noticia/item/[id]/page.tsx)

## Componentes Novos Necessários
- [ ] `DataTable` com TanStack Table (para comunidade)
- [ ] `Sparkline` component (para radar)
- [ ] `PricingTable` component (para planos)
- [ ] `Prose` typography component (para detalhe notícia)