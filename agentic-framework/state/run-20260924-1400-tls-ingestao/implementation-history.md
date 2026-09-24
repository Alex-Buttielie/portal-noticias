# Implementation History — 20260924-1400-tls-ingestao

## Escopo e estado inicial

- O pedido foi conferido contra `ANALISE_CUSTO_PERFORMANCE.md` §6/§7,
  especialmente E1/P0-3 e a decisão pendente sobre `ingestao-service/`.
- A topologia considerada canônica é PM2 + Nginx, com Django/Postgres,
  frontend Next.js e API acessível pelo mesmo host público e pelo caminho
  `/api/`. `Caddyfile` e `.env.production.example` foram lidos para
  identificar `DOMAIN_API`/`DOMAIN_FRONTEND` e a topologia Docker alternativa.
- A árvore de trabalho já continha alterações não commitadas de execuções
  anteriores. Elas não foram revertidas nem sobrescritas. Esta run alterou
  somente os arquivos de configuração/documentação listados abaixo e criou
  seus próprios artefatos; não fez commit.
- Nenhum arquivo Python/TypeScript de aplicação ou arquivo sob
  `ingestao-service/` foi editado. O diretório do microserviço não foi
  apagado.

## Decisões

### TLS e autoridade certificadora

1. **Certbot/Let's Encrypt foi escolhido; Cloudflare Origin CA não foi
   escolhido.** Certbot já é a ferramenta convencional do host
   Debian/Ubuntu, renova com timer do systemd e continua válido tanto sem
   Cloudflare quanto com a Cloudflare à frente. O runbook usa
   `certonly --webroot` e aponta o Nginx para
   `/etc/letsencrypt/live/<dominio-primario>/fullchain.pem` e `privkey.pem`.
2. **Nenhum domínio real foi inventado.** Cada site usa os marcadores
   explícitos `__DOMAIN_FRONTEND__` e, em PROD,
   `__DOMAIN_FRONTEND_WWW__`. O operador deve renderizar esses valores
   depois que o DNS existir. Na topologia PM2 ativa `DOMAIN_API` não é um
   segundo vhost Nginx: frontend e API compartilham o host e as requisições
   de API usam `/api/`. `DOMAIN_API` fica reservado à variante opcional
   Docker/Caddy.
3. **HTTP e HTTPS são blocos separados.** Um redirect no nível do servidor
   foi evitado porque também capturaria o challenge ACME. O bloco HTTP tem
   `location ^~ /.well-known/acme-challenge/`, uma exceção de `/healthz`
   apenas para loopback e 301 para tráfego normal. O bloco HTTPS carrega as
   locations da aplicação e as diretivas de certificado.
4. **O health interno é fail-safe.** A location HTTP envia
   `X-Forwarded-Proto: https` ao Django, portanto
   `SECURE_SSL_REDIRECT=true` não transforma o probe em redirect externo.
   A validação ativa do workflow percorre o vhost HTTPS real com
   `--resolve`; a validação de bootstrap usa o Gunicorn direto em HTTP. O
   runbook também testa a exceção HTTP de loopback. Saúde HTTP pública é
   negada; monitoramento normal deve usar HTTPS.
5. **A ordem segura de ativação é explícita.** O repositório não emite
   certificado. O runbook primeiro faz o vhost HTTP ativo servir o webroot
   ACME, emite o certificado, renderiza o conf TLS, executa `nginx -t`,
   recarrega e testa HTTPS; só então edita o `.env` real e muda a entrada do
   caller para `tls_enabled: true` antes do redeploy. Se HTTPS falhar, o
   operador deve manter os flags false e restaurar o vhost HTTP anterior,
   sem ativar o proxy laranja durante o rollback.
6. **HSTS não é duplicado no edge.** Django já controla HSTS com
   `DEBUG=False`; o comentário Nginx existente foi atualizado para exigir
   uma decisão explícita depois de conferir `includeSubDomains`.

### Workflow de deploy e flags de ambiente

- `deploy.yml` agora aceita o booleano tipado `tls_enabled`, com default
  seguro `false` para um host que ainda não tem certificado. Quando true, um
  `.env` novo recebe:
  `DJANGO_SECURE_SSL_REDIRECT=true`,
  `DJANGO_SESSION_COOKIE_SECURE=true` e
  `DJANGO_CSRF_COOKIE_SECURE=true`.
- Um `.env` existente nunca é sobrescrito. O workflow compara os três valores
  com a entrada e falha antes do build/PM2 se divergirem, evitando downgrade
  silencioso ou redirect ativado sem o estado correspondente do edge.
- A origem pública usada no build de `NEXT_PUBLIC_API_BASE_URL` e
  `NEXT_PUBLIC_SITE_URL` acompanha a entrada: `http://` enquanto TLS está
  desligado e `https://` quando está explicitamente ligado. Isso evita um
  bundle HTTPS quebrado durante o bootstrap HTTP.
- Os callers DEV, HOMOLOG e PROD expõem `tls_enabled: false` até o runbook
  human ser concluído. Alterar esses valores para true é uma ação humana de
  release, não um efeito colateral automático de um deploy de código.
- `.env.production.example` mantém defaults seguros porque a variante
  Docker/Caddy termina TLS; o comentário alerta que PM2/Nginx deve manter
  false até Certbot e o reload Nginx serem verificados.

### Cloudflare

- Cloudflare permanece opcional e exige conta, nameservers, registros DNS e
  ativação explícita do usuário. A documentação descreve possíveis ganhos
  de CDN/WAF/DDoS/Brotli como hipóteses condicionais, não resultados
  medidos, e alerta contra cache de respostas personalizadas/autenticadas.
- `Full (strict)` é documentado como o modo compatível com um certificado
  Certbot válido na origem. Cloudflare Origin CA foi explicitamente rejeitado
  para esta run.

### Decisão sobre `ingestao-service/`

- Recomendação: manter `MICROSERVICO_INGESTAO_URL` vazio, não promover esse
  segundo pipeline para produção agora e não apagar o diretório sem decisão
  humana.
- Evidência lida no código: Django já possui o pipeline Celery/Postgres em
  produção com validadores HTTP condicionais, idempotência por URL,
  deduplicação por janela recente, persistência em lote, snapshot/cache da
  configuração, curadoria por item e salvaguardas de direitos autorais, com
  cobertura no CI. O serviço oferece uma API FastAPI independente, token,
  Swagger, CRUD/sincronização de fontes e painel HTML próprio em `/painel`,
  mas duplica LLM/batch/dedup/curadoria e não compartilha as otimizações
  operacionais do Django. O alias raiz `/painel` é servido sem
  autenticação; somente `/api/v1/painel` exige token, portanto publicar o
  serviço como está adicionaria exposição de dados operacionais.
- A árvore de testes do serviço contém 43 funções `test_*` (18 de API, 23 de
  pipeline e 2 smoke), enquanto o workflow CI do repositório não executa esse
  diretório. O compose publica `27017:27017`, e o default documentado de
  preço LLM continua desatualizado. Esses fatos são custos de manutenção e
  segurança, não prova de que o serviço nunca poderá ter utilidade.
- Se o painel HTML for desejado, a recomendação é levar essa capacidade para
  o admin Django existente ou abrir uma experimentação separada, com CI,
  bind privado do Mongo, plano de migração/posse de dados, benchmark de
  custo/latência e uma decisão explícita sobre a fonte da verdade.

## Arquivos alterados

### Configuração Nginx e deploy

- `infra/nginx/portal-dev.conf`
- `infra/nginx/portal-homolog.conf`
- `infra/nginx/portal-prod.conf`
  - vhosts HTTP/HTTPS parametrizados;
  - caminhos Certbot e ajustes de protocolo/sessão TLS;
  - exceção ACME, exceção de health em loopback e redirect 301;
  - preservação de cache/rate/estático/mídia P1-4 e da proteção fail-closed
    da mídia.
- `.github/workflows/deploy.yml`
  - entrada `tls_enabled` e geração/validação segura do ambiente;
  - escolha de origem HTTP/HTTPS do build;
  - probe de health por Gunicorn no bootstrap e pelo vhost HTTPS na ativação.
- `.github/workflows/deploy-dev.yml`
- `.github/workflows/deploy-homolog.yml`
- `.github/workflows/deploy-prod.yml`
  - gate explícito `tls_enabled: false` e comentário de ativação.
- `.env.production.example`
  - defaults explícitos de cookie Secure/redirect para a variante Caddy.
- `infra/certbot/deploy-hook-nginx.sh`
  - hook executável de recarga fail-closed do Nginx após `nginx -t`.

### Documentação e registros de decisão

- `infra/DEPLOY.md`
  - seção Cloudflare opcional reescrita sem promessas não medidas;
  - nova seção “Ativando TLS” com bootstrap Certbot, renovação e ordem segura.
- `PROD_DECISOES.md`
  - decisão Certbot e status de ativação;
  - análise/recomendação do `ingestao-service/`.
- `ingestao-service/README.md`
  - apenas nota de status; nenhum código ou compose alterado.
- `agentic-framework/state/run-20260924-1400-tls-ingestao/task-plan.md`
- `agentic-framework/state/run-20260924-1400-tls-ingestao/implementation-contract.md`
- `agentic-framework/state/run-20260924-1400-tls-ingestao/run-state.json`
- este arquivo de histórico.

## Evidências de validação

- **Estrutura estática do Nginx:** uma checagem Python de chaves/aspas foi
  executada nos três sites e nos três snippets de location existentes. Todas
  as chaves ficaram balanceadas, todas as strings fechadas e cada site
  contém um `listen 443 ssl`, uma location ACME e um redirect 301 HTTPS.
- **Parser Nginx:** o host desta execução não tem binário `nginx`
  (`command -v nginx` vazio). Os arquivos-fonte contêm marcadores de domínio
  intencionalmente, portanto não podem ser testados sem renderização e
  certificado. Cada site foi renderizado em diretório temporário usando
  hostnames de teste `.invalid` e certificados efêmeros autoservidos; os
  arquivos renderizados foram combinados com `http-cache.conf` e os snippets
  em `nginx:alpine` 1.31.6. `nginx -t` retornou `syntax is ok` e `test is
  successful`. Nenhum hostname/certificado de teste foi escrito no repositório.
  Um smoke test de runtime com a mesma fixture confirmou `301` para HTTP
  normal, `200` para o token ACME, `403` para health HTTP externo e um
  handshake TLS válido (o `502` HTTPS foi esperado porque não havia
  upstream de aplicação em execução).
- **YAML dos workflows:** PyYAML leu com sucesso
  `.github/workflows/deploy.yml` e os três callers. Os scripts shell de
  deploy e validate passaram `bash -n` após substituir expressões GitHub por
  tokens de teste. Uma simulação pequena da matriz gerou all-false/HTTP para
  `tls_enabled=false` e all-true/HTTPS para `tls_enabled=true`.
- **Lint GitHub Actions:** `rhysd/actionlint:latest` retornou exit 0 para os
  quatro workflows de deploy.
- **Inventário de testes do microserviço:** a inspeção AST encontrou 43
  funções `test_*` (2 smoke + 18 API + 23 pipeline). O `pytest` não está
  instalado neste ambiente de execução; portanto nenhuma suíte foi declarada
  como executada. O serviço não foi alterado.
- **Whitespace:** `git diff --check` passou para todos os arquivos desta
  run.
- **Escopo:** nenhum commit foi feito. Alterações amplas preexistentes na
  worktree foram preservadas; as edições desta run estão limitadas aos
  arquivos listados e aos artefatos da run.

## Valores que o humano ainda precisa preencher na VPS

O operador deve fornecer/substituir estes valores; nenhum marcador é um valor
de runtime válido:

1. `DOMAIN_FRONTEND` de DEV, HOMOLOG e PROD (hostname DNS real, sem prefixo
   `https://`), usado para renderizar `__DOMAIN_FRONTEND__` e como diretório
   do lineage Certbot.
2. `DOMAIN_FRONTEND_WWW` de PROD se o alias `www` existente for mantido;
   use valor vazio somente se o alias for removido de forma intencional e
   mantenha a lista SAN do certificado e `allowed_hosts_extra` coerentes.
3. `DOMAIN_API` somente se a divisão opcional Docker/Caddy realmente for
   usada; não é exigido pela configuração PM2 de host único.
4. `CERTBOT_EMAIL`, além dos registros DNS A/AAAA dos nomes selecionados
   apontando para a VPS e do acesso de firewall TCP 80/443.
5. Os secrets existentes por ambiente `VPS_HOST`, `VPS_USER`,
   `VPS_PASSWORD` e `VPS_PORT` no GitHub Environment, além da senha de banco
   já exigida pelo deploy PM2.
6. Depois das verificações TLS, mudar o caller selecionado de
   `tls_enabled: false` para `true` e definir os três flags Django como
   `true` em `/home/apps/portal-<env>/backend/.env`; então fazer o redeploy
   documentado.
7. Se Cloudflare for desejado, fornecer separadamente conta/nameservers,
   IP/registros DNS de origem, decisão de proxy e regras de cache/WAF. Esses
   itens são opcionais e não devem ser preenchidos com valores inventados.

## Follow-ups para as próximas fases

- O tester deve repetir/confirmar as validações estáticas e renderizadas e
  inspecionar a matriz de flags do workflow.
- O reviewer deve revisar a fronteira de segurança (bootstrap TLS, ACME,
  health de loopback, renderização de domínio e ausência de downgrade
  silencioso do `.env`).
- O operador humano deve executar DNS/Certbot/Nginx/reload/flags/redeploy na
  VPS; validação do repositório não ativa produção.
- O humano deve decidir se arquivará futuramente o `ingestao-service/`. Esta
  run deixa o diretório intacto e recomenda mantê-lo desligado.

## Remediação (iteração 1) — 2026-09-24 — remediator

**Escopo:** corrigi o finding major de renovação TLS e o finding minor do
monitoramento. Respeitei a colisão declarada: não alterei
`.github/workflows/`, `infra/backup/`, `docker-compose.yml`, backend ou
frontend; não houve commit.

### Finding 1 — major — renovação TLS sem reload — resolvido

- Criei o hook versionado `infra/certbot/deploy-hook-nginx.sh` com modo
  `0755`. Ele registra o lineage em stderr/journal, executa `nginx -t` antes de
  qualquer reload, sai com erro sem recarregar quando o teste falha, tenta
  `systemctl reload nginx` e usa `nginx -s reload` como fallback. O retorno
  continua não zero se as duas formas de recarga falharem.
- `infra/DEPLOY.md` agora valida o hook com `bash -n`, documenta
  `chmod +x`, passa `--deploy-hook "$DEPLOY_HOOK"` no `certbot certonly` e
  explica que o comando grava o hook no config de renovação. Também explicita
  a alternativa, sem dupla execução, em
  `/etc/letsencrypt/renewal-hooks/deploy/`.
- A validação documentada agora usa
  `certbot renew --dry-run --run-deploy-hooks` e mostra como comparar serial,
  `notBefore`/`notAfter` do lineage com o certificado apresentado pelo Nginx
  via `openssl s_client`; compara a origem local quando há Cloudflare no proxy.
  O dry-run é explicitamente tratado como prova de challenge/hook, não como
  uma rotação real do certificado de produção.
- Evidência local: `bash -n infra/certbot/deploy-hook-nginx.sh` passou; os 31
  blocos Bash de `infra/DEPLOY.md` também passaram em `bash -n`; um smoke test
  com executáveis fake cobriu sucesso via `systemctl`, recusa de reload quando
  `nginx -t` falhou, fallback bem-sucedido e erro quando o fallback também
  falhou. Não houve emissão, `nginx -t` ou reload em uma VPS real.

### Finding 2 — minor — monitor externo HTTP receberia 403 — resolvido

- O runbook passou a recomendar explicitamente
  `https://$DOMAIN_FRONTEND/healthz` (isto é, `https://$DOMAIN/healthz`) para
  o monitor externo na topologia PM2 + Nginx. Ele alerta que HTTP é apenas
  loopback e deve retornar `403` fora da VPS; a URL `https://$DOMAIN_API/healthz`
  fica reservada à variante Docker/Caddy com host de API separado.
- A configuração Nginx não foi tocada, preservando a decisão de segurança do
  `/healthz` HTTP.

### Finding 3 — nit — política de ciphers — aceito com justificativa

- Mantive o default do Nginx/OpenSSL, sem alterar os três
  `infra/nginx/portal-*.conf`: eles já restringem os protocolos a TLS 1.2/1.3,
  e o default do pacote Debian/Ubuntu é a política mais compatível com clientes
  diretos e com Cloudflare opcional. Fixar uma lista de nomes OpenSSL nos
  sites pode falhar em combinações diferentes de Nginx/OpenSSL e reduzir a
  interoperabilidade sem uma matriz de clientes; a mudança de hook e a correção
  do monitor não exigem uma segunda política de cifra.
- A observação do tester é residual: o default pode ainda aceitar algumas
  suítes CBC/SHA em TLS 1.2. Se o requisito de segurança mudar para uma lista
  mínima estrita, deve ser uma alteração coordenada dos três sites, com
  renderização dos marcadores, certificado self-signed e novo `nginx -t` em
  `nginx:alpine` antes de qualquer reload. Como esta iteração não alterou os
  confs, não houve nova execução de `nginx -t` para esta decisão.

**Estado da finding:** 1 major, 1 minor e 1 nit tratados; a nit foi registrada
como decisão aceita com risco residual documentado. A run continua em revisão,
aguardando a re-revisão do orquestrador.
