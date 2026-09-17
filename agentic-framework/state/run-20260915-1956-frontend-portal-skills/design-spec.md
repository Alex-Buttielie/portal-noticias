# Design Spec — 20260915-1956-frontend-portal-skills

> Autoridade: `.claude/skills/frontend-portal/SKILL.md` (§0–§4). Ancoragem real: `app/page.tsx`, `components/Header.tsx`, `components/Rodape.tsx`, `app/globals.css:1-230`. Precedente: run `20260909-1200` revertida (`2d8063c`) — evoluir sem ruptura.

## 0. Guardrails

- Next.js 14 + React 18, TS. **Sem Tailwind/shadcn novo** (nova dependência → `review-triggers.md`).
- Evoluir tokens `--cor-*`, `--espaco-*`, `--raio-*`, `--sombra-*`, `--z-*`; não renomear tokens.
- Tipografia: `Inter` (corpo/UI) + `Source_Serif_4` (títulos) via `next/font`. Não trocar famílias.
- `data-theme` + `prefers-color-scheme`; script anti-flash em `layout.tsx` intocado. `prefers-reduced-motion` global preservado.
- Intocáveis: rotas/URLs, `lib/api.ts`, SEO, LGPD, skip-link `#conteudo-principal`.
- Verificação por frente: `tsc --noEmit` + `next build` exit 0. Sem browser/MCP: checagem estática + ressalva em `test-report.md`.

## 1. Paleta base (6 hex, evolução do atual)

| Nome | Light | Dark | Papel |
|---|---|---|---|
| `Papel` | `#F6F7F9` | `#07090E` | Fundo. Par com `Tinta` ≥7:1 |
| `Tinta` | `#0B0D12` | `#F2F4F8` | Texto principal |
| `Rio` (primária) | `#4338CA` (hover `#3730A3`) | `#818CF8` (hover `#A5B4FC`) | Links, foco, pills ativas, CTA |
| `Plantão` | texto `#C00500` / sólido `#E10600` | `#FF453A` | **Só** urgência + erro. Suave `#FFF1F0` / `#2A1413` |
| `Ouro Premium` | texto `#8A6D2B` / sólido `#B8954A` | `#D4B36A` | Só Premium/paywall |
| `Mata` | `#0F6F5C` | `#6EE7B7` | Sucesso/toast |

Suportes: borda `#E4E8F0`/`#1E2635`, texto-suave `#5B6472`/`#98A2B3`, primária-suave `#EEF0FE`/`#161D33`, fundo-elevado `#FFFFFF`/`#0D1117`. Gradiente marca `linear-gradient(135deg, Rio, #06B6D4)` restrito a `topo__orbe` + placeholder de card. AA: pares principais ≥4.5:1.

## 2. Tipos

- `Source_Serif_4`: só `h1` home, títulos de card/notícia, título do artigo. `text-wrap: balance`, `letter-spacing: -0.025em`.
- `Inter`: todo o resto (meta, UI, corpo). Hierarquia: eyebrow → título serif → meta 0.85rem → resumo.

## 3. Conceito

> **Um rio cronológico confiável à esquerda com sidebar de serviço à direita, onde a hierarquia vem de posição e tipografia — não de sombras ou cores novas.**

Home ≥1024 (`.portal-layout` 2 col):

```
+-- .topo --------------------------------------------------+
| [orbe Marca] [nav] [busca][K][tema][Entrar][Assine]       |
| [pills editorias scroll-x]                                |
+-----------------------------------------------------------+
| .faixa-publicidade (se exibir) | .banner-atualizacao      |
| .seu-rio: eyebrow + H1 + 1 linha                          |
| +-------------------------------+ +-------------------+ |
| | Para você (.grade, até 6)      | | .sidebar          | |
| | #ultimas (.lista-compacta, 12) | | .mais-lidas (ol)  | |
| | .editoria x3 (grade 3)         | | .newsletter-box   | |
| | Da comunidade (grade 3)        | | Salvos            | |
| +-------------------------------+ +-------------------+ |
| [Carregar mais notícias]                                  |
+-- .base: marca + links + fino ----------------------------+
```

360px: 1 coluna; sidebar empilha após o rio; pills em scroll-x; CTA full-width. Artigo: breadcrumb textual, H1 serif + meta (`Intl`), hero com dimensões, corpo 62–68ch/1.7, bloco "Por que confiar", `explicacao-ia` discreta, fluxo-leitura com 3–5 relacionados.

## 4. Princípios

1. **O rio é o produto** — cronológico por padrão; personalização é camada rotulada, nunca reordenação silenciosa.
2. **Confiança é contável** — `numero_fontes`, badges, `info-leitura`, "Por que confiar".
3. **Plantão com disciplina** — vermelho só em urgente/erro; 1 urgência por viewport.
4. **Leitor volta** — salvos locais, mais-lidas, newsletter, deep-link `?categoria=`/`?busca=`.
5. **Premium é ausência** — publicidade some p/ Premium; ouro só em Premium.

## 5. Anti-genérico (ousadia em 1 lugar: rio numerado + serifada de manchete)

Evitar: fundo creme+terracota; near-black+neon; grade de cards idênticos (usar 3 ritmos: `grade-noticias`, `lista-compacta` numerada sem thumb, `editoria-grade` com filete); eyebrow ALL-CAPS fora dos 4 rótulos do rio; `→` fora de `secao-ver-tudo`/`editoria-ver`; números fora de ranking/posição; hero com stats genéricos (home abre com **a notícia**). Motion: só `banner-atualizacao` na entrada + hovers 120–220ms em `transform`/`opacity`; nunca `transition: all`.

## 6. Contrato de classes (reutilizar nomes; classe nova só com prefixo do bloco)

- **FRENTE A (dona de `globals.css`)**: reescrever preservando 100% dos nomes usados em TSX (ver inventário da run) + legados documentados; estilizar os 3 ritmos de card, shell, sidebar, forms, tabelas, estados, overlays; breakpoints 360/768/1024/1440; dark; reduced-motion; print.
- **FRENTE B (shell)**: `.topo*`, `.topo__trilhas`, `.topo__pills/pill`, `.container`, `.base*`, `.palette*`. Arquivos: `Header`, `Rodape`, `PularParaConteudo`, `ThemeToggle`, `CommandPalette`, `layout.tsx` (só visual), `not-found.tsx`.
- **FRENTE C (componentes)**: `ui/*` + `Accordion/Badge/BlocoEditoria/BotaoSalvar/CartaoEsqueleto/Chip/DetalheNoticia/Dropdown/MaisLidas/Modal/PorQueEstouVendoIsso/Tabs/ToastProvider/Tooltip`. Props congeladas.
- **FRENTE D (páginas)**: `app/page.tsx`, `noticia/`, `comunidade/`, `radar/`, `planos/`, `login/`, `cadastro/`, `onboarding/`, `minha-conta/`, `admin/*`, `autor/`, `empresa/`, `jornalista/`, `lista-de-espera/`, `paginas/`, `privacidade/*`, `recuperar/redefinir-senha`, `verificar-email`. Só classes/estrutura; zero mudança em `lib/*`, queries, router, lógica. Query params do feed (`?categoria=`, `?busca=`) e `?token=`/`?uid=`+`?token=` intactos.

## 7. Copy/voz

Ativa, 2ª pessoa, pt-BR. CTA nomeia o resultado ("Assinar Premium", "Carregar mais notícias"). Microcopy do rio preservado. `…`, aspas curvas, `Intl` p/ datas, fontes sempre contadas. Erros humanos + ação. Premium sem dark-pattern.

## 8. Conformidade por frente (skill §3, enxuto)

`aria-label` em botão só-ícone; `<label>` em input; `<button>` ação / `<Link>` navegação; `scroll-margin-top` em âncoras; só `transform`/`opacity`; `truncate`+`min-w-0`; listas >50 virtualizadas; estado na URL. Reprovam: `user-scalable=no`, `onPaste+preventDefault`, `transition: all`, `outline-none` sem substituto, `div` clicável, imagem sem dimensão, input sem label, data hardcoded.
