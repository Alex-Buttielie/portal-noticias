# Task Plan — 20260923-1216-p1-feed-cache-indices

## Metadados
- **run_id:** 20260923-1216-p1-feed-cache-indices
- **Data de abertura:** 2026-09-23
- **Solicitado por:** Alex (humano) — pedido: prosseguir com o lote P1
- **Spec de origem:** nenhuma (deriva de `ANALISE_CUSTO_PERFORMANCE.md`, seção 7 — itens P1-1 e P1-2)

## Objetivo
O feed público (padrão de tráfego dominante) passa a responder com número limitado e constante de queries por request — via coluna denormalizada, corte no SQL, cache curto e índices — sem mudar o conteúdo entregue, exceto a flag `exibir_publicidade`, que migra para o endpoint dedicado de gating.

## Escopo
### Dentro do escopo
- P1-1: (a) denormalizar `numero_fontes_distintas` como coluna de `NewsCluster` (migração + backfill + atualização dos caminhos de persistência na ingestão); (b) `.only()`/defer de `conteudo_bruto`/`conteudo_completo` nas listagens + janela de tempo no SQL; (c) cache 30–60s das listagens públicas com chave por querystring normalizada; (d) remover `exibir_publicidade` dos payloads do feed e migrar o frontend para `/api/gating/status` (já consumido via `lib/premium.ts`); (e) cache curto de `ConfiguracaoSistema`/limites no caminho do feed.
- P1-2: migração com índice composto `(status_revisao, -timestamp_ingestao)` + índices em `categoria`/`urgente`/localidade em `NewsItem`; extensão `pg_trgm` + índice GIN para a busca (LIKE existente passa a usá-lo, sem reescrever queries).

### Fora do escopo (explicitamente)
- P1-3/P1-4/P1-5 (Gunicorn, Nginx, CI) e P1-6 (React Query): runs próprias (B e C).
- `EventoBusca` async, paginação da comunidade, rewrite da busca para FTS, cache de borda/Cloudflare: P2 ou futuro.
- Troca de provedor de LLM e demais itens do backlog.

## Suposições assumidas
- Staleness de 30–60s no feed público é aceitável (padrão já praticado pelo ISR de 60s no frontend) — motivo: dispensa invalidação explícita na ingestão.
- Janela de listagem do feed em 72h por padrão — motivo: cobre o ciclo de notícias sem varrer o acervo; reversível via parâmetro.

## Restrições
- Migração deve aplicar em **sqlite (dev/teste local) E Postgres (CI/prod)**: `TrigramExtension` e GIN trigram quebram no sqlite — isolar em migração com guarda por `connection.vendor`, sem falhar o `migrate` local.
- `GET /api/metricas/painel/` e admin continuam vendo dados consistentes (a coluna denormalizada é atualizada em todos os caminhos de escrita da ingestão, incluindo mesclagem de grupos).
- Testes seguem `backend/pytest.ini`; `pytest --cov-fail-under=80` deve continuar passando.
- Nenhuma dependência nova.

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | código + implementation-history.md |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked |
| 3 | reviewer (**obrigatório**: migração de schema + mudança em API pública) | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. O feed público faz um número pequeno e constante de queries por request, independente do volume do acervo.
2. Requests repetidos ao feed dentro de 1 minuto não rebatem no banco.
3. Buscas e filtros por categoria continuam retornando os mesmos resultados (só mais rápido).
4. O frontend continua exibindo/ocultando publicidade corretamente para free/premium, agora via endpoint de gating.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Coluna denormalizada dessincronizar em algum caminho de escrita | alto | mapear TODOS os caminhos (`_persistir_grupo`, `_persistir_grupo_mesclado`, merges) + backfill + teste dedicado |
| Migração `pg_trgm` quebrar `migrate` no sqlite (dev/teste) | médio | guarda por `connection.vendor`; CI (Postgres) valida o caminho real |
| `.only()` causar N+1 de deferred fields no pipeline (`equilibrar`, regras de curadoria) | médio | carregar explicitamente todos os campos usados no caminho de lista; teste com `assertNumQueries` |
| Frontend com uso esquecido de `exibir_publicidade` do feed | médio | grep exaustivo no frontend; `tsc --noEmit` como rede de segurança |

## Dependências
- Nenhuma decisão humana pendente. Deploy em produção exigirá `migrate` (já parte do entrypoint) — sem ação manual além do deploy normal.
