<!--
CONTRACT: task-plan
DONO: orchestrator
QUANDO É CRIADO: no início desta execução, antes da implementação.
-->

# Task Plan — 20260923-1600-p2-backend-perf

## Metadados
- **run_id:** 20260923-1600-p2-backend-perf
- **Data de abertura:** 2026-09-23
- **Solicitado por:** Alex (humano) — lote P2 de performance/custo do backend
- **Spec de origem:** `ANALISE_CUSTO_PERFORMANCE.md`, seção 6 (Outros 🟢) e tabela P2 da seção 7 (itens P2-2, P2-3 e P2-4); não há spec separada em `agentic-framework/specs/`.

## Objetivo
Eliminar as perdas de custo e consultas no caminho de leitura e ingestão do backend: listagem de comunidade limitada e sem N+1, registro de busca fora do request, autocomplete com cache, configuração do Celery segura para ingestão longa e ingestão com validações HTTP persistidas, persistência em lote e uma única leitura de configuração por execução.

## Escopo
### Dentro do escopo
- **P2-3a:** paginação com `page`/`page_size` e teto equivalente a `FeedPagination` nas listagens públicas de publicações e comentários; `select_related("autor")` no queryset de publicações.
- **P2-3b:** despachar `EventoBusca` para uma task Celery, serializando somente dados primitivos e preservando `request_id`, usuário, sessão, filtros e número de resultados; sem INSERT síncrono no request de leitura.
- **P2-3c:** cachear vocabulário de autocomplete (categorias e títulos/palavras) com `django.core.cache` e TTL configurável.
- **P2-4:** configurar `task_acks_late=True`, `worker_prefetch_multiplier=1`, limite de tarefas por child e `task_reject_on_worker_lost=True`, documentando a idempotência por URL da ingestão.
- **P2-2:** enviar `If-None-Match`/`If-Modified-Since` e persistir os validators por `FonteRobo`; persistir `NewsItem` com `bulk_create` após verificar que não há signals/cálculos dependentes; consolidar `cfg_valor` em um snapshot por execução.
- Testes automatizados específicos para cada item, migrações aplicáveis em SQLite e PostgreSQL e atualização de `implementation-history.md`.

### Fora do escopo (explicitamente)
- Frontend, Next.js, `frontend/lib/api.ts`, componentes de comunidade, `.github/workflows/`, `infra/`, `docker-compose.yml` e qualquer outro deploy.
- P1/P2-1, P2-5, P2-6, P2-7, FTS dedicado, CDN/Cloudflare e alterações de preço/limites de LLM.
- Reescrita do algoritmo de busca, mudança das regras de curadoria/moderação, novos pacotes ou troca de broker.
- Transformar o endpoint de ingestão manual em Celery (o item desta run é a task periódica e a configuração do worker); a alteração do endpoint manual fica para uma run própria.

## Suposições assumidas
- O envelope paginado será usado quando o cliente enviar `page` ou `page_size`; a resposta padrão continuará sendo uma lista para não quebrar o consumidor frontend durante esta run, mas sempre estará limitada ao `page_size` padrão. — motivo: a regra proíbe tocar frontend e os clientes atuais tipam esses endpoints como `Publicacao[]`/`Comentario[]`; a API oferece paginação explícita sem materializar o acervo.
- A ingestão de URLs já persistidas pode ser repetida com segurança após reentrega Celery porque a checagem `_urls_ja_ingeridas` e a constraint única de `url_fonte_original` tornam o efeito idempotente; clusters são atualizados dentro de transações. — motivo: necessário para `acks_late` e `reject_on_worker_lost`.
- Uma tarefa Celery pode estar indisponível em desenvolvimento; a falha de enfileiramento será registrada e não causará escrita síncrona no request. — motivo: preservar a garantia de que o caminho de leitura nunca faça INSERT, mesmo sem broker.
- Para `EventoBusca`, `request_id` será persistido quando disponível e usuário será serializado como `user_id`, resolvido novamente na task; isso permite correlação e sobrevive à serialização JSON do Celery. — motivo: preservar a métrica sem enviar objeto de usuário entre processos.
- Os validators HTTP só serão gravados depois que a execução confirmar a persistência do lote; uma queda entre fetch e persistência deve provocar novo download, nunca um 304 com itens perdidos. — motivo: proteger a idempotência/reentrega da ingestão.

## Restrições
- Somente backend e os artefatos desta run; não alterar arquivos de outras runs/proibidos nem fazer commit.
- Migrações novas devem ser reversíveis quando possível e aplicar sem SQL específico de um vendor em SQLite/PostgreSQL; qualquer migration de schema torna a revisão obrigatória.
- Não adicionar dependências; usar `requests`, Celery, Redis/Django cache e Django ORM já instalados.
- A suíte obrigatória é `cd backend && DJANGO_DB_ENGINE=sqlite3 DJANGO_CACHE_BACKEND=locmem .venv/bin/python -m pytest -q -p no:cacheprovider --cov=. --cov-report=term-missing --cov-fail-under=80`.
- Código e comentários devem seguir o padrão existente (português, funções pequenas, falha de cache/tracking best-effort sem derrubar a leitura).

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | código + testes + implementation-history.md |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked |
| 3 | reviewer (**obrigatório**: migration de schema) | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. Uma listagem pública de comunidade grande nunca retorna mais que o tamanho de página padrão ou máximo solicitado, e o nome do autor é obtido sem uma consulta por registro.
2. Uma busca pública responde os resultados sem INSERT síncrono de `EventoBusca`; quando o broker aceita a task, o evento conserva consulta, resultados, filtros, sessão, usuário e `request_id` para as métricas.
3. Digitar o mesmo prefixo de autocomplete dentro do TTL reutiliza o vocabulário cacheado, e novas sugestões continuam aparecendo após expirar o TTL.
4. Uma tarefa de ingestão perdida no meio pode ser reentregue sem duplicar `NewsItem`, e o worker não reserva várias tarefas longas de uma vez.
5. Fontes RSS com ETag/Last-Modified são consultadas condicionalmente; uma resposta 304 não baixa nem parseia o XML e os validators são mantidos por fonte.
6. Uma execução de ingestão faz uma única leitura de `ConfiguracaoRobo` para suas várias consultas de `cfg_valor` e persiste o lote de itens com operação `bulk_create` segura.
7. A suíte completa passa com o gate de cobertura de 80% e as migrations aplicam em SQLite; o caminho Postgres é escrito de forma compatível com o vendor.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Cliente atual espera lista e passa a receber envelope | alto | modo de compatibilidade: lista limitada no request sem parâmetros; envelope DRF somente com `page`/`page_size`; documentar follow-up para migrar consumidores |
| Task de evento perdida ou duplicada | médio | `request_id` único quando presente, `get_or_create` na task e log de falha de enqueue sem fallback síncrono |
| Reentrega da ingestão cria duplicatas ou clusters extras | alto | manter consulta de URLs + unique constraint + transações; teste de idempotência após worker perdido |
| `bulk_create` ignora `save()`/signals | alto | inspeção de signals, chamar `clean()` por objeto, manter check constraint e teste de fonte obrigatória/camadas de DB |
| Validator HTTP salvo em fonte errada ou resposta 304 mal tratado | médio | associar provider ao `FonteRobo` por id, persistir somente após parse válido e testar headers/304 |
| Cache de autocomplete serve dados antigos | baixo | TTL curto e versionado; evento/ingestão não bloqueiam a leitura, apenas atualizam a fonte de verdade |
| Migration com campo novo quebra vendor | médio | migration Django padrão para validators e `request_id`, sem SQL específico; teste `migrate --check`/SQLite e validação Postgres |

## Dependências
- Redis/Celery já configurados no ambiente de produção; em testes, o cache pode ser locmem e a task pode ser testada diretamente ou com `always_eager` explícito.
- A revisão formal é obrigatória porque a implementação inclui ao menos um migration de schema (validators de `FonteRobo` e, se confirmado no contrato, `request_id` do evento). Não há dependência de decisão humana para o código; resta follow-up de migração dos consumidores frontend para o envelope paginado.
