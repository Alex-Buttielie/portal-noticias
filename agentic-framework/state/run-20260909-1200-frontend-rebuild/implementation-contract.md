# Implementation Contract — 20260909-1200-frontend-rebuild

## Metadados
- **run_id:** 20260909-1200-frontend-rebuild
- **Deriva de:** task-plan.md (20260909-1200-frontend-rebuild)
- **Versão do contrato:** 1

## O que deve ser construído
Reconstrução total do frontend visual (jogar fora CSS/componentes visuais legados) com novo design system moderno em CSS puro:
- Reescrever `frontend/app/globals.css` com tokens v2 (cores editoriais modernas, tipografia, escala 4pt, raios, sombras suaves, gradientes discretos), mobile-first, breakpoints 480/768/1024/1280, dark mode completo, `prefers-reduced-motion`, print
- Rebuild de `components/Header.tsx`, `components/Rodape.tsx`, `components/ui/Button.tsx`, `components/ui/Cards.tsx`, `components/ui/Estados.tsx`, `components/ui/SearchBar.tsx`, `components/ui/FormField.tsx`, `components/ui/Data.tsx`, `components/ui/Drawer.tsx`, `components/BlocoEditoria.tsx`, `components/MaisLidas.tsx`, `components/DetalheNoticia.tsx` e demais componentes visuais para o novo sistema
- Reestruturar `app/page.tsx` (layout: hero + grade + sidebar sticky) e garantir que todas as rotas em `app/*` herdem o novo visual via globals + ajustes mínimos por página (sem mudar lógica de dados)
- Garantir responsividade: container fluido `min(1200px, 100% - 2rem)`, grids `auto-fill/minmax`, header com busca colapsável + menu hamburger acessível (`aria-expanded`), tabelas com `.tabela-wrapper`, imagens `max-width:100%`, sem `100vw` sem compensação

## Áreas/arquivos esperados
- `frontend/app/globals.css` (reescrita completa, mantendo nomes de classes consumidos + novos)
- `frontend/app/layout.tsx` (ajustes mínimos de estrutura se necessário; preservar SEO/fontes/metadata)
- `frontend/app/page.tsx` (novo layout do feed/rio)
- `frontend/components/Header.tsx`
- `frontend/components/Rodape.tsx`
- `frontend/components/ui/*`
- `frontend/components/BlocoEditoria.tsx`, `MaisLidas.tsx`, `DetalheNoticia.tsx`, demais em `components/*`
- `frontend/app/*/page.tsx` (apenas classes/estrutura visual, sem mudar chamadas api)
- Nenhum arquivo em `backend/`

## Interfaces afetadas
- Nenhuma API muda. Contrato `lib/api.ts` + `lib/queries.ts` é somente-leitura nesta run. Se um componente precisar de dado novo, adaptar no frontend sem pedir campo novo ao backend.

## Critérios de aceite (técnicos, testáveis)
1. Dado `npm run build` em `frontend/`, quando executado, então termina com exit 0 e sem erro de tipo
2. Dado `npx tsc --noEmit` em `frontend/`, quando executado, então termina com exit 0
3. Dado viewport 360px, quando home/notícia/login renderizam, então `document.documentElement.scrollWidth <= window.innerWidth` (sem overflow-x) e menu mobile abre/fecha com `aria-expanded`
4. Dado viewport 768px e 1024px, quando home renderiza, então grade usa 2 colunas e sidebar empilha sem sobreposição
5. Dado viewport 1440px, quando home renderiza, então grade usa 3 colunas e container centraliza com largura máxima
6. Dado `prefers-reduced-motion`, quando animações existem, então são desativadas via media query
7. Dado tema dark (`data-theme="dark"`), quando qualquer página renderiza, então contraste de texto principal >= 4.5:1 (tokens escuros) e sem flash de tema errado
8. Dado usuário navegando só por teclado, quando percorre header/feed/formulário, então foco visível em todos os interativos e skip-link leva a `#conteudo-principal`

## Não-objetivos
- Não alterar `backend/**`, rotas de API, serializers, autenticação ou regras de negócio
- Não adicionar Tailwind/MUI/Bootstrap ou qualquer dependência nova sem aprovação (manter `package.json` salvo patch mínimo)
- Não renomear rotas nem mudar URLs, sitemap, robots, rss
- Não fazer deploy em HOMOLOG/PROD

## Restrições técnicas
- **Performance:** sem webfont externa em runtime (manter next/font); imagens com `max-width:100%`; CSS sem `@import` remoto
- **Segurança/privacidade:** manter banner LGPD e links /privacidade; nenhuma chamada externa nova
- **Dependências permitidas:** nenhuma nova por padrão; se inevitável, justificar em implementation-history.md
- **Estilo/convenções:** TypeScript estrito, componentes funcionais, comentários concisos em pt-BR, manter `data-theme` e variáveis `--cor-*`, `--espaco-*`

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Testes escritos e passando (tester)
- [ ] Revisão de código aprovada, se exigida por `review-triggers.md` (reviewer)
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente
