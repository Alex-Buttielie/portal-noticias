<!--
CONTRACT: code-review-contract
DONO: reviewer
QUANDO: revisão obrigatória da run 20260924-1200-ops-higiene
-->

# Code Review Contract — 20260924-1200-ops-higiene

## Metadados

- **run_id:** `20260924-1200-ops-higiene`
- **escopo:** `infra/backup/pg_backup_pm2.sh`, `infra/postgres-tuning.conf`, `infra/logrotate/pg-backup.conf`, `docker-compose.yml`, workflows em `.github/workflows/`, `CI-CD.md`, `infra/DEPLOY.md`, `backend/requirements*.txt`, `backend/.env.example`, `.gitignore` e o comentário de cache em `backend/config/settings.py`.
- **contrato de referência:** `implementation-contract.md` desta run.
- **histórico considerado:** `implementation-history.md`, incluindo a remediação do gate `workflow_call`; `run-state.json` (tester: passed, blocker anterior resolvido).
- **gatilhos aplicados:** mudança de CI/CD de produção, backup de dados, configuração de infraestrutura, volume de linhas superior a ~300 e preservação de dados/mídia.
- **método:** leitura integral dos arquivos do escopo; leitura do contrato, histórico, estado e gatilhos; `bash -n`; `actionlint`; parse Compose/YAML; comparação do `pip freeze` com o lock; testes com binários `pg_dump`/`pg_restore`/`tar`/`aws` simulados; teste real com `postgres:16-alpine` para truncamento de archive; inspeção de permissões, retenção, ref/CI e escopo.
- **limitação:** não houve acesso a uma VPS real, bucket S3 real ou disparo real do GitHub; conclusões de produção que dependem disso estão explicitamente tratadas como risco residual.
- **isolamento:** a working tree é compartilhada e contém alterações de outras runs; mudanças de backend P2, frontend P2-5, Nginx e demais hunks não atribuíveis a esta run foram ignoradas. O único hunk de `settings.py` atribuído a esta run é o comentário das linhas 405–407.

## Veredito

**`changes_requested`**

A implementação atende a maior parte dos critérios mecânicos, mas há um risco bloqueante de aceitar e depois reter um dump PostgreSQL truncado, além de uma política de retenção que pode eliminar a única cópia local sem sinal de falha operacional. O gate CI→deploy foi corrigido e está majoritariamente correto, porém o deploy continua não-atômico e o lockfile não é o conjunto efetivamente instalado na VPS. Não há evidência de vazamento de senha em log no caminho normal, mas a precedência de configuração S3 e a retenção local-only criam uma condição de perda de dados.

## Findings

### Finding 1 — blocker — integridade do dump: `pg_restore --list` não valida todos os blocos do archive

- **Arquivo/linhas:** `infra/backup/pg_backup_pm2.sh:146-154`; impacto da retenção em `:206-210`.
- **Evidência:** o script aceita o arquivo após apenas `pg_restore --list`, que valida o cabeçalho/TOC, mas não garante que todos os blocos comprimidos de dados estejam presentes. Em um archive custom real de PostgreSQL 16.15, cortes de 50%, 80% e 99% do arquivo passaram em `pg_restore --list` com exit 0; os mesmos cortes falharam em `pg_restore --exit-on-error --file=/dev/null`.
- **Risco:** o script pode renomear, publicar e enviar um dump que parece válido, e em seguida apagar o backup local anterior; um desastre posterior pode deixar somente um archive irrecuperável.
- **Correção:** manter a checagem de lista, mas exigir uma leitura completa com `pg_restore --exit-on-error --file=/dev/null` ou, preferencialmente, restaurar em banco temporário descartável e executar sanity checks antes de `mv`; somente depois executar upload e retenção.

### Finding 2 — major — retenção pode apagar a única cópia e um bucket externo fornecido no ambiente pode ser sobrescrito por valores vazios

- **Arquivo/linhas:** `infra/backup/pg_backup_pm2.sh:68-88, 201-210`; `backend/.env.example:170-177`; documentação em `infra/DEPLOY.md:73-79`.
- **Evidência:** quando `BACKUP_S3_BUCKET` fica vazio, o script imprime apenas aviso, termina com 0 e ainda executa `find ... -mtime +7 -delete`; após sete dias a única cópia local pode desaparecer. Além disso, somente as variáveis `PG*` são preservadas antes de `source`; um `BACKUP_S3_BUCKET`/endpoint/chave passado pelo processo é sobrescrito por linhas vazias do arquivo de exemplo. Em simulação com bucket externo no ambiente e `BACKUP_S3_BUCKET=` no `.env`, o script não chamou `aws`, avisou local-only e retornou 0.
- **Risco:** o operador pode receber um código de sucesso mesmo sem cópia off-site e perder o histórico local; um upload mal configurado ou aceito sem verificação também pode disparar a retenção.
- **Correção:** em produção exigir `BACKUP_REQUIRE_REMOTE=1` (ou equivalente), não reter quando não houver destino remoto verificado, falhar/monitorar o modo local-only, preservar as variáveis S3 explícitas do processo e verificar o objeto remoto (`head-object`, tamanho/checksum) antes de apagar qualquer arquivo local. O caso normal de credencial errada é fail-closed: `aws s3 cp` retornou 42 em teste simulado, o script abortou e os arquivos antigos permaneceram.

### Finding 3 — major — o CI valida o lockfile, mas o deploy PM2 instala outro conjunto de dependências

- **Arquivo/linhas:** `.github/workflows/ci.yml:64-68` versus `.github/workflows/deploy.yml:219-225` (em especial `pip install -r requirements.txt`).
- **Evidência:** o job de verificação instala `backend/requirements-lock.txt`, enquanto o procedimento que executa `manage.py check`, `migrate` e `collectstatic` na VPS instala `requirements.txt`, cujas transitivas não estão fixadas. O lock foi regenerado corretamente e o freeze local confere, mas ele não governa o ambiente PM2 efetivamente implantado.
- **Risco:** uma transitiva pode ser resolvida de forma diferente na VPS, fazer o deploy falhar ou introduzir comportamento não testado; a alegação de reprodutibilidade do lock não é verdadeira para o caminho de produção.
- **Correção:** instalar `requirements-lock.txt` no deploy PM2 (e alinhar Dockerfile/CI, se o lock também for o contrato de produção), ou criar um lockfile runtime explícito; validar o Python da VPS e manter a separação runtime/dev como follow-up.

### Finding 4 — major — `concurrency` não cancela automaticamente, mas o deploy pode ser interrompido em estado inconsistente

- **Arquivo/linhas:** `.github/workflows/deploy.yml:103-105, 228-249`.
- **Evidência:** `cancel-in-progress: false` protege o run em andamento contra o disparo de um run mais novo, porém não protege contra cancelamento manual, queda da conexão SSH, timeout do runner ou falha após `pm2 delete`; o script apaga os dois processos antes de iniciar os substitutos e não tem rollback/trap. A validação posterior também não desfaz uma versão ruim.
- **Risco:** uma interrupção no meio da sequência pode deixar a API e a web fora do PM2, ou uma versão nova sem a outra, causando indisponibilidade de produção.
- **Correção:** usar release versionado/blue-green ou iniciar a nova versão em porta isolada, validar o health check e só então trocar o tráfego; manter a versão anterior e um `trap`/rollback para falhas de SSH, `pm2 start`, `migrate` ou smoke test.

### Finding 5 — major — o release GitHub de PROD é criado antes do gate de CI

- **Arquivo/linhas:** `.github/workflows/deploy-prod.yml:13-32` (`pre`) e `:34-45` (deploy reutilizável).
- **Evidência:** o job `pre` executa `gh release create` antes de `deploy-prod` chamar `deploy.yml`, cujo job `verify` é o gate; uma tag que falhar no CI/verify ainda deixa um release publicado, embora a VPS não seja implantada.
- **Risco:** consumidores podem instalar ou promover um release que não passou no gate; o fail-closed do VPS não cobre esse efeito de publicação.
- **Correção:** criar o release somente após `verify` (idealmente após smoke), ou criar um draft sem assets públicos e promovê-lo somente após o deploy; registrar a release como não verificada enquanto o gate estiver pendente.

### Finding 6 — minor — o usuário efetivo do cron não é validado

- **Arquivo/linhas:** `infra/backup/pg_backup_pm2.sh:109-119`; pré-requisitos em `infra/DEPLOY.md:34-37, 81-93`.
- **Evidência:** o script executa como o dono do crontab e apenas verifica que o diretório de mídia existe; não verifica UID, proprietário, permissão de leitura de `.env`/mídia nem escrita em `BACKUP_DIR`. Um cron instalado como root pode criar backups root-owned; outro usuário pode falhar ao ler `.env`/mídia ou escrever no checkout.
- **Risco:** o procedimento documentado funciona apenas quando o operador instala o cron no mesmo usuário do PM2; a pré-condição é manual e fácil de violar.
- **Correção:** instalar o cron/serviço explicitamente como o usuário de deploy (por exemplo `runuser`/`systemd User=`), testar `id`, `test -r` e `test -w` no mesmo contexto e falhar com mensagem clara quando o contexto não for o esperado.

## Avaliação dos pontos solicitados

### Backup PM2

- **Dump íntegro/validado:** finding 1; `pg_restore --list` é insuficiente para garantir a integridade dos dados.
- **Usuário na VPS:** o caminho pretendido é o usuário do deploy, usando `pg_dump` nativo via TCP e `PGPASSWORD`; funciona se o cron for instalado nesse usuário, mas isso não é verificado (finding 6).
- **Credenciais/logs:** no caminho normal, `backend/.env` é o fallback correto, `PGPASSWORD` é exportado apenas no processo e não aparece nos logs; a fonte por `source` e a precedência S3 têm o risco da finding 2.
- **Credenciais S3 erradas:** comportamento correto para erro convencional do AWS CLI: comando não condicionado sob `set -e`, exit não zero, retenção não executada e arquivos locais válidos preservados; simulado com exit 42.
- **`flock`:** não há deadlock; `flock -n` retorna 3 quando outra execução está ativa e o cron não espera.
- **Traversal:** nomes de dump/mídia são gerados pelo script e o S3 usa `basename`; não há entrada não confiável nos nomes de saída. Manter o diretório de backup privado e não compartilhar `BACKUP_DIR` com usuários não confiáveis.

### Workflows

- **`verify` versus CI:** aprovado; `deploy.yml:111-115` chama a mesma definição `ci.yml`, com os mesmos `manage.py check`, pytest/cobertura, `tsc` e `next build`; não há um guard degradado.
- **`checkout_ref`:** aprovado; `ci.yml:60` e `:80` usam a entrada nos dois jobs, e `deploy.yml:107` encaminha `verify_ref`.
- **`verify_ref` ausente:** aprovado; a entrada é `required: true` em `deploy.yml:43-45` e o shell também rejeita valor vazio em `:152`, antes de abrir a conexão SSH.
- **`concurrency`:** a serialização por ambiente e `cancel-in-progress: false` estão corretos; o risco residual de interrupção/rollback é finding 4.
- **cache/npm:** não identifiquei regressão; `npm ci` continua usando o lockfile, o cache persistente fica fora do diretório resetado e `--prefer-offline` respeita a integridade do lock; `npm start`/PM2 não foi substituído por um caminho de runtime incompatível.

### PostgreSQL, logs e dependências

- **Tuning:** `shared_buffers=1GB` é plausível, mas limite superior, para uma VPS realmente equipulada com 4 GB; `effective_cache_size=3GB` é apenas estimativa do planner e `work_mem=8MB` pode multiplicar-se por operações concorrentes, enquanto `maintenance_work_mem=256MB` pode causar pico durante manutenção. Como o arquivo não é aplicado automaticamente e a documentação exige janela/medição, não é blocker; não deve ser instalado em uma VPS menor sem recalcular os valores.
- **Logs Docker:** `10m × 3` por serviço e sete serviços resulta em aproximadamente 210 MB de logs rotacionados, mais metadados; é um limite razoável para uma VPS de 4 GB, desde que o disco tenha espaço para banco, mídia, imagens e backups.
- **Lockfile:** a comparação independente com `backend/.venv` não encontrou diferença e as versões diretas de `requirements.txt` conferem; pinning de transitivas é o trade-off esperado de um lockfile, mas o uso incorreto no deploy é finding 3.
- **Escopo:** não há alteração de lógica de aplicação atribuível a esta run; o comentário de `settings.py` está correto ao afirmar TTL de 45 s para as listagens do feed e ausência de invalidação por `plano.preco_alterado`. Alterações de outras runs na working tree foram ignoradas.

## Avaliação do risco de perda de dados

**Risco atual: alto** até que os findings 1 e 2 sejam corrigidos. Com bucket configurado e credencial inválida, o fluxo normal falha antes da retenção e preserva os arquivos locais; com o `pg_restore --list` isolado, porém, um dump truncado pode ser aceito e a retenção pode eliminar o último backup íntegro. Sem bucket — ou quando um valor S3 externo é sobrescrito por um `.env` vazio — o script retorna sucesso, mantém somente a janela local de sete dias e pode perder a única cópia disponível. O requisito de teste de restore em staging continua sendo obrigatório antes do próximo deploy produtivo.

## Itens que não constituem finding

- `set -euo pipefail`, `umask 077`, `flock -n`, arquivos temporários/rename e os testes de modo/bucket sem S3 foram observados funcionando.
- `pg_restore --list` rejeita archive vazio/claramente inválido; a finding 1 trata especificamente da insuficiência da cobertura, não da ausência de qualquer validação.
- O padrão de retenção não casa `db-*`/`media-*` do script Docker; o teste de arquivos sentinel confirmou que os nomes Docker permanecem.
- `actionlint` passou nos cinco workflows e o parser Compose aceitou a configuração; essas validações não substituem uma execução real na VPS/GitHub.

## Re-revisão — 2026-09-24 (iteração 2)

**Escopo e método.** Reinspeção independente do working tree, sem alteração de código e sem commit. Li o script, os cinco workflows e o histórico da run paralela de TLS; executei `bash -n`/ShellCheck, `actionlint` e parser YAML; conferi o grafo de needs e as expressões condicionais. Para o backup, rodei o script em `postgres:16` real com uma tabela de 10.000 linhas, um archive custom truncado em 99%, um usuário sem `CREATEDB`, sentinelas de retenção e um AWS CLI falso para `s3 cp`/`head-object`. Não houve VPS, bucket S3 real ou disparo real do GitHub.

### Resultado por finding original

| Finding | Status na re-revisão | Evidência independente em uma linha |
|---|---|---|
| **1 — blocker / integridade do dump** | **RESOLVIDO** | O restore real em `createdb -T template0` + `pg_restore --exit-on-error` + contagem `1|10000` passou; o archive truncado em 99% falhou no restore (exit 9), não criou final/temporário published e o banco `backup_validate_*` foi removido pelo cleanup; `createdb` sem privilégio também falhou fechado (exit 8). |
| **2 — major / retenção e S3** | **RESOLVIDO** | Sem bucket o ramo local não executa `find -delete` (sentinelas PM2/Docker preservaram); configuração órfã falhou (12/13), e o S3 falso exigiu `head-object` com tamanho local antes de liberar a retenção. |
| **3 — major / lock no deploy** | **RESOLVIDO** | `.github/workflows/deploy.yml:243` instala `backend/requirements-lock.txt`, o mesmo arquivo instalado pelo backend do CI em `ci.yml:66`. |
| **4 — major / atomicidade e indisponibilidade** | **PARCIALMENTE RESOLVIDO; major residual** | `pm2 delete` sumiu, há `restart`/`start`, `.env` temporário+`chmod`+`mv` e `validate` com `always()`, mas não há release versionado/blue-green, retenção do processo anterior nem rollback: uma queda de SSH, falha entre os dois restarts ou nova versão que não sobe pode deixar API/web parcial ou fora do PM2; o probe observa, mas não recupera. |
| **5 — major / release após gate** | **RESOLVIDO** | `gh release create` está somente no job `release`, com `needs: [pre, deploy-prod]`; o job confere `TAG_NAME^{commit}` contra `github.sha` e falha se a tag tiver sido movida. |
| **6 — minor / ownership e permissões** | **RESOLVIDO** | `check_runtime_permissions` registra UID, owner, modo, leitura/escrita de `BACKUP_DIR`/`MEDIA_DIR` e legibilidade do env sem transformar aviso em falha bloqueante. |

### Não-regressão da run paralela TLS

- `tls_enabled` continua sendo input tipado `boolean` do reusable `deploy.yml` e é passado por `deploy-dev.yml`, `deploy-homolog.yml` e `deploy-prod.yml` (hoje `false`).
- O shell do deploy escolhe `API_ORIGIN`/`WEB_ORIGIN` como `http://` ou `https://` conforme o booleano, grava/valida os três flags de TLS condicionadamente e o health check usa Gunicorn HTTP no bootstrap ou o vhost HTTPS com `--resolve` quando habilitado.
- A simulação independente das duas entradas e o parser/actionlint passaram; **o `tls_enabled` sobreviveu às edições do remediator e não há novo blocker de TLS**.

### Resumo e novo veredito

| Severidade | Quantidade |
|---|---:|
| blocker | 0 |
| major | 1 aberto (Finding 4 residual) |
| minor | 0 |

**`changes_requested`**

Cinco findings originais e a não-regressão de TLS foram corrigidos, mas o Finding 4 continua major: `restart`/`start` e `always()` reduzem a janela e melhoram a observabilidade, porém não atomicidade nem recuperação. A aprovação fica bloqueada até haver uma estratégia de troca/rollback que preserve o processo anterior (ou equivalente), sem reintroduzir `pm2 delete`; não há blocker de integridade nem regressão TLS nesta re-revisão. Nenhum código foi alterado e nenhum commit foi criado; este contrato é o único artefato atualizado.

## Re-revisão iteração 3 — 2026-09-24

**Escopo e método.** Reinspeção independente da remediação do Finding 4, sem alteração de código e sem commit. Li integralmente `.github/workflows/deploy.yml`, `.github/workflows/rollback.yml`, os três callers, `ci.yml` e a seção pertinente de `CI-CD.md`; executei `actionlint` 1.7.12 nos seis workflows, parse YAML, `bash -n`/`dash -n` de todos os blocos `run`/`script`, testes isolados do validador do rollback e mocks das funções PM2 extraídas do workflow. Não houve VPS, GitHub Actions ou S3 real.

### Verificação dos sete pontos solicitados

| Ponto | Resultado | Evidência independente |
|---|---|---|
| **1 — retry de restart** | **APROVADO** | `PM2_MAX_ATTEMPTS=3`; em dois mocks, estado `errored` nas duas primeiras tentativas e `online` na terceira, além de dois comandos de restart com exit != 0 seguidos de sucesso; ambos terminaram com rc 0 após exatamente três chamadas. Estado `errored` persistente terminou rc 1 e imprimiu o alvo de recuperação. |
| **2 — sanity antes do próximo processo** | **APROVADO** | `restart_or_start` só retorna 0 após o comando ter sucesso e `wait_for_pm2_online` obter duas confirmações consecutivas de `online`; `errored`, `stopped`, `missing` e JSON inválido esgotam a tentativa. A chamada de web está antes da de API, portanto a API só é tocada após o sanity da web. |
| **3 — marker `.deployed-sha`** | **PARCIAL; MINOR ABERTO** | O SHA anterior é lido e republicado por temporário + `mv` antes do primeiro `git reset`; a promoção exige API 200, web saudável, `deploy == success` e checkout igual ao SHA verificado. Porém o smoke web usa `curl -sf`, que também retorna 0 para HTTP 3xx; um teste local com 302 confirmou rc 0, então a web não é comprovada como **exatamente 200**. Em falha parcial, o marker representa o **último deploy aprovado/alvo de rollback**, não o SHA efetivo de cada processo PM2. |
| **4 — rollback** | **APROVADO** | `workflow_dispatch` com `confirm` obrigatoriamente verdadeiro e SHA normalizado com exatamente 40 hex; o caller reutiliza `deploy.yml` com `git_mode: rollback`, `verify_ref` igual ao SHA e `strict_validate: true`; não há job/step de release. SHA hex válido, mas semanticamente errado, ainda depende do operador e não é rejeitado pelo formato; precisa passar o CI e a confirmação, enquanto SHA inexistente falha no `verify` antes do SSH. |
| **5 — documentação de disponibilidade** | **APROVADO** | `CI-CD.md:75-82` e `:202-208` declaram explicitamente PM2 em VPS única, restart in-place, ausência de zero downtime e possível estado parcial; o gatilho para blue-green é “indisponibilidade perceptível ou tempo de manutenção inaceitável”. |
| **6 — limitações aceitas** | **ACEITÁVEIS, NÃO BLOQUEANTES NESTA ESCALA** | Não há `trap`/blue-green nem reversão automática de schema; a recuperação é manual, auditável e aponta para o marker anterior. O rollback não executa `migrate <version>` para desfazer schema: como o alvo normal é o último deploy bem-sucedido, suas migrations já deveriam estar aplicadas. Ainda assim, um SHA válido escolhido incorretamente pode rodar migrations pendentes; `confirm`, a obrigação documentada de verificar compatibilidade e o backup externo tornam isso um risco humano explícito, não um blocker novo. |
| **7 — não-regressão** | **APROVADO** | `verify` continua chamando `ci.yml` e `deploy` depende dele; `tls_enabled` continua boolean/default false nos callers e no rollback, com validação `true|false` e probes condicionais no reusable. `actionlint` passou nos seis workflows. `infra/backup/pg_backup_pm2.sh` e `infra/certbot/deploy-hook-nginx.sh` permanecem untracked, com mtimes (04:09 e 04:17) anteriores aos arquivos da remediação (04:42–04:45) e sem alteração posterior observável; ambos também passaram em `bash -n`. |

### Finding 7 — minor — o smoke web não exige HTTP 200 exato

- **Arquivo/linhas:** `.github/workflows/deploy.yml:514-518, 527-544`.
- **Cenário:** se `/` responder 3xx (ou outro status abaixo de 400), `curl -sf` retorna 0, `WEB_OK` é 1 e o marker pode ser promovido desde que a API retorne 200 e o restante do deploy esteja verde; isso diverge da garantia documentada de “API e web 200”.
- **Evidência:** um servidor HTTP local retornando 302 fez `curl -sf -o /dev/null` terminar com rc 0.
- **Correção sugerida:** capturar `WEB_HTTP_CODE` com `curl -s -o /dev/null -w '%{http_code}'` e exigir `200`, como já ocorre na API. É uma melhoria de precisão do smoke, não uma falha do retry/rollback que impeça esta aprovação com comentários.

### Resultado do Finding 4 residual

O finding anterior foi **resolvido dentro da mitigação conservadora acordada**: o deploy não usa mais `pm2 delete`, recupera falhas transitórias de timing por retry, bloqueia o avanço sobre um processo não saudável, conserva um alvo determinístico de recuperação e oferece rollback manual com gate estrito e sem release. O que permanece — breve indisponibilidade, dependência de recuperação manual e impossibilidade de reverter schema automaticamente — é limitação real e aceita, não disponibilidade garantida.

### Comentários operacionais aceitos

- `.deployed-sha` deve ser lido como “último deploy aprovado por smoke”, não como inventário paralelo dos dois processos após uma falha parcial.
- Um dispatch real em DEV/HOMOLOG ainda é obrigatório antes de PROD; mocks e análise estática não exercitam GitHub Environment, latência real de PM2/Nginx nem rollback de migrations.
- Para uma SLA de zero downtime, a decisão deve migrar para blue-green; para a topologia atual de VPS única, a mitigação é proporcional e operável.

### Resumo quantitativo final

| Severidade | Quantidade |
|---|---:|
| blocker | 0 |
| major | 0 |
| minor | 1 |
| nit | 0 |

## Veredito final — iteração 3

**`approve_with_comments`**

O major residual de recuperabilidade foi fechado no escopo de mitigação conservadora, e a não-regressão está verde. Permanece um minor: o probe web aceita 3xx, embora a promoção deva exigir 200; essa imprecisão não invalida o retry, o marker nem o rollback para a escala atual. Os demais comentários registram que a arquitetura permite downtime breve e recuperação manual, não reverte migrations e trata o marker como último deploy aprovado — riscos aceitáveis para a topologia atual, desde que o rollback seja exercitado em DEV/HOMOLOG e a compatibilidade de schema seja confirmada antes de PROD. Nenhum código foi alterado e nenhum commit foi criado; este contrato é o único artefato atualizado.

