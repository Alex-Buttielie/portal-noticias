# Task Plan — 20260924-1200-ops-higiene

## Metadados
- **run_id:** 20260924-1200-ops-higiene
- **Data de abertura:** 2026-09-24
- **Solicitado por:** sessão pai (Alex), como subagente executor do agentic-framework
- **Spec de origem:** `ANALISE_CUSTO_PERFORMANCE.md` — achados B1, K1/L1, seção 6 “Outros” e itens P2-6/P2-7 da seção 7

## Objetivo
Deixar a operação da VPS PM2 + Nginx segura e reproduzível: backup nativo de banco e mídia validado/enviado com retenção, deploys serializados com mitigação de OOM no build remoto, configurações de tuning e rotação de logs preparadas sem aplicação automática e higiene de dependências/documentação coerente com o runtime real.

## Escopo
### Dentro do escopo
- **P0-2:** criar `infra/backup/pg_backup_pm2.sh` para o Postgres nativo do host, com credenciais do ambiente PM2 ou `PG*`, `pg_dump -Fc`, validação `pg_restore --list`, mídia real `backend/media`, S3-compatível opcional e retenção local de 7 dias; manter o script Docker existente intacto.
- Documentar instalação do cron, diferenciação entre PM2 e Docker, S3, logrotate e tuning do Postgres na topologia ativa.
- **P1-5:** entregar a opção conservadora no workflow: serialização por ambiente, remoção do guard duplicado, cache npm persistente no home da VPS e limite de heap do Node; documentar o build standalone no runner como follow-up testado.
- **P2-6:** versionar `infra/postgres-tuning.conf` para VPS 4 GB, snippet de logrotate e limites de log dos containers da variante Docker.
- **P2-7:** regenerar `backend/requirements-lock.txt` a partir de `backend/.venv`, documentar o procedimento e a separação futura de dependências de desenvolvimento, e corrigir exclusivamente o comentário obsoleto do cache em `backend/config/settings.py`.
- Criar e manter os artefatos desta run em `agentic-framework/state/run-20260924-1200-ops-higiene/`.

### Fora do escopo (explicitamente)
- Aplicar tuning, instalar cron/logrotate, configurar bucket ou executar restore na VPS: esta execução não tem acesso ao host.
- Migrar de fato o build do frontend para artefatos `.next/standalone`; a mudança exige um deploy real e fica como plano documentado.
- Separar fisicamente requirements de runtime e desenvolvimento ou retirar pytest da imagem; é uma reestruturação com impacto em Docker/CI/deploy.
- Decidir se `ingestao-service/` será arquivado ou ativado; requer decisão de arquitetura independente.
- Tocar qualquer arquivo da run `run-20260923-2238-pendencias-pre-deploy`.
- Alterar código de aplicação Python em `apps/` ou qualquer TypeScript; a única exceção é texto de comentário em `backend/config/settings.py:405-407` solicitado explicitamente.

## Suposições assumidas
- O arquivo de ambiente canônico da topologia ativa é `/home/apps/portal-prod/backend/.env`, como criado e preservado por `.github/workflows/deploy.yml`; o novo script também aceitará `BACKUP_ENV_FILE=/home/apps/portal-prod/.env` e variáveis `PG*` puras. — motivo: confirmar o path real lendo o deploy e `MEDIA_ROOT = BASE_DIR / "media"`, sem assumir o path abreviado da análise inicial.
- O backup remoto é opcional por contrato, mas a ausência de `BACKUP_S3_BUCKET` deve produzir aviso inequívoco e não pode ser declarada sucesso operacional completo. — motivo: o bucket e suas credenciais não existem no repositório.

## Restrições
- Nenhum commit e nenhuma alteração de API, schema, modelo, regra de negócio, Python de `apps/` ou TypeScript.
- Preservar alterações de trabalho já presentes em `.github/workflows/deploy.yml`, `CI-CD.md`, `infra/DEPLOY.md` e `backend/config/settings.py`; editar apenas TREchos relacionados.
- Shell novo deve usar `set -euo pipefail`, falhar com código diferente de zero, não registrar segredos, validar artefatos antes da publicação e não apagar backups da variante Docker.
- Não usar `docker compose` no caminho PM2 e não documentar `pg_backup.sh` como o script da VPS ativa.
- Não aplicar configurações privilegiadas no ambiente local ou na VPS; entregar arquivos e comandos seguros com validação.
- Decisão preferencial de segurança para P1-5: sem migração de artefato de build não comprovada em deploy real.

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor (esta sessão) | implementação validada contra o checklist | config/scripts/docs + `implementation-history.md` |
| 2 | tester | `implementation-contract.md` + diff | veredito `passed`/`failed`/`blocked` |
| 3 | reviewer (obrigatório: credenciais de backup e CI/CD sensível) | diff do executor | `code-review-contract.md` |
| 4 | remediator (se necessário) | findings priorizados | correções + nova validação |
| 5 | documenter | histórico + evidências | `documentation-update.md` e consistência final |
| 6 | historian | todos os artefatos | `report.md` + entrada em `agentic-framework/state/HISTORY.md` |

## Critérios de aceite (nível de negócio/produto)
1. O operador da topologia PM2 consegue gerar, sem Docker, um dump Postgres e um arquivo de mídia que só são publicados após validação; o procedimento de cron e as pré-condições S3 ficam documentados.
2. A retenção local de 7 dias alcança apenas artefatos PM2 identificados, e a ausência de destino remoto é mostrada como risco explícito.
3. Dois deploys do mesmo ambiente não executam simultaneamente; o pipeline não repete o guard sem cache e o build Node na VPS tem cache persistente e heap limitado.
4. O Postgres tem um arquivo de tuning conservador pronto para instalação, mas nenhuma mudança privilegiada é aplicada por esta run; logs de backup e dos containers têm rotação versionada.
5. O lock de dependências reflete o ambiente disponível e o procedimento para regenerá-lo é reproduzível; a inclusão de dependências de teste no runtime está explicitamente reconhecida como follow-up.
6. A documentação do cache do feed descreve TTL de 45 segundos, sem afirmar invalidação por evento inexistente.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Credenciais de banco/S3 expostas em log ou arquivo de backup | alto | `umask 077`, `.env` nunca impresso, paths privados, falha explícita se credencial estiver incompleta |
| Backup local ser a única cópia e ainda expirar após 7 dias | alto | aviso explícito sem bucket, retenção exigida, documentação de R2/B2 e restore; configuração do bucket fica como ação humana |
| Upload S3 parcialmente concluído | alto | validar DB/mídia antes do upload; `aws s3 cp` com `set -e`; manter cópias locais válidas em falha para investigação |
| `NEXT_PUBLIC_*` divergir entre build e ambiente ao migrar para artifact | alto | preservar build remoto nesta entrega e documentar plano de build/teste/rollback antes da migração |
| Cache/heap ainda pressionar a VPS de 4 GB | médio | cache no home, `--prefer-offline` e heap de 1536 MB; medir no próximo deploy antes de aumentar |
| Tuning consumir RAM necessária de três stacks | médio | `shared_buffers` de 1 GB e valores conservadores; aplicar e verificar `SHOW` somente em janela controlada |
| logrotate trocar ownership e impedir o próximo append | médio | usar `copytruncate`, que preserva owner/mode do arquivo existente, e validar com `logrotate -d` |

## Dependências
- Na VPS: cliente PostgreSQL compatível com o servidor, `tar`, `flock` e `aws`/AWS CLI quando `BACKUP_S3_BUCKET` estiver configurado.
- Para proteção fora da VPS: bucket S3-compatível, credencial com permissão de escrita e lifecycle rule (por exemplo, 90 dias).
- Para o follow-up de build no CI: deploy de homologação com testes de `NEXT_PUBLIC_*`, boot do standalone, troca atômica e rollback.
