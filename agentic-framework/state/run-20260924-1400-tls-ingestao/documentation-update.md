# Atualização de documentação — 20260924-1400-tls-ingestao

## Escopo verificado

A documentação de produto foi conferida contra a topologia registrada em `CI-CD.md`, `infra/DEPLOY.md`, os três sites `infra/nginx/portal-*.conf` e o contrato da run. A realidade atual é **PM2 + Nginx**; o TLS está parametrizado/preparado para Certbot, mas ainda depende de valores reais, emissão do certificado, validação e ativação humana. Docker/Caddy permanece apenas como variante alternativa/local.

## Alterações realizadas

| Arquivo:linha (após a edição) | Antes → depois | Motivo |
|---|---|---|
| `README.md:37-39` | A seção “Deploy e infraestrutura” descrevia Nginx, cache/rate e a alternativa Docker/Caddy, mas não dizia o estado do TLS. → Acrescentado: “**TLS:** os confs Nginx já suportam HTTPS via Certbot, mas a ativação exige seguir o runbook em `infra/DEPLOY.md`; produção hoje continua em HTTP até o certificado ser emitido e `tls_enabled` ser habilitado.” | Impedir que a preparação dos arquivos seja interpretada como HTTPS já ativo e apontar o operador para a ordem segura de ativação. |
| `ARCHITECTURE.md:110-116` | O subtítulo dizia “Topologia (self-hosted, VPS única com Docker)” e o texto de apresentação não distinguia o edge de produção. → “Topologia ativa (self-hosted, VPS única com PM2 + Nginx)”, com Nginx explicitado como reverse proxy ativo, TLS de origem via Certbot/Let's Encrypt **quando ativado**, e Docker/Caddy identificado como variante alternativa/local. | Remover a premissa factual de que Caddy é o edge de produção. |
| `ARCHITECTURE.md:118-132` | O diagrama terminava TLS automaticamente no Caddy, usava Next.js standalone/Gunicorn em containers e dizia que toda a stack subia com `docker compose`. → Diagrama passa a mostrar Internet → Cloudflare opcional → Nginx → Next.js/Gunicorn sob PM2, Redis/PostgreSQL e Celery; o comando Compose/Caddy foi limitado explicitamente à variante alternativa. | Fazer a topologia de §9.2 refletir o deploy PM2 + Nginx e a preparação de TLS no edge correto. |
| `ARCHITECTURE.md:138-142` | A tabela de custo/segurança/confiabilidade/persistência atribuía containers/rede Docker, healthcheck Caddy e `pg_backup.sh` à topologia sem distinguir a variante; Cloudflare/Sentry/UptimeRobot também apareciam sem a ressalva de opcionalidade. → Cloudflare/Sentry/UptimeRobot foram marcados como opcionais; a segurança descreve Nginx como edge e Redis/PostgreSQL internos; a confiabilidade informa health HTTP loopback/HTTPS público; a persistência diferencia `pg_backup_pm2.sh` do backup Docker/Caddy. | Corrigir as afirmações factualmente erradas de §9.3 sem reescrever a seção inteira. |

## Verificações que não exigiram alteração

- `infra/DEPLOY.md` já documenta a seção “Ativando TLS (PM2 + Nginx)”, a ordem Certbot → `nginx -t` → reload → flags, o runbook de renovação e o monitor externo via HTTPS.
- Os callers dos workflows continuam com `tls_enabled: false`, coerente com o bootstrap sem certificado; os arquivos de workflow e a run paralela de ops não foram tocados nesta fase.
- `PROD_DECISOES.md` e `ingestao-service/README.md` já registram a recomendação de manter o microserviço desligado e a decisão humana pendente; não foi necessário duplicar esse conteúdo nos docs de produto.
- `Caddyfile` já contém a nota de drift dizendo que a VPS ativa usa Nginx + PM2 e que o Caddyfile é a variante alternativa/local; por isso não foi editado.

## Fora do escopo desta etapa

- Nenhum arquivo de código-fonte Python/TypeScript, workflow, configuração Nginx, workflow de GitHub Actions, `Caddyfile`, `docker-compose.yml` ou outro arquivo de infraestrutura foi alterado.
- Não foram emitidos certificados, alterados DNS, recarregados serviços nem preenchidos domínios/segredos fictícios: são ações humanas e estão descritas no runbook.
- Não foi feita uma nova validação de runtime na VPS nem uma ativação de HTTPS; as evidências continuam sendo as validações locais registradas em `implementation-history.md` e `code-review-contract.md`.
