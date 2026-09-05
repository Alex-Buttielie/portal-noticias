# Deploy na VPS — passo a passo

Guia de provisionamento da VPS HostGator (root/SSH) para a nova arquitetura
de infra (`docker-compose.yml` + `Caddyfile` na raiz do projeto). Faça uma
vez por VPS; deploys seguintes usam só a seção "Deploy de uma nova versão".

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
# aws CLI — usado por infra/backup/pg_backup.sh para enviar backups ao
# storage remoto (Backblaze B2 / Cloudflare R2, compatíveis com API S3).
apt install -y awscli
```

## 3. Cloudflare (CDN + WAF + DDoS, camada gratuita)

1. Aponte o domínio para os nameservers da Cloudflare.
2. Crie registros `A` para `DOMAIN_FRONTEND` e `DOMAIN_API` apontando para o
   IP da VPS, com o proxy **ativado** (nuvem laranja) — é isso que dá CDN,
   WAF e proteção DDoS de graça, escondendo o IP real da VPS.
3. Em **SSL/TLS**, modo **Full (strict)** — o Caddy já emite certificado
   válido sozinho (Let's Encrypt), então a Cloudflare pode validar a ponta
   Cloudflare→VPS de verdade, não só criptografar sem checar.
4. Em **Speed → Optimization**, ative Brotli e Auto Minify (grátis,
   melhora performance de borda sem tocar no código).
5. (Opcional, quando o tráfego justificar) crie uma **Page Rule** de cache
   agressivo para `DOMAIN_API/api/feed/*` respeitando os headers
   `Cache-Control` que a própria aplicação já envia.

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

## 7. Agendar backup diário

```bash
crontab -e
# Backup às 3h da manhã, horário de menor tráfego.
0 3 * * * /home/deploy/brd_portal_noticias/infra/backup/pg_backup.sh >> /var/log/pg_backup.log 2>&1
```

Depois, siga `infra/backup/RESTORE.md` **pelo menos uma vez** para
confirmar que o restore funciona de verdade.

## 8. Monitoramento de disponibilidade (grátis)

Cadastre `https://$DOMAIN_API/healthz` num monitor externo gratuito (ex.:
UptimeRobot, Better Stack Free) com alerta por e-mail/Telegram — assim uma
queda é sabida em minutos, não quando um usuário reclamar.

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
