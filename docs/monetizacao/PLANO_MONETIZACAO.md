# Plano de monetização — Portal de Notícias

Documento de trabalho para executar no Claude Code, dentro deste repositório.
Base: leitura do código de `frontend/` e `backend/` em outubro/2026. Nada foi
rodado no navegador nem há métricas reais; por isso cada item traz o arquivo
de origem para conferência antes de mexer.

---

## 0. Como usar este plano no Claude Code

Abra o Claude Code na raiz do repositório e comece com:

> Leia `docs/monetizacao/PLANO_MONETIZACAO.md`. Execute o **Sprint 1** item por
> item, na ordem. Antes de cada item, confirme os arquivos citados e diga se o
> diagnóstico ainda bate com o código. Depois de cada item, rode
> `cd frontend && npm run typecheck && npm test` (e `cd backend && pytest` quando
> tocar o backend). Um commit por item, mensagem `monetizacao(M-XX): ...`.
> Não faça push.

Regras que valem para todos os itens:

- Nenhum script de anúncio pode ser carregado antes do consentimento. Isso é
  decisão LGPD do projeto e está protegido por `frontend/scripts/verificar-consentimento-anuncios.mjs`.
- Premium não vê anúncio. `podeExibirAnuncio` em `frontend/lib/anuncios.ts` é o
  ponto único dessa regra; não duplique a lógica em componentes.
- Nunca fabricar conteúdo, número ou fonte para preencher espaço (ver
  `backend/catalogo_noticias/providers/fallback_local.py`).
- Conteúdo patrocinado precisa ser identificado como tal (BRD §17).
- Mudança visual segue `.claude/skills/frontend-portal/SKILL.md` (tokens `--cor-*`,
  acessibilidade, `prefers-reduced-motion`, layout de 360 a 1440 px).

Itens marcados **[conta]** dependem da conta Google AdSense ou de parecer
jurídico. Podem ser preparados no código antes, mas não ficam completos sem isso.

---

## 0.1 Restrições de infraestrutura verificadas na VPS (12/10/2026)

Levantamento feito direto no host de produção via SSH, não no código — por
isso não tem arquivo de origem como os demais achados. Relevante porque
vários itens deste plano somam processo, endpoint ou script novo nos mesmos
três ambientes (dev/homolog/prod) que já rodam na mesma VPS, com recurso
limitado.

| Achado | Detalhe | Como afeta este plano |
|---|---|---|
| RAM apertada | Host tem só 3,8 GB de RAM total; uso observado entre 75% e 83% com os três ambientes (dev/homolog/prod) do portal rodando, cada um com backend + 2 processos Celery + Postgres + Redis próprios. | Itens que somam processo novo (M-10 `backend/patrocinio/`, M-13 painel/GA4, M-16/M-17) devem ser medidos em homolog antes do prod. Evitar rodar o Sprint 1 inteiro em paralelo nos três ambientes ao mesmo tempo; se faltar RAM durante os testes, considerar pausar o ambiente dev temporariamente. |
| Sem observabilidade de infraestrutura | Nenhuma ferramenta (Prometheus, Grafana, Netdata, Portainer, cAdvisor) rodando hoje no host. O único painel existente é texto, via `pm2 list` / `docker stats`. | M-13 cria medição de **negócio** (RPM, funil, conversão), mas nada hoje avisa se o host ficou sem RAM/CPU por causa do próprio rollout. Antes de M-02 e M-10 irem a produção — os dois que aumentam tráfego/requisição — vale pelo menos um monitor externo de uptime nos domínios (não consome recurso do host). |
| nginx já tem throttle e cache por rota | `portal-prod` tem zonas de rate-limit dedicadas (`portal-location-write*.conf`, `portal-location-auth*.conf`) e cache de borda para GET públicos (`portal-location-cache*.conf`, allowlist explícita de rotas de `feed`). | Todo endpoint GET público novo (M-02: lista de IDs para o sitemap; M-10: `GET /api/patrocinio/ativo/`) deve entrar nessa mesma allowlist de cache/throttle já existente, em vez de criar regra própria ou subir sem limite — o padrão de defesa em profundidade do projeto já existe, só falta estender para as rotas novas. |
| Build/imagens Docker acumulados | `docker system df` mostrava ~10,8 GB de imagens não usadas e ~15,8 GB de build cache reclamável (disco do host em 63% de uso). | Não bloqueia o Sprint 1, mas cada deploy novo (M-11, M-02, M-10) soma outra tag de imagem. Vale um `docker image prune` periódico no pipeline de deploy antes do disco se tornar um problema. |
| Backups agendados em horário fixo | cron do host dispara `pg_backup.sh` dos 3 ambientes entre 03h00 e 03h04. | Evitar agendar testes de carga/CWV (M-20) ou deploy (M-11) nesse horário, para não medir sob concorrência de I/O do backup. |

Esses achados não bloqueiam o Sprint 1 (é trabalho de código). Devem ser
checados **antes de M-02 e M-10 irem ao ar em produção**, por serem os dois
itens que aumentam tráfego/requisição no host com menos margem dos três
ambientes.

---

## 1. Diagnóstico resumido (estado atual)

| Área | Situação encontrada | Evidência |
|---|---|---|
| AdSense | Código pronto (`AdsSlot`, `AdsScript`, `ads.txt`, meta de verificação), sem publisher ID nem slots. Sem ID, todo slot vira placeholder visível. | `frontend/components/AdsSlot.tsx`, `frontend/app/ads.txt/route.ts`, `frontend/app/layout.tsx`, `frontend/.env.local` (comentado) |
| Slots por formato | Um slot por formato (`SLOT_POR_FORMATO`). Todas as posições horizontais compartilham o mesmo bloco no AdSense, então o relatório não diz qual posição rende. | `AdsSlot.tsx` |
| Densidade | Home com 10 slots, categoria com 4, leitura da notícia com 3, `/planos` com 1, `/buscar` com 2, `/arquivo` com 2. | grep de `<AdsSlot` |
| Placeholder | Usuário sem consentimento vê caixa "PUBLICIDADE • Anúncio — Google AdSense (slot …)", com altura de até 600 px no formato vertical. | `AdsSlot.tsx` (bloco `podeExibir` falso) |
| SEO / indexação | `sitemap.ts` tem 14 rotas fixas. Nenhuma notícia `/noticia/[id]` entra no sitemap. RSS existe e aponta para as notícias. | `frontend/app/sitemap.ts`, `frontend/app/rss/route.ts` |
| Conteúdo | O detalhe público envia `conteudo` (até 6.000 caracteres do texto raspado) em cada fonte. A página não usa o campo, mas ele é público no JSON. | `backend/feed/services.py` (`detalhe_cluster`, `detalhe_item`) |
| Notícia sem resumo | Quando o resumo não é gerado, a página pode ficar sem texto próprio e continua indexável. | `backend/catalogo_noticias/providers/fallback_local.py` (resumo vazio é o comportamento honesto) |
| Premium | Cartão Premium único em `/planos` (variável `premium`). O BRD §6 prevê semestral (R$20) e anual (R$30). Não há chamada para assinar dentro da leitura da notícia. | `frontend/app/planos/page.tsx`, `frontend/app/noticia/LeituraPremium.tsx`, BRD §6 |
| Analytics | Central de eventos própria, com consentimento de `analytics`. Sem GA4/GTM. Não há métrica de RPM nem de funil. | `frontend/lib/analytics.ts`, `frontend/lib/anuncios.ts` (`GA4_NAO_IMPLEMENTADO = true`), `backend/metricas/models.py` (`EventoSite`) |
| Newsletter | Envio real já existe (`enviar_newsletters`), mas o corpo é texto puro. Já inclui uma linha para `/planos`. Gate de entrega real via `canal_entrega_real()`. | `backend/newsletter/services.py` (`montar_corpo_email`, `enviar_newsletters`) |
| Trial | BRD §9 prevê período de teste; não está ativado. | BRD §9, `backend/assinatura/` |
| Consentimento | Anúncio só com categoria `personalizacao`. Quem recusa não vê anúncio nenhum. | `frontend/lib/anuncios.ts` (`CATEGORIA_CONSENTIMENTO_ANUNCIO`), `frontend/components/BannerConsentimentoCookies.tsx` |

---

## 2. Backlog priorizado

Cada item traz: **por que** (receita ou risco), **onde** (arquivos), **como**
(passos), **aceite** (critério de pronto) e **dependência**.

### Sprint 1 — sem depender da conta AdSense

#### M-01 · Remover conteúdo raspado da API pública
- **Por quê:** risco de direito autoral e de reprovação do AdSense por conteúdo copiado. Contraria BRD §18.
- **Onde:** `backend/feed/services.py` (`detalhe_cluster`, `detalhe_item`); `frontend/lib/api.ts` (tipos de `FeedDetalhe`).
- **Como:** remover a chave `conteudo` do dicionário público. Se a análise interna precisar do texto, expor só em rota autenticada de admin. Atualizar o tipo TypeScript correspondente.
- **Aceite:** `GET /api/noticias/<id>` não contém `conteudo`. Teste novo em `backend/feed/tests/` garante a ausência. `npm run typecheck` e `pytest` passam.
- **Dependência:** nenhuma.

#### M-02 · Sitemap com notícias
- **Por quê:** o tráfego orgânico é a principal fonte de impressões. Hoje nenhuma notícia está no sitemap.
- **Onde:** `frontend/app/sitemap.ts`; novo endpoint leve em `backend/feed/` (lista de `id`, `timestamp`, `categoria`, apenas itens publicáveis, com paginação).
- **Como:** `sitemap.ts` passa a buscar os IDs publicáveis e gerar `/noticia/<id>` com `lastModified` do timestamp. Mantém as rotas fixas. Se passar de 50 mil URLs, usar `generateSitemaps`. Considerar também `/autor/*` e `/editorias/*`.
- **Aceite:** `/sitemap.xml` lista notícias publicáveis. Teste em `frontend/testes/` valida formato e ausência de notícias não publicáveis.
- **Dependência:** M-03 (noindex) deve vir antes, para não indexar notícias sem resumo.
- **Nota de infra (§0.1):** o endpoint novo é GET público e repetido a cada rebuild do sitemap — reaproveitar a allowlist de cache de borda já existente (`portal-location-cache*.conf`) em vez de bater direto no backend sem cache. O host tem só 3,8 GB de RAM compartilhados entre os 3 ambientes.

#### M-03 · Não indexar notícia sem resumo próprio
- **Por quê:** páginas finas prejudicam a qualidade do site para o AdSense e para o Google.
- **Onde:** `frontend/app/noticia/[id]/page.tsx` (`generateMetadata`).
- **Como:** se `d.fontes[0].resumo` estiver vazio, devolver `robots: { index: false, follow: true }`. Não remover a página: o leitor ainda pode abri-la pelo link.
- **Aceite:** notícia sem resumo gera `<meta name="robots" content="noindex, follow">`. Teste em `frontend/testes/jsonld.test.mjs` ou novo arquivo.
- **Dependência:** nenhuma.

#### M-04 · Um slot por posição, não por formato
- **Por quê:** sem isso, o AdSense não diz qual posição rende. É a base para otimizar qualquer outro item.
- **Onde:** `frontend/components/AdsSlot.tsx`; todos os pontos de montagem (`HomeClient.tsx`, `LeituraPremium.tsx`, `categoria/[slug]/page.tsx`, `buscar/page.tsx`, `arquivo/page.tsx`, `planos/page.tsx`, `SecaoRegiao.tsx`, `comunidade/*`, `radar/RadarClient.tsx`).
- **Como:**
  1. Trocar `SLOT_POR_FORMATO` por uma prop `slot` opcional. Quando ausente, usar o padrão do formato.
  2. Criar um mapa centralizado em `frontend/lib/anuncios.ts` com um nome de variável de ambiente por posição (`NEXT_PUBLIC_ADSENSE_SLOT_HOME_TOPO`, `..._NOTICIA_TOPO`, `..._NOTICIA_POS`, `..._CATEGORIA_INFEED` etc.).
  3. Atualizar `.env.example` (ou o comentário do `.env.local`) com a lista.
  4. Não mudar o comportamento de consentimento nem de Premium.
- **Aceite:** cada `AdsSlot` gera `data-ad-slot` distinto quando o env existe. Teste em `verificar-consentimento-anuncios.mjs` cobre que nenhum slot novo carrega script sem consentimento.
- **Dependência:** [conta] para criar os blocos no AdSense. O código pode sair antes.

#### M-05 · Tirar o placeholder visível e colapsar o espaço
- **Por quê:** "Anúncio — Google AdSense (slot …)" é texto técnico para o leitor. A caixa de 600 px cria buracos. Isso prejudica a experiência e a confiança.
- **Onde:** `frontend/components/AdsSlot.tsx` (ramo `podeExibir` falso).
- **Como:**
  1. Para Free sem consentimento: não renderizar nada. Mostrar, no lugar, um cartão curto "Leia sem anúncios — Premium a partir de R$ X" (ver M-09), com o mesmo tamanho mínimo do formato, sem texto técnico.
  2. Para o caso sem publisher ID configurado: não renderizar nada em produção. Manter o placeholder só em `NODE_ENV !== "production"`, para desenvolvimento.
  3. Remover a dependência de "slot {id}" no texto.
- **Aceite:** em produção, nenhum texto com "Google AdSense" aparece para o leitor. Em tela de 360 px, nenhum bloco vazio de mais de 120 px sem conteúdo. Revisar contraste AA do cartão.
- **Dependência:** nenhuma para o placeholder. O cartão Premium depende de M-09.

#### M-06 · Reduzir densidade de anúncios
- **Por quê:** excesso de anúncio derruba o tempo de leitura e o RPM por visita, e pode reprovar a conta.
- **Onde:** `HomeClient.tsx` (10 slots para 4 ou 5), `LeituraPremium.tsx` (3 para 2), `planos/page.tsx` (remover), `buscar/page.tsx` (manter 1), `arquivo/page.tsx` (manter 1), `categoria/[slug]/page.tsx` (manter 1 topo e 1 in-feed a cada 9 itens, no lugar de 6).
- **Como:** remover slots de posições redundantes, especialmente `home-sidebar-2`, `home-footer` (já removido) e os de `home-pos-*`. Priorizar `noticia-topo` e `noticia-pos`, que têm o leitor mais engajado.
- **Aceite:** contagem de `<AdsSlot` em cada arquivo conforme a meta. Rodar `npm run build` e conferir que nenhuma página quebra.
- **Dependência:** nenhuma. Meta a validar com o RPM depois de M-04 e [conta].

#### M-07 · Página de planos com as duas assinaturas do BRD
- **Por quê:** o BRD §6 prevê semestral (R$20) e anual (R$30). Hoje só existem os planos `free` e `premium` ativos no banco — falta o semestral. Mostrar a anual como melhor preço, com o total equivalente do semestral, aumenta a conversão.
- **Onde:** `frontend/app/planos/page.tsx`; `backend/assinatura/views.py` (`PlanosListView`, `Plan.objects.filter(ativo=True)`).
- **Como:** **[revalidado em 12/10/2026 — premissa mudou]** `planos/page.tsx` já não é um cartão fixo: já usa `useQueryPlanos()` e já renderiza todos os planos ativos vindos da API. O trabalho que falta é menor do que a versão original deste item descrevia:
  1. Cadastrar o plano semestral (R$20) no admin/banco, ativo.
  2. Confirmar se o cálculo de "Economize X%" entre durações já existe no componente; se não existir, escrever a partir dos dados dos planos (preço e duração) — nunca com número fixo.
  3. Destacar visualmente o plano de maior duração/melhor custo por mês.
- **Aceite:** com três planos ativos (`free`, premium semestral, premium anual), a página mostra os cartões corretos e o destaque de economia. Teste de snapshot ou de renderização em `frontend/testes/`.
- **Dependência:** nenhuma. Os preços continuam editáveis no admin (BRD §6).

#### M-08 · Chamada para assinar dentro da leitura
- **Por quê:** a leitura da notícia é o momento de maior intenção e hoje não tem nenhuma chamada para o Premium.
- **Onde:** `frontend/app/noticia/LeituraPremium.tsx`.
- **Como:** após o resumo, um cartão discreto "Leia sem anúncios e receba o resumo da manhã por e-mail", com link para `/planos`. Mostrar só para Free (não para Premium, usando `usePremiumAtivo` e o papel do usuário, como em `AdsSlot`). Não usar pop-up.
- **Aceite:** Premium não vê o cartão. Free vê uma vez por página. Link tem `aria-label` claro e alvo de 44 px.
- **Dependência:** nenhuma.

#### M-09 · Cartão "sem anúncios" como substituto do anúncio
- **Por quê:** o espaço que não tem anúncio (consentimento recusado, ou sem publisher) vira oportunidade de conversão em vez de buraco. Liga M-05 a M-07.
- **Onde:** `frontend/components/AdsSlot.tsx` (usar o novo componente `CartaoPremium`, a ser criado em `frontend/components/`).
- **Como:** o componente recebe `formato` e mostra um texto curto, o preço mais baixo ativo e o link para `/planos`. Não usar a palavra "publicidade" nem "AdSense".
- **Aceite:** o cartão é renderizado para Free sem consentimento. Não aparece para Premium. Passa em teste de contraste.
- **Dependência:** M-07 (para mostrar o preço real).

#### M-10 · Patrocínio identificado (receita direta, sem AdSense)
- **Por quê:** anúncio direto costuma render mais por impressão do que AdSense em portal de nicho, e não depende de conta nem de consentimento. BRD §5 e §17 já preveem.
- **Onde:** novo app `backend/patrocinio/` (modelo `Patrocinio`: anunciante, criativo, URL, posição, datas de início e fim, ativo); novo componente `frontend/components/PatrocinioSlot.tsx`; ponto de montagem na newsletter (M-13) e no Radar.
- **Como:**
  1. Modelo com validação de datas e posição. Admin para cadastro.
  2. Endpoint público `GET /api/patrocinio/ativo/?posicao=...` com cache curto — reaproveitar o include de cache de borda do nginx (`portal-location-cache*.conf`, ver §0.1) em vez de criar regra nova; manter a allowlist explícita por rota como o projeto já faz para `/api/feed/*`.
  3. Componente exibe rótulo "Patrocinado" visível, link com `rel="sponsored nofollow noopener"`, imagem com `alt` e dimensões fixas.
  4. Registrar cliques e impressões no `EventoSite` (novos tipos `patrocinio_view` e `patrocinio_click`), respeitando consentimento de `analytics`.
- **Aceite:** patrocínio fora da data não aparece. Rótulo "Patrocinado" sempre presente. Teste de backend para datas e de frontend para o rótulo.
- **Dependência:** definir com o responsável o que é um "espaço" comercial e a tabela de preço. Não há número inventado no código.

### Sprint 2 — com a conta AdSense e medição

#### M-11 · Publisher ID, slots e ads.txt em produção [conta]
- **Onde:** **[revalidado em 12/10/2026]** as variáveis `NEXT_PUBLIC_ADSENSE_CLIENT_ID`/`NEXT_PUBLIC_ADSENSE_SLOT_*` aparecem em 5 workflows, não só `deploy-prod.yml`: `deploy-prod.yml`, `deploy-homolog.yml`, `deploy-dev.yml`, `deploy.yml` e `deploy-pm2.yml`.
- **Como:** criar os blocos no AdSense conforme M-04. Preencher as variáveis nos workflows realmente ativos — confirmar primeiro se `deploy-pm2.yml` ainda está em uso: é o reutilizável **antigo** (PM2+Nginx); a VPS de produção hoje roda o portal-noticias inteiro via Docker (nenhum processo PM2 de `portal-*` ativo, só containers), então esse workflow pode ser resíduo da migração para Docker ainda não limpo. Se for código morto, não preencher as variáveis lá e considerar um item de limpeza separado (fora deste plano). Rebuild do frontend (as variáveis `NEXT_PUBLIC_*` entram no bundle no build). Validar `GET /ads.txt` com a linha `google.com, pub-…, DIRECT, f08c47fec0942fa0`.
- **Aceite:** `/ads.txt` responde 200 com o publisher correto. Google confirma a verificação do site.
- **Status (12/10/2026, confirmado pela sessão "Finalizar configuração do AdSense (Fase 2)"):** publisher ID (`ca-pub-8444783404549240`) e `/ads.txt` **já estão em produção e funcionando**. O que falta é só os slot IDs por posição — e isso está bloqueado: o site ainda está "em preparação" no painel do Google AdSense, que só libera a criação manual de blocos de anúncio depois de aprovar o site. Não dá para acelerar essa aprovação. Hoje `AdsSlot.tsx` só lê 4 env vars por **formato** (`NEXT_PUBLIC_ADSENSE_SLOT_HORIZONTAL/_RETANGULO/_VERTICAL/_INFEED`, todas vazias) — exatamente o problema que M-04 corrige. Na prática, M-11 (parte de slots) só fica útil depois de M-04 mudar para variáveis por posição; até a aprovação do Google chegar, o único trabalho real aqui é código (M-04), não configuração de conta.
- **Sem colisão confirmada:** aquela sessão só vai configurar os secrets/deploy quando o Google aprovar e ela tiver os slot IDs em mãos; não está tocando `AdsSlot.tsx`, M-04 ou M-12.

#### M-12 · Formato in-feed correto [conta]
- **Por quê:** o slot in-feed hoje usa `data-ad-format="auto"`. Anúncio in-feed do AdSense é do tipo `fluid`, com `data-ad-layout-key` gerado pelo próprio AdSense.
- **Onde:** `frontend/components/AdsSlot.tsx` (formato `in-feed`).
- **Como:** para `in-feed`, `data-ad-format="fluid"` e `data-ad-layout-key` vindo de env por posição. Manter `auto` para os demais.
- **Aceite:** nenhum slot in-feed sem layout-key. Teste estático em `verificar-consentimento-anuncios.mjs`.

#### M-13 · Medição de RPM e funil [conta para GA4]
- **Por quê:** sem medição, qualquer decisão de densidade ou posição é palpite.
- **Onde:** `frontend/lib/analytics.ts` (evento com `slot` e `posicao`), `backend/metricas/` (painel de RPM por posição usando os dados do AdSense exportados ou de `EventoSite`), e opcionalmente GA4 em `frontend/app/layout.tsx`.
- **Como:**
  1. Já: incluir `posicao` em `page_view`, `news_view` e nos cliques de patrocínio, todos com consentimento de `analytics`.
  2. Com conta: GA4 carregado somente após consentimento de `analytics`, com Consent Mode v2 em modo "denied" por padrão. Atualizar `GA4_NAO_IMPLEMENTADO` e a guarda de regressão.
  3. Painel interno: conversão Free → Premium, taxa de aceite de consentimento e leitura por posição.
- **Aceite:** painel mostra taxa de consentimento e leitura por posição. Nenhuma requisição ao Google antes do consentimento (já verificada em runtime pela guarda).
- **Dependência:** [conta] para GA4. A parte interna não depende de conta.
- **Nota de infra (§0.1):** este painel mede negócio (RPM, funil), não infraestrutura. O host de produção não tem hoje nenhuma observabilidade de RAM/CPU/containers (sem Prometheus, Grafana, Netdata ou Portainer) — se o tráfego crescer por causa de M-02/M-10/M-11, nada avisa sozinho se o host (3,8 GB de RAM) ficou sem margem. Considerar, em paralelo, um monitor externo leve (ex. uptime nos domínios) antes de escalar tráfego.

#### M-14 · Trial de 7 dias (BRD §9) [conta de teste opcional]
- **Por quê:** o trial é a alavanca de conversão mais testada em assinatura. O BRD já prevê.
- **Onde:** `backend/assinatura/` (modelo de plano ou configuração com `duracao_trial_dias`), `frontend/app/planos/page.tsx`.
- **Como:** configuração no admin, desativada por padrão. Quando ativa, o botão diz "Começar teste grátis de 7 dias" e o período aparece no resumo. Cancelamento antes do fim não cobra (testar).
- **Aceite:** trial ativo gera status `teste` (BRD §9). Teste de backend cobre transição para `ativa` e para `expirada`.
- **Dependência:** definir com o responsável se o trial exige cartão. Não assumir.

#### M-15 · Régua de lembrete para Free engajado
- **Por quê:** quem lê muito e não assina é o público mais barato de converter.
- **Onde:** `frontend/lib/` (contador de leituras por visitante, em `localStorage` com try/catch, apenas como conveniência), `frontend/app/noticia/LeituraPremium.tsx`.
- **Como:** após a 5ª notícia lida no mês, mostrar o cartão de M-08 com texto de "você já leu X notícias este mês". Não bloquear conteúdo. Respeitar o limite de Free definido em `gating` (ver `backend/gating/`).
- **Aceite:** o contador não sai do navegador. Sem consentimento, o contador não é gravado (é preferência técnica, mas por segurança tratar como `personalizacao`).
- **Dependência:** M-08.

### Sprint 3 — receita recorrente e compliance

#### M-16 · Newsletter com bloco patrocinado e upgrade
- **Por quê:** a newsletter tem envio real e lista própria. É o canal de maior retorno por assinante.
- **Onde:** `backend/newsletter/services.py` (`montar_corpo_email`).
- **Como:**
  1. Acrescentar linha "Patrocinado: …" quando houver patrocínio ativo para `newsletter` (M-10), com rótulo visível.
  2. Hoje o corpo é texto puro. Criar versão HTML com o mesmo conteúdo (sem alterar a versão texto), mantendo o descadastro e o link de confirmação.
  3. Adicionar um bloco de upgrade para Free, sem repetir o mesmo texto em toda edição (rodízio de 3 mensagens).
- **Aceite:** teste de backend garante o rótulo "Patrocinado" e a presença do link de descadastro. Envio só ocorre com `canal_entrega_real()` verdadeiro.
- **Dependência:** M-10. Entregabilidade depende do provedor (`config/email_resend.py`).

#### M-17 · Patrocínio por editoria e Radar
- **Onde:** `frontend/components/SecaoRegiao.tsx`, `frontend/app/radar/RadarClient.tsx`, `frontend/app/categoria/[slug]/page.tsx`.
- **Como:** "Editoria apresentada por …" ou "Radar em parceria com …", sempre com rótulo e rel `sponsored`. Usar o componente de M-10 com posição específica.
- **Aceite:** rótulo visível em todas as posições. Nenhum patrocínio aparece em notícia com `status_revisao` diferente de publicável.
- **Dependência:** M-10. Acordo comercial com o responsável.

#### M-18 · Parecer jurídico sobre consentimento e anúncios não personalizados [jurídico]
- **Por quê:** é a maior alavanca de receita escondida. Quem recusa "personalização" hoje não vê anúncio. Anúncios não personalizados (NPA) e Consent Mode v2 podem recuperar parte dessa receita, mas a decisão é jurídica, não de código.
- **Onde:** `frontend/lib/anuncios.ts`, `frontend/components/AdsScript.tsx`, texto do banner.
- **Como:** levar ao jurídico a pergunta: é possível servir anúncio não personalizado (sem cookie de perfil) para quem recusou, com aviso claro, à luz da LGPD e da política do Google? Só implementar depois do parecer, com a categoria de consentimento correspondente.
- **Aceite:** parecer por escrito. Se positivo, implementar em feature flag e medir.
- **Não fazer:** carregar o script do AdSense antes do consentimento sem o parecer. Isso contraria o próprio projeto e a LGPD.

#### M-19 · Revisar o banner de consentimento sem padrões escuros
- **Por quê:** taxa de aceite é receita. Mas banner enganoso ou com recusa escondida prejudica a marca e pode gerar ação da ANPD.
- **Onde:** `frontend/components/BannerConsentimentoCookies.tsx`.
- **Como:** "Aceitar" e "Recusar não essenciais" com o mesmo peso visual e o mesmo número de cliques. Texto que explica o benefício real do consentimento (anúncios com menos repetição e personalização).
- **Aceite:** ambos os botões com mesmo tamanho e contraste AA. Teste de acessibilidade.

#### M-20 · Performance e Core Web Vitals
- **Por quê:** LCP e CLS ruins derrubam o RPM e o ranqueamento.
- **Onde:** `frontend/app/page.tsx` (carrega 60 itens na home), `frontend/components/AdsSlot.tsx` (reserva de altura já existe).
- **Como:** medir com PageSpeed antes e depois. Reduzir a home para o necessário no primeiro render, carregar o restante sob demanda. Manter `lazyOnload` do AdSense.
- **Aceite:** CLS abaixo de 0,1 e LCP abaixo de 2,5 s em mobile nas páginas de notícia e home.
- **Nota de infra (§0.1):** medir fora da janela de backup do host (03h00–03h05) e, se possível, comparar homolog e prod sabendo que os três ambientes competem pela mesma RAM (3,8 GB) — um resultado ruim pode ser contenção do host, não regressão do código.

#### M-21 · Política de anúncios e conteúdo
- **Por quê:** evitar reprovação e suspensão da conta AdSense.
- **Onde:** `frontend/app/termos/`, `frontend/app/cookies/`, `frontend/app/privacidade/`.
- **Como:** revisar com o jurídico: política de anúncios, rotulagem de patrocínio, conflito de interesse (BRD §17) e uso de imagens de terceiros (BRD §18). Conferir também `frontend/app/paginas/` e `frontend/app/comunidade/` (conteúdo gerado por usuário).
- **Aceite:** páginas publicadas e atualizadas. Checklist assinado pelo responsável.

#### M-22 · Afiliados (não recomendado agora)
- **Por quê:** receita fácil, mas conflita com a posição do produto (BRD §3, curadoria sem vínculo comercial) e exige rotulagem clara. Só avaliar depois que o patrocínio (M-10) estiver rodando.
- **Como:** se for feito, usar a mesma regra de rotulagem de patrocínio e nunca em notícia.

#### M-23 · B2B como receita de médio prazo
- **Por quê:** o app `backend/b2b/` já existe. O BRD §19 prevê monitoramento por empresa e setor. Não é um ajuste de código agora; é produto.
- **Como:** tratar em outro documento. Este plano só registra a dependência: a audiência de M-02 e M-13 é o que torna o B2B vendável.

---

## 3. Roadmap resumido

| Sprint | Itens | Depende de |
|---|---|---|
| 1 (agora, sem conta) | M-01, M-03, M-02, M-04, M-05, M-06, M-07, M-08, M-09, M-10 | nada externo |
| 2 (com conta AdSense) | M-11, M-12, M-13, M-14, M-15 | conta AdSense, GA4 opcional |
| 3 (receita e compliance) | M-16, M-17, M-18, M-19, M-20, M-21 | parecer jurídico, acordos comerciais |
| Estratégico | M-22, M-23 | medição de audiência |

Ordem interna do Sprint 1: M-01 e M-03 primeiro (correções de risco), depois
M-02 (sitemap), M-04 (slots), M-05 e M-06 (densidade e placeholder), M-07 a M-09
(conversão) e por último M-10 (patrocínio).

Antes de M-02 e M-10 irem a produção (são os dois que aumentam tráfego/
requisição), checar §0.1 — host com só 3,8 GB de RAM compartilhado entre os
3 ambientes e sem observabilidade de infraestrutura hoje.

---

## 4. Métricas para acompanhar

- RPM por posição (quando M-04 e M-11 estiverem prontos).
- Taxa de aceite do consentimento de anúncio (M-13, evento interno).
- Conversão de Free para Premium, por origem (cartão da leitura, cartão do slot, planos, newsletter).
- Páginas de notícia indexadas e sessões orgânicas (Search Console, após M-02).
- Receita de patrocínio por posição e por período (M-10).
- CLS e LCP em mobile (M-20).

Meta inicial sugerida, a validar com dados reais: 2 slots por leitura, no máximo 5 na home, cartão Premium em todo espaço que ficaria vazio.

---

## 5. Itens para não fazer

- Carregar AdSense ou qualquer script de terceiros antes do consentimento.
- Mostrar anúncio ou cartão de assinatura a Premium.
- Esconder a recusa de cookies ou usar botão de recusa menor (padrão escuro).
- Patrocínio sem rótulo visível.
- Inventar número de audiência, preço ou resultado para preencher uma tela.
- Usar texto de notícia raspado como conteúdo público (ver M-01).
- Subir endpoint público novo sem reaproveitar os includes de rate-limit/cache
  do nginx já existentes (ver §0.1) — o host de produção tem só 3,8 GB de RAM
  e pouca margem, compartilhada entre os 3 ambientes.

---

## 6. Verificação ao final de cada sprint

Frontend:

```
cd frontend
npm run typecheck
npm test
npm run build
```

Backend:

```
cd backend
pytest
```

Checagem manual, em 360, 768, 1024 e 1440 px, com tema claro e escuro:
home, uma notícia (com e sem resumo), uma categoria, `/planos`, `/buscar`,
e a newsletter (e-mail de teste). Confirmar que Premium não vê anúncio nem
cartão de assinatura, e que Free sem consentimento não vê texto técnico.

Ao concluir, registrar o resultado em `docs/monetizacao/RESULTADOS.md` com data,
itens concluídos e pendências.
