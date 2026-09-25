<!--
CONTRACT: report
DONO: historian
QUANDO É CRIADO: no fechamento de cada execução (run).
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-20260924-1535-arquivar-ingestao/
-->

# Report — 20260924-1535-arquivar-ingestao

## Metadados

- **run_id:** `20260924-1535-arquivar-ingestao`
- **Período:** 2026-09-24 15:30 → 2026-09-24 17:15 (-03:00)
- **Tarefa:** Arquivar definitivamente o microserviço de ingestão e sua integração
- **Resultado final:** `entregue`
- **Estado observado:** `develop` em `d1e0456` (parent `f8d8db6`); a baseline usada na retestagem foi `f8d8db6`; nenhum branch foi criado ou trocado durante o fechamento
- **Commits desta execução:** nenhum
- **Revisão final:** `approve`, com 0 findings residuais

## Resumo executivo

A execução removeu definitivamente o segundo pipeline FastAPI/Mongo e deixou Django/PostgreSQL/Celery como fonte de verdade executável do portal. Foram removidos 33 arquivos versionados de `ingestao-service/` e 2 paths do adaptador/teste do cliente, além de retirar branches remotos, flags e referências operacionais. A revisão encontrou um único finding minor de cutover de cache; ele foi corrigido com `feed:v2` e coberto por regressão, e a re-revisão final aprovou com 0 findings. Os commits `5dc842d`, `f8d8db6` e `6e61a97` foram tratados como estado concorrente/externo, sem atribuição indevida a esta execução; o `d1e0456`, observado na reconciliação final, é um commit docs-only posterior e também externo. Nenhuma VPS, Mongo real, `.env` existente, volume externo, commit, reset ou push foi alterado por este fechamento.

## Métricas

| Métrica | Valor |
|---|---|
| Iterações (implementação ↔ revisão/remediação) | **1** ciclo de remediação; 5 registros de implementação/teste e 2 registros de fechamento/reconciliação |
| Findings de revisão — abertos | **0** (0 blocker, 0 major, 0 minor, 0 nit) |
| Findings de revisão — resolvidos | **1** (Finding 1, minor, cutover `feed:v1`→`feed:v2`) |
| Arquivos alterados | **35 removidos** (33 `ingestao-service/` + 2 adaptador/teste); **10 modificados** no Lote B de código/configuração/documentação; 2 paths de código/teste foram novamente ajustados na remediação |
| Testes adicionados | **1** função de regressão de cutover; 13 funções do cliente removido e 1 teste remoto auxiliar removido |
| Veredito final do tester | `passed` após reconciliação do baseline externo |
| Veredito final do reviewer | `approve` |

## Entregas

### 1. Arquivamento do serviço e do caminho alternativo

- Removidos **33 arquivos de `ingestao-service/`** (API, pipeline, collectors, painel, Docker/Compose, requirements, README, exemplo de ambiente e testes), sem stub ou cópia em `docs/archive`.
- Removidos **2 paths do adaptador/teste**: `backend/feed/microservice_client.py` e `backend/feed/tests/test_microservice_client.py`.
- `backend/feed/views.py` deixou de importar o cliente, testar `servico_ativo()` e fazer fallback remoto; services, serializers, curadoria, cache local, paginação, gating, busca e endpoints foram preservados.
- `backend/catalogo_noticias/robos_views.py` deixou de sincronizar fontes remotamente; o CRUD local e a resposta `202 Accepted` com execução em background foram preservados.
- `backend/config/settings.py` e `backend/.env.example` não contêm mais `MICROSERVICO_INGESTAO_URL` ou `INGESTAO_API_TOKEN`; o `.env` local ignorado não foi editado.

### 2. Configuração, operação e documentação

- O diff canônico do Lote B contém **10 modificações de código/configuração/documentação**, além das remoções e dos artefatos iniciais da execução; o ciclo de remediação voltou a alterar os 2 paths de `views.py`/teste de cache para o cutover.
- `PROD_DECISOES.md`, `ARCHITECTURE.md` e `infra/DEPLOY.md` registram Django/PostgreSQL/Celery como fonte única, a remoção do caminho remoto, o namespace `feed:v2` e o procedimento humano para limpar flags, processos e volumes externos somente após backup e validação.
- `git ls-files ingestao-service` está vazio, o diretório não existe no filesystem e o Compose resolvido não contém serviço, volume, porta ou comando do pipeline removido.

### 3. Cutover de cache

- Finding 1 (minor) identificado na revisão: a troca da fonte reutilizava `feed:v1` e podia devolver payload remoto legado durante o TTL de 45 s.
- Correção: `CACHE_NAMESPACE_LISTAGENS = "feed:v2"` em `backend/feed/views.py`, preservando prefixo, usuário, query normalizada e TTL nas cinco listagens (`lista`, `urgentes`, `mais-lidas`, `home` e `destaques`).
- Regressão adicionada em `backend/feed/tests/test_p1_feed_cache_indices.py`: semeia uma chave `feed:v1` com payload remoto falso, faz um request real com item local e confirma resposta local, ausência de leitura de `v1`, gravação em `v2` e TTL 45 s.

## Validações factuais

- **Suíte inicial:** 476 testes passaram em PostgreSQL real 16.15, cobertura total 88,84%, gate de 80% atendido.
- **Suíte final:** 477 testes passaram em PostgreSQL real 16.15, cobertura total **88,86%**, 209 warnings, gate de 80% atendido. A reexecução final independente também confirmou 477/477 e 88,86%.
- **Smoke offline:** passou com flags antigas apontando para porta inalcançável e chamadas `requests` bloqueadas explicitamente; feed, cache e robôs locais continuaram funcionando sem rede real. O smoke de todos os prefixes também confirmou a transição `feed:v1`→`feed:v2`.
- **Backend/integridade:** `manage.py check` passou sem issues; `compileall` passou; `makemigrations --check --dry-run` respondeu `No changes detected`; os testes focais de feed, robôs e gating passaram.
- **Frontend:** `npx tsc --noEmit` passou; `npm run build` gerou **59/59** páginas estáticas.
- **Compose:** `docker compose config --quiet` passou para a configuração base, localhost e homologação; os serviços resolvidos foram `db`, `redis`, `web`, `frontend`, `caddy`, `celery-beat` e `celery-worker`, sem `mongo`, `ingestao`, `27017` ou `8001`.
- **Escopo:** grep operacional não encontrou cliente, flags ou comando ativo do serviço; as ocorrências restantes em documentos vivos estão explicitamente marcadas como histórica/arquivada. `git diff --check`, `git diff --cached --check` e `git diff HEAD --check` passaram.
- **Critérios do contrato:** 9/9 critérios de aceite foram atendidos na validação independente.

## Revisões, remediação e concorrência

- A revisão inicial terminou em `approve_with_comments` com **1 finding minor** (o cutover de cache), sem blocker ou major.
- O remediator corrigiu o finding e o tester revalidou o cache, os cinco prefixes, o smoke offline e o escopo local. A reconciliação final foi `passed`.
- A re-revisão, com baseline explícita, terminou em **`approve`**, com 0 blocker, 0 major, 0 minor e 0 nit; o contador consolidado é **1 finding resolvido**.
- `6e61a97` é o commit externo do **Lote A** e foi o baseline inicial do tester.
- `5dc842d` é o commit externo do **Lote B**, feito por outra sessão após o baseline `6e61a97`; seu conteúdo foi preservado como autoridade para o diff validado, mas não foi realizado commit nem atribuído a esta execução.
- `f8d8db6` (parent `5dc842d`) é uma correção **independente de PM2** em `.github/workflows/deploy.yml`, feita por outra sessão. Foi preservado como baseline da retestagem final, registrado como follow-up externo e explicitamente **não é bug nem finding desta execução**. Não foi resetado, revertido, editado ou incorporado ao escopo de arquivamento.
- `d1e0456` (parent `f8d8db6`) foi criado por outra sessão às 17:09:03 e altera somente `infra/DEPLOY.md`, documentando estado HTTP-only/drift da VPS. A seção de cleanup já estava presente no worktree antes desse commit, mas o commit externo não foi atribuído a esta execução; é posterior à retestagem de comportamento e não é bug/finding do arquivamento. O baseline de validação continua sendo `f8d8db6`; medições de VPS citadas nessa documentação pertencem à sessão externa, não a esta run.
- A worktree permaneceu sem branch/commit/reset/push feito pelo fechamento; os paths de implementação e remediação ainda modificados continuam no estado de trabalho, enquanto o path documentado acima foi preservado no commit externo, sem reescrita.

## Integridade e limitações

- `run-20260924-1400-tls-ingestao/run-state.json` não foi alterado: SHA-256 `7c57ea9bfe8ebe2920247f94aa9d73b9b1efd152a3286b226a8ab20954f5dc4f`.
- `loteA-bugs/` não foi alterado: hash agregado dos arquivos `8fd8604942458cc6ff720c68fab4c13f814734e0099a777deeec3cea7313b05d`; o arquivo de histórico individual tem SHA-256 `16d394a4816725b4edfa95f5a1f052395ffee21a17faa027e265bb0fb0f28889`.
- Migrations não foram alteradas: hash agregado dos arquivos versionados `2877a483a570b5c1de62d950fac49a8bcb77be9b488b1e0ecfb4c24716ae7432`; não há migration no diff desta execução.
- O ledger anterior foi preservado: seu hash antes da entrada desta run era `3a0d4fcc60dbef4934632d3d9b80972931bcfedf200f1dbf7edb9c68510e0ce3`; apenas uma linha foi acrescentada, com hash final `8ebea52391b280bf54928993d92f2e9a45aee7b9dda36b72a4077fbf3c8d4400`.
- O `.env` existente não foi editado: SHA-256 `5560bcd29e4df3dde972207f6180f45cd7e2c38f9c258fcd1d79f297ae3a0a5a`; flags antigas, se presentes, ficaram inertes.
- Não houve acesso a VPS, Docker remoto, MongoDB externo, GitHub Actions real ou dados de produção; nenhum processo, container, banco ou volume externo foi desligado ou apagado.
- Não houve commit ou push desta execução. O commit externo de Lote B, a correção externa de PM2 e o commit docs-only `d1e0456` permanecem distinção de provenance, sem reescrita de histórico.

## Linha do tempo resumida

- **15:30–15:35** — planejamento e contrato materializados.
- **15:35–15:46** — executor removeu o serviço/adaptador e rodou a validação inicial.
- **15:56–16:01** — outra sessão criou `5dc842d` sobre `6e61a97`; o tester registrou a concorrência e preservou o conteúdo.
- **16:28–16:48** — Finding 1 (minor) foi corrigido com `feed:v2` e teste de cutover.
- **16:42–16:55** — outra sessão criou `f8d8db6`, parent de `5dc842d`; o tester reconciliou o baseline e validou novamente.
- **16:56–17:00** — re-revisão final aprovou com 0 findings.
- **17:00–17:05** — documentação operacional consolidada.
- **17:09** — historian preservou a síntese cronológica, criou este relatório, fechou o estado e acrescentou uma única linha ao ledger.
- **17:09:03–17:15** — outra sessão criou `d1e0456`; a reconciliação final registrou a concorrência e manteve `f8d8db6` como baseline da reteste.

## Desvios do plano original

Não houve desvio funcional: a decisão explícita de arquivamento definitivo foi implementada, e o caminho local Django/PostgreSQL/Celery permaneceu como fonte única. A única mudança de plano foi operacional: a remoção do código não podia desligar uma VPS ou apagar dados externos. A limpeza de flags em `.env` e de processos/volumes Mongo foi convertida em follow-up humano, conforme a documentação. Durante a validação houve commits de outras sessões; eles foram reconciliados como baseline externo, sem reversão nem atribuição a esta execução.

## Follow-ups / pendências

1. **Operação de infraestrutura (humana):** em cada VPS, localizar processos/contêineres/volumes Mongo do `ingestao-service`, confirmar backup e política de retenção e só então desligar ou remover o componente.
2. **Configuração existente (humana):** remover `MICROSERVICO_INGESTAO_URL` e `INGESTAO_API_TOKEN` de `.env` preexistentes se ainda presentes; esta execução deliberadamente não editou o arquivo operacional.
3. **Provenance PM2 (externa e independente):** manter `f8d8db6` separado do escopo desta execução; qualquer validação, revisão ou operação de deploy do PM2 deve referenciar seu próprio parent `5dc842d` e não deve ser contabilizada como bug de arquivamento.
4. **Provenance documental posterior:** `d1e0456` (parent `f8d8db6`) é externo e docs-only; não atribuí-lo a esta execução nem usá-lo como substituto da baseline de retestagem `f8d8db6`.
5. **Cache legado (opcional):** as chaves `feed:v1` não são lidas e expiram pelo TTL; uma limpeza explícita do Redis só deve ser considerada pela operação se houver uma política de retenção definida, sem alterar o contrato local.
6. **Backlog separado:** a migração de React Query e o movimento do build para o runner permanecem lotes independentes, conforme a run anterior.

## Artefatos desta execução

- `task-plan.md`
- `implementation-contract.md`
- `implementation-history.md`
- `code-review-contract.md`
- `documentation-update.md`
- `report.md`
- `run-state.json`

## Fechamento

O relatório foi consolidado, a síntese cronológica foi acrescentada sem editar entradas anteriores, o ledger recebeu exatamente uma linha append-only e `run-state.json` foi validado contra `agentic-framework/schemas/run-state.schema.json` com `status: closed` e `current_phase: done`. Findings finais: 0 blocker, 0 major, 0 minor, 0 nit; 1 resolvido.
