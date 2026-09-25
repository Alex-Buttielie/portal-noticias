<!--
CONTRACT: documentation-update
DONO: documenter
QUANDO É CRIADO: depois que testes passam e a revisão (se exigida) está aprovada.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-20260924-1535-arquivar-ingestao/documentation-update.md
-->

# Documentation Update — 20260924-1535-arquivar-ingestao

## Metadados
- **run_id:** 20260924-1535-arquivar-ingestao
- **Baseado em:** `task-plan.md`, `implementation-contract.md`, `implementation-history.md` completo, `code-review-contract.md` final, no commit `5dc842d`, na remediação de cache `feed:v2` e no commit externo `f8d8db6` (preservado como baseline concorrente, não atribuído à implementação desta run)
- **Escopo desta fase:** documentação viva e este artefato; o documenter não alterou código, teste, migration, workflow, run-state de outra execução ou dado externo

## Documentos afetados
| Documento | Tipo de mudança | Resumo |
|---|---|---|
| `PROD_DECISOES.md` | atualização operacional | A decisão de arquivamento passa a nomear `MICROSERVICO_INGESTAO_URL` e `INGESTAO_API_TOKEN`, esclarece que as flags antigas são inertes, registra o namespace `feed:v2` e a preservação do contrato local `202`/background, e mantém explícito que a remoção do checkout não apaga dados nem encerra serviços externos. |
| `ARCHITECTURE.md` | atualização | A decisão de stack deixa de aparecer como decisão em aberto; a fonte única Django/PostgreSQL/Celery, a ausência de fallback remoto, o namespace `feed:v2` para as cinco listagens e o endpoint local de robôs com `202`/background ficam declarados como arquitetura vigente. |
| `infra/DEPLOY.md` | atualização | Acrescenta uma orientação de limpeza manual para flags em `.env` e para processos/volumes Mongo legados, com backup e retenção como pré-requisitos; diferencia claramente remoção do código versionado de limpeza da VPS. |
| `ANALISE_CUSTO_PERFORMANCE.md` | alteração preexistente do Lote B, conferida | O achado histórico já está marcado como resolvido, sem apagar o diagnóstico anterior: o serviço foi arquivado, Django/PostgreSQL/Celery é a fonte única e a remoção de volumes externos depende de ação humana após backup. Não foi reescrito nesta fase. |
| `backend/.env.example` | configuração preexistente do Lote B, conferida | As duas flags do adaptador e seus comentários foram removidos do exemplo. O `.env` real/ignorado não foi editado. Não foi alterado novamente pelo documenter. |
| `README.md` e `CI-CD.md` | verificados sem alteração | A entrada de ingestão, o bootstrap e os runbooks de deploy não contêm uma instrução operacional que contradiga a fonte única ou que tente iniciar o serviço removido. |
| `agentic-framework/state/run-20260924-1535-arquivar-ingestao/documentation-update.md` | novo artefato de fase | Registra a mudança documental, a ausência de changelog, as validações e as limitações. |

## Sem impacto em documentação?
Não se aplica: houve atualização real em `PROD_DECISOES.md`, `ARCHITECTURE.md` e `infra/DEPLOY.md`. `README.md` e `CI-CD.md` foram conferidos, mas não precisaram de nova edição.

- [x] Seção avaliada: há impacto documental; portanto a afirmação de “sem impacto” não se aplica.

## Exemplos/snippets novos ou atualizados
- Não foi adicionado snippet de código. A orientação operacional foi expressa em linguagem de runbook: em cada VPS, procurar as flags antigas no `.env`, inspecionar processos/contêineres/volumes e só desligar ou remover depois de backup e decisão de retenção.
- O contrato local de robôs está explícito em `ARCHITECTURE.md`: `POST /api/admin/robos/executar/` responde `202 Accepted` imediatamente e o resultado é acompanhado por `GET /api/admin/robos/execucoes/`.
- O corte de cache está explícito em `ARCHITECTURE.md` e `PROD_DECISOES.md`: as listagens usam `feed:v2`; uma entrada antiga `feed:v1`, inclusive um payload remoto legado, não é lida e expira pelo TTL.

## Entrada de changelog
Não há arquivo `CHANGELOG*` no repositório e o projeto não mantém uma entrada de changelog para esta mudança. Nenhum arquivo ou linha de changelog foi criado.

## Verificação
- [x] Documentação viva coerente com o comportamento testado: serviço FastAPI/Mongo removido do código versionado; Django/PostgreSQL/Celery como única fonte; feed e robôs locais; `202`/background; `feed:v2` isolando payloads `feed:v1`.
- [x] Grep operacional: não há referência operacional ativa ao `ingestao-service`, `microservice_client`, `MICROSERVICO_INGESTAO_URL` ou `INGESTAO_API_TOKEN` em código, manifests ou exemplos versionados. Ocorrências em `agentic-framework/state/` e em seções explicitamente históricas dos documentos vivos foram preservadas para auditoria.
- [x] Bootstrap e manifests: `manage.py check` passou com as flags antigas presentes no ambiente de teste, e `docker compose config` foi validado para a topologia principal e variantes sem serviço/Mongo adicional.
- [x] Comportamento validado no histórico da implementação e da remediação: suíte focada de feed/robôs e smoke offline passaram; o teste de cutover semeou `feed:v1` com payload remoto falso e confirmou resposta local em `feed:v2` com TTL preservado; a suíte completa foi executada em PostgreSQL real 16 com `477 passed` e cobertura total de `88,86%` (gate de 80% atendido).
- [x] Verificações de frontend/infra já registradas para a implementação passaram: `tsc --noEmit`, build Next.js com `59/59` páginas e `docker compose config` sem Mongo/ingestão.
- [x] Markdown, links e whitespace: os documentos vivos e este artefato foram processados por verificação de Markdown e de links relativos; `git diff --check`, `git diff --cached --check` e `git diff HEAD --check` não encontraram whitespace inválido.
- [x] Integridade: migrations, `.env` real, run-state da execução TLS, `loteA-bugs/`, relatórios históricos e `HISTORY.md` permaneceram preservados. Os SHA-256 conferidos foram `7c57ea9bfe8ebe2920247f94aa9d73b9b1efd152a3286b226a8ab20954f5dc4f` (run-state TLS), `16d394a4816725b4edfa95f5a1f052395ffee21a17faa027e265bb0fb0f28889` (`loteA-bugs`) e `5560bcd29e4df3dde972207f6180f45cd7e2c38f9c258fcd1d79f297ae3a0a5a` (`backend/.env`).

## Limitações e integridade do escopo
- Não houve acesso à VPS, Docker remoto, MongoDB externo, GitHub Actions, DNS ou TLS. A remoção do diretório versionado não apaga um banco, volume ou processo que exista fora do checkout; a limpeza de flags, contêineres e volumes continua sendo humana e deve ocorrer somente após backup e confirmação da necessidade dos dados.
- O `.env` local/ignorado pode continuar contendo as flags antigas. Elas não são lidas pelo Django, mas foram deliberadamente preservadas para não editar um arquivo operacional ou secreto.
- `feed:v2` é o namespace pós-arquivamento das cinco listagens cacheadas. A troca impede a leitura de `feed:v1`; não implica uma migração ou limpeza imediata de Redis, e os payloads antigos expiram pelo TTL.
- O commit externo `f8d8db6` alterou somente `.github/workflows/deploy.yml` e é independente, concorrente e posterior ao Lote B. Ele foi preservado, não foi editado, não foi atribuído à implementação desta run e não deve ser descrito como parte do arquivamento.
- Durante esta fase de documentação, o documenter não alterou código, testes, migrations, workflows, dados de produção ou serviços externos; não foi criado commit.
