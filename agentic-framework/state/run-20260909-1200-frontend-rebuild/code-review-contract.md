# Code Review Contract — 20260909-1200-frontend-rebuild

## Metadados
- **run_id:** 20260909-1200-frontend-rebuild
- **Escopo revisado:** 40 arquivos frontend (`git diff --stat HEAD`: 1361 inserções / 3636 deleções; amostra aprofundada: `frontend/app/globals.css`, `frontend/components/Header.tsx`, `frontend/components/Rodape.tsx`, `frontend/components/ui/Button.tsx`, `frontend/components/ui/Cards.tsx`, `frontend/app/page.tsx` + apoio em `BlocoEditoria.tsx`, `MaisLidas.tsx`, `DetalheNoticia.tsx`, `ui/Drawer.tsx`, `ui/SearchBar.tsx`, `ui/ShareButtons.tsx`, `ui/FormField.tsx`, `ui/Estados.tsx`, `ui/Data.tsx`, `ui/ReadingProgress.tsx`, `app/privacidade/politica/page.tsx`, `app/privacidade/preferencias-cookies/PreferenciasCookiesConteudo.tsx`)
- **Contrato de referência:** implementation-contract.md (20260909-1200-frontend-rebuild), se existir
- **Gatilhos aplicados (de review-triggers.md):** diff acima de ~300 linhas alteradas (gatilho genérico de volume); verificado e descartado: nova dependência externa (não há), mudança em API pública/contrato (não há), auth/sessão, cobrança/assinatura, dados pessoais, schema, moderação, reputação, credenciamento, radar-geolocalização, B2B, direitos autorais (nenhum se aplica ao diff amostrado)

## Verificações de guarda (somente leitura)
- `git status --short -- backend/ frontend/lib/api.ts` → vazio (sem alterações).
- `git diff HEAD --name-only -- backend/` → vazio; `git diff HEAD --name-only -- frontend/lib/api.ts` → vazio.
- `git diff HEAD -- frontend/package.json frontend/package-lock.json` → vazio (sem novas dependências).
- `git diff HEAD -U0 -- frontend/components frontend/app` filtrado por `lib/api|FeedEntrada|FeedDetalhe` → apenas usos de tipos já existentes (`FeedEntrada`, `api.FeedDetalhe`); nenhuma prop nova, nenhum endpoint novo; rotas preservadas (`/noticia/cluster|item/:id`, `/?categoria=`, `/radar`, `/comunidade`, `/privacidade/*`).
- LGPD/privacidade: `Rodape.tsx` mantém `Termos de uso`, `Política de privacidade`, `Preferências de cookies`, `Política editorial` + barra `Privacidade · Cookies · RSS`; páginas de privacidade só ganharam classes (`secao-bloco`, `secao-eyebrow`, `secao-titulo`); banner "Rascunho jurídico" preservado.

## Findings

### Finding 1
- **Arquivo:** frontend/components/ui/Cards.tsx
- **Linha:** 54, 57, 71, 76, 87, 104 (e frontend/components/BlocoEditoria.tsx:91, 98)
- **Categoria:** style
- **Severidade:** minor
- **Resumo:** Classes `limitar-linhas-2/3` usadas mas inexistentes em `globals.css`.
- **Cenário de falha:** `NewsCard` com `class="cartao-noticia__resumo limitar-linhas-2"` cai no clamp base de 3 linhas (`.card-noticia-resumo` → `-webkit-line-clamp: 3`); resumo ocupa 1 linha a mais que o desenho, desalinhando a grade `grade-noticias` (cards com alturas diferentes do esperado no desktop).
- **Sugestão:** Definir os utilitários (`-webkit-line-clamp: 2/3/4` + `line-clamp` padrão) ou remover as classes e documentar que o clamp vem da base.

### Finding 2
- **Arquivo:** frontend/components/DetalheNoticia.tsx
- **Linha:** ~105-118 (`share-sticky` com style inline)
- **Categoria:** correctness
- **Severidade:** minor
- **Resumo:** Faixa de compartilhar usa `background: color-mix(...)` inline sem fallback, duplicando a classe `.share-sticky`.
- **Cenário de falha:** Navegador sem suporte a `color-mix` descarta a declaração → faixa fica transparente sobre o artigo, com botões flutuando sobre o texto durante a rolagem.
- **Sugestão:** Remover o `background` inline e confiar em `.share-sticky` (`var(--vidro)` + blur), ou declarar `background: var(--vidro); background: color-mix(...)` em cascata.

### Finding 3
- **Arquivo:** frontend/components/Header.tsx
- **Linha:** 88-114
- **Categoria:** correctness
- **Severidade:** minor
- **Resumo:** Busca colapsável abre sem mover o foco para o campo.
- **Cenário de falha:** Usuário de teclado ativa "Abrir busca", o foco permanece no botão alternador; é preciso tabular (passando pelo atalho `Ctrl K`, toggle de tema, avatar) até alcançar o campo, e leitor de tela não anuncia a mudança de contexto.
- **Sugestão:** `ref` no input + `focus()` ao abrir; `Escape` fecha e devolve o foco ao alternador.

### Finding 4
- **Arquivo:** frontend/components/Header.tsx
- **Linha:** 50-53, 186
- **Categoria:** correctness
- **Severidade:** minor
- **Resumo:** Navegação mobile não fecha com `Escape` e não declara o padrão de disclosure além de `aria-expanded`.
- **Cenário de falha:** Usuário de teclado abre o menu (hamburger <1024px), navega pelos links e precisa achar o botão para fechar; sem `Escape`, o menu permanece sobreposto ao conteúdo após mudar o foco para fora.
- **Sugestão:** Handler `Escape` → `setMenuAberto(false)` + foco de volta ao botão (Drawer já faz esse padrão).

### Finding 5
- **Arquivo:** frontend/components/Rodape.tsx
- **Linha:** 20-25, 43
- **Categoria:** security
- **Severidade:** nit
- **Resumo:** Links externos (`x.com`, `instagram.com`, `youtube.com`) abrem na mesma aba e `rel` só existe sem `target`.
- **Cenário de falha:** Leitor clica em "X (Twitter)" e perde o contexto do portal (navegação na mesma aba para domínio terceiro); `rel="noopener noreferrer"` sem `target="_blank"` é inócuo.
- **Sugestão:** `target="_blank" rel="noopener noreferrer"` para `href` com `http`, mantendo `/rss.xml` na mesma aba.

### Finding 6
- **Arquivo:** frontend/components/ui/Button.tsx
- **Linha:** 23-31
- **Categoria:** maintainability
- **Severidade:** nit
- **Resumo:** `{...resto}` espalhado após `className`/`disabled` permite override acidental.
- **Cenário de falha:** Chamada futura `<Button className="x" ...>` substitui `botao botao--*` em vez de compor, quebrando o visual do design system v2 sem erro de tipo (pré-existente, não introduzido neste diff, mas mantido).
- **Sugestão:** Extrair `className`/`type` de `resto` e fazer merge (`botao ... + className`).

## Resumo quantitativo
| Severidade | Quantidade |
|---|---|
| blocker | 0 |
| major | 0 |
| minor | 4 |
| nit | 2 |

## Veredito
**approve_with_comments**

Diff de volume alto mas restrito ao frontend visual; `backend/` e `frontend/lib/api.ts` intactos, sem novas dependências e sem quebra de contrato da API; a11y globalmente melhorada (foco visível, `aria-current/expanded`, `sr-only`, `time dateTime`, alvos 40px+, `reduced-motion`, `overflow-x` contido, breakpoints 480/768/1024/1280); findings 1–4 são divergências visuais/comportamentais menores e 5–6 são nits, nenhum bloqueante.
