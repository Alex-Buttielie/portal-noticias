# Implementation History — 20260923-1216-p1-feed-cache-indices

## O que mudou (arquivo:linha aprox.)

**Coluna denormalizada (P1-1)**
- `backend/catalogo_noticias/models.py:23` — `NewsCluster.numero_fontes_distintas = PositiveIntegerField(default=1)` (era `@property` com COUNT por cluster — N+1 no caminho quente). Decisão: **property REMOVIDA**, virada coluna; leitura direta em `feed/services.py:121`. Motivo: evita regressão acidental (qualquer uso volta a ser COUNT).
- `backend/catalogo_noticias/models.py:35-46` — `recalcular_numero_fontes()` (COUNT DISTINCT canônico, idempotente, só grava quando diverge). Usado pela ingestão e serve de referência lógica do backfill.
- `backend/catalogo_noticias/services/ingestao.py:322,328-333` — `_persistir_grupo`: conta fontes distintas do grupo em memória e grava na criação do cluster.
- `backend/catalogo_noticias/services/ingestao.py:451,465-469,533` — `_persistir_grupo_mesclado`: cobre os 3 sub-caminhos (fusão de clusters não-canônicos via `update(cluster=cluster)` + delete órfãos; promoção de standalone via `NewsCluster.objects.create` + `update(cluster=...)`; crescimento do canônico). A contagem é refeita via `cluster.recalcular_numero_fontes()` **após** mover/criar itens, a partir do estado real do banco.
- `backend/catalogo_noticias/admin.py:44-51` — `save_related` recalcula a coluna (inline do admin associa/desassocia itens fora do pipeline).
- `backend/catalogo_noticias/migrations/0009_newscluster_numero_fontes.py` (nova) — `AddField` + `RunPython(backfill)` idempotente (recomputa e só grava quando diverge; reverso no-op).

**Corte SQL + `.only()` (P1-1)**
- `backend/feed/services.py:36-51` — `CAMPOS_LISTA_FEED` (titulo, resumo_proprio, categoria, urgente, imagem_url, pais/estado/cidade, nome_fonte, autor, timestamps, cluster + `cluster__numero_fontes_distintas`). `conteudo_bruto`/`conteudo_completo` fora de propósito; regra documentada no comentário.
- `backend/feed/services.py:79-88` — `itens_publicaveis()`: janela `timestamp_ingestao >= agora - FEED_JANELA_HORAS` + `.only(*CAMPOS_LISTA_FEED)` + `select_related("cluster")`.
- `backend/feed/services.py:197-238` — `detalhe_cluster`/`detalhe_item`: fetch completo, sem `.only()` (`conteudo_completo` no payload).
- `backend/feed/busca.py:100-107` — busca usa `.only(*CAMPOS_LISTA_FEED, "tags")` (`tags` porque `_relevancia` pontua por elas; `conteudo_completo` só no filtro LIKE via GIN). Sem janela de tempo — mesmos resultados, só mais rápido.
- `equilibrar_por_categoria` opera só sobre dicts (sem toque em modelo); `aplicar_regras_curadoria` (`painel_admin/services_regras.py:69-76`) lê `id`/`cluster_id`/`autor` via `getattr` — todos no `.only()`. Radar (`radar/services.py`) não usa `.only()` (agregações `values/annotate`, sem colunas pesadas); seções/home/destaques reutilizam `itens_publicaveis()`.

**Cache listagens + gating (P1-1)**
- `backend/feed/views.py:27-48` — `_ttl_feed()`, `_chave_cache_listagem()` (querystring normalizada ordenada + sufixo usuário; anônimo compartilha `anon`).
- `backend/feed/views.py` — cache curto da resposta final em `FeedListView`, `UrgentesView`, `MaisLidasView`, `HomeSecoesView`, `DestaquesDiaView` (detalhe cluster/item e busca sem cache: detalhe é por-id, busca é personalizada/volátil).
- `backend/gating/services.py:20-44,52-64` — cache curto de `premium_ativo()` + `invalidar_cache_gating()`; `backend/gating/models.py` — `save()`/`delete()` de `FeatureLimit` e `ConfiguracaoSistema.save()`/`delete()` + `ConfiguracaoSistemaQuerySet.delete()` invalidam (cobre `filter().delete()` em lote).
- `backend/gating/views.py:16-44` — `MeusRecursosView`: 1 query em `FeatureLimit` (antes ~3N) + cache por plano.
- `backend/config/settings_test.py` — suíte usa `DummyCache` (cache locmem global vazaria respostas entre testes); testes dedicados religam locmem real via `override_settings`.

**`exibir_publicidade` (breaking controlado)**
- Backend: removido de todos os payloads do feed (`FeedListView`, detalhe cluster/item local, seções/destaques/urgentes/mais-lidas/busca/cobertura — serializers nunca tiveram o campo; views que o injetavam via `services.exibir_publicidade()` tiveram a injeção removida). Defesa: `views.py:93,139,171` fazem `pop("exibir_publicidade")` no payload vindo do microserviço (contrato antigo espelhado). `microservice_client.py` inalterado (serviço desligado por default; strip no limite protege se ligar).
- Frontend: campo removido das interfaces `FeedResposta`/`FeedDetalhe`/home (`frontend/lib/api.ts`, 3 pontos) + fallbacks das páginas de detalhe (`noticia/[id]`, `noticia/cluster/[id]`, `noticia/item/[id]`). Ads já via `GET /api/gating/status` (`lib/premium.ts` → `usePremiumAtivo()`, consumido em `HomeClient`, `planos`, `RadarClient`). `tsc --noEmit` passa; zero ocorrências de leitura do campo fora comentários/build (`frontend/.next` é artefato gerado, ignorado).

**Índices (P1-2)**
- `backend/catalogo_noticias/migrations/0010_...` (nova) — `feed_status_ingestao` (`status_revisao`, `-timestamp_ingestao`), `newsitem_categoria`, `newsitem_urgente`, `newsitem_localidade` (`pais`, `estado`, `cidade` — recorte confirmado em `feed/busca.py`, `feed/services.py`, `radar/services.py`).
- `backend/catalogo_noticias/migrations/0011_newsitem_busca_trgm.py` (nova) — `CREATE EXTENSION IF NOT EXISTS pg_trgm` + GIN (`titulo`, `resumo_proprio`, `conteudo_completo` — campos do LIKE em `busca.py:88-96`) com guarda `connection.vendor != "postgresql"` → no-op. Reverso: `DROP INDEX IF EXISTS` (extensão mantida).

**Settings novas** (todas com env + default, documentadas em `backend/.env.example`)
- `FEED_JANELA_HORAS` (default 72) — janela de listagem do feed.
- `FEED_CACHE_TTL_SEGUNDOS` (default 45) — TTL cache das listagens.
- `GATING_CACHE_TTL_SEGUNDOS` (default 45) — TTL cache flag premium/recursos.

**Docs fora da lista do contrato (justificativa)**: `ARCHITECTURE.md`, `README.md`, `HISTORY.md`, `frontend/app/layout.tsx` (revert de `headers()` que forçava render dinâmico — P0 de outra run), `frontend/app/admin/robos/page.tsx` (placeholder de preço), `catalogo_noticias/tests/test_summarization_provider.py`, `feed/tests/test_algoritmos_busca.py`, `feed/tests/test_sanity.py` — a maioria veio de runs paralelas no mesmo working tree (P0/P1-gunicorn); os toques em `test_sanity.py`/`test_algoritmos_busca.py` são asserts do critério 6 desta run.

## Decisões
- Property `numero_fontes_distintas` **removida** (não mantida): qualquer caminho que a usasse reintroduziria COUNT silencioso; coluna + `recalcular_numero_fontes()` cobrem todos os usos.
- Cache com sufixo de usuário (`u{pk|anon}`) mesmo após remoção do campo per-user: defesa em profundidade (seções personalizam por interesses); anônimo — tráfego dominante — compartilha chave.
- Detalhe cluster/item e busca **sem** cache: por-id e volátil/personalizado; fora do padrão "listagem pública repetida".
- `sqlmigrate 0011` emite só "Raw Python operation" (esperado — `RunPython` não tem SQL estático); validade Postgres checada via teste com `SchemaEditor` fake + CI.

## Evidências
- `cd backend && DJANGO_DB_ENGINE=sqlite3 DJANGO_CACHE_BACKEND=locmem DJANGO_DEBUG=true .venv/bin/python -m pytest -q` → **431 passed** (66s).
- Com gate do CI: `--cov=. --cov-report=term-missing --cov-fail-under=80` → **431 passed, cobertura 87.74%** (gate 80 OK).
- Foco: `feed/tests/test_p1_feed_cache_indices.py + catalogo_noticias/tests/test_migracao_trgm.py` → **18 passed**.
- Sanidade manual: `GET /api/feed/` com 6 clusters × 2 itens = **2 queries** (itens+join, regras); SQL sem `conteudo_bruto`/`conteudo_completo`.
- `migrate --check` sqlite: limpo. `tsc --noEmit` (frontend): exit 0.

## Critérios de aceite (contrato v1)
1. ✅ Coluna vale N na criação e mesclagem (4 testes, incl. fonte repetida não infla).
2. ✅ Backfill reflete COUNT DISTINCT real + idempotente (2ª execução sem mudança).
3. ✅ `GET /api/feed/` com 6 clusters em exatas 2 queries (teto fixo; com regras ativas segue 2).
4. ✅ SQL das listagens sem `conteudo_bruto`/`conteudo_completo` (inspeção `connection.queries`).
5. ✅ 2º GET idêntico com 0 queries; `MeusRecursosView` 2 queries fria / 0 quente.
6. ✅ Nenhum endpoint do feed expõe `exibir_publicidade` (9 URLs); `tsc` sem referências.
7. ✅ sqlite limpo (grafo sem pendências no banco de teste + no-op com guarda); SQL Postgres validado via fake (`CREATE EXTENSION IF NOT EXISTS pg_trgm`, `USING gin` nos 3 campos, `DROP INDEX IF EXISTS` no reverso). Validade real no CI (Postgres).
8. ✅ Suíte + gate de cobertura passam (87.74% ≥ 80%).

## Remediação (iteração 1) — resposta aos 6 findings do review

- Finding 1 (major, `backend/feed/views.py:188-220`): `UrgentesView` remoto agora faz `pop("exibir_publicidade")` por entrada + `cache.set` no caminho remoto (mesmo padrão de `FeedListView`), com checagem de cache antes do branch remoto. Teste: `TestUrgentesMicroservicoRemediacao::test_urgentes_remoto_remove_publicidade_e_usa_cache` (remoto sem campo + 2o GET com `requests.get.call_count == 1`).
- Finding 2 (minor, `backend/gating/models.py:5-21,108-127`): `ConfiguracaoSistema.delete()` + `ConfiguracaoSistemaQuerySet.delete()` (cobre `filter(pk=1).delete()` em lote, que não chama `Model.delete()`). Teste: `TestGatingCache::test_premium_ativo_invalida_no_delete` (criar→deletar invalida).
- Finding 3 (minor, migração 0009): aceito com justificativa — backfill row-by-row correto e idempotente; volume inicial pequeno, migração roda uma vez; `ponytail:` teto = backfill row-by-row, migrar para agregação (`values().annotate(Count)`) quando `migrate` passar de minutos.
- Finding 4 (minor, migração 0011): NÃO reescrito para CONCURRENTLY (não roda dentro da transação de migração sem esquema especial); documentado no docstring da migração + aqui: rodar `migrate` em janela fria, tabela `NewsItem` bloqueada para escrita durante o `CREATE INDEX`.
- Finding 5 (nit, `backend/feed/recomendacao.py:491-494`): aplicado `.only(*CAMPOS_SEM_RELACAO)` nas candidatas da cobertura (novo `CAMPOS_SEM_RELACAO` em `backend/feed/services.py` — `CAMPOS_LISTA_FEED` sem travessia `__`, inválida em `.only()`); `construir_feed_entries` lê só esses campos, `pontuar_entrada` opera sobre dicts. Cobertura: suíte feed/gating + sanity/busca passam.
- Finding 6 (nit, `backend/feed/views.py:189-192`): `UrgentesView` agora com `try/except (TypeError, ValueError) → default 6` (`?limite=abc` → 200 em vez de 500). Teste: `test_urgentes_limite_invalido_cai_no_default`.

Revalidação: `feed/tests/test_p1_feed_cache_indices.py + test_microservice_client.py + gating/` → 42 passed; suíte completa com gate do CI (`--cov=. --cov-report=term-missing --cov-fail-under=80`) → **434 passed, 87.75%** (gate 80 OK). Frontend não tocado (sem `tsc`).

## Docs atualizadas (de documentation-update.md)
- `README.md:93-94` — linha `GET /api/gating/status/` na tabela gating.
- `ARCHITECTURE.md:43` — `NewsCluster.numero_fontes_distintas` documentada.
- `infra/DEPLOY.md` — nota de janela fria para migração 0011 (GIN não-CONCURRENTLY).
- Não-alterados: `backend/.env.example` (3 settings já presentes), `ARCHITECTURE.md:156` (citação histórica), specs/backlog.

## Pendências
- Validação real da 0011 em Postgres sai no CI (`backend-tests`, serviço postgres:16).
- `frontend/.next` contém `exibir_publicidade` em artefatos de build gerados — some no próximo `next build`; não é código-fonte.
- Sem commit (regra da run); tudo em working tree.
