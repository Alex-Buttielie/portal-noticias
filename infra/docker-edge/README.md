# Caddy compartilhado (cutover Docker)

Único processo Caddy da VPS, compartilhado pelos três ambientes
(dev/homolog/prod) — o mesmo papel que o Nginx único faz hoje
(`infra/nginx/portal-{dev,homolog,prod}.conf`). Cada ambiente mantém seu
próprio `docker-compose.yml` completo (sem Caddy); este diretório é um
projeto Compose **separado**, instalado uma vez por VPS.

## Por que existe

Três ambientes não podem ter três Caddys independentes disputando as portas
80/443 do mesmo host. Em vez disso: `web`/`frontend` de cada ambiente
publicam só em `127.0.0.1` (ver `docker-compose.yml` da raiz), e este Caddy
único — com `network_mode: host` — alcança os seis (3×2) pelo loopback do
host, roteando por domínio.

## Instalação (uma vez por VPS)

```bash
cd infra/docker-edge
sed -i \
  -e "s/__DOMAIN_DEV__/dev.portal-noticias.com/" \
  -e "s/__DOMAIN_HOMOLOG__/homolog.portal-noticias.com/" \
  -e "s/__DOMAIN_PROD_WWW__/www.portal-noticias.com/" \
  -e "s/__DOMAIN_PROD__/portal-noticias.com/" \
  Caddyfile
cp .env.example .env   # preencha OBSERVABILITY_METRICS_TOKEN (mesmo valor dos 3 ambientes)
docker compose up -d
```

## Pré-requisitos

- Os três ambientes (`/home/apps/portal-{dev,homolog,prod}`) já implantados
  pelo menos uma vez, com seus volumes `static_data`/`media_data` existindo
  (nomes reais: `portal-<env>_static_data`/`portal-<env>_media_data` — o
  Compose deriva o nome do projeto do diretório; confirme com
  `docker volume ls` antes de instalar se o diretório tiver outro nome).
- DNS dos quatro hostnames já resolvendo para a VPS (Caddy emite o
  certificado Let's Encrypt automaticamente, mas falha se o domínio não
  resolver).
- Portas 80/443 livres no host (nada de Nginx/outro Caddy ocupando-as).

## Verificação

```bash
docker compose logs -f caddy
curl -sk https://dev.portal-noticias.com/livez
curl -sk https://homolog.portal-noticias.com/livez
curl -sk https://portal-noticias.com/livez
```

## Rotação do token de observabilidade

`OBSERVABILITY_METRICS_TOKEN` precisa ser o MESMO valor em quatro lugares:
este `.env`, e os três `backend/.env.production` (dev, homolog, prod).
Trocar um sem os outros três quebra o gate de `/health-detail`/`/metrics`
(nunca autoriza, nunca abre — fail-closed, mas fica tudo degradado até
sincronizar de novo).
