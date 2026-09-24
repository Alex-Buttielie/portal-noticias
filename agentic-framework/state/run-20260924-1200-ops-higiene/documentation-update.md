# Atualização de documentação — 20260924-1200-ops-higiene

## Metadados

- **run_id:** `20260924-1200-ops-higiene`
- **Baseado em:** `task-plan.md`, `implementation-contract.md`,
  `implementation-history.md` (iterações 1–3) e `code-review-contract.md`
  (`approve_with_comments` na iteração 3).
- **Escopo desta etapa:** documentação de operação e exemplos de uso; nenhum
  código-fonte Python/TypeScript ou workflow foi alterado. Os únicos ajustes de
  produto fora dos documentos narrativos foram comentários de exemplo/configuração
  alinhados ao runbook.

## Verificação geral

A documentação foi confrontada com a topologia real e com os arquivos
versionados. A topologia ativa é **PM2 + Nginx + PostgreSQL nativo**; Docker/Caddy
é a variante alternativa. O novo `infra/backup/pg_backup_pm2.sh` já estava
documentado no runbook principal, mas três textos ainda refletiam a versão
anterior do script: a validação do dump, a retenção local sem bucket e a
permissão S3 necessária para `head-object`. Esses textos foram alinhados ao
comportamento efetivamente implementado e testado.

## Alterações realizadas

| Arquivo:linha (após a edição) | Antes → depois | Motivo |
|---|---|---|
| `README.md:18-22` | A seção de deploy apontava para `CI-CD.md`/`infra/DEPLOY.md`, mas não dizia qual script de backup pertence à topologia ativa. → Acrescentado que PM2 usa `infra/backup/pg_backup_pm2.sh`, que o runbook cobre cron/S3/restore e que `infra/backup/pg_backup.sh` é exclusivo de Docker/Caddy. | Tornar a distinção PM2 × Docker visível já no ponto de entrada, sem duplicar o procedimento operacional. |
| `infra/DEPLOY.md:40-44` | O runbook mencionava `flock` e a diferença entre scripts, mas não explicava a permissão necessária para a validação padrão. → Acrescentado que `psql`/`createdb`/`dropdb` e `CREATEDB` são necessários e que a falta de permissão falha fechado. | O script agora valida o dump restaurando-o em banco descartável; a documentação precisa da pré-condição real. |
| `infra/DEPLOY.md:62-65` | A instrução de IAM dizia “apenas escrita” no prefixo. → Substituído por permissão de escrita e leitura (`s3:PutObject` e `s3:GetObject`), explicitando que `head-object` precisa da leitura e recomendando não conceder delete/listagem desnecessários. | O fluxo S3 verifica `ContentLength` antes de liberar a retenção; uma política somente-escrita faria o backup falhar mesmo após o upload. |
| `infra/DEPLOY.md:77-90` | O texto dizia apenas que o dump era validado por `pg_restore --list` e que a cópia local sem bucket “expira” após a retenção. → Documentado o restore integral em banco descartável e comparação de contagens por padrão, o escape explícito `BACKUP_VALIDATE_RESTORE=0`, a leitura integral que permanece nesse escape, a retenção somente após uploads/`head-object` e a suspensão de retenção que mantém todos os arquivos locais sem bucket. | Alinhar o runbook à remediação de integridade do dump e à política fail-closed de S3/retenção. |
| `infra/DEPLOY.md:107-111` | O comando de crontab não dizia qual contexto de usuário era esperado. → Acrescentado que cron e backup devem rodar no mesmo usuário efetivo do PM2, do checkout, do `.env` e da mídia; root não deve ser usado apenas por causa do `sudo` de instalação. | Evitar backups root-owned ou falha de leitura da mídia, correspondendo à validação de owner/permissões do script. |
| `infra/DEPLOY.md:575-582` | A seção de restauração oferecia `pg_restore --list`/`tar -tzf` como se fossem a prova de recuperabilidade. → Acrescentado que são apenas checagens de formato, que um truncado pode passar pelo `--list`, e o procedimento de `pg_restore --exit-on-error` em banco `createdb -T template0` descartável, contagens, `dropdb` e extração da mídia em diretório vazio. | A documentação deve refletir a validação real exigida pelo script e evitar que o operador confunda TOC com backup recuperável. |
| `backend/.env.example:170-178` | O comentário dizia que, sem bucket, o script mantinha a cópia local “por 7 dias”. → Corrigido para informar que todos os backups locais são mantidos, a retenção fica suspensa e existe risco explícito de perda da VPS. | Remover uma instrução de configuração que poderia induzir o operador a presumir uma retenção de sete dias inexistente no modo local-only. |

## Verificações sem alteração

- `infra/DEPLOY.md:18-39` já identifica os paths reais
  `/home/apps/portal-prod/backend/.env` e `backend/media`, o `BACKUP_ENV_FILE` e
  a dependência de `postgresql-client`, `tar`, `util-linux` e `awscli`.
- `infra/DEPLOY.md:46-117` contém o comando idempotente de cron, paths, S3/R2/B2,
  lifecycle, risco de cópia somente local, permissões e rotação com
  `logrotate -d`; não foi reescrito.
- `infra/DEPLOY.md:119-167` já contém o tuning versionado para a VPS de 4 GB,
  comandos de instalação controlada, `SHOW` antes/depois e rollback, deixando
  claro que a run não aplica o arquivo.
- `infra/DEPLOY.md:554-566` continua separando explicitamente o backup
  `pg_backup_pm2.sh` da VPS ativa do `pg_backup.sh` da variante Docker/Caddy.
  A seção 7 aponta para a seção 0 e não deve ser usada na VPS PM2.
- `CI-CD.md:20-25, 64-73` confirma o gate `verify` por `workflow_call`, o mesmo
  SHA verificado e a cobertura da tag de produção. `:75-117` confirma o
  marcador `.deployed-sha` e o rollback manual; `:119-208` mantém o procedimento
  shell, a limitação de migrations e a ausência de zero downtime; `:210-220`
  lista CI, DEV, HOMOLOG, PROD e rollback, seus gates e secrets; `:242-285`
  confirma `concurrency` sem cancelamento, cache npm persistente, heap de
  1536 MB e o plano de build standalone. O arquivo foi verificado, não reescrito,
  conforme solicitado.
- O uso do lockfile foi confirmado no caminho documentado de rollback
  (`CI-CD.md:138-160`) e no workflow de deploy (`.github/workflows/deploy.yml`,
  passo de instalação do runtime); a linha do workflow é a referência canônica
  para não duplicar um comando que poderia divergir. A procedência/regeneração e
  a limitação runtime/dev estão em `backend/requirements-lock.txt:1-10` e
  `backend/requirements.txt:69-73`. Nenhuma outra documentação precisou ser
  duplicada.
- O comentário de cache do feed em `backend/config/settings.py:405-410` já
  afirma TTL de 45 s e a ausência de invalidação por `plano.preco_alterado`.
- `docker-compose.yml:11-17` e os sete serviços mantêm o anchor `json-file`
  (`10m` × `3`); nenhuma configuração Compose foi alterada nesta etapa.

## Exemplos e snippets

- O exemplo de cron PM2, a lista de variáveis S3 e a sequência de restore
  estão consolidados em `infra/DEPLOY.md:46-117` e `:554-582`.
- O README agora fornece apenas o índice para o runbook, evitando uma segunda
  cópia de comandos que pode divergir.
- Não existe um `CHANGELOG.md` mantido pelo projeto; não foi criada uma entrada
  de changelog paralela.

## Verificação final

- [x] Não resta texto de runbook que atribua retenção de sete dias ao modo
  local-only ou que apresente `--list` como prova suficiente de restore.
- [x] A distinção entre `pg_backup_pm2.sh` e `pg_backup.sh` está explícita no
  README e no runbook.
- [x] As referências de `CI-CD.md` continuam coerentes com `ci.yml`,
  `deploy.yml`, callers e `rollback.yml`; nenhuma reescrita foi feita.
- [x] `git diff --check -- README.md infra/DEPLOY.md backend/.env.example`
  terminou com exit 0.
- [x] Nenhum código-fonte foi alterado nesta fase.

## Fora do escopo e motivo

- **Não reescrever `CI-CD.md`:** a referência já cobre gate, concorrência,
  lockfile, retry/sanidade, marker, rollback, secrets e limitações; a única
  imprecisão conhecida é o smoke web aceitar 3xx, registrada como minor
  independente na re-revisão. Alterar o workflow ou essa documentação agora
  exigiria uma nova alteração de código/teste fora do papel de documenter.
- **Não corrigir o minor do probe web:** a promoção do marker atualmente aceita
  qualquer resposta abaixo de 400 (`curl -sf`), embora o requisito ideal seja
  200 exato. O follow-up fica registrado no `report.md`; a run foi aprovada com
  comentário e o documenter não altera código de workflow.
- **Não configurar GitHub:** branch protection, required status checks,
  proteção de tags e approvals de Environment são configuração externa humana;
  o gate versionado não deve ser descrito como já configurado no repositório.
- **Não executar na VPS:** não foram instalados cron/logrotate, criados buckets,
  aplicadas regras de lifecycle, aplicados tuning, executado restore real ou
  disparados workflows. São ações humanas; o runbook deixa os comandos seguros e
  as pré-condições.
- **Não separar requirements runtime/dev nem migrar o build para standalone:**
  ambos foram explicitamente deferidos no plano por impacto em Docker/CI/PM2;
  permanecem follow-ups, não alterações documentais silenciosas.
- **Não alterar `pg_backup.sh`:** ele é preservado para a variante Docker/Caddy;
  esta run apenas tornou a seleção do script explícita.
