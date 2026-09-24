# Relatório de execução — 20260924-1400-tls-ingestao

- **Run:** `20260924-1400-tls-ingestao`
- **Tarefa:** P0-3 — preparar TLS no Nginx (Certbot) e registrar a decisão sobre `ingestao-service/`
- **Resultado:** entregue, com uma nit não bloqueante aceita com risco residual documentado
- **Revisão final:** `approve_with_comments`
- **Commit:** nenhum

## Objetivo

Deixar a topologia de produção **PM2 + Nginx** preparada para TLS com Certbot/Let's Encrypt sem ativar HTTPS prematuramente, preservar a ordem segura de bootstrap/renovação e registrar uma recomendação operacional fundamentada sobre o microserviço `ingestao-service/`, mantendo a decisão final de ativação ou arquivamento com o humano.

A run não emite certificado, não altera DNS, não recarrega uma VPS e não altera código de aplicação. A ativação exige valores reais, Certbot, `nginx -t`, reload, testes e a alteração explícita de `tls_enabled` conforme o runbook.

## Entregas

1. **TLS parametrizado nos três sites Nginx**
   - `infra/nginx/portal-dev.conf`, `infra/nginx/portal-homolog.conf` e `infra/nginx/portal-prod.conf` receberam vhosts HTTP/80 e HTTPS/443.
   - O vhost HTTP redireciona tráfego normal com `301 https://$host$request_uri`, mas preserva `/.well-known/acme-challenge/` sem redirect para o challenge ACME HTTP-01.
   - O vhost HTTPS usa `listen 443 ssl`, restringe protocolos a TLS 1.2/1.3 e referencia `fullchain.pem`/`privkey.pem` do lineage Certbot sob `/etc/letsencrypt/live/<DOMAIN_FRONTEND>/`.
   - Domínios reais não foram inventados: os marcadores `__DOMAIN_FRONTEND__` e `__DOMAIN_FRONTEND_WWW__` aguardam renderização pelo operador.
   - O `/healthz` em HTTP é permitido somente para `127.0.0.1`/`::1`; acesso externo recebe negação, e o probe loopback encaminha `X-Forwarded-Proto: https` para não depender do redirect público.

2. **Ativação segura nos workflows**
   - O workflow reutilizável `.github/workflows/deploy.yml` recebeu a entrada booleana `tls_enabled`, com default seguro `false`.
   - Os callers DEV, HOMOLOG e PROD expõem explicitamente `tls_enabled: false` até a validação humana.
   - Um `.env` novo recebe os três flags de redirect/cookies Secure somente quando `tls_enabled=true`; um `.env` existente é preservado e o deploy falha explicitamente se os flags não coincidirem, sem downgrade silencioso.
   - As origens públicas `NEXT_PUBLIC_*` e o probe de validação acompanham o estado HTTP/HTTPS do edge; com TLS desligado, o probe usa o Gunicorn direto e, com TLS ligado, percorre o vhost HTTPS via `--resolve`.

3. **Runbook “Ativando TLS”**
   - `infra/DEPLOY.md` contém a sequência de valores, DNS, webroot, emissão Certbot, renderização dos marcadores, `nginx -t`, reload, testes, ativação dos flags, redeploy, timer e verificação de renovação.
   - A seção documenta a exceção ACME, o health loopback-only, a ordem segura de ativação e Cloudflare como camada opcional.

4. **Hook de renovação**
   - `infra/certbot/deploy-hook-nginx.sh` foi versionado como executável `0755`.
   - O hook registra o lineage, executa `nginx -t` antes de qualquer reload, falha fechado se a configuração for inválida, tenta `systemctl reload nginx` e possui fallback `nginx -s reload`.
   - O runbook passa `--deploy-hook` ao Certbot ou descreve a alternativa global em `/etc/letsencrypt/renewal-hooks/deploy/`, sem registrar as duas formas simultaneamente.

5. **Decisão sobre `ingestao-service/`**
   - `PROD_DECISOES.md` registra a recomendação de manter `MICROSERVICO_INGESTAO_URL` vazio, não promover o segundo pipeline e não apagar o diretório sem decisão humana.
   - A comparação considera o pipeline Django/Postgres/Celery como fonte de verdade atual, o painel HTML próprio como diferencial do microserviço, a duplicação de pipeline, a suíte fora do CI, o MongoDB exposto e o custo de manutenção.
   - `ingestao-service/README.md` recebeu apenas a nota de status; nenhum código, compose ou teste do diretório foi alterado.

6. **Documentação de produto e histórico**
   - `README.md` agora informa explicitamente que os arquivos suportam HTTPS via Certbot, que a ativação exige `infra/DEPLOY.md` e que a produção permanece em HTTP até a emissão do certificado e a habilitação de `tls_enabled`.
   - `ARCHITECTURE.md` §9 foi corrigido para descrever PM2 + Nginx como topologia ativa, Certbot no Nginx como preparação de TLS e Docker/Caddy como variante alternativa/local.
   - `documentation-update.md` registra as alterações, verificações e itens deliberadamente deixados fora.

## Validações

As validações foram locais, com fixtures e certificados de teste; não substituem uma emissão/renovação real na VPS.

- **Nginx:** os três arquivos foram renderizados substituindo os marcadores por hostnames de teste `.invalid` e usando certificados efêmeros. Com `nginx:alpine` 1.31.6, `nginx -t` retornou `syntax is ok` e `test is successful`, individualmente e na combinação com os includes P1-4.
- **Runtime HTTP/TLS:** o smoke confirmou `301` para tráfego HTTP normal, `200` para o token ACME, `403` para `/healthz` HTTP externo e `200` para o probe loopback; o cenário com upstream também confirmou `200` em HTTPS. Uma fixture sem upstream registrou `502` de aplicação em um teste separado, esperado e sem afetar a validação do handshake TLS.
- **Handshake:** a fixture aceitou handshake TLS 1.2 e TLS 1.3 nos vhosts HTTPS parametrizados.
- **Workflows:** PyYAML e `actionlint` passaram nos quatro workflows de deploy durante a validação desta run; a colisão com a run paralela de ops é tratada no follow-up (f).
- **Runbook/hook:** `bash -n` passou no `infra/certbot/deploy-hook-nginx.sh` e nos 31 blocos Bash do runbook após a remediação. O smoke do hook cobriu sucesso com `systemctl`, recusa de reload quando `nginx -t` falha, fallback bem-sucedido e erro quando ambas as recargas falham.
- **Escopo:** `git diff --check` passou; nenhum fonte Python/TypeScript de aplicação foi alterado por esta run, e o diretório `ingestao-service/` permaneceu intacto.

## Revisão e remediação

O tester inicialmente encontrou um **major** porque a renovação do Certbot emitia/trocava o certificado sem recarregar o Nginx; também registrou um minor para o monitor externo em HTTP e uma nit sobre a política de ciphers. O finding major foi remediado com o `deploy-hook-nginx.sh` fail-closed, validação `nginx -t`, reload gracioso e documentação de registro/verificação da renovação. O monitor externo passou a ser documentado via HTTPS.

A re-revisão independente verificou o hook, o runbook, os três sites sem alteração adicional e o smoke do fallback. Resultado: **`approve_with_comments`**, com 0 blocker, 0 major e 0 minor abertos. Permanece 1 nit aceita: o default de ciphers do Nginx/OpenSSL pode ainda permitir algumas suítes CBC/SHA em TLS 1.2; a justificativa e o risco residual estão registrados em `implementation-history.md`, sem alteração dos três sites.

## Follow-ups

1. **Valores e ativação humana:** preencher os domínios reais de `DOMAIN_FRONTEND` para DEV/HOMOLOG/PROD e o alias `DOMAIN_FRONTEND_WWW` quando aplicável; preencher `CERTBOT_EMAIL`; configurar DNS A/AAAA para a VPS e liberar 80/443; renderizar os marcadores; executar Certbot, `nginx -t`, reload e testes HTTPS. Só depois editar os três flags do `.env` e mudar o caller correspondente para `tls_enabled: true` e fazer o redeploy. `DOMAIN_API` só é necessário na variante Docker/Caddy que realmente separar o host da API.
2. **Monitoramento externo:** migrar o monitor para `https://<DOMAIN>/healthz`; `/healthz` em HTTP é restrito a loopback e deve receber `403` fora da VPS.
3. **Ciphers:** o default do Nginx foi aceito para preservar compatibilidade; há risco residual de CBC/SHA. Uma lista mínima estrita, se exigida, deve ser uma alteração coordenada dos três sites, seguida de nova renderização, `nginx -t` em `nginx:alpine` e validação de runtime antes de reload.
4. **Cloudflare:** permanece opcional e requer conta, nameservers, registros DNS, IP de origem e regras manuais de proxy/cache/WAF. Se ativado, usar `Full (strict)` com o certificado Certbot da origem e medir antes de afirmar ganhos; a run não ativou Cloudflare.
5. **`ingestao-service/`:** a recomendação técnica é mantê-lo desligado; a decisão humana final sobre arquivamento, promoção ou uma experimentação separada ainda é necessária.
6. **Validação cruzada dos workflows:** `tls_enabled` e o gate CI dos workflows também foram alterados pela run paralela `20260924-1200-ops-higiene`. A validação YAML/actionlint e a verificação do grafo de CI/deploy devem ser refeitas quando as duas mudanças forem ativadas juntas; falhas da run paralela não foram atribuídas a esta run.

## Fechamento

A documentação de execução foi consolidada em `documentation-update.md`. Este relatório e a linha append-only em `agentic-framework/state/HISTORY.md` são os artefatos de fechamento; `run-state.json` deve permanecer coerente com o resultado `approve_with_comments`.
