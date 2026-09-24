# Code Review Contract — 20260923-1216-p1-feed-cache-indices

## Metadados
- **run_id:** 20260923-1216-p1-feed-cache-indices
- **Escopo revisado:** working tree diff (~423+/102- em 24 arquivos) + migrações untracked 0009/0010/0011
- **Contrato de referência:** implementation-contract.md (20260923-1216-p1-feed-cache-indices)
- **Gatilhos aplicados (de review-triggers.md):** migração de schema de banco de dados; mudança em API pública; diff > ~300 linhas; direitos autorais/compliance (BRD seção 18 — feed decide o que é publicado, verificado sem alteração)

## Findings

### Finding 1
- **Arquivo:** backend/feed/views.py
- **Linha:** 192-199
- **Categoria:** correctness
- **Severidade:** major
- **Resumo:** `UrgentesView` no caminho microserviço não remove `exibir_publicidade` nem usa cache
- **Cenário de falha:** com `MICROSERVICO_INGESTAO_URL` configurada, `GET /api/feed/urgentes/` repassa `Response(microservice_client.obter_urgentes(...))` cru — `FeedListView`/`ClusterDetailView`/`ItemDetailView` fazem `pop("exibir_publicidade")`, este não; viola critério de aceite 6 só com microserviço ligado (default desligado, por isso não é blocker)
- **Sugestão:** aplicar o mesmo `pop("exibir_publicidade", None)` por elemento da lista + `cache.set` no caminho remoto, espelhando `FeedListView`

### Finding 2
- **Arquivo:** backend/gating/models.py
- **Linha:** 89-97
- **Categoria:** correctness
- **Severidade:** minor
- **Resumo:** `ConfiguracaoSistema` invalida cache no `save()` mas não tem `delete()`
- **Cenário de falha:** `ConfiguracaoSistema.objects.filter(pk=1).delete()` via ORM/admin deixa `gating:v1:premium_ativo` stale até o TTL (45s) — `FeatureLimit` cobre save+delete, este modelo não
- **Sugestão:** adicionar `delete()` com invalidação igual ao `save()`

### Finding 3
- **Arquivo:** backend/catalogo_noticias/migrations/0009_newscluster_numero_fontes.py
- **Linha:** 14-27
- **Categoria:** performance
- **Severidade:** minor
- **Resumo:** backfill emite 1 COUNT + até 1 UPDATE por cluster (2N queries)
- **Cenário de falha:** banco com dezenas de milhares de clusters roda dezenas de milhares de queries no `migrate` — idempotente e correto, só lento; `iterator(chunk_size=500)` limita memória, não queries
- **Sugestão:** aceitar como está para o volume atual; se o acervo crescer, agregar em 1 query (`values("cluster_id").annotate(n=Count("nome_fonte", distinct=True))`) com updates em lote — `ponytail:` teto = backfill row-by-row; migrar para agregação quando `migrate` passar de minutos

### Finding 4
- **Arquivo:** backend/catalogo_noticias/migrations/0011_newsitem_busca_trgm.py
- **Linha:** 26-29
- **Categoria:** performance
- **Severidade:** minor
- **Resumo:** `CREATE INDEX` não-concorrente bloqueia escritas na tabela durante a migração
- **Cenário de falha:** em produção com ingestão contínua, `migrate` trava writes em `catalogo_noticias_newsitem` pelo tempo da construção do GIN (tabela com `conteudo_completo` = índice pesado); `CONCURRENTLY` não roda dentro da transação do Django, então o trade-off é consciente
- **Sugestão:** manter, mas rodar o `migrate` em janela de baixo tráfego; documentar no history

### Finding 5
- **Arquivo:** backend/feed/recomendacao.py
- **Linha:** 491-494
- **Categoria:** performance
- **Severidade:** nit
- **Resumo:** candidatas de relacionadas (`cobertura_completa`, até 200 linhas) com fetch completo incluindo colunas pesadas
- **Cenário de falha:** só custo extra de I/O por request de cobertura (fora do caminho quente do feed, sem `.only()`); sem incorreção
- **Sugestão:** aplicar `.only(*CAMPOS_LISTA_FEED)` como na busca, ou deixar (cobertura é por-id, baixo volume)

### Finding 6
- **Arquivo:** backend/feed/views.py
- **Linha:** 189
- **Categoria:** correctness
- **Severidade:** nit
- **Resumo:** `UrgentesView` faz `int(query_params["limite"])` sem `try/except` (`?limite=abc` → 500)
- **Cenário de falha:** pré-existente (não introduzido nesta run); `HomeSecoesView`/`DestaquesDiaView` tratam `ValueError`, esta não
- **Sugestão:** copiar o padrão `try/except → default` das vizinhas

## Verificações sem finding (escopo pedido, tudo certo)
- **Migrações 0009/0010:** reversíveis (`AddField` reverte com drop; reverso do `RunPython` no-op; `AddIndex` reversível); guarda vendor da 0011 correta (`schema_editor.connection.vendor != "postgresql"` → no-op, mesma guarda no reverso); nomes de índice sem colisão (`feed_status_ingestao`, `newsitem_categoria/urgente/localidade`, `newsitem_busca_trgm`); `sqlmigrate` emitir "Raw Python operation" é esperado.
- **Caminhos de escrita da coluna:** `_persistir_grupo` grava na criação; `_persistir_grupo_mesclado` recalcula do banco após mover/criar (cobre fusão, promoção de standalone e crescimento); `admin.save_related` cobre inline; sem signals/fixtures que escrevam cluster; `bulk_create` só em testes.
- **`.only()`:** todos os campos lidos no caminho de lista (`construir_feed_entries`, `_timestamp_ordenacao`, `aplicar_regras_curadoria` via `getattr autor/cluster_id/id`, `_relevancia` + `tags` incluído na busca, recomendação sobre dicts) estão em `CAMPOS_LISTA_FEED`; filtro `conteudo_completo__icontains` é SQL-side, não toca Python; detalhe com fetch completo.
- **Cache:** chave = querystring normalizada ordenada + sufixo usuário (cobre categoria/busca/page/page_size/limite/região); TTL respeitado via `_ttl_feed()`; só endpoints `AllowAny` sem payload per-user (pós-remoção do campo); personalização da home isolada por `pk`; `MeusRecursosView` 1 query + cache por plano, invalidado em escrita.
- **`exibir_publicidade`:** fora de todos os payloads locais, serializers nunca tiveram o campo, frontend sem nenhuma leitura fora comentários/build (`FeedResposta`/`FeedDetalhe`/home viraram comentários, fallbacks limpos, ads via `usePremiumAtivo()` → `/api/gating/status`); exceção: Finding 1 (urgentes remoto).
- **Regressão funcional:** filtros/busca/paginação/ordenação/curadoria intactos; janela 72h é mudança intencional do contrato (teste atualizado); busca sem janela preserva resultados.
- **Compliance BRD-18:** `_resumo_e_copia_ou_quase_copia`, `itens_publicaveis` (só publicáveis) e 404 de detalhe sem conteúdo aprovado intocados.

## Resumo quantitativo
| Severidade | Quantidade |
|---|---|
| blocker | 0 |
| major | 1 |
| minor | 3 |
| nit | 2 |

## Veredito
**changes_requested**

Finding 1 viola o critério de aceite 6 no caminho microserviço (único payload do feed sem `pop` na borda); resto é endurecimento menor. Corrigir 1 (one-liner) e 2 para aprovar.

## Re-revisão iteração 1

- **Finding 1 (major):** resolvido. `UrgentesView` (`backend/feed/views.py:188-220`) checa cache antes do branch remoto, faz `pop("exibir_publicidade")` por entrada dict + `cache.set` no caminho remoto, espelhando `FeedListView`. Teste `TestUrgentesMicroservicoRemediacao::test_urgentes_remoto_remove_publicidade_e_usa_cache` válido (strip + `requests.get.call_count == 1` no 2º GET).
- **Finding 2 (minor):** resolvido. `ConfiguracaoSistema.delete()` + `ConfiguracaoSistemaQuerySet.delete()` invalidam nos dois caminhos (cobre `filter(pk=1).delete()`); sem cascata (modelo sem FKs entrantes) nem duplo sinal (invalidação best-effort idempotente). Teste `test_premium_ativo_invalida_no_delete` passa.
- **Finding 3 (minor):** aceito com justificativa. Backfill correto + idempotente (só grava quando diverge), roda uma vez, `iterator(chunk_size=500)` limita memória. Porém o marcador `ponytail:` existe só em `implementation-history.md:69`, não como comentário no código da 0009 — pedir one-liner `ponytail:` no docstring da migração.
- **Finding 4 (minor):** resolvido. Docstring da 0011 (`0011_newsitem_busca_trgm.py:11-15`) documenta janela fria + bloqueio de escrita + motivo do não-`CONCURRENTLY`; precisa e suficiente.
- **Finding 5 (nit):** resolvido. `.only(*CAMPOS_SEM_RELACAO)` exclui só a travessia `cluster__numero_fontes_distintas` (válido em `.only()`); `construir_feed_entries` verificado com 0 queries extras (`numero_fontes` via `select_related`, `pontuar_entrada` sobre dicts).
- **Finding 6 (nit):** resolvido. `try/except (TypeError, ValueError) → default 6` cobre ausente/str inválida/float-string; default 6 consistente com `HomeSecoesView`. Nota: `MaisLidasView:227` mantém `int()` sem guarda (pré-existente, fora do escopo dos findings).
- **Escopo:** remediação restrita aos 6 findings (views/gating/recomendacao/services + testes + docstring 0011); nenhum extra.

## Veredito (iteração 1)
**approve_with_comments**

Funcional tudo resolvido (suíte 29 passed no foco; `CAMPOS_SEM_RELACAO` com 0 queries extras confirmado). Comentários: (1) adicionar `ponytail:` no docstring da 0009; (2) opcional: mesma guarda `try/except` em `MaisLidasView:227`.

## Nota do orchestrator (ressalva do finding 3)
O reviewer aprovou com a ressalva de que o `ponytail:` do backfill row-by-row
vive só no `implementation-history.md`, não no código da migração 0009.
Decisão: aceito — migração é artefato run-once; poluir seu código com nota de
performance futura confundiria a leitura do schema. O registro no histórico +
critério de volume ("quando `migrate` passar de minutos") é o lugar certo.
