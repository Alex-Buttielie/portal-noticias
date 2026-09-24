# Code Review Contract — 20260923-2150-review-p1-feed-cache

## Metadados
- **run_id:** 20260923-2150-review-p1-feed-cache
- **Escopo revisado:** diff não-commitado vs HEAD=4174998, lote P1 (24 arquivos modified + 5 novos: 0009/0010/0011, test_migracao_trgm.py, test_p1_feed_cache_indices.py)
- **Contrato de referência:** implementation-contract.md (20260923-1216-p1-feed-cache-indices)
- **Gatilhos aplicados (de review-triggers.md):** migracao-schema, api-publica-breaking, cache-variacao-por-usuario, only-defer, seguranca-migrate, frontend-ads
- **Verificação executada:** `pytest` completa passa (431 passed); recorte P1 passa (58 passed: test_migracao_trgm + test_p1_feed_cache_indices + test_sanity + test_algoritmos_busca + test_summarization_provider)

## Findings

### Finding 1
- **Arquivo:** backend/catalogo_noticias/admin.py
- **Linha:** 55
- **Categoria:** correctness
- **Severidade:** minor
- **Resumo:** `NewsItemAdmin` (edição direta de item) não recalcula `numero_fontes_distintas` — só `NewsClusterAdmin.save_related` recalcula.
- **Cenário de falha:** admin reatribui item a outro cluster (ou edita `nome_fonte`) pela página do item → coluna denormalizada dos clusters antigo/novo fica stale (display `numero_fontes` errado; reavaliação de alta relevância não dispara nesse caminho).
- **Sugestão:** chamar `recalcular_numero_fontes()` nos clusters afetados em `NewsItemAdmin.save_model` (antigo + novo), ou documentar como residual aceito (drift só via admin, corrigível pelo backfill idempotente).

### Finding 2
- **Arquivo:** backend/feed/views.py
- **Linha:** 194
- **Categoria:** correctness
- **Severidade:** minor
- **Resumo:** `UrgentesView` no caminho microserviço retorna payload remoto sem `pop("exibir_publicidade")` e sem cache (FeedList/detalhes fazem o strip).
- **Cenário de falha:** microserviço ligado (hoje desligado por default) espelhando contrato antigo com flag per-entry → `/api/feed/urgentes/` vaza `exibir_publicidade`, quebrando o "saiu de TODOS os payloads".
- **Sugestão:** aplicar o mesmo `pop` defensivo (por entrada) no retorno de `obter_urgentes`, ou documentar que o serviço remoto já segue o contrato novo.

### Finding 3
- **Arquivo:** backend/catalogo_noticias/migrations/0011_newsitem_busca_trgm.py
- **Linha:** 31
- **Categoria:** security
- **Severidade:** minor
- **Resumo:** `CREATE EXTENSION IF NOT EXISTS pg_trgm` exige privilégio de superuser/`CREATE` no banco — migrate falha em prod se o usuário for restrito.
- **Cenário de falha:** banco gerenciado com usuário sem privilégio de extensão → `migrate` quebra no deploy mesmo com a guarda por vendor correta.
- **Sugestão:** checagem operacional pré-deploy (confirmar extensão pré-instalada ou privilégio do usuário em prod/CI Postgres); sem mudança de código.

### Finding 4
- **Arquivo:** backend/feed/recomendacao.py
- **Linha:** 491
- **Categoria:** performance
- **Severidade:** minor
- **Resumo:** `cobertura_completa` busca até 200 `NewsItem` relacionados com fetch completo (inclui `conteudo_bruto`/`conteudo_completo`), fora do padrão `.only()` do caminho de lista.
- **Cenário de falha:** cobertura de categoria volumosa → detalhe carrega colunas pesadas de 200 linhas para derivar 5 relacionadas (custo aceito hoje, mas inconsistente com o objetivo P1).
- **Sugestão:** aplicar `.only(*CAMPOS_LISTA_FEED)` nesse queryset (só lista usa os campos), ou registrar como residual fora do contrato (detalhe não tem teto de queries).

### Finding 5
- **Arquivo:** backend/gating/services.py
- **Linha:** 35
- **Categoria:** correctness
- **Severidade:** minor
- **Resumo:** invalidação do cache de gating só via `save()`/`delete()` — `queryset.update()` em massa não invalida (stale até 45s).
- **Cenário de falha:** escrita em massa em `FeatureLimit`/`ConfiguracaoSistema` (shell, fixture, migração de dados) → `MeusRecursosView`/flag premium servem valor antigo por um TTL.
- **Sugestão:** nenhuma mudança necessária se o TTL for o mecanismo aceito (documentar); alternativa é chamar `invalidar_cache_gating()` nos pontos de escrita em massa conhecidos.

### Finding 6
- **Arquivo:** backend/feed/views.py
- **Linha:** 48
- **Categoria:** performance
- **Severidade:** nit
- **Resumo:** chave de cache por querystring normalizada aceita cardinalidade ilimitada (qualquer param arbitrário gera entrada de 45s).
- **Cenário de falha:** tráfego com querystrings aleatórias (`?x=<rand>`) → muitas entradas curtas em locmem/Redis (baixo impacto pelo TTL de 45s).
- **Sugestão:** se um dia virar problema, branquear params conhecidos na chave; hoje não fazer nada.

### Finding 7
- **Arquivo:** backend/catalogo_noticias/migrations/0011_newsitem_busca_trgm.py
- **Linha:** 12
- **Categoria:** maintainability
- **Severidade:** nit
- **Resumo:** nome da tabela (`catalogo_noticias_newsitem`) hardcoded no DDL cru.
- **Cenário de falha:** futuro `db_table` customizado no modelo → migração cria índice na tabela errada (hoje o nome confere com o default).
- **Sugestão:** derivar via `apps.get_model(...)._meta.db_table` se a migração for tocada novamente; hoje não fazer nada.

## Resumo quantitativo
| Severidade | Quantidade |
|---|---|
| blocker | 0 |
| major | 0 |
| minor | 5 |
| nit | 2 |

## Veredito
**approve_with_comments**

Sem blocker/major: backfill idempotente com guarda por vendor, `.only()` sem deferred-touch, `exibir_publicidade` fora de todos os payloads locais, cache sem vazamento entre usuários e suíte completa verde (431 passed). Findings 1–5 são minors residuais (drift via admin, strip no path remoto de urgentes, privilégio de extensão em prod, fetch completo em relacionadas, invalidação em escrita massiva) — nenhum impede merge.
