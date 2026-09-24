<!--
CONTRACT: implementation-contract
DONO: orchestrator (preenche) / executor, tester, reviewer (leem)
-->

# Implementation Contract — 20260923-1600-p2-backend-perf

## Metadados
- **run_id:** 20260923-1600-p2-backend-perf
- **Deriva de:** task-plan.md (20260923-1600-p2-backend-perf)
- **Versão do contrato:** 2

## O que deve ser construído

### P2-3a — comunidade paginada e sem N+1
1. Introduzir paginação de página numérica para `GET /api/comunidade/publicacoes/` e `GET /api/comunidade/comentarios/`, com `page`, `page_size`, default 20 e máximo 100, no mesmo padrão de `FeedPagination`.
2. Aplicar `select_related("autor")` à listagem de publicações antes da serialização de `autor_nome`; preservar filtros, ordenação e a anotação de comentários.
3. Por compatibilidade com os clientes atuais que não enviam parâmetros de paginação, a resposta padrão será a lista já limitada; ao enviar `page` ou `page_size`, responder o envelope paginado DRF (`count`, `next`, `previous`, `results`). Nenhum request pode materializar o acervo inteiro.

### P2-3b — evento de busca assíncrono
1. Criar task Celery `feed.tasks.registrar_evento_busca` que receba apenas valores JSON-serializáveis: query, resultados, `user_id`, sessão, filtros e `request_id`; resolver o usuário por id dentro da task e persistir `EventoBusca`.
2. Alterar `registrar_busca` para enfileirar a task e nunca chamar `EventoBusca.objects.create` no caminho de leitura. Falha de broker/enqueue deve ser best-effort, logada e não convertida em escrita síncrona.
3. Tornar o evento idempotente quando `request_id` existir, para reentrega de task não duplicar a métrica; preservar o comportamento de eventos sem request id.

### P2-3c — autocomplete com cache
1. Adicionar setting `FEED_AUTOCOMPLETE_CACHE_TTL_SEGUNDOS` (default curto, configurável por ambiente) e usar `django.core.cache`.
2. Cachear, sob chave versionada, o vocabulário de categorias e títulos/palavras usado pelo autocomplete. A chave de cache deve incluir o prefixo normalizado ou permitir filtrar o payload em memória; a consulta de termos populares pode ter snapshot separado com o mesmo TTL.
3. Não cachear resposta dependente de usuário; a fonte continua sendo `NewsItem`/`EventoBusca` e a invalidação natural é o TTL.

### P2-4 — Celery confiável para ingestão longa
1. Adicionar settings no namespace `CELERY`: `CELERY_TASK_ACKS_LATE=True`, `CELERY_WORKER_PREFETCH_MULTIPLIER=1`, `CELERY_WORKER_MAX_TASKS_PER_CHILD` e `CELERY_TASK_REJECT_ON_WORKER_LOST=True`.
2. Documentar que a task de ingestão é idempotente por URL e por transações de grupo, e que a reentrega após worker perdido não deve duplicar item; não alterar regras de curadoria.

### P2-2 — ingestão HTTP condicional, lote e configuração
1. Adicionar `etag` e `last_modified` a `FonteRobo` com migration Django padrão, associar cada provider RSS ao registro correspondente e enviar `If-None-Match`/`If-Modified-Since` quando houver validator.
2. Em resposta 304, retornar lista vazia sem parsear corpo; em resposta 200 válida, capturar os validators e só persisti-los no `FonteRobo` depois que os `NewsItem` e o registro da execução terminarem sem erro. Essa confirmação tardia impede que uma queda entre o fetch e a persistência faça o próximo request receber 304 e perder o lote. Fontes seed sem linha correspondente ao modelo não podem quebrar a execução.
3. Trocar os `NewsItem.objects.create` dos dois caminhos de persistência por `bulk_create` em lote, depois de `clean()`/validação em memória. Confirmar no código que não existem signals nem cálculos que dependam de `save()`; manter a check constraint e as transações.
4. Adicionar um context manager/snapshot de `cfg_valor` que carregue `ConfiguracaoRobo` uma única vez por `executar_ingestao`, reutilizado pelas funções auxiliares e providers, e descarte o snapshot ao final inclusive em exceção.

## Áreas/arquivos esperados
- `backend/comunidade/views.py` e `backend/comunidade/tests/` — paginação/`select_related`.
- `backend/feed/busca.py`, `backend/feed/views.py` (somente se necessário para contexto), `backend/feed/tasks.py`, `backend/feed/models.py`, `backend/feed/migrations/` e testes de feed — async/cache.
- `backend/config/settings.py`, `backend/config/settings_test.py` (somente isolamento de testes) — cache/Celery.
- `backend/catalogo_noticias/models.py`, `backend/catalogo_noticias/providers/news_source.py`, `backend/catalogo_noticias/services/config_robo.py`, `backend/catalogo_noticias/services/ingestao.py`, `backend/catalogo_noticias/migrations/` e testes de ingestão.
- `agentic-framework/state/run-20260923-1600-p2-backend-perf/implementation-history.md` — evidências e decisões.
- Qualquer alteração fora dessa lista deve ser justificada no histórico; não tocar frontend, `.github/workflows/`, `infra/` ou `docker-compose.yml`.

## Interfaces afetadas
- **API pública:** listagens da comunidade passam a aceitar `page`/`page_size` e retornam envelope quando paginação explícita é solicitada; o default limitado mantém compatibilidade de formato.
- **Celery:** nova task `feed.tasks.registrar_evento_busca`; chamadas usam IDs/strings, nunca objetos Django.
- **Schema:** novos validators em `FonteRobo`; `request_id` em `EventoBusca` se a opção idempotente for implementada. Ambas exigem migration e revisão.
- **Comportamento de ingestão:** 304 representa feed sem alterações; 200 continua sendo parseado e persistido; validators só avançam após a conclusão segura do lote; URLs já ingeridas continuam ignoradas.

## Critérios de aceite (técnicos, testáveis)
1. Dado um queryset com mais de 20 publicações/comentários, quando `GET` é chamado sem `page_size`, então no máximo 20 itens são serializados; dado `page_size=500`, então no máximo 100 são retornados e `page` avança a página.
2. Dado várias publicações de autores distintos, quando a listagem é serializada, então `select_related("autor")` está presente e o número de queries de autor não cresce com o número de publicações.
3. Dado uma busca pública com broker disponível, quando a view responde, então nenhum `INSERT` em `EventoBusca` ocorre antes do retorno e a task recebe `user_id`/`request_id`/sessão/filtros; dado a task, quando ela roda, então o evento é criado com o usuário resolvido.
4. Dado a mesma task repetida com o mesmo `request_id`, quando executada duas vezes, então existe no máximo um `EventoBusca` para esse request.
5. Dado `autocomplete("prefixo")` duas vezes dentro do TTL, quando a segunda chamada ocorre, então o vocabulário cacheado é reutilizado e não há nova varredura de `NewsItem`; expirado o TTL, o snapshot é reconstruído.
6. Dado uma fonte com ETag/Last-Modified, quando a próxima busca envia os validators e o servidor responde 304, então o provider envia ambos os headers, retorna vazio sem parsear XML e mantém os campos; quando responde 200, então captura os headers e só os persiste após a confirmação pós-persistência.
7. Dado um lote de itens válidos em `_persistir_grupo` ou `_persistir_grupo_mesclado`, quando a persistência termina, então `bulk_create` é usado, os objetos têm PKs e o número de inserts é constante em relação ao tamanho do lote.
8. Dado uma execução que chama `cfg_valor`/`categorias_sensiveis` várias vezes, quando ela termina, então `ConfiguracaoRobo` foi consultada no máximo uma vez para o snapshot e uma nova execução pode ver configuração alterada.
9. As settings Celery têm os valores de acks late/prefetch/rejeição documentados, e um teste de reentrega não duplica itens por URL.
10. `migrate` aplica em SQLite; toda operação específica de PostgreSQL, se houver, é guardada por `connection.vendor`; a suíte completa passa com cobertura mínima de 80%.
11. Dado um worker que cai entre o fetch 200 e a persistência dos itens, quando a task é reentregue, então os validators ainda não foram confirmados, o XML é buscado novamente e a constraint de URL evita duplicidade.

## Não-objetivos
- Não modificar frontend/consumidores, UI, Nginx, workflows, Compose, FTS, curadoria, moderação, autenticação ou preços de LLM.
- Não transformar a ingestão manual em task nem adicionar dependência/broker novo.
- Não garantir freshness instantânea do autocomplete; TTL e consistência eventual são deliberados.
- Não persistir payload bruto de request, cookie, IP ou user-agent no evento de busca.

## Restrições técnicas
- **Performance:** limitar queries e materialização; `bulk_create` deve ser transacional e não pode retirar validações de `NewsItem`.
- **Segurança/privacidade:** somente nome/id de usuário já presente no modelo; `request_id` é identificador técnico limitado, sem IP, cookie ou conteúdo sensível; task recebe dados JSON.
- **Dependências permitidas:** nenhuma; usar bibliotecas já declaradas.
- **Estilo/convenções:** português, docstrings justificando decisões, imports explícitos, testes pytest-django com SQLite/locmem.
- **Revisão:** obrigatória (`review-triggers.md`: migration de schema; a task de background também altera contrato/evento).

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Testes escritos e passando (tester)
- [ ] Revisão de código aprovada (reviewer — obrigatório)
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente
