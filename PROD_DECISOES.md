# Fila de decisões para produção — BRD Portal de Notícias

> Gravado a pedido do Alex em 2026-09-17. Regra: **se precisar de qualquer
> informação externa (chaves, contas, provedor, revisão), PERGUNTAR ao Alex
> em vez de adivinhar.** Infra decidida: `infra/DEPLOY.md` (Docker + Caddy),
> validada localmente (compose config, builds, up, healthz, feed, superuser).

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

## Registro de conclusões

- 2026-09-17 — Leitura dentro do sistema entregue (`conteudo_completo` RSS +
  seção Matéria com crédito + CTA para a fonte).
- 2026-09-17 — Caminho Docker do DEPLOY.md validado local (builds, up,
  healthz, feed, superuser). Correção: `frontend/Dockerfile`, `.dockerignore`
  e `.env.local.example` convertidos de UTF-16 para UTF-8 (BuildKit quebrava).
