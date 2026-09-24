# Fila de decisões para produção — BRD Portal de Notícias

> Gravado a pedido do Alex em 2026-09-17. Regra: **se precisar de qualquer
> informação externa (chaves, contas, provedor, revisão), PERGUNTAR ao Alex
> em vez de adivinhar.** Infra ativa: **PM2 + Nginx** na VPS, conforme
> `CI-CD.md` e `infra/nginx/`; Docker + Caddy é a variante alternativa/local
> documentada em `infra/DEPLOY.md`.

## Ordem de execução

1. **Pagamento real — Mercado Pago (sandbox)** — implementado
   (`MercadoPagoGatewayProvider` via `/preapproval`, sem SDK): criar cobrança
   → checkout (`sandbox_init_point`), webhook
   `/api/assinatura/webhook/mercadopago/` confirma/recusa, `checkout_url`
   devolvido no assinar + redirect no `/planos`. Testes mockados: 8 novos.
   Falta (Alex): gerar Access Token **TEST-** em
   developers.mercadopago.com → credenciais de teste, e cadastrar a URL do
   webhook (`https://<DOMAIN_API>/api/assinatura/webhook/mercadopago/`) no
   painel do MP; depois preencher `ASSINATURA_MP_ACCESS_TOKEN` (+ `=mercadopago`
   no provider). Para produção futura: token APP_USR + `SANDBOX=false`.
   Status: código pronto, aguardando credencial TEST do Alex.
2. **LLM / e-mail / OAuth** (decidido 2026-09-17: OpenAI + Resend, Google depois)
   - LLM: código já fala Chat Completions (`gpt-4o-mini` default) — só falta
     `CATALOGO_NOTICIAS_LLM_API_KEY` real no prod. Sem chave, cai em revisão
     humana (comportamento seguro). Status: aguardando chave OpenAI do Alex.
   - E-mail: backend Resend implementado (`config/email_resend.py`, sem SDK,
     4 testes) — ligar com `DJANGO_EMAIL_BACKEND=config.email_resend.ResendEmailBackend`
     + `RESEND_API_KEY=re_...` + remetente de domínio verificado.
     Status: código pronto, aguardando chave Resend do Alex.
   - OAuth Google: settings prontos (`GOOGLE_OAUTH_CLIENT_ID/SECRET`), fluxo
     adiado. Status: aguardando credenciais do Alex.
3. **AdSense** — código pronto (`AdsScript` no layout + `AdsSlot` real quando
   `NEXT_PUBLIC_ADSENSE_CLIENT_ID` + slots por formato configurados; sem isso,
   placeholder sem chamada externa). Falta (Alex): publisher ID `ca-pub-...`,
   4 slots numéricos, aprovação da conta e rebuild. Status: aguardando Alex.
4. **Revisão jurídica da privacidade** — política atual é rascunho funcional.
   Status: pendente.
5. **Ligar a flag premium** — `ConfiguracaoSistema.premium_ativo` nasce
   desligada (tudo liberado, assinaturas pausadas/409). Ligar SOMENTE quando
   pagamento + planos estiverem prontos para cobrar de verdade.
   Status: pendente (decisão final do Alex).

## Registro de conclusões (TRABALHO LOCAL — NÃO COMMITADO, NÃO PUBLICADO)

- Microserviço `ingestao-service/` (FastAPI + Mongo, Swagger /docs): esqueleto,
  pipeline (RSS/dedup/LLM/curadoria + regras N1–N4), API + painel `/painel`,
  portal adaptado (`feed/microservice_client.py` com fallback local, sync de
  fontes best-effort). Testes: 43 service + 41 feed-portal. `tsc 0`, build OK.
  Ligar no portal: `MICROSERVICO_INGESTAO_URL` + `INGESTAO_API_TOKEN`.
- Categorias com subcategorias fixas + vivas das notícias (`lib/categorias.ts`),
  menu Editorias no Header (desktop/mobile), editorias e categoria com tópicos,
  footer "Desenvolvido por ButtielieDev", ritmo de espaçamento normalizado.

## Decisões desta execução (2026-09-24)

6. **TLS na topologia ativa (P0-3)** — preparação versionada, ativação humana
   pendente. O Nginx da VPS usa **Certbot/Let's Encrypt na origem** com
   `certonly --webroot`; não foi escolhido Cloudflare Origin CA. A escolha é
   deliberada: o certificado da origem continua válido com ou sem Cloudflare,
   é o padrão Debian/Ubuntu e tem renovação por timer. Os três sites foram
   preparados com HTTP → 301, `listen 443 ssl`, ACME HTTP-01 e exceções para
   o health check interno. O domínio não foi inventado: os arquivos usam
   marcadores `__DOMAIN_FRONTEND__`/`__DOMAIN_FRONTEND_WWW__` e o operador
   precisa renderizá-los na VPS. Cloudflare (CDN/WAF/DDoS/Brotli) continua
   opcional, exige conta e deve ser medido após a ativação; esta run não mede
   nem promete ganho. Status: **repo pronto; certbot, DNS, `nginx -t`, reload,
   `.env` e `tls_enabled=true` aguardam operador**.

7. **`ingestao-service/` — recomendação de não ativar agora** — o diretório
   continua desligado (`MICROSERVICO_INGESTAO_URL` vazio) e não será apagado
   nesta run. A comparação honesta é:
   - **Pipeline Django (fonte de verdade atual):** já roda em produção/Celery,
     busca RSS paralela com `ETag`/`Last-Modified`, idempotência por URL,
     janela de deduplicação, `bulk_create`, snapshot/cache da configuração,
     curadoria e proteção de cópia, integração direta com Postgres, feed e
     painel administrativo. A suíte Django roda no CI.
   - **Microserviço:** oferece isolamento de processo/dados, API FastAPI com
     token, CRUD/sincronização de fontes, Swagger e um painel HTML próprio em
     `/painel`; o painel é um diferencial real de operação. O alias raiz
     `/painel` é servido sem autentização no código atual, enquanto a rota
     `/api/v1/painel` exige token — outro motivo para não expor o serviço
     como está. Em troca,
     duplica regras de pipeline, mantém LLM/batch/dedup/curadoria em outra
     base, não tem o mesmo cache/ETag/`bulk_create` do Django, e seus testes
     não são um gate do workflow principal.
   - **Riscos operacionais:** duas fontes de verdade e contratos de feed,
     MongoDB adicional, mais um serviço para observar/backupar; o compose
     publica `27017:27017` (interface `0.0.0.0` no host), o que cria uma
     superfície de ataque desnecessária. O default `LLM_PRECO_1K=0.15` também
     está desatualizado em relação ao pipeline Django, sem medição que
     justifique a duplicação.
   - **Recomendação:** manter `MICROSERVICO_INGESTAO_URL` vazio, não promover
     o microserviço a produção e não apagar o diretório sem decisão humana.
     Se o painel for necessário, levar essa capacidade para o admin Django ou
     criar uma run de experimentação com CI, bind privado do Mongo, plano de
     migração de dados, benchmark de custo/latência e critério claro de
     fonte da verdade. Status: **recomendação técnica; decisão do humano
     pendente**.

## Registro de conclusões

- 2026-09-17 — Leitura dentro do sistema entregue (`conteudo_completo` RSS +
  seção Matéria com crédito + CTA para a fonte).
- 2026-09-17 — Caminho Docker do DEPLOY.md validado local (builds, up,
  healthz, feed, superuser). Correção: `frontend/Dockerfile`, `.dockerignore`
  e `.env.local.example` convertidos de UTF-16 para UTF-8 (BuildKit quebrava).
