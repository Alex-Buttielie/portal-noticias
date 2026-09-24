# Relatório de execução — 20260924-1200-ops-higiene

## Metadados

- **Run:** `20260924-1200-ops-higiene`
- **Tarefa:** P0-2/P1-5/P2-6/P2-7 — backup PM2, deploy seguro e higiene operacional
- **Período:** 2026-09-24 12:00 → 2026-09-24 14:30 (-03:00)
- **Resultado final:** entregue
- **Iteração final:** 3
- **Veredito final do tester:** `passed`
- **Veredito final do reviewer:** `approve_with_comments`
- **Findings finais:** 0 blocker, 0 major, 1 minor, 0 nit; 7 resolvidos
- **Commit:** nenhum

## Objetivo

Deixar a operação da VPS PM2 + Nginx segura e reproduzível: oferecer backup
nativo de PostgreSQL e mídia com validação de restore real e destino remoto
opcional, serializar e proteger o deploy, deixar rollback operacional, versionar
tuning do PostgreSQL e limites de logs, regenerar o lockfile e corrigir o
comentário de cache. A execução não teve acesso à VPS, a bucket S3 real ou ao
GitHub Actions e, portanto, não aplicou configurações privilegiadas nem fez
deploy/restore real.

## Entregas

1. **Backup nativo da topologia PM2**
   - Criado `infra/backup/pg_backup_pm2.sh`, com `set -euo pipefail`, `umask
     077`, `flock`, credenciais sem exposição de segredos, `pg_dump -Fc`, tar da
     `backend/media`, publicação por temporário/rename e retenção de sete dias
     limitada aos nomes `pm2-*`.
   - A validação padrão (`BACKUP_VALIDATE_RESTORE=1`) faz `pg_restore --list`,
     restaura o archive inteiro em banco PostgreSQL descartável com
     `pg_restore --exit-on-error`, compara contagens de tabelas/linhas e só então
     publica. O escape `BACKUP_VALIDATE_RESTORE=0` ainda exige leitura integral
     do archive, mas deixa o restore/contagem explicitamente desabilitados.
   - S3/R2/B2 é opcional e fail-closed quando configurado: uploads de dump e
     mídia são verificados por `head-object`/tamanho antes de liberar a
     retenção. Sem bucket, a operação local pode terminar com zero, mas mantém
     todos os arquivos e suspende a retenção, com aviso explícito de que a cópia
     está somente na VPS.
   - `infra/backup/pg_backup.sh` foi preservado para a variante Docker/Caddy. O
     README e o runbook agora deixam explícita a seleção PM2 × Docker.

2. **CI/CD com gate real e serialização**
   - `ci.yml` continua sendo feedback independente e passou a ser reutilizável via
     `workflow_call` com `checkout_ref`.
   - `deploy.yml` ganhou o job `verify`, que chama `./.github/workflows/ci.yml`,
     e o job `deploy` depende dele (`needs: verify`). Falha, cancelamento ou
     não conclusão do CI impede a conexão SSH. DEV, HOMOLOG e PROD passam o
     mesmo SHA que será buscado na VPS; a tag de PROD é coberta mesmo sem
     trigger de tags no workflow CI independente.
   - `concurrency.group = portal-deploy-<environment_name>` com
     `cancel-in-progress: false` impede deploys concorrentes do mesmo ambiente
     sem cancelar o run já em andamento.
   - O guard duplicado e `guard_ref` não foram reintroduzidos. O gate é uma
     chamada única à definição de CI, não uma segunda lógica de testes.

3. **Deploy PM2 com retry, sanity e recuperação**
   - O deploy instala `backend/requirements-lock.txt`, o mesmo conjunto validado
     pelo CI, preservando o lock como contrato do caminho PM2.
   - O shell não usa mais `pm2 delete`; usa `restart --update-env` ou `start`
     apenas quando necessário, com até três tentativas, espera entre tentativas
     e confirmações consecutivas de estado `online` via `pm2 jlist` antes de
     tocar o processo seguinte.
   - O marker `/home/apps/portal-<ambiente>/.deployed-sha` preserva o SHA anterior
     e só é promovido após probes, resultado de deploy e checkout verificado. A
     promoção usa arquivo temporário, `chmod 600` e `mv` atômico.
   - Criado `.github/workflows/rollback.yml`: `workflow_dispatch`, seleção de
     DEV/HOMOLOG/PROD, SHA hexadecimal de 40 caracteres, `confirm` explícito,
     `tls_enabled`, reutilização do mesmo `deploy.yml` em `git_mode: rollback` e
     `verify`/`ci.yml` também no rollback. Não há release/tag nessa operação.
   - A documentação declara que a troca é in-place e **não garante zero
     downtime**; retry, marker, smoke e rollback manual são mitigação, não
     blue-green nem reversão automática de migrations.

4. **PostgreSQL, logs e higiene operacional**
   - Versionado `infra/postgres-tuning.conf` para a VPS de 4 GB:
     `shared_buffers=1GB`, `effective_cache_size=3GB`, `work_mem=8MB` e
     `maintenance_work_mem=256MB`. O repositorio apenas prepara o include; a
     aplicação, medição e eventual rollback são ações humanas.
   - Versionado `infra/logrotate/pg-backup.conf` com rotação diária, 14
     retenções, `maxsize 20M`, compressão, `copytruncate`, `missingok` e
     `notifempty`.
   - `docker-compose.yml` recebeu anchor `json-file` reutilizável com
     `max-size: 10m` e `max-file: "3"` nos sete serviços, sem mudar a topologia
     PM2.
   - `backend/requirements-lock.txt` foi regenerado a partir de `backend/.venv`
     e validado em Python 3.12; o cabeçalho documenta o comando e reconhece que
     pytest/coverage ainda estão no conjunto até a separação runtime/dev.
   - Corrigido exclusivamente o comentário de `backend/config/settings.py`: o
     cache de feed existe, expira por TTL de 45 s e não é invalidado por
     `plano.preco_alterado`.
   - Atualizado o runbook de restore/cron/S3 e o exemplo `.env` para refletir a
     validação real, retenção suspensa sem bucket e permissão de leitura necessária
     ao `head-object`.

## Validações

As evidências abaixo foram executadas durante implementação, tester e as três
iterações de remediação; não houve acesso a uma VPS, bucket real ou disparo real
de GitHub Actions.

- **PostgreSQL real (`postgres:16-alpine`):** `pg_dump -Fc` → restore integral
  em `createdb -T template0` → contagem de origem/restaurado `1|10000`; novo
  re-restore manual também confirmou 10.000 linhas. Um archive real truncado em
  99% passou em `pg_restore --list`, mas falhou no restore real com exit 9 e não
  publicou dump final nem temporário. O modo sem bucket preservou sentinelas
  PM2 e Docker; S3 simulado validou `head-object` e retenção.
- **Integridade e operação do script:** modo sem `CREATEDB` falhou fechado;
  upload S3 simulado com erro preservou arquivos; configuração S3 órfã falhou;
  `BACKUP_VALIDATE_RESTORE=0` registrou o escape; concorrência via `flock`,
  permissões, arquivos temporários, modos privados e retenção seletiva foram
  exercitados.
- **Workflows:** `actionlint` 1.7.12 passou nos seis workflows após a iteração 3;
  parser YAML e verificações de grafo confirmaram `workflow_call`, `needs:
  verify`, refs exatos, `tls_enabled` e ausência de `guard`/`guard_ref`/`needs:
  guard`. Blocos `run`/`script` passaram em `bash -n` e `dash -n`.
- **Infraestrutura:** `docker compose --env-file .env.production.example -f
  docker-compose.yml config --quiet` passou; `logrotate -d` leu o padrão com
  rotação/14/maxsize esperados; o tuning foi incluído em `postgres:16-alpine` e
  os quatro valores foram confirmados com `SHOW`.
- **Dependências e backend:** `pip check` passou no ambiente local e em uma
  instalação limpa do lock em Python 3.12; `manage.py check` passou; a
  comparação `pip freeze` com `requirements-lock.txt` ficou vazia.
- **Testes rápidos:** `pytest -q feed/tests/test_sanity.py` terminou em
  **12 passed**, com 11 warnings esperados de staticfiles ainda inexistente.
- **Higiene:** `git diff --check` passou; não houve alteração de API/schema,
  migrations, regras de negócio ou TypeScript atribuível a esta run.

## Revisão e remediação

1. **Tester — iteração 1:** encontrou o blocker de gate: os deploys removiam o
   guard sem esperar o CI e as tags não eram cobertas pelo trigger de branches.
   A **remediação da iteração 1** adotou `workflow_call` reutilizável, com
   `verify`/`needs`, refs fixas e gate de PROD para a tag.
2. **Reviewer — iteração 2:** a revisão encontrou um blocker de integridade do
   dump (`pg_restore --list` não detecta todos os truncamentos) e quatro majors:
   retenção/S3 podia perder a única cópia, o deploy não instalava o lockfile, o
   restart podia deixar estado parcial/interrompido e a release PROD era criada
   antes do gate. Havia ainda um minor de contexto/permissões do cron. A
   **remediação da iteração 2** tratou os seis findings: restore real e
   contagem, S3 fail-closed/head-object/retenção condicional, lock no deploy,
   restart sem delete e release somente após verify/deploy/validate, além dos
   avisos de owner/permissão.
3. **Re-revisão —Finding 4 residual:** a mitigação anterior ainda não fornecia
   recuperação para queda de SSH, falha entre os dois processos ou nova versão
   que não subisse; o reviewer classificou isso como major residual. A
   **remediação da iteração 3** adicionou retry/sanity PM2, marker
   `.deployed-sha`, smoke antes da promoção e `.github/workflows/rollback.yml`,
   mantendo a estratégia conservadora e sem rollback automático de schema.
4. **Re-revisão final — iteração 3:** `approve_with_comments`. O finding de
   rollback foi considerado resolvido dentro da mitigação acordada. Restou um
   minor: o smoke web usa `curl -sf` e aceita 3xx, embora a promoção ideal
   devesse exigir HTTP 200 exato; não invalida o retry, marker ou rollback na
   escala atual. Não houve blocker, major ou nit aberto.

## Follow-ups / pendências

- **(a) Minor do marker/smoke web:** tornar o probe web explícito para exigir
  HTTP 200 exato; hoje a promoção de `.deployed-sha` ocorre quando API e web
  passam, mas `curl -sf` aceita 3xx. O marker representa o último deploy
  aprovado como alvo de recuperação, não um inventário paralelo dos dois
  processos após uma falha parcial.
- **(b) Proteção externa do GitHub:** configurar branch protection/ruleset para
  `develop`/`main`, proteção de tags, required status checks e approvals dos
  GitHub Environments. É configuração humana e complementa o gate versionado;
  não foi presumida como aplicada.
- **(c) Aplicação real na VPS:** instalar/configurar o cron no usuário correto,
  criar/configurar o bucket e lifecycle, testar backup e restore em staging,
  instalar/validar logrotate e aplicar tuning com `SHOW` antes/depois, espaço,
  RAM e rollback sob controle humano. Esta run não executou nenhum passo
  privilegiado na VPS.
- **(d) Build standalone no runner:** a migração do build frontend para
  `.next/standalone` foi deferida; o plano documentado exige testar em HOMOLOG,
  os mesmos `NEXT_PUBLIC_*`, validar o bundle, smoke, troca atomicamente
  versionada e rollback antes de PROD.
- **(e) Requirements runtime versus desenvolvimento:** separar
  `pytest`/`pytest-cov`/`pytest-django` do runtime e retirar ferramentas de teste
  da imagem de produção exige alterar Docker, CI e deploy de forma coordenada;
  o lock atual continua incluindo-as e registra essa limitação.
- **Recomendação adicional:** exercitar o rollback manual em DEV/HOMOLOG com um
  SHA real e confirmar a compatibilidade de schema antes de PROD. Se a
  indisponibilidade perceptível ou o tempo de manutenção for inaceitável,
  planejar blue-green e uma estratégia explícita para migrations.

## Desvios e limitações do plano

- A build standalone no runner e a separação física de requirements não foram
  implementadas, conforme os não-objetivos; ambas têm plano/follow-up.
- Não houve dispatch real de workflow, SSH à VPS, bucket S3 real, emissão de
  secrets ou restore produtivo. A validação do restore foi real em PostgreSQL 16
  de teste; a operação de infraestrutura depende do humano.
- O resultado final é entregue com um minor aceito e riscos residuais
  explicitamente documentados; a aprovação é `approve_with_comments`, não uma
  promessa de zero downtime ou de rollback automático de schema.

## Artefatos desta execução

- `task-plan.md`
- `implementation-contract.md`
- `implementation-history.md` (implementação e três remediações)
- `code-review-contract.md` (revisões e veredito final)
- `documentation-update.md`
- `report.md`
