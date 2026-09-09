# Apêndice Shell — run 20260909-1200-frontend-rebuild

## Arquivos tocados
- `frontend/app/globals.css` — REESCRITA COMPLETA (~1100 linhas, era 3457).
- `frontend/components/Header.tsx` — rebuild (logo, busca colapsável, hamburger, nav editorias + secundária, tema, usuário).
- `frontend/components/Rodape.tsx` — rebuild (grid 4→2→1, privacidade/cookies, social, barra copyright, dark elegante).
- `frontend/app/layout.tsx` — SEM ALTERAÇÃO (já preserva metadata/SEO/fonts/JsonLd/Providers/skip-link/main#conteudo-principal; nenhum ajuste estrutural necessário).
- `frontend/lib/api.ts` — somente leitura, NÃO editado.

## Decisões
1. **Container fluido**: `width: min(1200px, 100% - 2rem)` com `margin-inline: auto`; breakpoint 480px volta para `100% - 2rem` contido. Nada de padding lateral fixo que some com a conta.
2. **Overflow-x**: `html, body { overflow-x: hidden }`; corrigidos dois culpados do CSS antigo — `.ticker` usava `margin: 0 calc(50% - 50vw); width: 100vw` (trocado por faixa `width: 100%` contida, trilho com animação) e `.drawer` usava `min(420px, 100vw)` (trocado por `100%`).
3. **Grade**: `.grade-noticias` agora é `repeat(auto-fill, minmax(min(300px, 100%), 1fr))` como exige o contrato (antes eram 3 colunas fixas com media queries, que quebravam em larguras intermediárias). `.grade-cartoes`/`.editoria-grade` seguem o mesmo padrão.
4. **Portal layout**: `minmax(0, 1fr) 320px` (exato do contrato), sidebar `position: sticky; top: 132px`, empilha em `≤1024px` com `position: static`.
5. **Nomenclatura**: `.cabecalho*` é o canônico do Header novo e `.rodape*` o do Rodape novo; `.topo*`/`.base*` antigos mantidos como **aliases** no CSS para não quebrar nenhum componente de outro agente que ainda os use (ex.: `ui/Cards.tsx`, `CommandPalette`, páginas com `.cartao*`). Todas as classes legadas consumidas (`cartao`, `cartao-titulo/meta`, `badge`, `chip`, `toast`, `modal`, `dropdown`, `tooltip`, `tabs`, `accordion`, `esqueleto`, `banner-cookies`, `tabela-wrapper`, `paginacao`, `plano-*`, `kpi`, `admin-*`, etc.) foram preservadas.
6. **Header**: busca colapsável (botão `aria-expanded`/`aria-controls` + form expansível; em `≤1024px` vira linha full-width abaixo do topo); hamburger `.botao-menu-mobile` com `aria-expanded`/`aria-controls={navId}`, fecha ao trocar de rota; nav editorias uppercase com `aria-current="page"` + secundária (Últimas/Comunidade/Radar/Premium + Jornalista/Empresa/Admin condicional); `ThemeToggle`, avatar inicial + Sair / Entrar + Assine; palette Ctrl+K mantido. Responsivo 360/768/1024 via CSS.
7. **Rodape**: `footer.rodape.rodape--dark` elegante, grid 4 col (marca + Seções + Institucional com privacidade/cookies + Conta) → 2 col em `≤900px` → 1 col em `≤600px`; social com `aria-labels`; barra copyright + links rápidos.
8. **Dark mode**: `:root[data-theme="dark"]` explícito (precedência) + `prefers-color-scheme` só quando sem `data-theme="light"`; script anti-flash do layout preservado (layout intocado).
9. **Dependências/rotas/API**: nenhuma adicionada, nenhuma rota renomeada, nenhuma chamada `api.ts` alterada. TypeScript estrito, componentes funcionais, comentários concisos.

## Resultado tsc
- `npx --yes tsc --noEmit -p tsconfig.json` (em `frontend/`; o `npx tsc` na raiz resolveu para pacote errado, sem TS local) → **exit 0, sem erros**. Cobre todos os arquivos do frontend, incluindo os 3 tocados por este agente.

## Pendências
- Validação visual em viewports (360/768/1024/1440) e auditoria de contraste/keyboard ficam com tester/reviewer.
- `npm run build` completo não executado neste escopo (só tsc, conforme ordem); recomendar ao orquestrador.
