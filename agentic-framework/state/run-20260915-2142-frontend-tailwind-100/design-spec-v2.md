# Design Spec v2 — 20260915-2142 (Tailwind+shadcn 100%)

> Autoridade: `.claude/skills/frontend-portal/SKILL.md` + 5 origens cruas (fetch 2026-09-15). Base: `design-spec.md` v1 (rio + sidebar). Migração autorizada.

## 0. Decisão
CSS puro → **Tailwind CSS 3.4.17 + shadcn/ui v4 (Radix)** sobre tokens `--cor-*` existentes. `@tailwind base/components/utilities` no topo de `globals.css`, `theme.extend.colors: var(--cor-*)`, `darkMode: ["class", '[data-theme="dark"]']` casando `layout.tsx:77` anti-flash. `globals.css` vira camada de tokens, não é deletado. `next/font` Inter/Source_Serif_4 mantidos.

## 1. Paleta (6 hex, §1 v1 preservado)
`Papel #F6F7F9/#07090E`, `Tinta #0B0D12/#F2F4F8`, `Rio #4338CA/#818CF8`, `Plantão #E10600/#FF453A`, `Ouro #B8954A/#D4B36A` (texto AA `#8A6D2B`), `Mata #0F6F5C/#6EE7B7`. Suportes `borda #E4E8F0/#1E2635`, `texto-suave #5B6472/#98A2B3`. Gradiente marca só `topo__orbe`. AA ≥4.5:1.

## 2. Tipos
`Inter` corpo/UI, `Source_Serif_4` só H1 home + títulos card/artigo. `text-wrap: balance`, `tracking-[-0.025em]`, `max-w 80ch` (artigo 62–68ch/1.7). Tailwind `fontFamily: {corpo: var(--fonte-corpo), titulo: var(--fonte-titulo)}`.

## 3. Conceito
> **Rio cronológico confiável à esquerda, sidebar de serviço à direita — hierarquia por posição+tipografia, não por sombras.**

Wireframes v1 mantidos; Tailwind utilitários sem quebrar `container`/`topo__trilhas`/`portal-layout` (contrato).

## 4. 3 ritmos (anti SaaS-kit)
- `grade-noticias` 3col imagem+gradiente
- `lista-compacta` horizontal numerada `01..12` sem thumb
- `editoria-grade` filete `border-l-3`

## 5. Anti-genérico (5 sinais)
Sem creme `#F4F1EA`+terracota `#D97757`, sem near-black+neon, sem cards idênticos `rounded+shadow`, sem `→` fora de `secao-ver-tudo`/`editoria-ver`, sem `01/02/03` fora de sequência real.

## 6. Motion
1 entrada `banner-atualizacao` + hovers `150ms` `transform/opacity`; `motion-reduce:`; nunca `transition-all`.

## 7. Tokens→Tailwind
`colors: {border: var(--cor-borda), background: var(--cor-fundo), foreground: var(--cor-texto), primary: var(--cor-primaria), premium: var(--cor-premium), ...}`, `borderRadius: var(--raio-*)`, `spacing: var(--espaco-*)`, `boxShadow: var(--sombra-*)`, `zIndex: var(--z-*)`.

## 8. Checklist Tailwind guardrails
- [ ] `content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"]`
- [ ] `cn()` = `clsx+twMerge`
- [ ] `shadcn add button card dialog dropdown-menu tabs tooltip accordion toast badge avatar separator skeleton` cobrindo `components/ui/*`
- [ ] `cva` variantes preservando `variante/tamanho` props existentes
- [ ] `lucide-react` ícones
- [ ] `prefers-reduced-motion` + `:focus-visible:ring` + `scroll-margin-top` preservados
