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
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_SITE_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL
ARG NEXT_PUBLIC_SENTRY_DSN=""
ARG NEXT_PUBLIC_SENTRY_ENVIRONMENT=""
ARG NEXT_PUBLIC_SENTRY_RELEASE=""
ENV NEXT_PUBLIC_SENTRY_DSN=$NEXT_PUBLIC_SENTRY_DSN
ENV NEXT_PUBLIC_SENTRY_ENVIRONMENT=$NEXT_PUBLIC_SENTRY_ENVIRONMENT
ENV NEXT_PUBLIC_SENTRY_RELEASE=$NEXT_PUBLIC_SENTRY_RELEASE
# AdSense (PROD_DECISOES.md item 3): também NEXT_PUBLIC_*, também vazio é
# seguro — sem publisher ID, AdsSlot fica como placeholder sem chamada
# externa (ver frontend/.env.local.example). Achado da migração: nem o
# runtime PM2 nem este Dockerfile passavam essas 5 variáveis ao build real
# antes desta correção.
ARG NEXT_PUBLIC_ADSENSE_CLIENT_ID=""
ARG NEXT_PUBLIC_ADSENSE_SLOT_HORIZONTAL=""
ARG NEXT_PUBLIC_ADSENSE_SLOT_RETANGULO=""
ARG NEXT_PUBLIC_ADSENSE_SLOT_VERTICAL=""
ARG NEXT_PUBLIC_ADSENSE_SLOT_INFEED=""
ENV NEXT_PUBLIC_ADSENSE_CLIENT_ID=$NEXT_PUBLIC_ADSENSE_CLIENT_ID
ENV NEXT_PUBLIC_ADSENSE_SLOT_HORIZONTAL=$NEXT_PUBLIC_ADSENSE_SLOT_HORIZONTAL
ENV NEXT_PUBLIC_ADSENSE_SLOT_RETANGULO=$NEXT_PUBLIC_ADSENSE_SLOT_RETANGULO
ENV NEXT_PUBLIC_ADSENSE_SLOT_VERTICAL=$NEXT_PUBLIC_ADSENSE_SLOT_VERTICAL
ENV NEXT_PUBLIC_ADSENSE_SLOT_INFEED=$NEXT_PUBLIC_ADSENSE_SLOT_INFEED
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

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD node -e "fetch('http://localhost:3000').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
