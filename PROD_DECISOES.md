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

## Decisões do Bloco C2 — deploy (2026-09-25, run `20260925-1020-observabilidade`)

8. **Release atômica do TIER WEB, com o backend in-place** — o deploy prepara
   `frontend/releases/<id>/`, faz smoke nela e só então alterna o symlink
   `current`; a anterior fica em `previous` e é o retorno de um comando. O
   backend **não** foi movido para release: `git reset --hard` + `migrate` no
   lugar preservam `backend/.env` e `backend/media/` (untracked), reaproveitam
   o `.venv` e não exigem mover as units systemd, os scripts de backup e a
   árvore de mídia — centenas de MB por release numa VPS de 4 GB, sem ganho de
   atomicidade. Symlink só promove o que não tem migration. **O que isto não
   é:** blue-green nem zero downtime; continua havendo janela de restart, e o
   ganho é reversibilidade. Marker `.deployed-sha`, `concurrency` sem
   cancelamento, `strict_validate` e o caminho `git_mode: rollback` seguem
   intactos.
9. **A estratégia de build NÃO mudou: continua compilando na VPS** (heap 1536
   MB, três stacks na mesma máquina). A §P1-5 apontava compilar no runner como
   follow-up, mas a troca exigiria resolver a divergência de domínio
   `.com` × `.com.br` (R-2, risco aberto da run de go-live) e o
   `NEXT_PUBLIC_*` embutido no bundle; refazer esse problema agora seria trocar
   um ganho pequeno por um risco grande. O que mudou foi **onde** o build vira
   release, não **quem** compila.
10. **O caminho novo de runtime tem escape hatch explícito** (`web_runtime`:
    `standalone` | `npm`). Remover o caminho `npm` é a última etapa da mudança,
    não uma parte dela: só depois de um deploy `standalone` validado num
    ambiente real com probes verdes.
11. **Retorno automático só no caminho "o processo não subiu"** — quando o PM2
    não fica `online` em 3 tentativas, `current` volta para `previous`, o
    processo sobe na anterior e o deploy **falha** mesmo assim, porque um exit
    0 promoveria no marker um SHA cuja release não está no ar. O caminho "o
    processo subiu mas o comportamento está ruim" **não** é automaticado: a
    decisão ali é de julgamento (a release pode ter migration, e desfazer não é
    automático), e o procedimento manual está em `infra/DEPLOY.md` §9.2.
12. **Celery no systemd é fail-open no deploy** — as units são instaladas e
    ativadas por ambiente, mas falha de Celery **não** derruba o deploy: web e
    API já estão no ar e o worker parado é degradação visível em
    `/health-detail`. Um deploy que caísse por causa do Celery seria pior que o
    Celery parado. Nenhum processo gerenciado pelo PM2 foi tocado.
13. **A senha do SSH continua lá; a chave é alternativa, não sucessora** — com
    `VPS_SSH_KEY`/`VPS_HOST_FINGERPRINT` configurados, a action oferece a senha
    primeiro e a chave depois (a ordem é do cliente SSH da action, não do
    workflow). Remover `VPS_PASSWORD` é operação que depende de acesso real à
    VPS e de um run verde autenticando só com a chave; o procedimento está em
    `infra/DEPLOY.md` §9.5.
14. **Source maps com fail-open, inclusive na falha de upload** — sem token o
    passo nem roda (fork/clone local); com token, uma falha de upload não
    reprova o build. Bloquear deploy por indisponibilidade do Sentry converteria
    um problema de diagnóstico em indisponibilidade de deploy.
15. **O gate de infra no CI é estrito COM pendência declarada** — em vez de
    reprovar para sempre por um `runbook_url` com domínio reservado `.invalid`,
    o validador ganhou um terceiro estado: pendência declarada
    (`scripts/observability/pendencias-ci.txt`) é visível e não reprova;
    pendência **não** declarada reprova; chave declarada que não ocorre mais
    **falha** (lista envelhecida passaria a esconder pendência nova). Gate
    vermelho permanente acaba ignorado, que é pior que a pendência.
16. **`R-1` e `R-2` seguem abertos e fora do escopo desta mudança** — o script
    de proveniência (`scripts/release/verificar-proveniencia.sh`) continua fora
    de qualquer workflow (risco aceito, aberto, **não** coberto pelo gate, por
    decisão da run de go-live, com assinatura exigida no go/no-go), e a
    divergência de domínio `.com` × `.com.br` continua registrada e não
    corrigida. Registrados aqui como fronteira, sem mudança de status.

## Registro de conclusões

- 2026-09-25 — Deploy com release atômica, runtime standalone e Celery no
  systemd (C2, run `20260925-1020-observabilidade`): release do tier web com
  smoke antes da promoção por symlink, retorno automático quando o processo não
  sobe, `web_runtime` como escape hatch para o `npm start`, units do Celery
  instaladas por ambiente com os placeholders resolvidos, SSH com chave e host
  key pinados **mantendo a senha**, source maps fail-open e gate de infra
  estrito com pendência declarada. Validações reais: 6/6 workflows com YAML
  válido (`actionlint` 1.7.7 sem achado), `bash -n` nos 2 scripts embutidos, 9
  cenários de release e 5 de systemd executados contra as funções extraídas do
  workflow, e `validar-infra.sh --estrito` verde com a pendência declarada
  visível. **Não validado em VPS** (exige acesso real): o primeiro deploy com
  `standalone`, a ativação do Celery e o SSH por chave. Run
  `20260925-1020-observabilidade`; decisões 8-16 acima.
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
