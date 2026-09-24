# Report — 20260923-1600-p2-backend-perf

## Objetivo

Executar o lote P2 de performance/custo do backend, eliminando materialização e queries desnecessárias no caminho de leitura, reduzindo custo de ingestão e impede efeitos síncronos ou reentregas inseguras sem alterar frontend, infraestrutura ou as regras de curadoria. O escopo cobriu P2-2 (ingestão HTTP condicional, lote e snapshot de configuração), P2-3a/b/c (comunidade, métrica de busca e autocomplete) e P2-4 (Celery confiável por task).

## Itens implementados

### P2-2 — ingestão condicional, lote e snapshot

- `FonteRobo` passou a persistir `etag` e `last_modified`; o provider RSS envia `If-None-Match` e `If-Modified-Since` quando há validators válidos.
- Resposta `304` retorna vazio sem baixar/parsear o XML. Os validators são capturados após parse válido, mas confirmados somente depois de todos os itens e do registro da execução serem persistidos, evitando a janela de perda entre fetch e persistência.
- A reconciliação completa sem headers é feita a cada `CATALOGO_NOTICIAS_REVALIDACAO_COMPLETA_HORAS` (padrão 6 horas), protegendo contra 304 falso, exclusão/restauração local ou URL trocada durante a execução. Falha de fetch invalida os validators com comparação condicional.
- Os dois caminhos de persistência de `NewsItem` usam `bulk_create` após `clean()` e deduplicação, com retry/requery em conflito de URL; a constraint única continua sendo a garantia final.
- `cfg_valor` usa um snapshot de `ConfiguracaoRobo` por execução, carregado uma vez e descartado em `finally`, inclusive em exceção.

### P2-3a — paginação de comunidade

- `CommunityPagination` aceita `page`/`page_size`, com padrão 20 e máximo 100.
- A resposta legada sem parâmetros continua sendo a lista esperada pelos consumidores atuais; requests com paginação explícita recebem o envelope DRF (`count`, `next`, `previous`, `results`).
- A listagem de publicações usa `select_related("autor")`, eliminando o N+1 de autores.

### P2-3b — `EventoBusca` assíncrono

- `feed.tasks.registrar_evento_busca` recebe somente valores JSON-serializáveis, resolve `user_id` no worker e persiste `EventoBusca`.
- `registrar_busca` apenas enfileira a task; não existe `EventoBusca.objects.create` no caminho de leitura nem fallback síncrono quando o broker falha. A falha de enqueue é best-effort e logada.
- `request_id` permite idempotência da métrica em reentregas; o sentinel `-`/vazio é tratado como ausência de ID.

### P2-3c — cache de autocomplete

- Categorias, títulos e termos populares são snapshots versionados em `django.core.cache`, com `FEED_AUTOCOMPLETE_CACHE_TTL_SEGUNDOS=300` por padrão.
- O filtro por prefixo ocorre em memória, evitando nova varredura `DISTINCT` a cada tecla; falhas de cache são degradadas para reconstrução.
- A ingestão invalida as chaves após cada lote. TTL e invalidação são complements: eventos/admin que escapem da escrita podem aguardar a expiração.

### P2-4 — Celery por task

- O worker usa prefetch 1 e recycle de 100 tarefas por child.
- `acks_late` e `reject_on_worker_lost` ficam explicitamente nas tasks idempotentes de ingestão e `EventoBusca`, não em defaults globais.
- Tasks de newsletter, B2B e assinatura, com efeitos externos sem idempotência durável, mantêm `acks_late=False`/`reject_on_worker_lost=False`.

## Testes e validações

- Suíte final obrigatória: **462 passed**, cobertura total **88,34%** (gate mínimo de 80%).
- Re-revisão focada: 27 testes P2 direcionados passaram; suíte completa na re-revisão: 462 passed.
- `manage.py check`: sem problemas.
- `makemigrations --check --dry-run`: `No changes detected`.
- `migrate` em SQLite limpo aplicou as migrations `catalogo_noticias.0012`, `catalogo_noticias.0013` e `feed.0003`.
- Não havia PostgreSQL em `localhost:5432` no sandbox; a aplicação real dessas migrations em PostgreSQL permanece uma verificação de CI.

## Revisão

- Primeira revisão: **changes_requested**, com 6 major, 2 minor e 1 nit.
- Remediação: **8/9 findings tratados**; a Finding 7 (minor) foi aceita com benchmark e justificativa de compatibilidade para preservar `clean()` e as URLs históricas.
- Re-revisão: **approve_with_comments**, com 6/6 majors confirmados como resolvidos. Permanecem ressalvas não bloqueantes de consistência eventual/observabilidade, detalhadas nos follow-ups.

## Documentação

- `README.md` foi atualizado para documentar paginação da comunidade, validators RSS e reconciliação periódica, Celery por task, `EventoBusca` assíncrono e a relação com rate limiting.
- `backend/.env.example` foi verificado: TTL de autocomplete, revalidação completa e limite de tarefas por child já estavam presentes com defaults e motivo.
- `ARCHITECTURE.md` foi atualizado para refletir o registro assíncrono de `EventoBusca` e a economia de banda/reconciliação de RSS.
- `documentation-update.md` registra verificações, alterações com arquivo:linha e itens deliberadamente não alterados.

## Follow-ups

1. **Minor 8 — parcial:** aprovação/rejeição de item pelo admin não invalida imediatamente o cache do autocomplete; a inconsistência eventual pode durar até o TTL de 300 s. O snapshot também permanece limitado aos 500 títulos recentes.
2. **Nit 9 — parcial:** um `X-Request-ID` externo longo pode colidir depois do truncamento para 64 caracteres; o caminho HTTP com UUID não é afetado.
3. **Major 5 — residual:** não há staging/resultado durável. Em uma reentrega após queda do worker, o LLM pode ser chamado novamente; a reserva de custo permanece contabilizada no `RegistroExecucaoIngestao`, mas a chamada é repetida.
4. **Minor 7 — residual:** formato e limites completos da URL não são validados pelo banco; `clean()` e as constraints de rastreabilidade são preservados para compatibilidade.
5. **Migrations:** `catalogo_noticias.0012`, `catalogo_noticias.0013` e `feed.0003_eventobusca_request_id` precisam de validação em PostgreSQL real no CI; o sandbox não tinha servidor disponível.

## Artefatos

- `task-plan.md`
- `implementation-contract.md`
- `implementation-history.md`
- `code-review-contract.md`
- `documentation-update.md`
- `report.md`
- `run-state.json` — fechado com `status: closed` e `current_phase: done`
