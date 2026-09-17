# Design Spec — 20260916-1430-frontend-rebuild-5skills

## Pass 1 — Plano de Design

### 1. Paleta Base (6 hex nomeados + variações)

| Token | Light | Dark | Uso |
|-------|-------|------|-----|
| `--cor-primaria` | `#1E3A8A` | `#818CF8` | Brand principal, CTAs, links, foco |
| `--cor-primaria-hover` | `#1E40AF` | `#A5B4FC` | Hover estados primários |
| `--cor-primaria-suave` | `#DBEAFE` | `#161D33` | Backgrounds sutis, badges, pills |
| `--cor-secundaria` | `#0F172A` | `#F8FAFC` | Texto principal, headings |
| `--cor-sucesso` | `#059669` | `#6EE7B7` | Sucesso, confirmado, ativo |
| `--cor-alerta` | `#D97706` | `#FBBF24` | Atenção, pendente, warning |
| `--cor-erro` | `#DC2626` | `#EF4444` | Erro, destrutivo, crítico |
| `--cor-fundo` | `#FDFBF7` | `#07090E` | Background página (papel jornal off-white) |
| `--cor-fundo-elevado` | `#FFFFFF` | `#0D1117` | Cards, modais, dropdowns |
| `--cor-borda` | `#E5E7EB` | `#1E2635` | Bordas, divisores, inputs |
| `--cor-texto` | `#111827` | `#F2F4F8` | Texto principal |
| `--cor-texto-suave` | `#6B7280` | `#98A2B3` | Texto secundário, placeholders, meta |
| `--cor-texto-invertido` | `#F9FAFB` | `#030712` | Texto sobre primário/erro/sucesso |
| `--cor-foco` | `#2563EB` | `#60A5FA` | Focus ring, acessibilidade |
| `--cor-sombra` | `0, 0, 0` | `0, 0, 0` | RGB puro para `rgba(var(--cor-sombra), opacity)` |
| `--cor-vidro` | `rgba(255,255,255,0.8)` | `rgba(13,17,23,0.8)` | Glassmorphism header/overlays |
| `--gradiente-marca` | `linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%)` | `linear-gradient(135deg, #818CF8 0%, #22D3EE 100%)` | Brand accents, avatar, hero |

> **Anti-genérico:** Evitado creme `#F4F1EA` + terracota `#D97757` (default Anthropic); evitado near-black + ácido. Escolha: azul editorial profundo (`#1E3A8A`) + off-white papel (`#FDFBF7`) — identidade jornalística brasileira.

### 2. Tipografia e Papéis

| Papel | Família | Tamanhos (scale) | Pesos | Line-height |
|-------|---------|------------------|-------|-------------|
| **Display/Headings** | `Source_Serif_4` (via `next/font`, `variable: "--fonte-titulo"`) | `text-2xl` → `text-4xl` (`clamp(1.9rem, 3vw+1rem, 2.6rem)`) | `650` (semibold) | `1.05` (compact) |
| **Corpo/UI** | `Inter` (via `next/font`, `variable: "--fonte-corpo"`) | `xs` `0.75rem` → `base` `1rem` → `xl` `1.5rem` | `400` normal, `600` medium, `700` bold | `1.5` (padrão), `1.25` (compact), `1.7` (solta) |
| **Mono/Dados** | `JetBrains Mono` (fallback `ui-monospace`) | `xs` `sm` | `400` `500` | `1.5` |

> **Escala fluida:** `h1` `clamp(1.9rem, 3vw+1rem, 2.6rem)`, `h2` `clamp(1.5rem, 2.5vw+1rem, 2rem)`, `h3` `clamp(1.25rem, 2vw+0.8rem, 1.5rem)`. `text-wrap: balance` em todos headings.

### 3. Conceito de Layout (1 frase + ASCII)

**Conceito:** "Rio editorial responsivo — hero notícia principal + grid assimétrico 2/1 desktop, carrossel mobile, sidebar sticky `lg:sticky top-24`, breakpoints 360/768/1024/1440."

#### Wireframe ASCII

```
MOBILE (360px)                              DESKTOP (1440px)
┌─────────────────────┐                     ┌─────────────────────────────────────┐
│ Header              │                     │ Header (logo | nav | busca | avatar)│
│ [☰] Portal· [🔍]   │                     ├──────────────────┬─────────────────┤
├─────────────────────┤                     │ HERO: Notícia    │ Mais Lidas      │
│ HERO: Notícia       │                     │   principal      │ (sticky top-24) │
│   principal         │                     │   (imagem +      │  1. Título      │
│   (img + título)    │                     │    título + lead)│  2. Título      │
├─────────────────────┤                     ├──────────────────┼─────────────────┤
│ Bloco Editoria 1    │                     │ Bloco Editoria   │ Sidebar:        │
│   [███] [███]       │                     │   (grid 2 col)   │  - Mais Lidas   │
│   ← carrossel →     │                     │  ┌─────┬─────┐   │  - Newsletter   │
├─────────────────────┤                     │  │Art.1│Art.2│   │  - Tags         │
│ Bloco Editoria 2    │                     │  ├─────┼─────┤   │  - Anúncio      │
│   [███] [███]       │                     │  │Art.3│Art.4│   │                 │
│   ← carrossel →     │                     │  └─────┴─────┘   │                 │
├─────────────────────┤                     ├──────────────────┴─────────────────┤
│ Bottom Nav (5 tabs) │                     │ Rodapé (grid 4 col: Institucional, │
│ [🏠] [👥] [🧭] [👑] [👤]│                    Produto, Legal, Redes)            │
└─────────────────────┘                     └─────────────────────────────────────┘
```

**Breakpoints:**
- `360px` — mobile single col, bottom nav, carrossel editorias
- `768px` — tablet, bottom nav hidden, header nav visible, grid 2 col
- `1024px` — desktop, sidebar sticky, grid assimétrico `lg:grid-cols-[minmax(0,1fr)_330px]`
- `1440px` — wide, max-width container `1280px`, hero imagem maior

### 4. Princípios (o que torna esta página única)

1. **Notícia como protagonista** — Hero abre com conteúdo real (imagem + título + lead da notícia mais importante), não números genéricos nem cards decorativos. Ousadia contida: **um** elemento de destaque (hero), resto disciplinado.
2. **Serifa carrega autoridade** — `Source_Serif_4` exclusivamente em headings (`h1`–`h3`, `.cartao-titulo`, `.cartao-hero-titulo`); `Inter` em todo corpo/UI. Identidade jornalística brasileira (como *Folha*, *Estadão*, *NYT*).
3. **Mobile-first real** — Touch targets ≥44px (`min-h-[44px]`), `touch-manipulation`, `env(safe-area-inset-*)`, carrossel horizontal (`scroll-snap`) para editorias no mobile, bottom nav fixo `sm:hidden`.
4. **Copy ativa, 2ª pessoa, CTA nomeado** — "Assine Premium" (não "Continuar"), "Personalize seu feed" (não "Configurar"), "Leia a matéria completa" (não "Ver mais"). Voz ativa, sem filler.
5. **Motion só responde a ação** — Zero animações de entrada (`fade-in-up` em tudo = genérico). Apenas: (a) hero imagem `transform: scale(1.02)` no hover desktop, (b) Sheet/Drawer slide `300ms`, (c) toast slide-in, (d) `prefers-reduced-motion` desliga tudo.
6. **Estrutura = informação** — Grid assimétrico 2/1 comunica hierarquia (principal vs. secundário); carrossel mobile comunica "há mais"; numbered pills `01/02/03` **apenas** em sequências reais (onboarding steps), nunca em conteúdo editorial.

---

## Pass 2 — Revisão Anti-Genérica

### Checklist contra defaults §1.2 (frontend-design)

| Default genérico | Nossa escolha | Por que mudou |
|---|---|---|
| Fundo creme `#F4F1EA` + serifada + terracota `#D97757` | Off-white papel `#FDFBF7` + azul editorial `#1E3A8A` | Cremes/terracotas = default Anthropic/Claude; azul editorial = identidade jornalística brasileira |
| Near-black + acento ácido | Off-white + azul profundo | Near-black = default "SaaS dark mode"; off-white = papel jornal, legibilidade diurna |
| Grade de cards idênticos com mesma sombra | Grid assimétrico 2/1 + carrossel mobile | Cards idênticos = "SaaS-card kit"; assimetria comunica hierarquia editorial |
| Eyebrow ALL-CAPS com tracking em todo heading | Sem eyebrow; heading serifado direto | ALL-CAPS = template tell; serifa já comunica peso |
| `→` em todo link | Setas **apenas** em breadcrumbs e "Leia mais" (ação) | Seta universal = tell de geração; links navegam, setas indicam direção |
| `01/02/03` em conteúdo não-sequencial | Números **apenas** em onboarding (passo 1/2/3) | Números fora de sequência = decoração vazia |
| `transition: all` / `fade-in-up` em tudo | Motion só: hero hover scale, Sheet slide, toast slide | Animação decorativa = genérico; motion responde a ação do usuário |
| Sombra suave `rgba(0,0,0,.1)` em tudo | 3 níveis semânticos `--sombra-1/2/3` + `--cor-sombra` RGB | Sombra única = flat; níveis comunicam elevação real |
| Tinted near-black `#0B0B0B` no dark | `#07090E` papel escuro + tinta clara `#F2F4F8` | Near-black = default; papel escuro = legibilidade noturna jornalística |

### Decisões documentadas

1. **Paleta:** 6 hex base + variações hover/soft/foreground = 18 tokens de cor. Não 4 (muito pouco) nem 20+ (verbose). Cada token tem papel semântico claro.
2. **Tipografia:** 2 famílias apenas (`Source_Serif_4` + `Inter`). `JetBrains Mono` só em código/dados. Sem terceira família decorativa.
3. **Layout:** Assimétrico 2/1 desktop → carrossel mobile. Não grid 12 col simétrico. Sidebar `lg:sticky` comunica "conteúdo relacionado fica acessível".
4. **Componentes:** shadcn/ui v4 como base (acessível, auditado). 21st.dev para blocos complexos (Pricing, Hero, Dashboard). **Portar, não colar** — adaptar a `var(--cor-*)`.
5. **Copy:** "Assine Premium", "Personalize seu feed", "Leia agora", "Siga este autor". Verbos ativos, 2ª pessoa, resultado nomeado.

---

## Evidência de Uso das 5 Skills

| Skill | Como foi aplicada |
|---|---|
| **frontend-design** | Este documento = Pass 1 (plano) + Pass 2 (revisão anti-genérica) |
| **shadcn-ui-mcp-server** | Componentes UI primitives (Frente C) via `npx @jpisnice/shadcn-ui-mcp-server` demos/metadados |
| **21st-dev/magic-mcp** | Blocos: Hero (`app/page`), Pricing (`app/planos`), Dashboard (`app/admin/metricas`, `app/radar`) via `search`/`get_component` |
| **web-design-guidelines** | `command.md` fresco fetchado antes de cada validação; auditoria por arquivo em `test-report.md` |
| **chrome-devtools-mcp** | Validação final: `navigate_page` → `wait_for` → `take_snapshot` → `click`/`fill` → `take_screenshot` 360/768/1024/1440 + dark/light + tab-order + AA |

---

## Próximos Passos (Implementação)

1. **Frente A ✅** — Tailwind setup + tokens (concluído: `tailwind.config.ts`, `postcss.config.js`, `components.json`, `lib/utils.ts`, `globals.css` compatível)
2. **Frente E ✅** — Design spec (este documento)
3. **Frente B** — Shell shadcn/21st (`Header`, `Rodape`, `BottomNav`, `app/layout`, `ThemeToggle`, `BannerConsentimentoCookies`, `PularParaConteudo`)
4. **Frente C** — UI primitives 25+ (`components/ui/*`)
5. **Frente D1** — Páginas núcleo (`app/page`, `comunidade`, `radar`, `planos`, `noticia`)
6. **Frente D2** — Páginas auth/onboarding/admin
7. **Validação** — `tsc 0` + `build 32/32` + `command.md` 0 blocker/major + chrome-devtools screenshots