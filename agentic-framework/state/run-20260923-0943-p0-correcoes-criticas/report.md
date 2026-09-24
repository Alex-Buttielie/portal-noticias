# Report — 20260923-0943-p0-correcoes-criticas

## Objetivo
Corrigir a unidade de preço estimado do provedor de LLM (default ~1000x acima do real, o que esgotaria o teto diário em poucos lotes e inflava o painel de métricas) e confirmar via `next build` se o `headers()` no root layout convertia as rotas ISR em SSR por request — corrigindo se confirmado. Itens P0-1 e P0-4 de `ANALISE_CUSTO_PERFORMANCE.md` (§7).

## O que foi entregue
Sem commit git (só working tree). 6 arquivos alterados, diff ≈ 50 inserções / 21 deleções:

**Parte A — P0-1 (preço estimado do LLM, `0.15` → `0.0003` USD/1k tokens):**
- `backend/config/settings.py:855-868` — default de `CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS` corrigido para `0.0003`, com comentário reescrevendo a derivação (gpt-4o-mini: entrada $0.15/1M, saída $0.60/1M; lote típico de 10 itens ≈ 5000 in + 2200 out ≈ $0.00029/1k → `0.0003` conservador). Nome, unidade, leitura via env e fórmula em `providers/summarization.py` intactos.
- `backend/.env.example` — documenta `CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS=0.0003` (+ `CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD=5.0`).
- `README.md` (seção "Teto de gasto diário com o provedor de LLM") — padrão `0.0003` com derivação resumida + volume suportado (~16M tokens/dia com o teto de $5), mais bloco `> **Nota operacional:**` do documenter sobre o override no banco.
- `backend/catalogo_noticias/tests/test_summarization_provider.py:271-300` — teste reescrito para travar o default corrigido (1000 tokens → `approx(0.0003)`) e o critério de aceite (10000 tokens → `approx(0.003)`); configurabilidade via override preservada.
- `frontend/app/admin/robos/page.tsx:405` — dica de exemplo `Ex: 0.15.` → `Ex: 0.0003.` (cosmética, fora da lista do contrato, justificada no history).

**Parte B — P0-4 (ISR vs SSR):**
- Diagnóstico confirmado por `next build`: `headers()` em `frontend/app/layout.tsx:50` forçava o app inteiro para renderização por request (até páginas 100% estáticas apareciam como `ƒ`).
- `frontend/app/layout.tsx:1-53` — removidos `headers`/`perfilPorUserAgent`/try-catch; detecção de UA preservada no cliente via `DeviceProvider` (corrige pós-hidratação; trade-off consciente: primeira pintura em mobile usa perfil desktop até hidratar).
- Pós-correção (rebuild limpo, exit 0): `/` e `/ao-vivo` voltaram a ISR (`○` + `revalidate`); `/noticia/item/[id]`, `/noticia/cluster/[id]`, `/categoria/[slug]` seguem `●`; `/buscar`, `/arquivo`, `/api/[...path]`, `/comunidade/[id]` permanecem dinâmicos por motivo legítimo próprio.

**Comportamento resultante:** o teto de $5/dia passa a cobrir ~16,7M tokens/dia (antes ~33k); `custo_llm_hoje_usd` no painel passa à ordem de grandeza real; rotas de conteúdo voltam a ISR.

## Veredito de testes
**passed** — 5/5 critérios do contrato. Suíte completa: **413 passed, 0 failed** (32 alvo + 142 módulos afetados + 271 resto; só warnings pré-existentes de `staticfiles/`). Cobertura **87,27%** (gate 80 do CI OK). Rebuild Next independente confirma ISR.

## Revisão
**Dispensada.** Nenhum gatilho de `review-triggers.md` se aplica (sem auth/billing/dados pessoais/migração/API pública/moderação/dependência nova) e o diff (≈ 50+/21- em 6 arquivos da run; `ARCHITECTURE.md` modificado no working tree é alteração preexistente de 2026-09-22, alheia a esta run) está abaixo do limiar de ~300 linhas. Verificação independente coberta pelo tester (`passed`).

## Docs atualizadas
- `README.md` (default + derivação + volume + nota operacional sobre `ConfiguracaoRobo`).
- `backend/.env.example` (vars documentadas).
- Verificadas sem necessidade de edição: `ARCHITECTURE.md` (sem valor numérico), `frontend/.env.local.example`, `agentic-framework/specs/*` (só menções conceituais). `ANALISE_CUSTO_PERFORMANCE.md` intencionalmente preservado como relatório diagnóstico pré-fix.

## Follow-ups (fora desta run)
1. **P0-2:** backup funcional na topologia PM2 — exige SSH na VPS; runbook pendente.
2. **P0-3:** TLS em PROD via Cloudflare — exige SSH na VPS; runbook pendente.
3. **ingestao-service/** ainda repete o default `0.15` em 6 arquivos (`app/config.py:40`, `app/schemas.py:96`, `app/pipeline/summarizer.py:149`, `.env.example:12`, `README.md:37`, `tests/test_pipeline.py:36,252`) — mesmo bug, outro serviço (desligado por padrão, fora do escopo do contrato); run dedicada sugerida.
4. **ConfiguracaoRobo com valor antigo no banco de produção:** deploys com linha (pk=1) já persistida carregam `llm_preco_por_1k_tokens=0.15` do banco, ignorando o settings corrigido — ajuste manual via tela admin de robôs ou env no deploy (one-liner, sem código). Contrato vedava mudança de schema, por isso `models.py:195` + migrations não foram tocados.

## Artefatos da run
- `task-plan.md`, `implementation-contract.md`, `implementation-history.md`, `documentation-update.md`, `report.md` (este), `run-state.json` (`status: closed`).
