# Code Review Contract — 20260915-1956-frontend-portal-skills

## Metadados
- **run_id:** 20260915-1956-frontend-portal-skills
- **Escopo revisado:** `git diff HEAD -- frontend/` (42 arquivos, 1600 insertions, 911 deletions, só `M`, sem renames/deletes)
- **Contrato de referência:** implementation-contract.md (20260915-1956-frontend-portal-skills)
- **Gatilhos aplicados (de review-triggers.md):** tamanho do diff (>300 linhas → revisão obrigatória por volume); avaliados e NÃO disparados como mudança de comportamento: auth/sessão, cobrança/assinatura, dados pessoais, API/contratos, moderação, nova dependência (package.json vazio), reputação/BRD §§13/16/18/19-20, direitos autorais (link à fonte preservado)

## Findings

### Finding 1
- **Arquivo:** frontend/app/globals.css
- **Linha:** 1166-1169
- **Categoria:** maintainability
- **Severidade:** minor
- **Resumo:** `input:focus-visible, select:focus-visible, textarea:focus-visible { outline: none; }` remove o anel global sem substituto na própria regra.
- **Cenário de falha:** Usuário de teclado foca um campo de formulário → especificidade (`input:focus-visible` 0,1,1) vence o `:focus-visible` global (l.281-286, 0,1,0) → resta só `border-color + box-shadow 8%` da regra `:focus` (l.1158-1164), indicação sutil demais em contraste baixo.
- **Sugestão:** Usar `var(--anel-foco)` / `outline: 2px solid var(--cor-foco)` na regra, igual ao global.

### Finding 2
- **Arquivo:** frontend/components/CommandPalette.tsx
- **Linha:** 53
- **Categoria:** correctness
- **Severidade:** minor
- **Resumo:** Backdrop `<div className="palette-fundo" onClick={aoFechar} role="presentation">` é mouse-only.
- **Cenário de falha:** Usuário de teclado/leitor de tela não fecha pelo backdrop (só por `Escape`, l.26-29) — mitigado pois fechar por backdrop é suplementar e o dialog tem `role="dialog" aria-modal` (l.54); não substitui navegação.
- **Sugestão:** Manter como está ou trocar por `<button aria-label="Fechar">` / tornar o fechamento por backdrop redundante explícito.

### Finding 3
- **Arquivo:** frontend/components/ui/Drawer.tsx
- **Linha:** 37
- **Categoria:** correctness
- **Severidade:** minor
- **Resumo:** Mesmo anti-pattern do Finding 2 (`<div className="drawer-fundo" onClick={aoFechar} role="presentation">`), não listado no test-report.
- **Cenário de falha:** Idêntico ao Finding 2 para o Drawer.
- **Sugestão:** Mesma do Finding 2; considerar regra única compartilhada para backdrops.

### Finding 4
- **Arquivo:** frontend/components/ui/Data.tsx
- **Linha:** 56-78 (dentro de `.tabela-wrapper`, l.34)
- **Categoria:** correctness
- **Severidade:** minor
- **Resumo:** `<nav className="paginacao" aria-label="Paginação">` está dentro de `.tabela-wrapper` (região de scroll horizontal), como sinalizado na history (Iterações 3 e 5).
- **Cenário de falha:** Em tabelas largas a 360px, os botões Anterior/Próxima rolam para fora da vista junto com a tabela em vez de permanecerem fixos; nav dentro de região de overflow também é subótimo para leitores de tela. Conteúdo segue alcançável — não é bloqueante.
- **Sugestão:** Mover o `<nav>` para fora do `.tabela-wrapper` (exige editar `ui/Data.tsx`, fora da partição das frentes — tarefa do remediator).

### Finding 5
- **Arquivo:** frontend/app/verificar-email/VerificarEmailConteudo.tsx
- **Linha:** 40
- **Categoria:** style
- **Severidade:** nit
- **Resumo:** `rotulo="Verificando..."` usa `...` ASCII em vez de `…` (guideline § Texto).
- **Cenário de falha:** Apenas tipográfico, sem impacto funcional.
- **Sugestão:** Trocar por `Verificando…`.

### Finding 6
- **Arquivo:** frontend/app/globals.css
- **Linha:** 292
- **Categoria:** style
- **Severidade:** nit
- **Resumo:** `main:focus { outline: none; }`.
- **Cenário de falha:** Nenhum — `main` é alvo programático do skip-link (`tabIndex={-1}`, layout.tsx:96) e o `:focus-visible` global (l.281-286) preserva o anel para teclado.
- **Sugestão:** Nenhuma ação necessária; manter.

## Resumo quantitativo
| Severidade | Quantidade |
|---|---|
| blocker | 0 |
| major | 0 |
| minor | 4 |
| nit | 2 |

## Veredito
**approve_with_comments**

Rebuild confirmado como só-visual: `backend/`, `frontend/lib/`, `package.json`, `robots.ts`/`sitemap.ts` com diff vazio; linhas de lógica no diff (queries/mutations/router/`rel`/`url_fonte_original`) são só re-indentação; JsonLd/skip-link/consentimento intactos. Nenhum blocker/major; os 4 minors + 2 nits (incl. paginação do DataTable, que merece correção não-bloqueante do remediator) não impedem o merge.
