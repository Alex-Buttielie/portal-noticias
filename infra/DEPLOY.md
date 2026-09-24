# Deploy na VPS — passo a passo

> **Caminho ativo: PM2 + Nginx** (ver `CI-CD.md`) — mesma infra do deploy
> anterior: `/home/apps/portal-{dev,homolog,prod}`, portas 310x/510x,
> secrets `VPS_HOST/USER/PASSWORD/PORT`. Este arquivo documenta a variante
> Docker + Caddy, mantida como alternativa local/opcional (não usada pela
> esteira). O deploy de produção sai da tag `v*` via
> `.github/workflows/deploy-prod.yml`.
>
> **Nota de drift Docker vs PM2:** VPS roda PM2 (não Docker Compose);
> healthcheck Docker é só para localhost (`docker-compose.yml` / `docker-compose.localhost.yml`).
> Não usar `docker compose --env-file .env.production` na VPS.
>
> Guia de provisionamento da VPS HostGator (root/SSH) para a nova arquitetura
> de infra (`docker-compose.yml` + `Caddyfile` na raiz do projeto). Faça uma
> vez por VPS; deploys seguintes usam só a seção "Deploy de uma nova versão".

## Atenção: limpeza manual de uma instância legada de ingestão

A remoção do `ingestao-service/` (FastAPI/Mongo) do código versionado não
apaga dados externos, não encerra processos que já estejam em execução e não
remove volumes de uma VPS. O operador deve tratar cada ambiente separadamente:

- No arquivo de ambiente da VPS, procure e remova
  `MICROSERVICO_INGESTAO_URL` e `INGESTAO_API_TOKEN` se ainda existirem. As
  flags antigas não são mais lidas pelo Django e, portanto, são inertes, mas
  não devem continuar em uma configuração operacional sem revisão.
- Inspecione os serviços gerenciados (PM2, systemd ou Docker) e os volumes
  associados a uma instância antiga de ingestão/Mongo. A remoção do checkout
  não aparece nesses inventários.
- Só desligue o processo e remova o container/volume depois de confirmar um
  backup, a política de retenção e a necessidade de preservar os dados. Não
  remova um volume que ainda seja necessário para recuperação ou auditoria.

Esta é uma etapa humana posterior ao deploy; a remoção do código no repositório
não deve ser interpretada como prova de que a VPS foi limpa.

## 0. Operação da topologia ATIVA — PostgreSQL do host + PM2 + Nginx

Esta seção prevalece sobre qualquer comando Docker/Caddy das seções seguintes.
Os paths foram confirmados no deploy e no Django: o arquivo de ambiente é
`/home/apps/portal-prod/backend/.env` e `MEDIA_ROOT` é
`/home/apps/portal-prod/backend/media`. Se o layout mudar, passe
`BACKUP_ENV_FILE`/`BACKUP_MEDIA_DIR` explicitamente; não adivinhe um path.

### Dependências do host

```bash
sudo apt update
sudo apt install -y postgresql-client tar util-linux
# Só é obrigatório quando BACKUP_S3_BUCKET estiver configurado:
sudo apt install -y awscli

chmod 0755 /home/apps/portal-prod/infra/backup/pg_backup_pm2.sh
chmod 0600 /home/apps/portal-prod/backend/.env
test -r /home/apps/portal-prod/backend/.env
test -d /home/apps/portal-prod/backend/media
```

`util-linux` fornece o `flock`, que impede dois backups simultâneos. A validação
padrão do dump também exige `psql`, `createdb` e `dropdb` (incluídos no
`postgresql-client`) e permissão `CREATEDB` no cluster; sem essa permissão o
script falha fechado e não publica o arquivo. O script não usa `docker compose`:
`pg_backup.sh` continua sendo exclusivamente para a variante Docker/Caddy.

### Backup diário PM2: configuração, execução e aviso de risco

Cadastre as variáveis de object storage no **env real da aplicação**, sem
commitar valores:

```dotenv
BACKUP_S3_ENDPOINT=https://<endpoint-r2-ou-b2>
BACKUP_S3_BUCKET=<bucket>
BACKUP_S3_ACCESS_KEY=<chave>
BACKUP_S3_SECRET_KEY=<segredo>
```

`BACKUP_S3_ENDPOINT` pode ficar vazio para AWS S3. Se access/secret forem
omitidos, o script usa a credencial/IAM já disponível no host. As chaves acima
são compatíveis com Backblaze B2 e Cloudflare R2. Configure no bucket uma
lifecycle rule (por exemplo, retenção de 90 dias); o script local não substitui
essa política. Mantenha o bucket privado e conceda à chave somente as permissões
necessárias para escrever e verificar/ler os objetos no prefixo de backup
(`s3:PutObject` e `s3:GetObject`; o `head-object` precisa da leitura). Evite
conceder delete ou listagem desnecessárias.

Execute uma vez manualmente e confira o exit code antes de agendar:

```bash
cd /home/apps/portal-prod
bash -n infra/backup/pg_backup_pm2.sh
BACKUP_ENV_FILE=/home/apps/portal-prod/backend/.env \
  infra/backup/pg_backup_pm2.sh
ls -lh infra/backup/pm2-*.dump infra/backup/pm2-*.tar.gz
```

O script usa `pg_dump -Fc`, faz a checagem de TOC com `pg_restore --list` e,
por padrão (`BACKUP_VALIDATE_RESTORE=1`), restaura o archive inteiro em um
banco PostgreSQL descartável, compara as contagens de tabelas/linhas e só então
publica o dump. Também valida o tar da mídia. O escape explícito
`BACKUP_VALIDATE_RESTORE=0` ainda faz a leitura integral do archive, mas
desliga o restore/contagem; use-o somente em emergência e registre o risco no
log. A retenção de 7 dias é aplicada **somente** aos nomes `pm2-db-*` e
`pm2-media-*`, depois que os dois uploads e as verificações remotas por
`head-object` Tennham sucesso; backups Docker não são apagados. Se o bucket não
for definido, a execução local pode terminar com sucesso, mas mantém todos os
artefatos locais e suspende a retenção: a cópia fica somente na VPS, sem
proteção contra perda do host. Configuração S3 parcial ou upload/verificação
com erro faz o script falhar com código diferente de zero, preservando os
arquivos locais válidos.

Instale o crontab de forma idempotente (remove apenas linhas antigas deste
script e mantém as demais):

```bash
(
  crontab -l 2>/dev/null | grep -v 'pg_backup_pm2[.]sh' || true
  printf '%s\n' '0 3 * * * BACKUP_ENV_FILE=/home/apps/portal-prod/backend/.env /home/apps/portal-prod/infra/backup/pg_backup_pm2.sh >> /var/log/pg_backup.log 2>&1'
) | crontab -

sudo touch /var/log/pg_backup.log
sudo chown "$(id -un)":"$(id -gn)" /var/log/pg_backup.log
sudo chmod 0640 /var/log/pg_backup.log
crontab -l
```

Execute o backup e instale essa linha no mesmo usuário efetivo que mantém o
processo PM2, o checkout, `backend/.env` e `backend/media`; não use root apenas
porque a instalação do sistema foi feita com `sudo`. O script registra owner e
permissões e falha de verdade quando não consegue ler a mídia ou escrever no
diretório de backups.

`DJANGO_DB_PASSWORD=troque-aqui` faz o próprio script falhar com credencial
incompleta. Para uma instalação que use somente variáveis padrão do libpq,
exporte `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGHOST` e `PGPORT` no processo
do cron; o script também aceita o fallback `/home/apps/portal-prod/.env` por
compatibilidade.

### Rotação do log de backup

O redirecionamento do cron não é rotação. Instale o snippet versionado e
valide sem alterar arquivos:

```bash
cd /home/apps/portal-prod
sudo install -m 0644 infra/logrotate/pg-backup.conf \
  /etc/logrotate.d/portal-backup
sudo logrotate -d /etc/logrotate.d/portal-backup
```

O arquivo mantém 14 rotações, comprime as antigas e usa `copytruncate` para
preservar owner/mode de `/var/log/pg_backup.log`. Emita também
`maxsize 20M` para que um backlog não espere o ciclo diário. A variante Docker
tem limite próprio por container em `docker-compose.yml`: `json-file`,
`max-size=10m` e `max-file=3`.

### Tuning do PostgreSQL para a VPS de 4 GB (não aplicado por este repositório)

O arquivo `infra/postgres-tuning.conf` contém somente valores conservadores:
`shared_buffers=1GB`, `effective_cache_size=3GB`, `work_mem=8MB` e
`maintenance_work_mem=256MB`. Instale como include do cluster **em janela
controlada**; `shared_buffers` só entra em vigor após restart.

```bash
cd /home/apps/portal-prod
PG_CONFIG="$(sudo -u postgres psql -Atqc 'SHOW config_file')"
PG_CONF_DIR="$(dirname "$PG_CONFIG")"
PG_TUNING_FILE="$PG_CONF_DIR/conf.d/portal-tuning.conf"

# Registra os valores atuais para comparação antes de alterar.
sudo -u postgres psql -x \
  -c 'SHOW shared_buffers' \
  -c 'SHOW effective_cache_size' \
  -c 'SHOW work_mem' \
  -c 'SHOW maintenance_work_mem'

sudo install -d -m 0755 "$PG_CONF_DIR/conf.d"
sudo install -m 0644 infra/postgres-tuning.conf "$PG_TUNING_FILE"
PG_INCLUDE="include_if_exists = '$PG_TUNING_FILE'"
sudo grep -Fq "$PG_TUNING_FILE" "$PG_CONFIG" || \
  printf '\n%s\n' "$PG_INCLUDE" | sudo tee -a "$PG_CONFIG"
sudo -u postgres psql -Atqc 'SELECT pg_reload_conf()'
sudo systemctl restart postgresql

# Confirme que o cluster está ativo, aceita o include e mostra os 4 valores.
sudo -u postgres pg_isready
sudo -u postgres psql -x \
  -c 'SHOW shared_buffers' \
  -c 'SHOW effective_cache_size' \
  -c 'SHOW work_mem' \
  -c 'SHOW maintenance_work_mem'
```

Se houver regressão, remova a linha `include_if_exists` de `$PG_CONFIG` (ou o
arquivo em `conf.d`) e reinicie o PostgreSQL. Monitore RAM livre e queries que
usem sort/hash; `effective_cache_size` é apenas uma estimativa do planner, mas
`shared_buffers` é memória real. Esta run **não executa** os comandos acima.

## 1. Hardening inicial do sistema operacional

Faça isso **antes** de instalar qualquer coisa da aplicação — é a base de
segurança de toda a arquitetura.

```bash
apt update && apt upgrade -y

# Usuário não-root para operar o servidor (nunca trabalhar como root no dia
# a dia — reduz o dano de qualquer comando errado ou chave SSH vazada).
adduser deploy
usermod -aG sudo deploy

# Firewall: só SSH, HTTP e HTTPS ficam acessíveis. Tudo que os containers
# expõem entre si (Postgres, Redis, Django direto) fica de fora — só o
# Caddy publica porta no host (ver docker-compose.yml).
apt install -y ufw
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable

# fail2ban: bloqueia IPs após tentativas repetidas de força bruta no SSH.
apt install -y fail2ban
systemctl enable --now fail2ban

# Atualizações de segurança automáticas do SO (não da aplicação).
apt install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
```

Depois disso, desabilite login SSH por senha (só chave pública) em
`/etc/ssh/sshd_config` (`PasswordAuthentication no`, `PermitRootLogin no`) e
reinicie o `sshd`.

## 2. Docker

```bash
curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy
# aws CLI — usado por infra/backup/pg_backup.sh (Docker) e
# infra/backup/pg_backup_pm2.sh (PM2) para enviar backups ao storage remoto
# (Backblaze B2 / Cloudflare R2, compatíveis com API S3).
apt install -y awscli
```

## 3. Cloudflare (opcional — CDN + WAF + DDoS, camada gratuita)

Esta etapa é **opcional** e exige uma conta do usuário. A topologia ativa
(PM2 + Nginx) usa **Certbot/Let's Encrypt na origem**, não Origin CA da
Cloudflare. O ganho esperado é descrito como possibilidade, não como
resultado medido: CDN pode reduzir requisições à VPS e latência de conteúdo
cacheável; WAF/DDoS pode filtrar ataques antes da origem; Brotli pode
economizar banda. O efeito real depende de tráfego, taxa de cache e
configuração, portanto não se promete economia ou percentual sem medir.

1. Aponte o domínio para os nameservers da Cloudflare.
2. Crie registros `A` para `DOMAIN_FRONTEND` e, na variante que realmente
   separa API, `DOMAIN_API`, apontando para o IP da VPS. Só ative o proxy
   laranja depois que o TLS direto da VPS estiver validado.
3. Em **SSL/TLS**, escolha **Full (strict)**: a Cloudflare validará o
   certificado Certbot da origem. Não selecione Origin CA para esta run.
4. Em **Speed → Optimization**, avalie Brotli e Auto Minify; meça antes/depois
   em rotas representativas.
5. (Opcional) crie regras de cache somente para respostas públicas e
   explicitamente cacheáveis (por exemplo, a allowlist de feed/radar). Nunca
   faça cache de `/api/auth/`, painel, filas, webhooks, respostas personalizadas
   ou qualquer rota que dependa de cookie/Authorization. A regra da aplicação
   continua sendo a fonte de verdade.
6. Depois de ativar, compare `curl -sI https://<host>/...`, os headers
   `CF-Cache-Status`/`CF-Ray` quando aplicável e os logs da VPS. Se o tráfego
   ainda não justificar, mantenha o TLS direto e deixe a Cloudflare desligada.

## 3-Z. ESTADO ATUAL NA VPS: variante HTTP-only (sem DNS, sem certificado)

> **Situação real em 2026-09-24.** `portal-noticias.com.br` **não tem registro
> A nem NS** (confirmado de dentro da VPS consultando o 8.8.8.8 — o resolver
> funciona, o domínio do projeto não resolve). Com isso:
>
> - o Let's Encrypt **não consegue** emitir certificado: o challenge HTTP-01
>   exige que o domínio aponte para a VPS;
> - os confs de site deste repositório têm `listen 443 ssl` com
>   `ssl_certificate` **incondicional**, então `nginx -t` falha sem certificado
>   (o fail-safe do projeto mantém o ambiente antigo, mas o P1-4 não ativa).
>
> **O que foi feito** para ativar o P1-4 mesmo assim, sem TLS:
>
> 1. `http-cache.conf` e os três `portal-location-*.conf` instalados em
>    `/etc/nginx/`, com o `include /etc/nginx/http-cache.conf` dentro do
>    `http {}` de `/etc/nginx/nginx.conf` (antes de `sites-enabled/*`);
> 2. `/var/cache/nginx/feed` criado e pertencente a `www-data`;
> 3. **variantes HTTP-only** dos três sites em `/etc/nginx/sites-available/`.
>
> **O que continua valendo na variante:** cache de borda, rate limit, gzip,
> `keepalive`, `/static/` e `/media/public/` servidos direto. O único item
> ausente é o TLS. Verificado no PROD: `X-Cache-Status: HIT` no feed, `MISS`→`HIT`
> no radar, `BYPASS` com cookie de sessão, 429 após o burst de 20/min,
> `/media/credenciamento/*` em 404 e `/static/*` em 200 com `immutable`.

### ⚠️ Drift: os arquivos na VPS NÃO são os deste repositório

`/etc/nginx/sites-available/portal-{dev,homolog,prod}` são **variantes
geradas**, não os arquivos versionados. Cada uma tem no cabeçalho um aviso.
A transformação aplicada ao bloco `server` da 443 (o que serve a aplicação) foi
apenas esta — nada mais foi alterado:

- `listen 443 ssl` → `listen 80`
- remoção de `ssl_certificate`, `ssl_certificate_key`, `ssl_protocols`,
  `ssl_session_cache` e `ssl_session_timeout`
- descarte do bloco da porta 80 original (ACME + `/healthz` + `return 301
  https://…`), porque o redirect deixaria o site inacessível sem a 443

O bloco `upstream` e todos os `location` (inclusive os `include` de cache e
rate) são os mesmos deste repositório.

### Quando o DNS for configurado — volte ao conf do repositório

**Não edite a variante.** Siga a seção 3A a partir do 3A.1, que já tem o
procedimento completo. Em resumo:

1. configure o registro A apontando para o IP da VPS e espere propagar;
2. `dig +short @8.8.8.8 <dominio> A` tem que devolver o IP da VPS;
3. siga **3A.2 → 3A.3 → 3A.4 → 3A.5** (webroot, `certonly`, conf TLS, flags);
4. copie o conf **do repositório** (com TLS) por cima da variante, com os
   marcadores `__DOMAIN_FRONTEND__` substituídos pelo hostname real;
5. `nginx -t && systemctl reload nginx` e confirme `listen 443` respondendo.

Backup do estado anterior a esta instalação:
`/root/nginx-backup-20260924-165515/` (`nginx.conf`, `sites-available`,
`sites-enabled`).

## 3A. Ativando TLS (PM2 + Nginx)

Esta seção é o caminho da topologia ativa. **A emissão e o reload são ações
humanas na VPS**; o repositório apenas deixa a configuração preparada. A
abordagem escolhida é **Certbot/Let's Encrypt com `certonly --webroot`**. Não
usamos Cloudflare Origin CA: o mesmo certificado de origem funciona com ou
sem Cloudflare e não exige escolher um provedor de CA antes de o domínio
existir.

### 3A.1. Valores que devem ser preenchidos

Defina os valores no shell da VPS antes de copiar qualquer arquivo. Os
marcadores entre `< >` são propositalmente substituíveis; não são domínio
válido:

```bash
# Execute uma vez por ambiente; troque os valores entre < > antes de usar.
export ENV_NAME=prod                 # dev | homolog | prod
export DOMAIN_FRONTEND='<DOMAIN_FRONTEND_DO_AMBIENTE>'
export DOMAIN_FRONTEND_WWW='<DOMAIN_FRONTEND_WWW_DO_AMBIENTE>' # vazio se não houver alias
export CERTBOT_EMAIL='<SEU_EMAIL_DE_CERTBOT>'

# Na topologia PM2, frontend e API usam o mesmo host e /api/.
# DOMAIN_API continua sendo usada apenas pela variante Docker/Caddy e não
# deve ser confundida com o segundo hostname do Nginx.
```

Para PROD, `DOMAIN_FRONTEND_WWW` deve ser o alias real (por exemplo, o `www`
que o time decidir manter) e o certificado deve incluir os dois nomes. Para
DEV/HOMOLOG sem alias, use uma string vazia. O nome do lineage do Certbot
será o primeiro domínio; por isso o caminho do certificado no conf deve
começar por `DOMAIN_FRONTEND`. Confira também o input `host` e
`allowed_hosts_extra` do caller do ambiente: eles devem refletir exatamente
esses mesmos hostnames, pois alimentam `DJANGO_ALLOWED_HOSTS` e o build.

Confira DNS antes de pedir o certificado: o hostname deve resolver para a
VPS e as portas TCP 80/443 devem estar liberadas no firewall.

```bash
getent ahosts "$DOMAIN_FRONTEND"
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### 3A.2. Preparar o HTTP-01 antes de existir o certificado

O conf completo já contém a location ACME, mas ele referencia o certificado
que ainda não existe. Para a **primeira emissão**, adicione temporariamente
esta location dentro do `server { listen 80; }` que está ativo hoje (não
ative ainda `DJANGO_SECURE_SSL_REDIRECT`):

```nginx
location ^~ /.well-known/acme-challenge/ {
  root /var/www/certbot;
  default_type text/plain;
  try_files $uri =404;
}
```

Crie o webroot e valide o vhost HTTP existente:

```bash
sudo apt update
sudo apt install -y certbot
sudo install -d -o www-data -g www-data -m 0755 /var/www/certbot/.well-known/acme-challenge
sudo nginx -t
sudo systemctl reload nginx
```

Não faça reload se `nginx -t` falhar. Se a Cloudflare já estiver com proxy
laranja, mantenha o challenge acessível (ou use DNS somente durante a
emissão) e não bloqueie a origem no firewall antes do TLS. Uma verificação
de challenge local evita perder a janela de emissão:

```bash
TOKEN='verificacao-acme'
sudo install -m 0644 /dev/null "/var/www/certbot/.well-known/acme-challenge/$TOKEN"
printf 'ok' | sudo tee "/var/www/certbot/.well-known/acme-challenge/$TOKEN" >/dev/null
curl -fsS "http://$DOMAIN_FRONTEND/.well-known/acme-challenge/$TOKEN"
sudo rm -f "/var/www/certbot/.well-known/acme-challenge/$TOKEN"
```

### 3A.3. Emitir o certificado e instalar o conf TLS

Solicite um certificado por domínio e, se fornecido, pelo alias. Antes da
emissão, valide o hook versionado e deixe-o executável; o Certbot executa o
deploy-hook como root:

```bash
# Ajuste APP_DIR se o input app_dir do caller usar outro caminho.
APP_DIR="/home/apps/portal-$ENV_NAME"
cd "$APP_DIR"
DEPLOY_HOOK="$APP_DIR/infra/certbot/deploy-hook-nginx.sh"
bash -n "$DEPLOY_HOOK"
sudo chmod +x "$DEPLOY_HOOK"
test -x "$DEPLOY_HOOK"
```

O hook executa `nginx -t` e só recarrega o Nginx quando esse teste passa. Se
`nginx -t` falhar, ele sai com erro sem enviar um reload, mantendo o processo
que já está em produção; o log fica no stderr do Certbot e no journal quando
`logger` está disponível. Em caso de falha do `systemctl`, o próprio hook
registra a falha e tenta o fallback `nginx -s reload`.

```bash
CERTBOT_ARGS=(-d "$DOMAIN_FRONTEND")
if [ -n "$DOMAIN_FRONTEND_WWW" ]; then
  CERTBOT_ARGS+=(-d "$DOMAIN_FRONTEND_WWW")
fi
sudo certbot certonly --webroot -w /var/www/certbot \
  "${CERTBOT_ARGS[@]}" \
  --email "$CERTBOT_EMAIL" --agree-tos --no-eff-email \
  --deploy-hook "$DEPLOY_HOOK"
sudo certbot certificates
```

O `--deploy-hook` é gravado no config de renovação do lineage. Portanto, o
`certbot renew` executado pelo `certbot.timer` do pacote Debian/Ubuntu também
invoca esse hook; não é necessário um reload manual silencioso. A alternativa
é registrar uma cópia executável do mesmo script em
`/etc/letsencrypt/renewal-hooks/deploy/`, que será executada para os lineages
renovados. Escolha **uma** forma de registro. A forma principal acima é passar
`--deploy-hook`; se escolher a alternativa global, omita essa opção do comando
e execute o `install` abaixo. Nunca registre as duas formas ao mesmo tempo,
pois isso executaria a recarga duas vezes:

```bash
sudo install -d -m 0755 /etc/letsencrypt/renewal-hooks/deploy
sudo install -m 0755 "$DEPLOY_HOOK" \
  /etc/letsencrypt/renewal-hooks/deploy/portal-nginx.sh
```

O resultado esperado é `/etc/letsencrypt/live/$DOMAIN_FRONTEND/fullchain.pem`
e `privkey.pem`. **Não copie o conf da repo enquanto os marcadores
`__DOMAIN_FRONTEND__` ou `__DOMAIN_FRONTEND_WWW__` estiverem presentes.**
Renderize uma cópia temporária, verifique que não sobrou marcador e só então
instale:

```bash
RENDERED_SITE="/tmp/portal-$ENV_NAME.conf"
DOMAIN_FRONTEND_WWW="${DOMAIN_FRONTEND_WWW:-}"
sed -e "s|__DOMAIN_FRONTEND__|$DOMAIN_FRONTEND|g" \
    -e "s|__DOMAIN_FRONTEND_WWW__|$DOMAIN_FRONTEND_WWW|g" \
    "infra/nginx/portal-$ENV_NAME.conf" > "$RENDERED_SITE"
if grep -q '__DOMAIN_' "$RENDERED_SITE"; then
  echo 'ERRO: ainda existe marcador de domínio; revise os valores'; exit 1
fi

sudo install -m 0644 "$RENDERED_SITE" "/etc/nginx/sites-available/portal-$ENV_NAME"
sudo ln -sfn "/etc/nginx/sites-available/portal-$ENV_NAME" \
  "/etc/nginx/sites-enabled/portal-$ENV_NAME"
sudo nginx -t
sudo systemctl reload nginx
```

O procedimento deve ser repetido separadamente para `dev`, `homolog` e `prod`,
com os respectivos valores de domínio. A porta 80 do conf completo agora
redireciona para HTTPS, mas deixa passar o challenge ACME; `/healthz` é
permitido apenas de loopback e continua disponível para o probe interno.

### 3A.4. Só agora ativar os flags de TLS

Verifique o TLS diretamente antes de alterar o ambiente Django:

```bash
curl -fsSI "http://$DOMAIN_FRONTEND/"       # esperado: 301 para HTTPS
curl -fsS --resolve "$DOMAIN_FRONTEND:80:127.0.0.1" \
  "http://$DOMAIN_FRONTEND/healthz"           # esperado: 200, loopback
curl -fsSI --resolve "$DOMAIN_FRONTEND:443:127.0.0.1" \
  "https://$DOMAIN_FRONTEND/healthz"          # esperado: 200
sudo openssl x509 \
  -in "/etc/letsencrypt/live/$DOMAIN_FRONTEND/fullchain.pem" \
  -noout -subject -issuer -dates
```

O primeiro comando deve resultar em `301` para HTTPS; o probe HTTP de
saúde é restrito a loopback e é testado separadamente. Em seguida,
edite `/home/apps/portal-$ENV_NAME/backend/.env` **manualmente** e deixe
exatamente:

```dotenv
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true
```

No mesmo commit/PR de configuração, altere `tls_enabled: false` para
`tls_enabled: true` no caller correspondente (`deploy-dev.yml`,
`deploy-homolog.yml` ou `deploy-prod.yml`) e dispare o redeploy. O workflow
não sobrescreve um `.env` existente: ele falha de forma explícita se os três
valores não coincidirem com o input, evitando um loop de redirecionamento ou
um downgrade silencioso. A ordem é: **Certbot → `nginx -t` → reload →
testar HTTPS → editar `.env` → `tls_enabled=true` → redeploy**.

Se qualquer teste HTTPS falhar, não edite os flags para true: corrija o
certificado ou restaure o vhost HTTP anterior, mantenha `tls_enabled=false` e
refaça a validação. Não ative o proxy laranja durante esse rollback.

Se o `.env` foi editado manualmente fora do workflow, reinicie o processo
correspondente e persista a lista:

```bash
pm2 restart "portal-api-$ENV_NAME"  # use dev, homolog ou prod
pm2 save
```

A validação do workflow, quando `tls_enabled=true`, percorre o vhost HTTPS
com `--resolve` em loopback; assim `SECURE_SSL_REDIRECT=true` não transforma o
health check em redirect e nenhum header de proxy é enviado diretamente ao
Gunicorn. A exceção HTTP local continua disponível para operadores que
precisem consultar `/healthz` durante a migração; não exponha essa rota
publicamente.

### 3A.5. Renovar e verificar

O pacote Debian/Ubuntu do Certbot instala um timer. O `certbot.timer` executa
`certbot renew` periodicamente; o Certbot, por sua vez, executa os deploy-hooks
registrados (no config de renovação passado no passo 3A.3 ou em
`/etc/letsencrypt/renewal-hooks/deploy/`). Ative o timer e valide o caminho
completo, incluindo a execução do hook:

```bash
sudo systemctl enable --now certbot.timer
sudo systemctl status certbot.timer --no-pager
sudo certbot renew --dry-run --run-deploy-hooks
sudo certbot certificates
sudo systemctl list-timers certbot.timer --no-pager
sudo journalctl -u certbot.service -n 50 --no-pager
```

`--run-deploy-hooks` é necessário no dry-run porque, sem essa opção, o Certbot
pode deliberadamente não executar hooks. O resultado
`Congratulations, all simulated renewals succeeded` prova o challenge, mas
não substitui a conferência do certificado que o Nginx está servindo. O conf
HTTP do passo 3A.3 deixa `/.well-known/acme-challenge/` acessível sem
redirect, portanto o timer pode renovar sem desligar o site.

Depois de uma renovação real, compare o certificado no lineage com o
certificado que o Nginx está servindo. A comparação local evita que uma
consulta pública veja o certificado da borda quando a Cloudflare está com proxy
laranja:

```bash
CERT_LINEAGE="/etc/letsencrypt/live/$DOMAIN_FRONTEND"
sudo openssl x509 -in "$CERT_LINEAGE/fullchain.pem" \
  -noout -subject -issuer -serial -dates

# Nginx local, com SNI do domínio; repita após o timer ter renovado.
openssl s_client -connect 127.0.0.1:443 -servername "$DOMAIN_FRONTEND" \
  </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -serial -dates

# Equivalente público, para a topologia sem proxy Cloudflare:
openssl s_client -connect "$DOMAIN_FRONTEND:443" \
  -servername "$DOMAIN_FRONTEND" </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -serial -dates
sudo certbot certificates
```

O `serial`, `notBefore` e `notAfter` do primeiro bloco devem coincidir com os
do segundo (e `certbot certificates` deve mostrar a mesma expiração). Em uma
renovação efetiva, o serial e a data de expiração devem ter mudado em relação
à medição anterior; esse é o teste de que o Nginx passou a servir o arquivo
novo, e não apenas de que o certificado foi emitido. O dry-run não substitui o
certificado de produção, então compare novamente depois de uma renovação real
do timer. Se `nginx -t` falhar, o hook não recarrega e o processo antigo
continua servindo; corrija a configuração e execute a renovação real novamente
após o `nginx -t` passar.

### 3A.6. Cloudflare depois do TLS (opcional)

Consulte a seção 3. A Cloudflare é uma camada adicional, não um pré-requisito
do Certbot e não substitui o teste local. Mantenha `Full (strict)`, ative o
proxy laranja somente depois de validar o par Cloudflare→origem, mantenha
PostgreSQL e Redis restritos às interfaces internas e meça cache/latência antes
de afirmar ganhos.
A conta, os nameservers, o IP de origem e as regras de cache são decisões
humanas; nada é ativado por esta run.

## 4. Clonar o projeto e configurar segredos

```bash
git clone <seu-repositorio> /home/deploy/brd_portal_noticias
cd /home/deploy/brd_portal_noticias
cp .env.production.example .env.production
# Preencha .env.production com os valores reais (ver comentários no
# próprio arquivo) — SECRET_KEY forte, senha do Postgres, domínios,
# credenciais do provedor de LLM/e-mail/pagamento quando definidos.
chmod 600 .env.production
```

## 5. Subir a stack

```bash
docker compose --env-file .env.production up -d --build
docker compose --env-file .env.production ps   # todos "healthy"
curl -I https://$DOMAIN_API/healthz             # 200
```

O `docker-entrypoint.sh` do serviço `web` já roda `migrate` e
`collectstatic` automaticamente a cada start — não é necessário rodar isso
manualmente.

## 6. Criar o primeiro superusuário do admin

```bash
docker compose --env-file .env.production exec web python manage.py createsuperuser
```

## 7. Agendar backup diário — variante Docker/Caddy

Esta seção **não é o caminho da VPS ativa**. Para PostgreSQL nativo + PM2 +
Nginx, use `pg_backup_pm2.sh` e o comando idempotente da seção 0.

```bash
crontab -e
# Backup às 3h da manhã, horário de menor tráfego.
# SOMENTE variante Docker/Caddy:
0 3 * * * /home/deploy/brd_portal_noticias/infra/backup/pg_backup.sh >> /var/log/pg_backup.log 2>&1
```

`infra/backup/RESTORE.md` descreve comandos da variante Docker. Antes de
considerar qualquer backup recuperável, valide também o artefato da topologia
ativa sem sobrescrever produção:

```bash
pg_restore --list /caminho/para/pm2-db-AAAAMMDDTHHMMSSZ.dump >/dev/null
tar -tzf /caminho/para/pm2-media-AAAAMMDDTHHMMSSZ.tar.gz >/dev/null
```

Esses dois comandos são apenas checagens rápidas de formato; um archive
truncado pode passar em `pg_restore --list`. Para provar recuperabilidade,
execute `pg_restore --exit-on-error` em um banco PostgreSQL descartável criado
com `createdb -T template0` (usando as mesmas credenciais/paths), verifique as
tabelas e contagens esperadas e remova o banco com `dropdb`. O script já faz
essa validação por padrão antes de publicar o arquivo; repita o procedimento em
uma cópia de staging antes de confiar no restore de produção. Extraia a mídia em
um diretório vazio e confira o conteúdo, sem sobrescrever `backend/media`.

## 8. Monitoramento de disponibilidade (grátis)

Na topologia ativa **PM2 + Nginx**, frontend e API compartilham o mesmo host.
Cadastre `https://$DOMAIN_FRONTEND/healthz` (isto é,
`https://$DOMAIN/healthz`) num monitor externo gratuito (ex.: UptimeRobot,
Better Stack Free), com alerta por e-mail/Telegram. **Use HTTPS**: o
`/healthz` em HTTP é liberado somente para loopback, e um monitor externo em
HTTP receberia `403` por decisão de segurança. Na variante Docker/Caddy, em
que a API tem host próprio, use `https://$DOMAIN_API/healthz`. Assim uma queda
é sabida em minutos, não quando um usuário reclamar.

## Deploy de uma nova versão

```bash
cd /home/deploy/brd_portal_noticias
git pull
docker compose --env-file .env.production up -d --build
docker compose --env-file .env.production ps
```

Isso reconstrói só as imagens que mudaram e reinicia os containers
afetados; `db`/`redis` (com dados persistidos em volume) não são recriados.
Ver `.github/workflows/ci.yml` — a suíte de testes roda automaticamente a
cada push, então um `git pull` só deve acontecer depois de o CI passar.

> **Janela fria para o `migrate`:** a migração `0011_newsitem_busca_trgm` cria
> um índice GIN (não-CONCURRENTLY) sobre `catalogo_noticias_newsitem` e
> bloqueia escrita na tabela durante a construção. Rode o deploy/migrate em
> horário de baixo tráfego.

## Nginx na VPS: ativação versionada de cache/rate (P1-4)

Os arquivos de site `infra/nginx/portal-{dev,homolog,prod}.conf` são
**standalone e fail-safe**: não declaram `map`, `limit_req_zone` ou
`proxy_cache_path` diretamente. Assim, copiar um site antes da preparação do
`http {}` global não quebra `nginx -t`; cache/rate ficam apenas desativados
até a ativação documentada abaixo. Os valores efetivos estão versionados em
`infra/nginx/http-cache.conf` (contexto `http`) e nos três snippets
`infra/nginx/portal-location-{cache,auth,write}.conf` (contexto `location`).

> **Ordem obrigatória de ativação na VPS:** (1) copie
> `http-cache.conf` para `/etc/nginx` e inclua-o **uma única vez dentro do
> `http {}` global**; (2) somente depois instale os três snippets e o site do
> ambiente; (3) rode `sudo nginx -t`; (4) se o teste passar, recarregue com
> `sudo systemctl reload nginx`; (5) reinicie a API correspondente no PM2
> para que o Gunicorn carregue a configuração atual. O passo (2) dos snippets
> é opcional para manter o site sintaticamente válido, mas **sem ele o
> cache/rate permanece inativo**.

### 1. Preparar o `http {}` global (uma vez)

No checkout de cada ambiente, copie primeiro o include global para
`/etc/nginx` e crie o diretório do cache com permissão do usuário que executa
o worker:

```bash
cd /home/apps/portal-prod       # use portal-dev ou portal-homolog
sudo install -d -o www-data -g www-data -m 0750 /var/cache/nginx/feed
sudo install -m 0644 infra/nginx/http-cache.conf /etc/nginx/http-cache.conf
```

Edite `/etc/nginx/nginx.conf` **dentro do `http {}`**, sem duplicar a diretiva
em cada site:

```nginx
http {
    include /etc/nginx/http-cache.conf;
    include /etc/nginx/sites-enabled/*;
}
```

O include global contém os dois mapas, as duas `limit_req_zone` e o
`proxy_cache_path`. Não coloque `map`/`limit_req_zone` dentro de `server {}`:
esse é o contexto inválido que fez o reload anterior falhar.

Com o include global já referenciado, instale os três snippets de location
(só agora; eles referenciam as zones do passo anterior):

```bash
sudo install -m 0644 infra/nginx/portal-location-cache.conf /etc/nginx/portal-location-cache.conf
sudo install -m 0644 infra/nginx/portal-location-auth.conf /etc/nginx/portal-location-auth.conf
sudo install -m 0644 infra/nginx/portal-location-write.conf /etc/nginx/portal-location-write.conf
```

### 2. Instalar os sites e validar antes do reload

Copie somente o conf do ambiente, mantenha o link em `sites-enabled` e rode
`nginx -t` antes de qualquer reload:

```bash
sudo cp infra/nginx/portal-prod.conf /etc/nginx/sites-available/portal-prod
sudo ln -sfn /etc/nginx/sites-available/portal-prod /etc/nginx/sites-enabled/portal-prod
sudo nginx -t                       # obrigatório; não recarregar se falhar
sudo systemctl reload nginx
```

Repita para `portal-dev` e `portal-homolog`. Se ainda não for possível
instalar o include global, **não copie os snippets de location**: os globs
nos sites não têm arquivos correspondentes e o `nginx -t` continua passando,
com cache/rate inativos. A ordem segura é: include global → snippets de
location → conf do site → `nginx -t` → reload. Copiar um snippet de location
antes do global produzirá `unknown zone` e o reload será recusado.

`portal-location-write.conf` limita POST a 20/min (a key global fica vazia
para GET/HEAD); `portal-location-auth.conf` mantém os demais endpoints de
autenticação em 10/min. `/api/auth/cadastro/` e `/api/feed/interacoes/` têm
locations exatas com o limite de escrita pública, portanto não ficam sob o
limite de 10/min nem sob o regex de cache.

### 3. Reiniciar as APIs no PM2

Depois de validar e recarregar o Nginx, reinicie **cada API alterada** para
que o Gunicorn leia `backend/gunicorn.conf.py`. Não é necessário reiniciar os
processos web. Execute no usuário que gerencia o PM2:

```bash
pm2 restart portal-api-prod     # ou portal-api-homolog / portal-api-dev
pm2 save
curl -fsS http://127.0.0.1:5103/healthz
```

Use a porta `5103` para PROD, `5102` para HOMOLOG e `5101` para DEV. Para
ativar os três ambientes, reinicie os três processos `portal-api-*` e persista
a lista do PM2 novamente. Se o backend foi publicado pelo workflow, ele já
recria a API com `--config .../gunicorn.conf.py`; ainda assim, confira
`pm2 status`, `/healthz` e os logs antes de considerar a ativação concluída.

### Mídia e privacidade

O grep dos `FileField`/`upload_to` encontrou os três uploads de
`credenciamento` (`foto` da solicitação, `documento` e `foto` do perfil) sob
`media/credenciamento/<user_id>/`. O alias genérico de `MEDIA_ROOT` foi
removido: as locations `= /media/credenciamento` e
`^~ /media/credenciamento/` retornam 404, e não existe
proteção por extensão. O documento só é baixado pelo `DocumentoView`, que
exige o próprio solicitante ou admin. O único alias direto é
`/media/public/`, uma allowlist explícita para arquivos revisados como
públicos; qualquer novo upload privado deve ficar fora desse subtree. As
fotos de perfil atuais também ficam fora do alias até a separação de storage
ser feita; não as copie para `public/` apenas para restaurar a imagem.

> **Contrato de segurança — variante Docker/Caddy:** a configuração versionada
> é fail-closed. `/media/credenciamento` e seus descendentes retornam 404;
> somente `/media/public/*` é servido, a partir de `/srv/media/public`; e
> qualquer outro caminho sob `/media*` é fechado, sem fallback para toda a
> árvore `/srv/media`. Os documentos privados continuam disponíveis somente
> pela `DocumentoView` autenticada. Depois de qualquer alteração, valide a
> configuração com os domínios renderizados e repita os probes HTTP privado,
> público e desconhecido antes de usar a variante com credenciamento. Essa
> validação local não constitui evidência de que a variante foi implantada na
> VPS; a topologia ativa continua sendo Nginx + PM2.

### Timeout Gunicorn/Nginx

O default implantado agora é **60 s** nos dois lados. No momento desta
revisão, o endpoint `/api/admin/robos/executar/` ainda pode estar síncrono no
ref publicado: o 202+background está em uma alteração de trabalho não
commitada. **Não ative
`GUNICORN_TIMEOUT=45` nem `proxy_read_timeout 45s` antes de o commit 202 ser
um ancestral comprovado do ref implantado.** Depois desse commit, reduza o
Gunicorn e os três confs Nginx na mesma mudança. No PM2, o `cd
"$APP_DIR/backend"` imediatamente antes do start faz o PM2 herdar
`pm_cwd=backend` e encontrar o conf; `--config` absoluto torna essa garantia
explícita e não se depende somente de `--chdir`.

### Invalidação do cache de borda

O cache de borda tem TTL 45s (`proxy_cache_valid 200 45s`). Para forçar
limpeza imediata, remova os arquivos e valide/recarregue; reload sozinho não
apaga entradas:

```bash
sudo rm -rf /var/cache/nginx/feed/*
sudo nginx -t && sudo systemctl reload nginx
```

O cache cobre a allowlist de GETs públicas configurada no location (feed,
urgentes, mais-lidas, home, destaques, busca pública, autocomplete e
`radar/tendencias/`). Busca o histórico, interações, detalhes e demais rotas
não são cacheados; header/cookie de autenticação também faz bypass e
`no_cache`. Confirme com `curl -sI https://<host>/api/feed/ | grep -i
x-cache-status` (`HIT` = cache, `MISS` = upstream).

## Ambiente de homologação (multi-env)

Ideia incorporada do protótipo `testes-ia` (que tinha DEV/HOMOLOG/PROD via
PM2 — aqui adaptada para Docker+Caddy, sem PM2): rode uma segunda cópia da
stack na mesma VPS com domínios e portas diferentes, usando o override
`docker-compose.homolog.yml` na raiz do projeto.

```bash
cp .env.production.example .env.homolog
# edite .env.homolog: DOMAIN_API=homolog-api.seu-dominio.com.br,
# DOMAIN_FRONTEND=homolog.seu-dominio.com.br, senha do Postgres DIFERENTE
# da produção, SECRET_KEY diferente.
chmod 600 .env.homolog
docker compose --env-file .env.homolog -f docker-compose.yml \
  -f docker-compose.homolog.yml up -d --build
```

Notas:

- O override publica 8080/8443 no host para conviver com a produção
  (80/443) na mesma VPS — aponte os DNS de homolog para o mesmo IP e, se
  houver Cloudflare na frente, crie os registros `homolog*` com proxy
  ativado do mesmo jeito.
- Cada ambiente tem seus próprios volumes? **Não por padrão**: se subir os
  dois composes no mesmo host Docker, os volumes nomeados (`postgres_data`,
  etc.) colidem. Para homolog na mesma VPS, adicione `-p homolog` (nome de
  projeto Compose separado) ao comando acima — isso prefixa containers,
  redes e volumes, isolando os dados da produção.
- O que **não** foi trazido do `testes-ia`: os 25 scripts `scripts/fix_*`
  (debug manual pontual, sem valor permanente), as regras Firestore
  (`firestore.rules` — este projeto usa Postgres, não Firestore) e o
  deploy via PM2 (substituído pelo Compose+Caddy aqui).
