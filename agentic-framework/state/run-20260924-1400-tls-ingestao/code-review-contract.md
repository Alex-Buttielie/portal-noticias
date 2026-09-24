<!--
CONTRACT: code-review-contract
DONO: reviewer
QUANDO: re-revisão da remediação da run 20260924-1400-tls-ingestao
-->

# Code Review Contract — 20260924-1400-tls-ingestao

## Metadados

- **run_id:** `20260924-1400-tls-ingestao`
- **escopo desta re-revisão:** `infra/certbot/deploy-hook-nginx.sh`, a seção “Ativando TLS” de `infra/DEPLOY.md`, a recomendação de ciphers e a não-regressão dos três `infra/nginx/portal-*.conf`.
- **contrato de referência:** `implementation-contract.md` e `task-plan.md` desta run.
- **histórico considerado:** `implementation-history.md`, especialmente a seção “Remediação (iteração 1)”; baseline informado da revisão anterior: 1 major, 1 minor e 1 nit.
- **nota de integridade do artefato:** o `code-review-contract.md` anterior não estava presente no diretório ao iniciar esta re-revisão. O baseline foi reconstituído de forma explícita a partir do pedido, do `implementation-history.md` e do `run-state.json`; não foi substituído silenciosamente por uma avaliação diferente.
- **método:** leitura direta do hook, do runbook, dos três sites e do histórico; `bash -n` nos 31 blocos Bash do runbook e no hook; smoke test isolado do hook com `nginx`/`systemctl` falsos; inspeção de permissões; `git diff --stat -- infra/nginx/`; comparação dos confs atuais com a fixture renderizada antes da remediação; inspeção estática dos comandos e da ordem do runbook.
- **limitação:** não houve emissão real de certificado, timer real, VPS, reload real ou verificação de um certificado real em produção. As afirmações de produção abaixo são limitadas ao comportamento documentado e ao fake test do hook.
- **colisão declarada:** `.github/workflows/*` foi alterado pela run paralela `20260924-1200-ops-higiene`. Esses arquivos foram apenas observados para isolamento e suas possíveis falhas não são atribuídas nem reportadas como finding desta run.

## Veredito anterior

O veredito que originou a remediação foi **`changes_requested`**, com:

1. **major:** renovação Certbot não recarregava o Nginx depois de trocar o certificado;
2. **minor:** monitor externo apontava para `/healthz` em HTTP, que é restrito a loopback;
3. **nit:** não havia decisão documentada sobre a política de ciphers.

A seção abaixo registra a reinspeção independente, não apenas a alegação do remediator.

## Re-revisão iteração 1

### Resultado por finding anterior

| Finding | Resultado | Evidência independente |
|---|---|---|
| **1 — major — renovação TLS sem reload** | **RESOLVIDO** | `infra/certbot/deploy-hook-nginx.sh` existe com modo `0755`; `nginx -t` é executado antes de qualquer reload e, se falha, o script sai com 1 sem chamar `systemctl` nem `nginx -s reload`; há `systemctl reload nginx` e fallback `nginx -s reload`. O fake test confirmou: falha de `nginx -t` → somente `nginx -t` e exit 1; sucesso do systemctl → `-t` + reload e exit 0; falha do systemctl → fallback e exit 0; falha das duas recargas → exit 1. O runbook registra `--deploy-hook`, a alternativa global e a validação de renovação. |
| **2 — minor — monitor HTTP** | **RESOLVIDO** | `infra/DEPLOY.md:571-576` recomenda `https://$DOMAIN_FRONTEND/healthz` para o monitor externo PM2 + Nginx e informa explicitamente que HTTP está liberado somente para loopback e receberia 403 fora da VPS; a variante Docker/Caddy permanece separada em `https://$DOMAIN_API/healthz`. |
| **3 — nit — ciphers** | **ACEITO COM RESSALVA** | Os três sites restringem protocolos a TLS 1.2/1.3 e não definem `ssl_ciphers`; a decisão de manter o default do Nginx/OpenSSL e sua justificativa de compatibilidade estão em `implementation-history.md:270-284`, junto do risco residual de suítes CBC/SHA. A nit é não bloqueante e permanece como follow-up coordenado dos três sites se o requisito de segurança mudar. |

### Verificações positivas da seção “Ativando TLS”

- **Hook fail-closed:** `set -Eeuo pipefail` está ativo; o teste de configuração ocorre nas linhas 25–29, antes das linhas 32–46 de reload. A ausência de `nginx`, a falha de `nginx -t` e a falha das duas formas de recarga retornam erro.
- **Segurança do reload:** não há `eval`, interpolação de comando nem escrita de configuração; `RENEWED_LINEAGE` é usado apenas em log. O hook não substitui o certificado nem reconfigura o vhost: ele valida a configuração existente e só solicita um reload gracioso. Um certificado sintaticamente inválido que faça `nginx -t` falhar não chega ao reload; em um teste adicional no `nginx:alpine`, certificado e private key incompatíveis também foram rejeitados com `key values mismatch`. A validade temporal/hostname do certificado é conferida pelo operador/Certbot e pelo procedimento de comparação documentado.
- **Registro do hook:** `infra/DEPLOY.md:323-347` valida `bash -n`, exige `chmod +x`/`test -x` e passa `--deploy-hook "$DEPLOY_HOOK"` no `certbot certonly`; `:351-365` explica que a opção fica no config de renovação e oferece a alternativa, sem duplicar reload, em `/etc/letsencrypt/renewal-hooks/deploy/`.
- **Renovação verificável:** `infra/DEPLOY.md:448-502` habilita o timer, mostra `certbot renew --dry-run --run-deploy-hooks`, compara `serial`, `notBefore` e `notAfter` do lineage com o certificado servido via `openssl s_client` (local e, opcionalmente, público), e explicita que o dry-run não substitui uma renovação real.
- **Ordem de ativação:** a sequência documentada é webroot/challenge → `certbot` → renderizar e instalar o vhost → `nginx -t` → reload → testar HTTP local/HTTPS → só então editar `.env`, habilitar `tls_enabled` e redeployar (`infra/DEPLOY.md:279-446`). O texto ordena que nenhum reload seja feito quando o teste falhar.
- **Sintaxe:** `bash -n` passou no hook e nos 31 blocos Bash de `infra/DEPLOY.md`; não foi executado nenhum comando de emissão, reload ou alteração na VPS.

### Não-regressão dos confs Nginx

O comando solicitado foi executado literalmente:

```text
infra/nginx/portal-dev.conf     | 203 ++++++++++++++++++++++++++++-----------
infra/nginx/portal-homolog.conf | 203 ++++++++++++++++++++++++++++-----------
infra/nginx/portal-prod.conf   | 204 +++++++++++++++++++++++++++++++++++++++++++-----------
3 files changed, 439 insertions(+), 171 deletions(-)
```

Esse resultado é o diff acumulado da implementação original, não um delta adicional da remediação: os três arquivos têm mtime de `03:03:34`, anterior ao início da remediação (`infra/certbot/deploy-hook-nginx.sh` às `04:17:53` e `implementation-history.md` às `04:23:18`). A comparação independente dos três arquivos atuais, após normalizar os marcadores para `test.invalid`, foi idêntica às fixtures pré-remediação em `/tmp/opencode/tls-nginx-fixture/portal-*-exact.conf` para DEV, HOMOLOG e PROD. Portanto, não foi observado arquivo Nginx alterado na iteração 1; a validação `nginx -t` anterior continua aplicável. O `git diff --stat` sozinho não isola uma remediação não commitada, por isso a comparação explícita foi registrada.

### Findings após a re-revisão

- **Blocker aberto:** 0.
- **Major aberto:** 0.
- **Minor aberto:** 0.
- **Nit:** 1, aceito com risco residual documentado (política de ciphers).
- **Novos findings:** nenhum.

## Novo veredito

**`approve_with_comments`**

O finding major de renovação TLS está **RESOLVIDO** independentemente: existe hook executável, `nginx -t` precede o reload, o hook falha fechado e possui fallback; o runbook documenta registro, dry-run e comparação do certificado servido. O finding minor do monitor também está resolvido pelo uso explícito de HTTPS. Não há blocker, major ou minor aberto; permanece somente a nit não bloqueante sobre a política de ciphers, cuja justificativa e risco residual foram documentados. A run pode seguir para as fases de documentação/fechamento, mantendo o requisito de repetir a validação de workflows fora desta atribuição por causa da colisão declarada.

**Nenhum commit foi criado e nenhum código de aplicação, configuração Nginx ou workflow foi alterado nesta re-revisão.**
