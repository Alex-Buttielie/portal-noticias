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

## Contexto histórico da ingestão

- **Estado anterior a 2026-09-24 (não operacional):** o segundo pipeline
  FastAPI/Mongo tinha 43 testes próprios e o conjunto de testes do portal
  contava 41 testes. Esse caminho foi removido do repositório; os números e a
  topologia anterior são registrados apenas como histórico da decisão abaixo,
  não como instruções para implantação.
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

7. **Arquivamento definitivo do segundo pipeline (decisão humana de
   2026-09-24)** — `ingestao-service/` foi removido por decisão explícita do
   solicitante, sem stub e sem cópia em `docs/archive`. O adaptador HTTP do
   feed, a sincronização remota de fontes dos robôs, seus testes e as flags de
   URL/token também foram eliminados. **Django/PostgreSQL/Celery é a única
   fonte de verdade executável**; as capacidades de curadoria permanecem no
   admin Django.
   - **Motivos:** duplicar pipeline, dedup, curadoria e contratos de feed criava
     duas bases e dois contratos; o painel próprio era servido sem
     autenticação; a configuração anterior expunha MongoDB em `0.0.0.0`; e os
     testes do segundo pipeline não eram gate do CI principal.
   - **Decisão de produto:** não ativar nem recuperar esse segundo pipeline. Se
     surgir necessidade de uma tela operacional, implementar a capacidade no
     admin Django autenticado em uma run própria.
   - **Ação operacional após o deploy:** em arquivos de ambiente preexistentes,
     remover as duas flags antigas se ainda estiverem presentes; variáveis
     remanescentes passam a ser ignoradas pelo Django. Em cada VPS, inspecionar
     serviços/contêineres e volumes Mongo antigos, desligar o componente e
     remover o volume **somente após confirmar backup e necessidade dos dados**.
     Esta decisão de repositório **não acessou a VPS, não desligou a instância e
     não afirma que o banco Mongo ou seus volumes foram apagados**.

## Registro de conclusões

- 2026-09-17 — Leitura dentro do sistema entregue (`conteudo_completo` RSS +
  seção Matéria com crédito + CTA para a fonte).
- 2026-09-17 — Caminho Docker do DEPLOY.md validado local (builds, up,
  healthz, feed, superuser). Correção: `frontend/Dockerfile`, `.dockerignore`
  e `.env.local.example` convertidos de UTF-16 para UTF-8 (BuildKit quebrava).
