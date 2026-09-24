# Task Plan — 20260923-0943-p0-correcoes-criticas

## Metadados
- **run_id:** 20260923-0943-p0-correcoes-criticas
- **Data de abertura:** 2026-09-23
- **Solicitado por:** Alex (humano) — pedido: análise de custo/performance do projeto + iniciar o plano de ação
- **Spec de origem:** nenhuma (deriva de `ANALISE_CUSTO_PERFORMANCE.md`, seção 7 — itens P0-1 e P0-4)

## Objetivo
Corrigir a unidade de preço estimado do provedor de LLM (hoje ~1000x acima do preço real, o que esgotaria o teto diário em poucos lotes e infla o painel de métricas) e confirmar via `next build` se o `headers()` no root layout está convertendo as rotas ISR em SSR por request — corrigindo se confirmado.

## Escopo
### Dentro do escopo
- P0-1: corrigir o default de `CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS` para o preço real de mercado do modelo default (gpt-4o-mini, blended ~0.0003 USD/1k), com derivação documentada; atualizar `.env.example`, docs e testes afetados.
- P0-4: rodar `next build` no frontend, capturar os marcadores de rota (`●` ISR vs `ƒ` Dynamic) para `/`, `/noticia/item/[id]`, `/noticia/cluster/[id]`, `/categoria/[slug]`; se dinâmico por causa do `headers()` em `app/layout.tsx:50`, mover a detecção de UA para client component isolado mantendo o root layout estático.

### Fora do escopo (explicitamente)
- P0-2 (backup na topologia PM2) e P0-3 (TLS/Cloudflare em PROD): exigem acesso SSH à VPS — entram como follow-ups com runbook, não nesta execução.
- Troca de provedor de LLM (Groq/Ollama), ETag nos feeds RSS, cache de feed, e demais itens P1/P2: backlog futuro.
- Preço separado de entrada/saída por token: manter o modelo atual de preço blended único (simplicidade deliberada); só corrigir o valor e documentar a derivação.

## Suposições assumidas
- Preço blended default `0.0003` USD/1k tokens para gpt-4o-mini — motivo: ~5000 tokens de entrada ($0.00015/1k) + ~2200 de saída ($0.0006/1k) por lote típico de 10 itens ≈ $0.00029/1k, arredondado para cima (conservador). Reversível via env var sem código.
- Build do frontend executa neste ambiente (Node 18+, rede para `next/font/google`) — motivo: diagnóstico exige o build real; se o ambiente não suportar, o executor registra a evidência parcial e a execução degrada para correção por análise de código + verificação pendente.

## Restrições
- Stack obrigatória mantida (Django+DRF, Next.js 14, PostgreSQL); nenhuma dependência nova sem aprovação explícita (não prevista).
- Compatibilidade retroativa: a variável de ambiente continua existindo com o mesmo nome e unidade (USD/1k tokens); quem já definiu valor próprio não é afetado.
- Testes do backend seguem `backend/pytest.ini`; `pytest --cov-fail-under=80` deve continuar passando (CI exige).

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | código + implementation-history.md |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked |
| 3 | reviewer (se `review-triggers.md` aplicar) | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. O teto de gasto diário de $5 passa a cobrir milhões de tokens/dia (ordem de grandeza correta), em vez de se esgotar em ~33k tokens.
2. O painel de métricas (`custo_llm_hoje_usd`) exibe valores na ordem de grandeza do custo real do provedor.
3. Sabe-se com evidência de build se as rotas de conteúdo são ISR ou SSR por request; se eram SSR por causa do `headers()`, voltam a ser ISR.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Preço real do provedor mudar no futuro | baixo | valor continua configurável via env; comentário documenta a derivação e quando revisar |
| `next build` não rodar neste ambiente (sem Node/rede) | médio | executor registra evidência parcial; diagnóstico vira follow-up com comando exato para rodar local |
| Testes existentes fixarem o valor antigo (0.15) | baixo | executor grepa por `0.15`/`PRECO_USD` e atualiza asserções com o novo valor derivado |

## Dependências
- Nenhuma decisão humana pendente para P0-1/P0-4.
- P0-2/P0-3 (follow-ups): acesso SSH à VPS + decisão de ativação Cloudflare.
