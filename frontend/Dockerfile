# Build multi-stage: a imagem final n├úo carrega toolchain de build (~v├írias
# centenas de MB a menos), s├│ o output standalone do Next.js ÔÇö importante
# numa VPS onde essa imagem convive com Postgres/Redis/backend/Celery.

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Garante que /app/public existe mesmo quando o projeto não tem assets
# estáticos em public/ — sem isso o COPY no stage runner falha
# ("failed to calculate checksum ... /app/public: not found").
RUN mkdir -p ./public
# Vari├íveis NEXT_PUBLIC_* s├úo embutidas no bundle JS NO MOMENTO DO BUILD
# (n├úo em runtime) ÔÇö precisam estar dispon├¡veis aqui via build arg, n├úo s├│
# no ambiente do container final.
#
# Canal de release/ambiente do Bloco B2 (critérios 6 e 20), em uma linha: o
# navegador recebe release e ambiente EMBUTIDOS (o release de um bundle e, por
# construcao, o SHA do codigo que ele executa), e o servidor standalone os le
# de VARIAVEL DE RUNTIME (o mesmo artefato roda em dev, homolog e prod na
# mesma VPS - congelar o ambiente no build faria os tres se reportarem com o
# mesmo nome, e nenhum alerta por ambiente dispararia).
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_SITE_URL
# DSN do Sentry. NAO e segredo: por definicao ele vai embutido no bundle e a
# chave publica do projeto esta dentro dele. O que e segredo e o
# SENTRY_AUTH_TOKEN, que fica so neste stage (ver abaixo) e nunca e copiado
# para a imagem final.
ARG NEXT_PUBLIC_SENTRY_DSN=""
ARG NEXT_PUBLIC_SENTRY_ENVIRONMENT=""
ARG NEXT_PUBLIC_SENTRY_RELEASE=""
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL
ENV NEXT_PUBLIC_SENTRY_DSN=$NEXT_PUBLIC_SENTRY_DSN
ENV NEXT_PUBLIC_SENTRY_ENVIRONMENT=$NEXT_PUBLIC_SENTRY_ENVIRONMENT
ENV NEXT_PUBLIC_SENTRY_RELEASE=$NEXT_PUBLIC_SENTRY_RELEASE
# SENTRY_ORG/SENTRY_PROJECT sao metadados publicos do projeto no Sentry, lidos
# pelo plugin de source map; SENTRY_AUTH_TOKEN e o segredo de upload e so
# existe aqui.
ARG SENTRY_ORG=""
ARG SENTRY_PROJECT=""
ARG SENTRY_AUTH_TOKEN=""
ENV SENTRY_ORG=$SENTRY_ORG
ENV SENTRY_PROJECT=$SENTRY_PROJECT
ENV SENTRY_AUTH_TOKEN=$SENTRY_AUTH_TOKEN
# Release usada pelo plugin de source map e pelos eventos gerados no build.
# Sem SENTRY_AUTH_TOKEN o upload e pulado com aviso e o build continua - que e
# o comportamento correto em dev e em build sem credencial, e nunca um "verde"
# silencioso em producao, porque o aviso aparece no log.
ARG SENTRY_RELEASE=""
ENV SENTRY_RELEASE=$SENTRY_RELEASE
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Canal de runtime do Sentry no servidor (criterios 6 e 19). `output:
# standalone` nao le ARG: estas variaveis vem do ambiente do container, que e
# o unico lugar onde dev/homolog/prod se diferenciam.
#
# SENTRY_TECHNICAL_CONSENT_DEFAULT e o MESMO nome e o MESMO default (false) do
# backend (backend/config/observability.py): o servidor do Next nao tem como
# saber o consentimento de um visitante, entao a decisao e do operador e o
# default e NAO enviar. Fail-closed: so quem ligar a variavel, com a
# consequencia juridica assumida, passa a reportar erro de servidor.
ENV SENTRY_ENVIRONMENT=""
ENV SENTRY_RELEASE=""
ENV SENTRY_DSN=""
ENV SENTRY_TECHNICAL_CONSENT_DEFAULT=false

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD node -e "fetch('http://localhost:3000').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
