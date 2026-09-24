# Report — 20260923-1216-p1-feed-cache-indices

## Objetivo
P1-1 + P1-2 de `ANALISE_CUSTO_PERFORMANCE.md`: feed público com número pequeno e constante de queries por request (coluna denormalizada, corte SQL, cache curto, índices), sem mudar conteúdo — exceto `exibir_publicidade`, migrado para `GET /api/gating/status`.

## Entregas
**P1-1 (N+1, SQL, cache, gating):**
- `backend/catalogo_noticias/models.py`: `numero_fontes_distintas` virou coluna (`PositiveIntegerField`); property removida; `recalcular_numero_fontes()` canônico.
- `backend/catalogo_noticias/migrations/0009_newscluster_numero_fontes.py`: `AddField` + backfill idempotente.
- `backend/catalogo_noticias/services/ingestao.py`: `_persistir_grupo` e `_persistir_grupo_mesclado` (3 sub-caminhos) mantêm coluna; `admin.py` `save_related` cobre inline.
- `backend/feed/services.py`: `CAMPOS_LISTA_FEED` + `itens_publicaveis()` com janela 72h (`FEED_JANELA_HORAS`), `.only()`, `select_related`; detalhe com fetch completo. `busca.py` usa `.only()` + `tags`; `recomendacao.py` usa `CAMPOS_SEM_RELACAO`.
- `backend/feed/views.py`: cache curto (`FEED_CACHE_TTL_SEGUNDOS=45`) por querystring normalizada em `FeedListView`, `UrgentesView`, `MaisLidasView`, `HomeSecoesView`, `DestaquesDiaView`.
- `backend/gating/`: cache curto de `premium_ativo()` + invalidação em `save`/`delete` (`FeatureLimit`, `ConfiguracaoSistema` incl. `QuerySet.delete`); `MeusRecursosView` 1 query + cache.
- `exibir_publicidade` removido de todos payloads do feed (com `pop` defensivo no caminho microserviço); frontend migrado para `lib/premium.ts` → `/api/gating/status`; `tsc --noEmit` exit 0.
- Settings novas (`FEED_JANELA_HORAS=72`, `FEED_CACHE_TTL_SEGUNDOS=45`, `GATING_CACHE_TTL_SEGUNDOS=45`) em `settings.py` + `.env.example`.

**P1-2 (índices):**
- Migração 0010: `feed_status_ingestao` (`status_revisao`, `-timestamp_ingestao`), `newsitem_categoria`, `newsitem_urgente`, `newsitem_localidade`.
- Migração 0011: `pg_trgm` + GIN trigram (`titulo`, `resumo_proprio`, `conteudo_completo`) com guarda `connection.vendor`, no-op em sqlite.

## Testes
- Foco: `test_p1_feed_cache_indices.py + test_migracao_trgm.py` → 18 passed.
- Final com gate CI (`--cov-fail-under=80`): **434 passed, 87.75%**.
- Sanidade: `GET /api/feed/` (6 clusters × 2 itens) = 2 queries; SQL sem `conteudo_bruto`/`conteudo_completo`; 2º GET com 0 queries; `migrate --check` sqlite limpo; `tsc` exit 0. Critérios 1–8 todos ✅.

## Revisão
- 1ª passada: **changes_requested** (1 major / 3 minor / 2 nit).
- Remediação: **6/6 tratados** (5 corrigidos + backfill 0009 aceito com justificativa + `ponytail:`).
- Re-revisão: **approve_with_comments** (1: `ponytail:` no docstring da 0009 — orchestrator decidiu manter só no history, migração é run-once; 2 opcional: guarda `try/except` em `MaisLidasView:227`).

## Docs atualizadas
- `README.md:93-94`: linha `GET /api/gating/status/` na tabela gating.
- `ARCHITECTURE.md:43`: `NewsCluster.numero_fontes_distintas` documentada.
- `infra/DEPLOY.md`: nota de janela fria para migração 0011 (GIN não-CONCURRENTLY).
- Não-alterados: `.env.example` (já com as 3 settings), `ARCHITECTURE.md:156` (citação histórica), specs/backlog.

## Follow-ups
- Validade real da 0011 em Postgres sai no CI (`backend-tests`, postgres:16).
- `MaisLidasView:227` sem guarda de `limite` — fora de escopo, candidato a próxima run.
- Runbooks VPS P0-2/P0-3 seguem pendentes.
