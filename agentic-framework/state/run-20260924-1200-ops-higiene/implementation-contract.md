# Implementation Contract — 20260924-1200-ops-higiene

## Metadados
- **run_id:** 20260924-1200-ops-higiene
- **Deriva de:** `task-plan.md` (20260924-1200-ops-higiene)
- **Versão do contrato:** 1

## O que deve ser construído

### 1. Backup nativo para a topologia PM2 (P0-2)
1. Criar `infra/backup/pg_backup_pm2.sh`, executável, com `set -euo pipefail`, `umask 077` e lock contra execuções concorrentes.
2. Resolver credenciais sem imprimir segredos: `BACKUP_ENV_FILE` explícito; por padrão, usar o env real do deploy (`backend/.env`) e fallback para `.env` na raiz; aceitar `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGHOST` e `PGPORT` do ambiente.
3. Executar `pg_dump` nativo do host em formato custom (`-Fc`), validar o custom archive com `pg_restore --list` e só então renomear/publicar o arquivo final.
4. Arquivar `backend/media` (confirmado por `MEDIA_ROOT = BASE_DIR / "media"` e pelo cwd do backend no deploy) com `tar czf`, validar o gzip/tar e falhar se o diretório não existir.
5. Quando `BACKUP_S3_BUCKET` existir, enviar dump e mídia via AWS CLI/S3 API, usando endpoint opcional e credenciais fornecidas ou cadeia IAM do host. Sem bucket, emitir aviso explícito e manter o exit code zero apenas se todas as operações locais tiverem passado.
6. Aplicar retenção de 7 dias exclusivamente aos nomes `pm2-db-*.dump` e `pm2-media-*.tar.gz`; nunca remover artefatos do script Docker.
7. Manter `infra/backup/pg_backup.sh` inalterado e documentar qual script usar em PM2 e em Docker.

### 2. Operação da VPS e P2-6
8. Versionar `infra/postgres-tuning.conf` com `shared_buffers=1GB`, `effective_cache_size=3GB`, `work_mem=8MB` e `maintenance_work_mem=256MB`, comentado como include para PostgreSQL em VPS 4 GB.
9. Versionar `infra/logrotate/pg-backup.conf` para `/var/log/pg_backup*.log`, com rotação, compressão, `copytruncate`, `missingok` e `notifempty`.
10. Atualizar `infra/DEPLOY.md` com comandos de instalação do cron PM2, pré-requisitos, S3, paths reais, restauração, logrotate e tuning/verificação; não executar nenhum comando na VPS.
11. Adicionar `logging` com `json-file`, `max-size` e `max-file` a todos os serviços de `docker-compose.yml` por âncora reutilizável.

### 3. Deploy conservador e P1-5
12. Adicionar `concurrency` por `inputs.environment_name`, sem cancelar um deploy em andamento, para impedir colisão de `pm2 delete/start`.
13. Remover o job `guard`, o input `guard_ref` e as referências nos callers; manter `ci.yml` como gate de validação fora do deploy.
14. No build que permanece temporariamente na VPS, usar cache persistente `$HOME/.npm`, `--prefer-offline` e `NODE_OPTIONS=--max-old-space-size=1536`.
15. Documentar em `CI-CD.md` por que o artefato standalone não foi migrado agora e quais testes/rollback são obrigatórios antes do follow-up.

### 4. Higiene P2-7
16. Regenerar `backend/requirements-lock.txt` a partir de `backend/.venv` e atualizar o comentário de regeneração em `backend/requirements.txt`.
17. Adicionar as variáveis de backup S3 ao `backend/.env.example`, pois esse é o env da topologia PM2.
18. Corrigir somente o comentário em `backend/config/settings.py:405-407`: o cache do feed existe e expira por TTL de 45 s; não é invalidado pelo evento de preço.
19. Criar `implementation-history.md` com decisões, comandos, evidências e follow-ups.

## Áreas/arquivos esperados
- `infra/backup/pg_backup_pm2.sh` (novo)
- `infra/postgres-tuning.conf` (novo)
- `infra/logrotate/pg-backup.conf` (novo)
- `infra/DEPLOY.md`
- `.github/workflows/deploy.yml`, `.github/workflows/deploy-dev.yml`, `.github/workflows/deploy-prod.yml`
- `CI-CD.md`
- `docker-compose.yml`
- `backend/.env.example`
- `backend/requirements.txt`, `backend/requirements-lock.txt`
- `backend/config/settings.py` (somente comentário já existente nas linhas 405-407)
- `agentic-framework/state/run-20260924-1200-ops-higiene/`

## Interfaces afetadas
- **Operação PM2:** novo entrypoint de backup, consumindo o mesmo `backend/.env` do deploy ou variáveis `PG*`; não altera API ou schema.
- **CI/CD:** cada ambiente passa a serializar runs; o job `guard` e seu input deixam de existir; o build continua na VPS, mas usa cache persistente e heap limitado.
- **Configuração de containers:** limite de arquivos de log Docker; não altera portas, volumes, redes ou healthchecks.
- **Dependências:** pins do lock passam a refletir o `.venv` disponível; o conjunto continua incluindo ferramentas de teste até a separação futura.

## Critérios de aceite (técnicos, testáveis)
1. Dado um checkout PM2 com `backend/.env` válido e PostgreSQL acessível, quando `pg_backup_pm2.sh` é executado, então são criados `pm2-db-<timestamp>.dump` e `pm2-media-<timestamp>.tar.gz`, ambos reconhecidos por `pg_restore --list`/`tar -tzf`, e o processo termina com 0.
2. Dado `BACKUP_ENV_FILE` apontando para outro arquivo ou somente variáveis `PG*` válidas no ambiente, quando o script resolve as credenciais, então ele usa essa fonte sem imprimir senha e sem exigir `DJANGO_DB_*` no arquivo.
3. Dado credencial ausente, binário ausente, banco inacessível, arquivo vazio/corrompido ou path de mídia inexistente, quando qualquer etapa falha, então o script imprime causa clara, remove apenas temporários e termina com código diferente de zero.
4. Dado `BACKUP_S3_BUCKET` vazio, quando um backup local válido termina, então a saída contém aviso de que a cópia está somente na VPS; dado bucket configurado, então `aws s3 cp` é executado para dump e mídia e qualquer falha interrompe com código não zero.
5. Dado arquivos PM2 antigos e arquivos Docker antigos, quando a retenção roda, então apenas `pm2-db-*.dump` e `pm2-media-*.tar.gz` com mais de 7 dias são considerados.
6. Dado o repositório, quando um operador lê `infra/DEPLOY.md`, então encontra um comando idempotente de crontab para `pg_backup_pm2.sh`, o path real `backend/.env`/`backend/media`, a opção `BACKUP_ENV_FILE`, a distinção PM2 × Docker e os passos de S3/logrotate/tuning.
7. Dado `infra/postgres-tuning.conf`, quando um administrador o inclui no cluster PostgreSQL 16, então ele contém os quatro valores conservadores e nenhuma aplicação automática é disparada pelo repositório.
8. Dado `docker-compose.yml`, quando Compose resolve a configuração, então todos os sete serviços referenciam o mesmo driver de log com `max-size: 10m` e `max-file: "3"`.
9. Dado duas execuções do workflow para `production`, quando a segunda inicia antes de a primeira terminar, então `concurrency` impede a segunda de executar em paralelo; `cancel-in-progress` é `false` para não matar o deploy vigente.
10. Dado o workflow reutilizável, quando ele é analisado, então não existe job `guard`, `guard_ref` ou `needs: guard`, e o build frontend na VPS contém cache `$HOME/.npm`, `--prefer-offline` e heap Node de 1536 MB.
11. Dado o `.venv` local disponível, quando `pip freeze` é executado, então o conteúdo de `requirements-lock.txt` corresponde exatamente ao conjunto congelado e o procedimento de regeneração está documentado.
12. Dado o comentário de cache em `settings.py`, quando ele é lido, então afirma TTL de 45 s e não afirma invalidação por `plano.preco_alterado`.
13. Dado o diff desta run, quando `bash -n infra/backup/pg_backup_pm2.sh` e as validações Python/YAML/documentais forem executadas, então não há erro de sintaxe; `manage.py check` e um subconjunto rápido de pytest permanecem verdes.

## Não-objetivos
- Não alterar banco, migrations, modelos, regras de negócio, endpoints, Python de `apps/` ou TypeScript.
- Não aplicar `ALTER SYSTEM`, editar `postgresql.conf`, instalar logrotate/cron ou reiniciar PostgreSQL/PM2.
- Não publicar artefato `.next/standalone` pelo runner nesta versão.
- Não dividir requirements em runtime/dev nem remover `pytest*` do `requirements.txt`/Dockerfile.
- Não apagar, migrar ou ativar `ingestao-service/`.
- Não editar nenhum arquivo de `run-20260923-2238-pendencias-pre-deploy`.

## Restrições técnicas
- **Performance:** impedir concorrência por ambiente; limitar heap Node a 1536 MB e reutilizar cache fora do diretório apagado por `git reset`; não agravar pressão da VPS de 4 GB.
- **Segurança/privacidade:** não logar `.env`, `PGPASSWORD` ou chaves S3; artefatos locais com modo privado; `pg_dump` com senha via `PGPASSWORD` e sem prompt; nunca executar Docker no fluxo PM2.
- **Dependências permitidas:** nenhuma biblioteca nova. Scripts usam apenas utilitários esperados em Ubuntu (`bash`, `flock`, `tar`, `pg_dump`, `pg_restore`, opcionalmente AWS CLI quando S3 está ativo).
- **Estilo/convenções:** documentação e mensagens em português; YAML válido; mudanças mínimas e cirúrgicas em arquivos já modificados por outras runs.
- **Compatibilidade:** manter Node 20, PM2, Nginx, PostgreSQL 16 e os callers thin existentes; não introduzir rsync/scp/artifact sem validação real.

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Testes escritos e passando (tester)
- [ ] Revisão de código aprovada, se exigida por `review-triggers.md` (reviewer)
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente
