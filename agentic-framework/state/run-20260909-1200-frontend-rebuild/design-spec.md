# Design Spec — run 20260909-1200-frontend-rebuild (portal de notícias)

> Status: somente especificação. Nenhum CSS/componente foi alterado.
> Implementador (`frontend-ui-executor`): reescrever `frontend/app/globals.css` seguindo estes tokens e regras.
> Backend (`lib/api.ts`, `lib/queries.ts`): somente-leitura, sem mudanças.
> Base existente: `layout.tsx` já provê `next/font` (`--fonte-corpo` = Inter, `--fonte-titulo` = Source_Serif_4), `data-theme` + script anti-flash, skip-link `#conteudo-principal`. Preservar tudo isso.

## 1. Princípios

1. Editorial moderno: serifada só em títulos/hero, Inter em corpo/UI.
2. Mobile-first, CSS puro, variáveis CSS como única fonte de verdade.
3. Light é padrão; dark espelha todos os tokens (nunca hardcode hex fora de `:root`).
4. Contraste AA (4.5:1 texto, 3:1 UI grande) nos dois temas.
5. Toque ≥ 40px, foco sempre visível, `prefers-reduced-motion` desliga tudo.
6. Sem `100vw` sem compensação; sem `@import` remoto; imagens `max-width:100%`.

## 2. Paleta v2 (tokens `--cor-*`)

### 2.1 Light (`:root`)

```css
:root {
  /* Neutros — papel + tinta */
  --cor-fundo: #f6f7f9;
  --cor-fundo-elevado: #ffffff;
  --cor-fundo-card: #ffffff;
  --cor-fundo-suave: #eef1f6;      /* NOVO: hover neutro / trilho skeleton */
  --cor-texto: #111318;            /* ~15.5:1 sobre #ffffff */
  --cor-texto-suave: #5b6472;      /* ~5.9:1 sobre #ffffff — OK AA */
  --cor-borda: #e4e8f0;
  --cor-borda-forte: #c9d1e0;      /* NOVO: divisórias/foco hover */

  /* Primária — índigo editorial */
  --cor-primaria: #4338ca;         /* 8.0:1 com texto branco — OK AA */
  --cor-primaria-hover: #3730a3;
  --cor-primaria-ativa: #312e81;   /* NOVO: estado :active */
  --cor-primaria-suave: #eef0fe;
  --cor-primaria-texto-sobre: #ffffff;

  /* Acento — vermelho/coral editorial (urgente, eyebrow alternativa, premium links) */
  --cor-destaque: #e10600;         /* 5.0:1 com branco — OK AA p/ texto */
  --cor-destaque-hover: #b80500;
  --cor-destaque-suave: #fff1f0;
  --cor-destaque-texto-sobre: #ffffff;

  /* Semânticas */
  --cor-erro: #c81e1e;             /* AJUSTE v2: #e10600 puro falha AA em fundo suave; reservar #e10600 p/ acento grande */
  --cor-erro-suave: #fdecec;       /* NOVO */
  --cor-sucesso: #0f6f5c;          /* ~5.3:1 sobre branco — OK AA */
  --cor-sucesso-suave: #e6f4ef;    /* NOVO */
  --cor-aviso: #92400e;            /* NOVO */
  --cor-aviso-suave: #fef3c7;      /* NOVO */
  --cor-info: #1d4ed8;             /* NOVO */
  --cor-info-suave: #eff6ff;       /* NOVO */

  /* Marca / premium */
  --cor-premium: #8a6d2b;          /* AJUSTE v2: #b8954a falha AA como texto; usar como texto escuro, dourado claro só p/ fundo */
  --cor-premium-suave: #faf3e3;    /* NOVO */
  --cor-foco: #4338ca;             /* anel de foco = primária no light */
  --cor-sobre-primaria: #ffffff;

  /* Skeleton / sombra base / vidro / gradientes discretos */
  --cor-skeleton-base: #e9edf3;
  --cor-skeleton-brilho: #ffffff;
  --cor-sombra: 30, 34, 60;
  --cor-overlay: rgba(17, 19, 24, 0.45);
  --gradiente-marca: linear-gradient(135deg, #4338ca 0%, #06b6d4 100%);
  --gradiente-hero: radial-gradient(1200px 320px at 50% -80px, var(--cor-primaria-suave), transparent);
  --vidro: rgba(255, 255, 255, 0.72);
}
```

### 2.2 Dark (`:root[data-theme="dark"]` + fallback `@media (prefers-color-scheme: dark)` → `:root:not([data-theme="light"])`)

```css
:root[data-theme="dark"] {
  --cor-fundo: #07090e;
  --cor-fundo-elevado: #0d1117;
  --cor-fundo-card: #0d1117;
  --cor-fundo-suave: #161c28;
  --cor-texto: #f2f4f8;            /* ~15:1 sobre #07090e */
  --cor-texto-suave: #98a2b3;      /* ~7:1 sobre #07090e — OK AA */
  --cor-borda: #1e2635;
  --cor-borda-forte: #33405a;

  --cor-primaria: #818cf8;
  --cor-primaria-hover: #a5b4fc;
  --cor-primaria-ativa: #c7d2fe;
  --cor-primaria-suave: #161d33;
  --cor-primaria-texto-sobre: #0b0d12;

  --cor-destaque: #ff453a;
  --cor-destaque-hover: #ff6b61;
  --cor-destaque-suave: #2a1413;
  --cor-destaque-texto-sobre: #1a0a09;

  --cor-erro: #ff6b61;
  --cor-erro-suave: #2a1413;
  --cor-sucesso: #34d399;
  --cor-sucesso-suave: #0b241c;
  --cor-aviso: #fbbf24;
  --cor-aviso-suave: #2a2111;
  --cor-info: #60a5fa;
  --cor-info-suave: #0f1e33;

  --cor-premium: #d4b36a;
  --cor-premium-suave: #241d0c;
  --cor-foco: #a5b4fc;
  --cor-sobre-primaria: #0b0d12;

  --cor-skeleton-base: #141a26;
  --cor-skeleton-brilho: #1e2635;
  --cor-sombra: 0, 0, 0;
  --cor-overlay: rgba(0, 0, 0, 0.6);
  --gradiente-marca: linear-gradient(135deg, #818cf8 0%, #22d3ee 100%);
  --gradiente-hero: radial-gradient(1200px 320px at 50% -80px, #161d33, transparent);
  --vidro: rgba(13, 17, 23, 0.72);
}
```

Regras:
- Todo texto usa `var(--cor-texto)` / `var(--cor-texto-suave)`; links usam `var(--cor-primaria)` (dark: `#818cf8`).
- `--cor-destaque` só para: badge `Urgente`, eyebrow de cobertura ao vivo, CTA Premium. Nunca para corpo de texto longo.
- Contraste mínimo verificado: texto principal ≥ 7:1, texto suave ≥ 4.5:1, botões primários (branco sobre índigo) ≥ 4.5:1 nos dois temas.

## 3. Tipografia (tokens `--fonte-*`)

Fontes já instaladas via `next/font` em `layout.tsx` — NÃO trocar, NÃO adicionar webfont remota:

```css
:root {
  --fonte-corpo: var(--fonte-corpo, "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif);
  --fonte-titulo: var(--fonte-titulo, "Source Serif 4", Georgia, "Times New Roman", serif);
  --fonte-mono: ui-monospace, "Cascadia Code", Menlo, Consolas, monospace; /* NOVO: metadados/código */

  --fonte-tamanho-xs: 0.75rem;    /* 12px — meta, eyebrow, selos */
  --fonte-tamanho-sm: 0.875rem;   /* 14px — corpo secundário, UI */
  --fonte-tamanho-md: 1rem;       /* 16px — corpo base */
  --fonte-tamanho-lg: 1.125rem;   /* 18px — lead, subtítulo */
  --fonte-tamanho-xl: 1.5rem;     /* 24px — h3 / título de card grande */
  --fonte-tamanho-xxl: 2rem;      /* 32px — h2 seção */
  --fonte-tamanho-display: clamp(2rem, 5vw, 3.25rem); /* NOVO: h1 hero / .seu-rio__titulo */

  --fonte-peso-normal: 400;
  --fonte-peso-medio: 500;        /* AJUSTE v2: 600→500 p/ Inter não engordar UI */
  --fonte-peso-semibold: 600;     /* NOVO */
  --fonte-peso-negrito: 700;

  --linha-altura-compacta: 1.25;  /* títulos */
  --linha-altura-padrao: 1.5;     /* UI */
  --linha-altura-solta: 1.7;      /* corpo de notícia */
}
```

Aplicação:
- `body`: Inter `md/padrão`, `letter-spacing: 0`.
- `h1/h2/h3, .cartao-titulo, .hero__titulo, .seu-rio__titulo`: `var(--fonte-titulo)`, `letter-spacing: -0.02em`, `text-wrap: balance`, peso 650–800.
- Eyebrow (`.secao-eyebrow`, `.hero__eyebrow`): Inter `xs/negrito`, `uppercase`, `letter-spacing: 0.14em`, cor primária.
- Meta de card (`categoria · fontes · data`): Inter `xs`, `uppercase`, `0.06em`, cor suave.
- Corpo de notícia (`.detalhe-corpo`): Inter `md/solta`, `max-width: 68ch`.

## 4. Espaçamento 4pt, raios, sombras, movimento (tokens `--espaco-*`, `--raio-*`, `--sombra-*`)

```css
:root {
  /* Escala 4pt — base 0.25rem; manter degraus legados */
  --espaco-0: 0.125rem;   /* 2px  — AJUSTE v2: era 0.15rem (quebra 4pt); aceitar 2px só p/ gap mínimo */
  --espaco-1: 0.25rem;    /* 4px  */
  --espaco-1-5: 0.375rem; /* 6px  — AJUSTE v2: era 0.3rem; arredondar p/ 4pt */
  --espaco-2: 0.5rem;     /* 8px  */
  --espaco-2-5: 0.625rem; /* 10px — AJUSTE v2: era 0.6rem */
  --espaco-3: 0.75rem;    /* 12px */
  --espaco-4: 1rem;       /* 16px */
  --espaco-5: 1.5rem;     /* 24px */
  --espaco-6: 2rem;       /* 32px */
  --espaco-7: 3rem;       /* 48px */
  --espaco-8: 4rem;       /* 64px */

  --raio-sm: 8px;
  --raio-md: 12px;
  --raio-lg: 16px;
  --raio-xl: 24px;        /* NOVO: hero, drawer desktop */
  --raio-completo: 999px; /* pills, avatar, botões pill */

  --sombra-1: 0 1px 2px rgba(var(--cor-sombra), 0.05);
  --sombra-2: 0 8px 24px rgba(var(--cor-sombra), 0.08);
  --sombra-3: 0 20px 48px rgba(var(--cor-sombra), 0.14);
  --anel-foco: 0 0 0 3px color-mix(in srgb, var(--cor-foco) 30%, transparent); /* NOVO (já consumido; formalizar) */

  --duracao-rapida: 120ms;
  --duracao-normal: 220ms;
  --duracao-lenta: 420ms;
  --curva-padrao: cubic-bezier(0.2, 0.7, 0.3, 1);

  /* Dimensões de componente (não são espaçamento) */
  --largura-max-modal: 520px;
  --altura-max-modal: 700px;
  --largura-min-menu: 200px;
  --largura-max-tooltip: 240px;
  --deslocamento-flutuante: 6px;
  --tamanho-botao-icone: 40px;  /* AJUSTE v2: era 36px; mínimo de toque */
  --altura-min-item-menu: 40px; /* AJUSTE v2: era 36px */
  --altura-header: 64px;        /* NOVO */
  --largura-sidebar: 320px;     /* NOVO */
}
```

## 5. Breakpoints mobile-first (480 / 768 / 1024 / 1280)

Base = 360px sem media query. Só `min-width`, em ordem crescente:

| Token / breakpoint | Largura | O que muda |
|---|---|---|
| base (0–479) | 360px ref | 1 coluna; header só marca + busca colapsável + hamburger; trilhas viram drawer/coluna; hero compacto; tabelas com scroll |
| `--bp-sm: 480px` | ≥480 | container padding 1rem→1.5rem; drawer vira bottom-sheet; botões full-width liberados p/ inline |
| `--bp-md: 768px` | ≥768 | feed 2 colunas; `secao-titulo` sobe p/ xxl; newsletter box lado a lado |
| `--bp-lg: 1024px` | ≥1024 | `portal-layout` 2 colunas (conteúdo + sidebar 320px); header mostra nav completa, hamburger some; grade 2→3 colunas conforme largura |
| `--bp-xl: 1280px` | ≥1280 | container trava em 1200px centralizado; hero padding cheio; grade 3 colunas estáveis |

```css
:root {
  --bp-sm: 480px;
  --bp-md: 768px;
  --bp-lg: 1024px;
  --bp-xl: 1280px;
  --container-max: 1200px; /* min(1200px, 100% - 2rem) */
}
```

Proibido: `@media (max-width: ...)` novo (legado usa; migrar p/ min-width), `width: 100vw`, breakpoints fora da lista (ex.: 720/900/960 legados → mapear p/ 768/1024).

## 6. Grid do portal

### 6.1 Container

```css
.container { width: min(var(--container-max), 100% - 2rem); margin-inline: auto; padding-inline: 0; }
@media (min-width: 480px) { .container { width: min(var(--container-max), 100% - 3rem); } }
```

### 6.2 Home — hero + grade + sidebar

```
main#conteudo-principal
└─ .faixa-publicidade
└─ .portal-hero (NOVO nome; herda .hero legado)
│   ├─ .hero__eyebrow + .hero__titulo + .hero__resumo + .hero__acoes
│   └─ .hero__lista (3 secundárias)
└─ .portal-layout
    ├─ .portal-feed (coluna principal)
    │   ├─ section "Para você" → .grade-noticias
    │   ├─ section "Últimas" → .lista-compacta (HorizontalNewsCard)
    │   └─ BlocoEditoria × N
    └─ aside.sidebar (320px, sticky)
        ├─ MaisLidas, .newsletter-box, .bloco-sidebar (Salvos)
```

```css
.portal-layout { display: grid; gap: var(--espaco-6); grid-template-columns: 1fr; }
.grade-noticias { display: grid; gap: var(--espaco-4); grid-template-columns: 1fr; }
@media (min-width: 768px)  { .grade-noticias { grid-template-columns: repeat(auto-fill, minmax(min(300px, 100%), 1fr)); } }
@media (min-width: 1024px) {
  .portal-layout { grid-template-columns: minmax(0, 1fr) var(--largura-sidebar); align-items: start; }
  .sidebar { position: sticky; top: calc(var(--altura-header) + var(--espaco-4)); display: flex; flex-direction: column; gap: var(--espaco-4); }
}
.lista-compacta { display: flex; flex-direction: column; gap: var(--espaco-3); }
```

### 6.3 Header / Rodapé

- `.topo`: sticky, `var(--vidro)` + `blur(14px)`, `z-index: var(--z-cabecalho)`, altura 64px.
- Linha 1 (`.topo__barra`): [hamburger mobile] marca (orbe + "Portal·") · nav desktop (Últimas/Comunidade/Radar/Premium) · busca (desktop inline / mobile colapsável) · ⌕ · ThemeToggle · Entrar/Assine ou avatar+Sair.
- Linha 2 (`.topo__trilhas`): pills de editoria com scroll-x (scrollbar oculta) + links de área. Mobile: `hidden` até `aria-expanded=true` (classe `.aberto`), empilha em coluna.
- `.base` (rodapé): 1 coluna mobile → 3 colunas ≥768px (marca / institucional / LGPD+RSS), linha fina de copyright.

### 6.4 Cards

- `NewsCard`: imagem 16/9 (`min-height` só como fallback), corpo `gap-2`, título serifado `lg/compacta`, resumo `sm` clamp-3, meta + BotaoSalvar.
- `FeaturedNewsCard` (hero): título `xl→display`, resumo clamp-4, borda primária sutil.
- `HorizontalNewsCard`: número fantasma (`xxl/negrito`, `var(--cor-borda)`) + título; divisor `1px borda` entre itens.
- Hover: `translateY(-2px)` + `var(--sombra-2)` (desligado em `reduced-motion` e touch).

## 7. Estados

| Estado | Spec |
|---|---|
| Hover (botão primário) | `background: var(--cor-primaria-hover)`; transição `120ms curva-padrão` |
| Active | `var(--cor-primaria-ativa)` + `scale(0.99)` |
| Disabled / carregando | `opacity: 0.6`, `cursor: not-allowed`, `aria-busy="true"`, texto "Carregando…" (nunca só spinner) |
| Focus | `:focus-visible { outline: 2px solid var(--cor-foco); outline-offset: 2px; }` + `var(--anel-foco)` em inputs |
| Skeleton | `.esqueleto` com shimmer `base→brilho`, `border-radius: sm`, respeita `reduced-motion` (vira bloco estático) |
| Empty/Error | `.estado-vazio/.estado-erro`: título `lg/negrito` + descrição suave + ação primária ("Tentar novamente") |
| Toast | `position: fixed; bottom: espaco-4; right: espaco-4; max-width: min(360px, calc(100% - 2rem))`, `z-index: var(--z-toast)`, variantes sucesso/erro/info com faixa lateral colorida, `role="status"` |
| Modal/Drawer | overlay `var(--cor-overlay)` (`z-modal-fundo`), conteúdo `var(--z-modal)`, `max-width: var(--largura-max-modal)`; mobile = bottom-sheet `raio-lg` topo; foco preso + ESC fecha + retorna foco ao gatilho |
| Newsletter/ads | `.newsletter-box`, `.faixa-publicidade`, `.banner-atualizacao` mantêm nomes; banner usa `z-banner` |

Variantes de `Button` (classes `.botao--primaria/.botao--secundaria/.botao--fantasma/.botao--perigo`, tamanhos `--pequeno/--medio/--grande`, min-height 40/44/52px).

## 8. Acessibilidade (obrigatório no CSS v2)

1. **Foco visível:** `:focus-visible` global (§7); `main:focus { outline: none }` só no alvo do skip-link; nunca `outline: none` sem substituto.
2. **Reduced motion:** bloco único cobrindo `*, *::before/after, .cartao-noticia, .botao, .drawer, .progresso-leitura__barra` → `animation: none; transition: none; scroll-behavior: auto`.
3. **Contraste AA:** pares do §2; placeholder usa `var(--cor-texto-suave)` (nunca `#aaa`); selo sobre imagem usa overlay + texto branco.
4. **Toque:** interativos `min-height: 40px`, `min-width: 40px` (ícones); itens de menu 40px; pills com padding vertical ≥ 10px.
5. **Teclado/leitor:** hamburger com `aria-expanded/aria-controls`; pills com `aria-current="page"`; feed com `aria-live="polite"`; `role="status"` em sugestão; drawer/modal com `aria-modal`, `aria-label`.
6. **Print:** esconder header/ações/toast/cookies/publicidade; texto preto sobre branco; links com URL visível em notícia.

## 9. Escala z (tokens `--z-*`, manter nomes)

```css
:root {
  --z-conteudo-elevado: 10;
  --z-banner: 20;
  --z-painel-flutuante: 30;
  --z-cabecalho: 40;
  --z-modal-fundo: 900;
  --z-modal: 910;
  --z-toast: 1000;
  --z-cookies: 1000;
}
```

Nenhum `z-index` literal fora daqui (legado tinha `z-index: 0/1` e `calc(cabecalho+1)` — migrar: progresso de leitura → `z-cabecalho`, cards → sem z ou `conteudo-elevado` no hover).

## 10. Aliases legados a preservar (não quebrar testes/E2E)

Manter seletores (podem virar aliases do novo sistema): `.container`, `.cabecalho*`, `.topo*`, `.base*`, `.botao*`, `.cartao-noticia*`, `.grade-noticias`, `.portal-layout`, `.sidebar`, `.bloco-sidebar*`, `.secao-*`, `.hero*`, `.seu-rio*`, `.tabela-wrapper` (+ `overflow-x: auto`), `.campo*`, `.busca*`, `.drawer*`, `.esqueleto*`, `.estado-*`, `.faixa-publicidade`, `.banner-atualizacao`, `.sugestao-adaptativa`, `.newsletter-box`, `.link-nulo`, `.texto-suave`, `.pular-para-conteudo`. Remover `width: 100vw` órfão (linha ~827) e breakpoints fora do §5.

## 11. Riscos/debt herdados do CSS atual (3457 linhas) — o que o v2 resolve

- 3 camadas de header (`.cabecalho` + `.topo` + `.botao-menu-mobile`) → unificar em `.topo` (§6.3).
- Breakpoints inconsistentes (400/480/600/720/900/960/1020) → 4 oficiais (§5).
- `100vw` sem compensação + `drawer width: min(420px, 100vw)` → `100%` + container §6.1.
- `--espaco-0: 0.15rem`, `--espaco-1-5: 0.3rem` fora do 4pt → renormalizados (§4).
- `--tamanho-botao-icone: 36px` < 40px → 40px (§4/§8.4).
- Erro/destaque ambos `#e10600` sem variante suave escura legível → semânticas separadas (§2).
- `--anel-foco` e `--transicao-rapida` consumidos mas não definidos → definir `anel-foco` (§4), padronizar `duracao-*`.
