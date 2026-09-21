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
