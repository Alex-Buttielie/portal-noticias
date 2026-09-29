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

   **P1-07 (2026-09-26) — o caminho foi exercitado de ponta a ponta com
   dublês e 5 defeitos de dinheiro foram encontrados e corrigidos.** O que
   mudou, e o que o Alex precisa saber:

   - **O webhook agora é autenticado.** Antes ele era `AllowAny` sem
     nenhuma verificação de assinatura: qualquer um que descobrisse a URL
     escrevia estado financeiro, e o `id` de preapproval do MP é
     sequencial. Agora confere `x-signature` (HMAC-SHA256 do manifesto
     `id:…;request-id:…;ts:…;` com o secret do painel) **antes** de tocar
     o banco ou sair para a rede. **Isto exige uma variável nova no
     ambiente: `ASSINATURA_MP_WEBHOOK_SECRET`** — o mesmo secret que o
     painel do MP mostra em *Webhooks › Configure notificação*. Sem ela o
     webhook é **fail-closed**: recusa tudo, loga ERROR no boot e nenhuma
     assinatura é confirmada por notificação. O aviso é proposital — com
     o segredo faltando, "funcionar" e "aceitar webhook de qualquer um"
     seriam a mesma configuração.
   - **Conferência de valor e moeda** antes de aceitar qualquer confirmação.
   - **Cancelamento agora chega ao provedor** (antes cancelava só aqui e o
     débito continuava ativo lá) e a conciliação reenvia se a primeira
     tentativa falhar.
   - **Renovação corrigida**: "pendente" do MP não é mais tratado como
     recusa (toda renovação caía em `inadimplente`), a referência da
     cobrança nova é gravada (o webhook da renovação não encontrava a
     assinatura), e há guarda contra cobrar o mesmo ciclo duas vezes.
   - **Existe conciliação** (`assinatura-reconciliar-com-provedor`, no
     Beat): compara o provedor com o banco e corrige — inclusive o caso em
     que o cliente pagou e a notificação se perdeu. Era o furo que prendia
     o assinante em `pagamento_pendente` para sempre.

   **O que ainda NÃO está validado (depende da credencial real):** o
   algoritmo HMAC-SHA256 da assinatura contra a implementação real do MP
   (os testes provam consistência interna, não que o MP usa o mesmo
   esquema — o provedor já teve um esquema md5 antes) e a forma real da
   resposta `GET /preapproval/<id>`. Até isso ser validado, o caminho
   seguro é o que está: falha fechada. Para validar: disparar um evento de
   teste pelo painel do MP e conferir no log que houve `confirmada`, e não
   `recusada` por `assinatura_nao_confere`. Detalhes e lista de testes:
   `backend/assinatura/tests/test_mercadopago_webhook.py`.
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
     admin Django autenticado em uma tarefa futura.
   - **Corte do cache e contratos locais:** as listagens do feed usam o
     namespace `feed:v2`; payloads legados em `feed:v1` não são lidos durante o
     corte. As operações locais de feed e robôs permanecem disponíveis, e a
     execução manual dos robôs continua respondendo `202 Accepted` e iniciando o
     trabalho em background.
   - **Ação operacional após o deploy:** em arquivos de ambiente preexistentes,
     remover `MICROSERVICO_INGESTAO_URL` e `INGESTAO_API_TOKEN` se ainda
     estiverem presentes. As flags não são mais lidas pelo Django; se
     permanecerem em uma VPS, são inertes e ainda exigem limpeza humana. Em
     cada VPS, inspecionar serviços/contêineres e volumes Mongo antigos,
     desligar o componente e remover o volume **somente após confirmar backup e
     necessidade dos dados**. Esta decisão de repositório **não acessou a VPS,
     não desligou a instância e não afirma que o banco Mongo ou seus volumes
     foram apagados**.

## Registro de conclusões

- 2026-09-25 — Cache de cliente com TanStack Query entregue (P1-6): os 22
  sites de carregamento de backend inventariados em 15 arquivos passam a ser
  gerenciados por hooks `useQuery` (27 hooks de leitura), com política
  conservadora aprovada pelo solicitante: memória-only, público 60 s,
  autenticado 15 s, decisão (Admin) 0 s, chaves sem token/PII (usuario.id
  apenas), logout limpa o cache privado e sem persistência. Mutations
  invalidam as queries afetadas. Check `verificar-query-client.mjs` na
  esteira de CI (job `frontend-build`) e como gate `verify` dos deploys.
  Validações: tsc 0 erros, build 59/59 páginas, smoke HTTP 25/25 rotas 200,
  tester 15/15 critérios passed, reviewer approve_with_comments (1 major
  corrigida durante o review). Run `20260924-1721-react-query-migracao`.
- 2026-09-17 — Leitura dentro do sistema entregue (`conteudo_completo` RSS +
  seção Matéria com crédito + CTA para a fonte).
- 2026-09-17 — Caminho Docker do DEPLOY.md validado local (builds, up,
  healthz, feed, superuser). Correção: `frontend/Dockerfile`, `.dockerignore`
  e `.env.local.example` convertidos de UTF-16 para UTF-8 (BuildKit quebrava).

---

## Lote P0-1 — Baseline de proveniência e gate de release (decisões)

> Seção adicionada pelo lote P0-1 da run `20260925-1433-go-live-producao`.
> Nenhuma seção anterior deste arquivo foi reescrita. Nenhum workflow,
> gatilho, job, secret ou environment foi alterado, criado ou removido.

### Decisões registradas

1. **Gate de proveniência entregue como ferramenta, não como pipeline.**
   `scripts/release/verificar-proveniencia.sh` é read-only, fail-closed, sem
   rede, sem segredo e determinístico (`0` aprovado, `1` reprovado/incompleto,
   `2` uso incorreto). Detalha uso, contrato e cobertura em `CI-CD.md`.
2. **Nenhum pipeline foi alterado.** O gate não é executado por nenhum
   workflow e não é today nenhum required status check.
3. **A eficácia do gate depende de configuração humana (HD-2 / HD-6).** Só
   bloqueia de fato com branch protection do GitHub (PR obrigatório) **e**
   registro como required status check. Branch protection sozinha, sem check
   registrado, não torna o gate obrigatório. HD-2 e HD-6 são pré-requisitos
   de eficácia, não de entrega, e não bloqueiam o go-live.
4. **Verificação de `backend/config/settings.py`, sem correção.** O gate G1
   (P0-02) validou o arquivo com `ast.parse` e `compile()` in-memory: válido
   no estado atual, sem `__pycache__` gerado e sem uma única edição. O
   `manage.py check` foi **pulado com motivo registrado** (o `settings.py`
   carrega `backend/.env` no import, o que exigiria acesso a segredo, vedado
   a este lote). A correção de conteúdo, se necessária, é o lote **P0-02b /
   GP-1b**, não este.
5. **`.github/` permanece byte a byte intocado.** Comprovado por `sha256` de
   todos os arquivos de `.github/` antes e depois, e por `git status`/`git
   diff` vazios para esse caminho.

### R-1 — supply chain PR → VPS: ACEITO, ABERTO, NÃO MITIGADO, NÃO COBERTO PELO GATE

- **Fato atual, inalterado:** `.github/workflows/deploy-homolog.yml` dispara
  em `pull_request` para `main` e implanta o head do pull request na VPS
  persistente que hospeda HOMOLOG (`/home/apps/portal-homolog`, 3102/5102,
  via `deploy.yml` com `git_mode: pr` e `verify_ref` do SHA do head do PR).
  Código de pull request não aprovado pode rodar em uma máquina que tem
  segredos.
- **Situação padronizada: ACEITO** (decisão do solicitante) e, por isso,
  **NÃO BLOQUEANTE para o go-live**; permanece **ABERTO**, **não mitigado**,
  **não bloqueado** e **NÃO COBERTO PELO GATE** (o gate inspeciona o
  repositório local e não participa de nenhum pipeline).
- **Aceite explícito e assinado no go/no-go é obrigatório**, com: qual é o
  caminho afetado, o que está sendo aceito, por quanto tempo e quem assinou.
  O go/no-go lista R-1 como **aceito**, nunca como resolvido.
- A decisão futura sobre substituir o caminho PR → VPS é de **lote próprio com
  revisão de CI/CD** (**HD-1**) e não é precondição de lançamento.
- Nenhum artefato deste lote pode afirmar ou sugerir que R-1 foi resolvido,
  mitigado, bloqueado ou coberto pelo gate.

### R-2 — divergência de domínio: ABERTO, registrada

O canônico do programa é `https://portal-noticias.com/`; os workflows usam
`portal-noticias.com.br` (DEV/HOMOLOG/PROD e `www`). Registrado como
pendência de lote posterior, sem alteração de workflow, gatilho ou
comportamento. Nenhum valor de domínio em workflow foi alterado.

### Pendências humanas que continuam abertas

| ID | Pendência | Efeito |
|---|---|---|
| **HD-1** | Decisão futura sobre substituir o caminho PR → VPS (lote próprio com revisão de CI/CD) | Não bloqueia o go-live; bloqueia a alegação de que a supply chain está fechada |
| **HD-2** | Branch protection no GitHub com PR obrigatório + registro de evidência | Pré-requisito de eficácia do gate; não entregue por este lote; não bloqueia o go-live |
| **HD-3** | SHA/branch de release e política de promoção (o SHA é re-derivado por `git rev-parse HEAD` a cada execução) | Uso de `--expected-sha` em promoção real |
| **HD-5** | Reconciliação formal das runs abertas e dos arquivos não atribuídos | Este lote apenas registra a atribuição |
| **HD-6** | Onde o gate rodará de forma recorrente, já que nenhum workflow pode ser alterado | Eficácia operacional; não bloqueia a entrega do script |

Evidência completa do lote:
`agentic-framework/state/run-20260925-1433-go-live-producao/lote-p0-1-evidencias.md`.
