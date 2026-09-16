---
name: frontend-portal
description: Padrão obrigatório para qualquer trabalho visual no frontend do portal (Next.js 14 em frontend/). Consolida 5 referências externas em um workflow só: direção de design distintiva, componentes shadcn/ui e 21st.dev, checklist de conformidade web e verificação em browser. Use quando for criar, redesenhar ou revisar qualquer UI do portal.
---

# frontend-portal

Skill própria do projeto. Adapta para este repositório (Claude Code **e** OpenCode —
sem MCP configurado por padrão) as 5 referências externas indicadas pelo responsável:

| # | Origem | Papel nesta skill |
|---|---|---|
| 1 | `shadcn-ui-mcp-server` — https://github.com/Jpisnice/shadcn-ui-mcp-server | Fonte de componentes acessíveis (código-fonte, demos, metadados) |
| 2 | `magic-mcp` → **21st MCP** — https://github.com/21st-dev/magic-mcp | Catálogo de 10.000+ componentes React/Tailwind + geração de UI por IA |
| 3 | `frontend-design` — https://github.com/anthropics/claude-code/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md | Direção de design: identidade distintiva, anti-padrão-genérico |
| 4 | `web-design-guidelines` — https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines | Checklist de conformidade (a11y, foco, forms, animação, performance) |
| 5 | `chrome-devtools-mcp` — https://github.com/ChromeDevTools/chrome-devtools-mcp | Verificação em browser real (debug, performance, screenshots) |

> Textos-fonte integrais (fetch cru, sem JS do GitHub):
> - `https://raw.githubusercontent.com/anthropics/claude-code/main/plugins/frontend-design/skills/frontend-design/SKILL.md`
> - `https://raw.githubusercontent.com/vercel-labs/agent-skills/main/skills/web-design-guidelines/SKILL.md`
> - `https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md` (regras vigentes — **buscar de novo a cada revisão**)
> - `https://raw.githubusercontent.com/21st-dev/magic-mcp/main/skills/21st-ui/SKILL.md`
> - `https://raw.githubusercontent.com/ChromeDevTools/chrome-devtools-mcp/main/skills/chrome-devtools/SKILL.md`

## 0. Restrições do projeto (não-negociáveis)

- Stack: **Next.js 14 App Router + React 18**, TypeScript + **Tailwind CSS 3.4 + shadcn/ui v4 (Radix)** (`frontend/tailwind.config.ts`, `frontend/postcss.config.js`, `frontend/components.json`, `frontend/lib/utils.ts` `cn`). Migração autorizada explicitamente no `task-plan.md` da run `20260916-1430-frontend-rebuild-5skills` (precedente `20260915-2142`).
  - Regra: nova dependência externa de UI continua exigindo aprovação explícita no `task-plan.md` e cai em `review-triggers.md` (revisão obrigatória). Ver seção 4.
- MCPs: **runtime quando disponíveis, com fallback documentado** (precedente `2d8063c`): shadcn via MCP (`npx @jpisnice/shadcn-ui-mcp-server`) ou `https://ui.shadcn.com/docs/components/<nome>` + portar para tokens `--cor-*`; 21st via MCP HTTP (`https://21st.dev/api/mcp`, `x-api-key: API_KEY_21ST`) ou site; chrome-devtools via MCP (`--slim --headless`, breakpoints 360/768/1024/1440 + dark/light + tab-order + AA) ou `tsc`+`build`+checagem estática com ressalva em `test-report.md`.
- Design system atual: tokens CSS `--cor-*`, `--espaco-*`, `--raio-*`, `--sombra-*`, `--z-*` no topo de `frontend/app/globals.css`; tipografia `Inter` (corpo) + `Source_Serif_4` (títulos) via `next/font`; tema claro/escuro via `data-theme` + `prefers-color-scheme`; `prefers-reduced-motion` global.
- Intocáveis sem motivo registrado no `implementation-history.md`: rotas/URLs existentes, `frontend/lib/api.ts` (contrato com o Django), SEO (`metadataBase`, `sitemap.ts`, `rss.xml`, `JsonLd`), LGPD (banner + `/privacidade/*`), skip-link `#conteudo-principal`, script anti-flash de tema em `app/layout.tsx`.
- Verificação mínima de toda mudança visual: `tsc --noEmit` (binário local `frontend/node_modules/.bin/tsc`) + `npm run build --prefix frontend` exit 0. `next lint` sem config — não exigir (tech-debt conhecida).

## 1. Direção de design (fonte: `frontend-design`)

Agir como diretor de arte com ponto de vista próprio para **portal de notícias brasileiro** (audiência: leitor geral + assinante Premium; trabalho da página: ler rápido, confiar, assinar). Antes de codar, produzir o **plano curto em 2 passes**:

1. **Plano:** paleta base (4–6 hex nomeados), tipos e papéis (1–2 famílias), conceito de layout em 1 frase + wireframe ASCII, princípios do que torna esta página única.
2. **Revisão anti-genérico:** se qualquer eixo do plano for o default que sairia para "qualquer portal", revisar e registrar o que mudou e por quê. Sinais de default a evitar (salvo se o brief pedir exatamente isso): fundo creme `#F4F1EA` + serifada + acento terracota `#D97757`; fundo near-black + acento ácido; grade de cards idênticos com mesma sombra; eyebrow em ALL-CAPS com tracking em todo heading; `→` em todo link; `01/02/03` em conteúdo que não é sequência.
3. **Restrição:** ousadia em **um** lugar; o resto disciplinado. Hero abre com o mais característico do assunto (neste portal: a notícia, não números genéricos). Motion só orquestrado em 1 momento + motion que responde a ação do usuário. Copy em voz ativa, segunda pessoa, CTA nomeando o resultado ("Assinar Premium", não "Continuar").

## 2. Componentes (fontes: shadcn + 21st)

Ordem de preferência — não escrever UI do zero se o catálogo resolve:

1. **shadcn/ui v4 (React):** componente acessível já auditado. Sem MCP: consultar `https://ui.shadcn.com/docs/components/<nome>` e portar para os tokens `--cor-*` do projeto (nunca hardcodar cor). Com MCP: `npx @jpisnice/shadcn-ui-mcp-server` (recomendado com `--github-api-key`).
2. **21st.dev:** inspiração e blocos prontos (`search` → `get_component`; `search_logo` p/ logos em JSX; `generate` **só** se `get_usage.aiGenerationEnabled` for true e `generate` constar em `tools/list` — sem IA, adaptar via catálogo). Servidor HTTP MCP em `https://21st.dev/api/mcp` com header `x-api-key` (chave gratuita em `https://21st.dev/mcp`, variável `API_KEY_21ST`). Sem MCP: buscar no site e portar o código ao padrão do projeto.
3. **Portar, não colar:** ao integrar, adaptar a `frontend/components/ui/*` (props/rotas existentes intactas), tokens do §0, `cn`-style simples se necessário — sem introduzir Tailwind silenciosamente.

## 3. Conformidade (fonte: `web-design-guidelines` + `command.md`)

Toda entrega visual passa neste checklist (buscar `command.md` fresco antes de cada revisão; saída no formato `arquivo:linha — achado`, terse):

- **A11y:** botão só-ícone com `aria-label`; input com `<label>`; `<button>` p/ ação, `<a>`/`<Link>` p/ navegação (nunca `div onClick`); `img` com `alt`; `aria-live="polite"` em updates assíncronos; headings hierárquicos + skip link; `scroll-margin-top` em âncoras.
- **Foco:** `focus-visible` sempre visível; nunca `outline: none` sem substituto; `:focus-visible` > `:focus`.
- **Forms:** `autocomplete` + `name` + `type` correto; nunca bloquear paste; label clicável; botão de submit habilitado até o request iniciar + spinner; erro inline + foco no 1º erro; placeholder terminado em `…`.
- **Animação:** respeitar `prefers-reduced-motion`; animar só `transform`/`opacity`; nunca `transition: all`; loops >5s com controle de pausa.
- **Texto:** `…` (não `...`), aspas curvas, `text-wrap: balance` em headings, `truncate`/`line-clamp`/`break-words` + `min-w-0` em flex.
- **Imagens:** `width`+`height` explícitos (anti-CLS); `loading="lazy"` abaixo da dobra; `priority` acima.
- **Performance:** listas >50 itens virtualizadas; sem leitura de layout no render; inputs não-controlados por padrão.
- **Estado/URL:** filtros, tabs, paginação e painéis refletidos na query string (deep-link); ação destrutiva com confirmação ou undo.
- **Anti-patterns (reprovar):** `user-scalable=no`, `onPaste`+`preventDefault`, `transition: all`, `outline-none` sem foco substituto, navegação por `onClick` sem `<a>`, `div` clicável, imagem sem dimensão, input sem label, data/hora hardcoded (usar `Intl.*`).

## 4. Verificação em browser (fonte: `chrome-devtools-mcp`)

Quando houver browser/MCP disponível, seguir o workflow oficial: `navigate_page`/`new_page` → `wait_for` → `take_snapshot` (estrutura + `uid`s) → interagir (`click`/`fill` com `pageId`) → `take_screenshot` só p/ inspeção visual → `evaluate_script` p/ dados fora da árvore de acessibilidade. Breakpoints obrigatórios do portal: **360 / 768 / 1024 / 1440** + dark/light + tab-order + contraste AA.

Sem MCP (ambiente atual): fallback obrigatório — `npm run build --prefix frontend` + `tsc --noEmit` + checagem estática dos breakpoints/`aria` no código, e registrar como ressalva no `test-report.md` que o runtime em browser real não foi executado (precedente: run `20260909-1200`, revertida em `2d8063c` — ver `git show a1d37d8:...report.md`).

## MCPs opcionais (configuração, quando o usuário aprovar)

```json
{
  "mcpServers": {
    "shadcn": { "command": "npx", "args": ["-y", "@jpisnice/shadcn-ui-mcp-server"] },
    "21st": { "url": "https://21st.dev/api/mcp", "headers": { "x-api-key": "API_KEY_21ST" } },
    "chrome-devtools": { "command": "npx", "args": ["-y", "chrome-devtools-mcp@latest", "--slim", "--headless"] }
  }
}
```

Notas: shadcn aceita `--github-api-key` (5000 req/h) e `--framework react`; 21st exige chave de `https://21st.dev/mcp` (chaves antigas do Magic foram resetadas); chrome-devtools modo `--slim` p/ tarefas básicas, completo (sem flag) p/ performance/rede; `--categoryExtensions` só se for testar extensão.

## Quando NÃO usar esta skill

- Mudança exclusiva de backend (`backend/`, sem reflexo visual) — usar `agentic-run` direto.
- Revisão de código já escrito sem rebuild — usar `agentic-review`.
- Checagem de conformidade isolada ("isso atende ao contrato?") — usar `agentic-verify`.
