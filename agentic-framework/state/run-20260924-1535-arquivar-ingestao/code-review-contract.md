<!--
CONTRACT: code-review-contract
DONO: reviewer
QUANDO É CRIADO: revisão independente da run 20260924-1535-arquivar-ingestao
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-20260924-1535-arquivar-ingestao/
-->

# Code Review Contract — 20260924-1535-arquivar-ingestao

## Metadados
- **run_id:** 20260924-1535-arquivar-ingestao
- **Escopo revisado:** diff canônico `6e61a97..5dc842d` (49 caminhos: 35 remoções — 33 de `ingestao-service/` e 2 do adaptador/teste do cliente —, 10 modificações de produção/documentação e os 4 artefatos iniciais da run). A pequena alteração não commitada do `implementation-history.md` e do `run-state.json` foi lida como estado concorrente, não como código de produção.
- **Contrato de referência:** `implementation-contract.md` e `task-plan.md` da run.
- **Histórico lido:** `implementation-history.md` completo, incluindo as entradas do tester (iterações 2 e 3) e o registro do commit concorrente `5dc842d`.
- **Gatilhos aplicados (de `review-triggers.md`):** alteração de API/comportamento público; segurança (remoção do painel sem autenticação e do MongoDB exposto); settings/configuração; grande volume de remoções; dependência de fonte de verdade. Não houve alteração de schema, modelo, frontend ou migration.
- **Método e limites:** leitura do diff e do código circundante, AST/imports, `manage.py check`, `makemigrations --check`, testes focados, `git diff --check` e `docker compose config`; o relatório do tester (476 passed em PostgreSQL 16, 88,84%, smoke offline, tsc/build 59/59) foi usado como evidência complementar, não como substituto da leitura. Não houve acesso a VPS, Mongo externo, GitHub Actions ou alteração de branch/commit/reset.

## Findings

### Finding 1
- **Arquivo:** `backend/feed/views.py:30–43,69–74` (commit `5dc842d`; interação com `backend/config/settings.py:420–431` e o Redis persistente do compose)
- **Linha:** 69–74
- **Categoria:** correctness
- **Severidade:** minor
- **Resumo:** a troca da fonte remota para a local reutiliza o namespace de cache `feed:v1`, sem invalidação, flush de cutover ou nova versão.
- **Cenário de falha:** antes do deploy, com `MICROSERVICO_INGESTAO_URL` não vazia, o ramo removido no pai (`6e61a97`, antigas linhas 82–95) gravava uma resposta remota bem-sucedida de `GET /api/feed/?categoria=...` (ou `/urgentes/`, antigas linhas 199–217) em `feed:v1:lista:uanon:categoria=...`/`feed:v1:urgentes:uanon:...`. O Redis usado pelo Django na topologia PM2 ou o volume `redis_data` do Compose pode conservar essa chave durante o reinício. Após `5dc842d`, o mesmo request encontra `em_cache` e retorna em `backend/feed/views.py:70–72` antes de `services.itens_publicaveis()`/PostgreSQL; por até o TTL configurado o cliente recebe payload/IDs/paginação do FastAPI removido em vez do catálogo local, contrariando a fonte única após o arquivamento. O TTL é configurável (45 s por padrão). O smoke com cache limpo não exercita esta transição.
- **Sugestão:** versionar o namespace ao mudar a fonte (por exemplo, `feed:v2`) ou invalidar explicitamente as chaves `feed:v1:*` no corte/deploy, considerando também qualquer cache de borda ativado; adicionar teste que pré-popula uma entrada remota legada e prova que o request passa pelo serviço local.

## Itens verificados sem finding

- **Feed e todos os endpoints:** o diff de `backend/feed/views.py` remove somente `logging`, o cliente/erro e os quatro branches `servico_ativo()`; `services`, serializers, curadoria, `FeedPagination`, limites, gating, busca, cobertura, interações, `AllowAny`, cache local e todos os caminhos de 404 foram preservados. As rotas em `backend/feed/urls.py` não mudaram. O único desvio encontrado é a transição de cache descrita no Finding 1.
- **Robôs:** `robos_views.py` remove somente o import, o helper de sincronização e suas quatro chamadas. Os gates `IsAuthenticated`/admin, CRUD de `FonteRobo`, configuração, execuções, `threading.Thread(daemon=True)`, `HTTP_202_ACCEPTED`, `request_id`, `close_old_connections()` e logging de sucesso/falha permanecem intactos; não foi introduzido erro silencioso novo.
- **Settings e ambiente:** `MICROSERVICO_INGESTAO_URL` e `INGESTAO_API_TOKEN` não existem mais no settings versionado nem no exemplo. `backend/.env` foi preservado deliberadamente; com as flags antigas não vazias, `manage.py check` passou e `hasattr(settings, ...)` foi falso para ambas. `requests` continua sendo dependência direta usada por providers RSS/LLM, pagamento, e-mail e endereços, portanto não ficou órfão.
- **Segurança e arquivo:** no pai, o FastAPI tinha `/painel` sem auth e o compose próprio publicava `27017:27017`; no commit `5dc842d` os 35 paths foram removidos, `git ls-files` não encontra `ingestao-service` nem o cliente, não há rota `/painel` operacional no Django/Nginx/frontend e o Compose raiz resolve apenas `db, redis, web, frontend, caddy, celery-beat, celery-worker`, sem Mongo/27017/8001. Não há stub/cópia em `docs/archive` nem segredo novo.
- **Documentação viva:** `PROD_DECISOES.md:69–89`, `ARCHITECTURE.md:21–25` e `ANALISE_CUSTO_PERFORMANCE.md:308–315` registram arquivamento, Django/PostgreSQL/Celery como fonte única, motivos e ação humana para desligar/remover instâncias e volumes Mongo somente após backup. Dizem explicitamente que a run não acessou a VPS, não desligou a instância e não apagou dados; não há comando para iniciar o serviço arquivado.
- **Escopo e estado:** não há paths de frontend, migrations ou modelos no diff. Os hashes de `run-20260924-1400-tls-ingestao/run-state.json` e `loteA-bugs/` coincidem com o histórico; migrations não aparecem no status/diff. Os agregados `d796f446e0976321894a07efca858f474b7775055d815ba5ad57842722e1936c` (executor) e `2877a483a570b5c1de62d950fac49a8bcb77be9b488b1e0ecfb4c24716ae7432` (tester) usam métodos de hash diferentes, não indicam alteração de migrations. O commit foi preservado; a única modificação de `infra/DEPLOY.md` foi a substituição da instrução residual sobre Mongo por Postgres/Redis, justificada no histórico. Nenhuma alteração de código, run-state ou histórico anterior foi feita nesta revisão.
- **Artefatos locais ignorados:** existem `.pyc` antigos do cliente removido em `backend/feed/__pycache__/` e `backend/feed/tests/__pycache__/`; não são versionados, são excluídos por `.gitignore`/`.dockerignore`, e `importlib.util.find_spec` retorna `None` para ambos os módulos ausentes. São caches locais, não runtimes versionados órfãos; foram registrados aqui para não confundi-los com o contrato de arquivamento.

## Verificações executadas

```text
git diff --check 6e61a97 5dc842d                         → OK
manage.py check (flags antigas, DEBUG=false, Postgres)  → 0 issues
manage.py makemigrations --check --dry-run                → No changes detected
pytest feed + robos admin/background                       → 58 passed, 36 warnings
AST/tokenize de 277 arquivos Python                       → OK
imports/symbols em feed e robos                           → sem cliente/requests/logger remote
settings com flags antigas                                → ambos os atributos ausentes
probe locmem com payload remoto legado                   → 200/count 99, serviço local não chamado
docker compose config (raiz + homolog + localhost)        → OK; sem mongo/27017/8001
git ls-files -- 'ingestao-service'                         → vazio; find sem diretório
```

## Resumo quantitativo
| Severidade | Quantidade |
|---|---:|
| blocker | 0 |
| major | 0 |
| minor | 1 |
| nit | 0 |

## Veredito
**approve_with_comments**

Não há blocker nem major: a remoção versionada, os caminhos locais, a resposta 202 dos robôs, a configuração e a documentação atendem ao contrato. Permanece um minor de consistência na troca de fonte do cache (Finding 1), que é transitório e não bloqueia o arquivamento, mas deve ser tratado no cutover para que uma entrada remota legada não seja servida como se fosse do Django.

## Observação de estado

O `git status` atual mostra, além deste artefato, a entrada append-only do tester em `implementation-history.md` e a atualização de fase em `run-state.json`; ambos estão fora do diff canônico de produção e foram preservados. O commit `5dc842d` foi tratado como autoridade do código e não foi desfeito; nenhum run-state foi editado por esta revisão.

## Re-revisão da remediação — baseline `f8d8db6`

### Escopo e método

- Re-revisão restrita ao diff real `git diff f8d8db6 --`: `backend/feed/views.py`, `backend/feed/tests/test_p1_feed_cache_indices.py` e os artefatos append-only da run (`implementation-history.md` e `run-state.json`). O `code-review-contract.md` é o artefato desta revisão. O commit externo `f8d8db6` (parent `5dc842d`) foi preservado como baseline explícita; `.github/workflows/deploy.yml` não foi revisado nem alterado.
- Li o Finding 1 original, a entrada de remediação e as revalidações do tester (iterações 4 e 5), além do código circundante e do diff real, sem tratar os relatórios como substituto da leitura.
- Não houve commit, branch switch, reset, unstaging ou edição de `run-state.json` durante esta re-revisão.

### Status do Finding 1 — resolvido

- `backend/feed/views.py:35` define `CACHE_NAMESPACE_LISTAGENS = "feed:v2"`; `_chave_cache_listagem` (`:38–51`) usa a constante, mantendo ordenação da query, `usuario = pk ou "anon"` e o prefixo. As cinco listagens chamam o helper em `FeedListView` (`:77`), `UrgentesView` (`:148`), `MaisLidasView` (`:163`), `HomeSecoesView` (`:210`) e `DestaquesDiaView` (`:233`).
- `_ttl_feed()` e todos os `cache.set` das cinco listagens permanecem no caminho anterior; a única alteração de produção é o namespace. AST não encontrou literal runtime `feed:v1` em `views.py`; a ocorrência em comentário é explicativa, e a ocorrência no teste é a semente legada deliberada.
- O teste de cutover semeia `feed:v1:lista:uanon:categoria=cidades&page_size=20` com payload remoto distinto, cria um `NewsItem` local real, faz GET via `APIClient`, verifica ID/título locais, confirma ausência de `cache.get(v1)`, preservação da chave v1, gravação em `feed:v2` e TTL 45. Não substitui o banco nem o cache por um fake de serviço e não é tautológico: o payload remoto teria outro ID/título e o teste prova a resolução local.
- Verificações independentes: cutover `1 passed`; arquivo completo `15 passed`; `feed` + robôs admin/background + gating `73 passed`; `manage.py check` sem issues; `makemigrations --check --dry-run` sem alterações; probes de namespace confirmaram cinco prefixes, query normalizada e chaves anônima/autenticada.

### Não-regressão e escopo

- Search/autocomplete, gating, robôs e o contrato HTTP 202/thread daemon foram exercitados pelos testes focais; não houve modificação在这些 caminhos. O serviço arquivado e seus clientes continuam ausentes; o diff relativo a `f8d8db6` não contém código de frontend, migrations, modelos, Compose ou do serviço removido.
- O commit externo de PM2 foi tratado somente como baseline fora do escopo, conforme solicitado. O `git diff --check f8d8db6 --` passou. A suíte completa reportada pelo tester (477 passed, 88,86% em PostgreSQL 16) foi considerada evidência complementar; a leitura e os testes desta re-revisão confirmaram especificamente o cutover.

## Findings da re-revisão

Nenhum finding novo. O Finding 1 anterior está **RESOLVIDO**; não há blocker, major, minor ou nit residual no escopo revisado.

## Resumo quantitativo da re-revisão

| Severidade | Quantidade |
|---|---:|
| blocker | 0 |
| major | 0 |
| minor | 0 |
| nit | 0 |

## Veredito da re-revisão

**approve**

A remediação troca o namespace do cache de listagens para `v2` sem alterar TTL, usuário, query ou prefixo, e o teste prova o cutover de uma entrada `v1` para a resposta local em `v2`. Não encontrei regressão nos caminhos exercitados nem problema no código arquivado; o commit externo `f8d8db6` permanece preservado e fora do escopo. O `run-state.json` foi deliberadamente deixado sem edição, portanto seu contador de findings pré-reconciliação não foi tratado como achado de código.
