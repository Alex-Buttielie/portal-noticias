<!--
CONTRACT: documentation-update
DONO: documenter
QUANDO É CRIADO: depois que testes passam e a revisão (se exigida) está aprovada.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/documentation-update.md
-->

# Documentation Update — 20261014-2113-correcao-seo

## Metadados
- **run_id:** 20261014-2113-correcao-seo
- **Baseado em:** implementation-history.md (20261014-2113-correcao-seo, Iteração 1 — executor, Iteração 2 — tester), implementation-contract.md v2, code-review-contract.md (veredito `approve_with_comments`)

## Documentos afetados
| Documento | Tipo de mudança | Resumo |
|---|---|---|
| `README.md` (raiz) | Atualização (seção "SEO técnico") | Corrigida a descrição do que o Open Graph de fato emite (removida a afirmação de que `og:image` é gerado — não é); o bullet de "Canonical" passou a descrever a cobertura real (toda página indexável, não só "página de conteúdo", mais o fallback global do layout raiz); novo bullet curto sobre heading único (`<h1>`) e `alt` de imagem informativa, já que isso é comportamento novo e relevante para quem for criar uma página nova; o parágrafo "Limitação conhecida" foi reescrito para declarar explicitamente que `frontend/public/og-padrao.svg` não existe no projeto (nem a pasta existe), por isso nenhuma página emite `og:image` hoje, com o passo exato para resolver isso quando houver um asset real. |
| `ARCHITECTURE.md` | Atualização (linha "Segurança" da tabela §9.3) | Acrescentada uma frase sobre o `Caddyfile` agora enviar `Strict-Transport-Security` em toda rota do site (inclusive as servidas pelo Next.js, que antes não recebiam HSTS) e redirecionar `www.` para o domínio apex com 301 — é uma mudança real de postura de segurança da topologia ativa, então pertence a essa tabela. |
| `Caddyfile` (comentário, não comportamento) | Correção de comentário | O comentário acrescentado pelo executor dizia que o HSTS era "duplicado... para cobrir as duas origens de resposta", dando a entender que o valor do Django e o do Caddy coexistem independentemente por rota. Corrigido para deixar explícito que, como o `header` do Caddy roda sem `match` (toda resposta do site), o valor de 1 ano do Caddy é o que de fato chega ao cliente em TODAS as rotas — o HSTS do Django passa a ser redundante, não complementar. Isto é exatamente o finding `nit` apontado pelo reviewer no `code-review-contract.md` (achado 1), que havia sido classificado como "não bloqueia merge" mas é uma correção textual trivial e de baixo risco. |
| `frontend/lib/site.ts` (comentário de `IMAGEM_OG_PADRAO`) | Correção de comentário | O comentário antigo chamava o asset de "placeholder de rascunho... precisa ser substituída", o que sugeria que o arquivo existia, só não estava finalizado. Reescrito para declarar o fato confirmado de forma independente por três agentes nesta run (executor, tester, reviewer): o arquivo não existe, a pasta `frontend/public/` não existe, a constante hoje só é usada no JSON-LD (não no Open Graph), e SVG não serviria mesmo que existisse (formato não aceito como `og:image` pelos principais consumidores). Também documenta o passo exato para resolver quando houver asset real. |

## Sem impacto em documentação?
Não se aplica integralmente — ver tabela acima. Mas vale registrar o que ficou **de fora**, deliberadamente:
- Nenhuma mudança foi feita em `README.md`/`ARCHITECTURE.md` sobre GA4, pois nada de código ou comportamento mudou nesta run quanto a isso (decisão humana pendente, já tratada como não-objetivo no `implementation-contract.md` — não há nenhuma doc de produto afirmando hoje que existe GA4, então não havia contradição a corrigir).
- Não toquei no bloco do topo do `README.md` (linhas 16-18) que descreve a topologia de produção ativa como "Gunicorn + PM2 + Nginx", mesmo esse texto parecendo inconsistente com o `ARCHITECTURE.md` (que registra cutover para Docker Compose + Caddy em 2026-10-11). Essa é uma contradição pré-existente, anterior e sem relação com esta run — não é algo que as mudanças desta run tenham causado ou que eu tenha evidência própria para arbitrar qual das duas está correta hoje. Fica fora do escopo deste documenter; se for real, é assunto para uma run própria de atualização de infraestrutura/documentação.
- Não criei nenhuma entrada de CHANGELOG porque **o projeto não mantém um arquivo de CHANGELOG** (confirmado por busca — não existe `CHANGELOG.md` nem equivalente na raiz, em `frontend/` ou em `docs/`). O histórico de mudanças deste tipo de projeto vive nos commits e no `implementation-history.md` de cada run, não em um changelog de produto — não inventei um arquivo novo só para esta run.

## Exemplos/snippets novos ou atualizados
- `README.md`, seção "SEO técnico": novo bullet "Heading e `alt` de imagem" e parágrafo "Limitação conhecida" reescrito (ver diff do arquivo).
- `frontend/lib/site.ts`: comentário de `IMAGEM_OG_PADRAO` reescrito com o passo exato (`images: [IMAGEM_OG_PADRAO]` em `frontend/app/layout.tsx`) para quem for ligar o `og:image` futuramente, quando o asset existir.

## Entrada de changelog
Não aplicável — o projeto não mantém CHANGELOG (ver "Sem impacto em documentação?" acima).

## Verificação
- [x] Nenhum exemplo/trecho de documentação existente ficou contraditório com a mudança — os três pontos de contradição encontrados (README "SEO técnico" afirmando `og:image` presente, comentário do `Caddyfile` sobre HSTS "duplicado", comentário de `IMAGEM_OG_PADRAO` como "rascunho existente") foram corrigidos nesta run.
- [x] Build/lint de documentação rodado (se o projeto tiver um) — o projeto não tem linter de Markdown nem build de docs; como `frontend/lib/site.ts` é código (comentário dentro de arquivo `.ts`), roda `eslint`/`tsc` normalmente: `npx eslint lib/site.ts` → sem issues; `npx tsc --noEmit` → sem erros (edição foi só de comentário, sem alterar a linha de código `export const IMAGEM_OG_PADRAO = ...`).
