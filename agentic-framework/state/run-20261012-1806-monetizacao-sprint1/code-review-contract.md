# Code Review Contract — 20261012-1806-monetizacao-sprint1

## Metadados
- **run_id:** 20261012-1806-monetizacao-sprint1
- **Escopo revisado:** diff completo `b1a33c6..HEAD` no worktree `monetizacao-sprint1` (M-01 a M-10, Sprint 1 do plano de monetização)
- **Contrato de referência:** `agentic-framework/state/run-20261012-1806-monetizacao-sprint1/implementation-contract.md`
- **Gatilhos aplicados:** cobrança/assinatura (M-07), API pública (M-01, M-02, M-10), direitos autorais/compliance BRD §18 (M-01), volume >300 linhas (3383+/101-)

## Findings

### Finding 1
- **Arquivo:** `backend/feed/services.py:68-99` (`itens_publicaveis`) e `backend/feed/services.py:255-267` (`entradas_sitemap`, reaproveita a mesma função); `frontend/app/sitemap.ts:14-28`
- **Linha:** `services.py:83-91` (janela de 72h), `services.py:263-267` (sitemap reaproveita sem remover a janela)
- **Categoria:** correctness (gap de escopo vs. intenção de negócio do item)
- **Severidade:** major
- **Resumo:** `entradas_sitemap()` reaproveita `itens_publicaveis()`, que filtra `timestamp_ingestao__gte = agora - FEED_JANELA_HORAS` (padrão 72h, confirmado em `.env.production.example:204` e `backend/config/settings.py:1435` — é o valor real de produção). Isso significa que nenhuma notícia com mais de 3 dias jamais aparece no `/sitemap.xml`, mesmo que ela continue publicável, indexável (com resumo) e ao vivo em `/noticia/<id>` sem `noindex`.
- **Cenário de falha:** uma notícia publicada há 4 dias, com `resumo_proprio` preenchido (passa o filtro de M-03, não tem `noindex`), `status_revisao` publicável — continua acessível e indexável em `/noticia/<id>`, mas `GET /api/feed/sitemap/` nunca a devolve, em nenhuma página, para sempre. O "porquê" declarado do próprio M-02 no plano é "o tráfego orgânico é a principal fonte de impressões… hoje nenhuma notícia está no sitemap" — a implementação resolve isso só para uma janela de 3 dias, depois volta a ser exatamente o problema original (notícia sem sitemap), sem nenhum teste cobrindo esse limite e sem nenhuma nota no `implementation-history.md` reconhecendo esse efeito colateral (a Iteração 4 só menciona a reutilização da janela como ganho de performance — "sem N+1 novo" — não como uma limitação de cobertura SEO). Não há endpoint nem lógica alternativa para o acervo mais antigo (`/arquivo` não tem entrada de sitemap própria).
- **Sugestão:** decidir explicitamente se a janela de 72h é aceitável para o sitemap (documentar a decisão) ou usar um filtro de publicabilidade/indexabilidade sem o corte de tempo em `entradas_sitemap()` (ex.: nova queryset sem `timestamp_ingestao__gte`, preservando `.only()`/paginação para não reintroduzir N+1).

### Finding 2
- **Arquivo:** `backend/assinatura/migrations/0003_seed_plano_semestral.py:14-22`
- **Linha:** 15-21
- **Categoria:** maintainability
- **Severidade:** minor
- **Resumo:** o `get_or_create(nome="Premium Semestral", ...)` só é idempotente para correspondência exata de nome; não há `unique=True` em `Plan.nome` (`backend/assinatura/models.py:15`).
- **Cenário de falha:** se alguém já tivesse cadastrado manualmente um plano chamado "Semestral Premium" ou "Premium semestral" (case/ordem diferente) antes do deploy desta migration, o banco passaria a ter dois planos semestrais quase idênticos ativos simultaneamente em `/planos`, confundindo o leitor. Baixa probabilidade (não há evidência de que isso exista hoje em nenhum ambiente), mas a migration roda sem checar por nomes parecidos.
- **Sugestão:** nenhuma ação obrigatória agora; se for prática comum do time cadastrar planos manualmente antes de uma migration de seed, vale um `Plan.objects.filter(nome__icontains="semestral")` de verificação antes do `get_or_create`, ou just documentar a premissa.

### Finding 3
- **Arquivo:** `backend/patrocinio/views.py:15` vs. `infra/nginx/portal-{prod,homolog,dev}.conf` (`portal-location-cache.conf`, TTL 45s)
- **Linha:** `views.py:15` (`_TTL_SEGUNDOS = 60`)
- **Categoria:** maintainability
- **Severidade:** nit
- **Resumo:** o TTL do cache de app de patrocínio (60s) é diferente do TTL do cache de borda do nginx (45s, mesmo valor usado por `feed/views.py` via `FEED_CACHE_TTL_SEGUNDOS`). O comentário do código diz "mesmo desenho do cache de `feed/views.py`", mas o valor numérico não é o mesmo.
- **Cenário de falha:** pior caso de defasagem para uma edição no admin (ex.: desativar um patrocínio) aparecer no ar: até ~105s (45s de borda + 60s de app), em vez dos ~45-90s esperados se os dois TTLs fossem iguais. Não é um bug funcional, só uma inconsistência de documentação/intenção.
- **Sugestão:** alinhar `_TTL_SEGUNDOS` a `FEED_CACHE_TTL_SEGUNDOS` (ou documentar por que é intencionalmente diferente).

## Pontos verificados e aprovados (sem finding)
- **M-01:** `conteudo` removido do serializer e do dict bruto do service; 3 testes HTTP reais confirmam ausência da chave. Nenhum consumidor órfão do campo removido (busca em `frontend/` só achou campos homônimos não relacionados). `conteudo_completo` no backend só é usado internamente (busca full-text).
- **M-02 (paginação/cache/N+1):** `SitemapView` paginada (500/página, máx. 1000), cacheada em app (45s), allowlist de borda nginx estendida corretamente nos 3 ambientes. `entradas_sitemap()` reaproveita `select_related`/`.only()` — sem N+1 novo. (A janela de 72h é o Finding 1, separado do ponto de performance.)
- **M-07:** migration idempotente para o caso normal. Cálculo de economia a partir de `preco`/`duracao_dias` reais da API — nenhum número fixo.
- **M-10 (datas/consentimento):** fronteiras inclusivas testadas nos dois extremos; 10 testes de backend reais. Tracking fail-closed antes de montar payload (confirmado lendo o código). Rótulo "Patrocinado" sempre visível.
- **Migration `TIPO_CHOICES` (M-10):** só `AlterField` de `choices`, sem mudança de schema.
- **M-05/M-08/M-09/M-10(frontend):** gate de Premium vem antes de qualquer ramo de anúncio/placeholder/cartão. Nenhuma palavra "AdSense"/"publicidade" em `CartaoPremium`. Nenhum preço/percentual/dado fabricado em nenhum dos quatro componentes.
- **Nenhuma fabricação de conteúdo/número/preço encontrada** em nenhum dos 10 itens.

## Resumo quantitativo
| Severidade | Quantidade |
|---|---|
| blocker | 0 |
| major | 1 |
| minor | 1 |
| nit | 1 |

## Veredito
**changes_requested**

Nenhum blocker (nada de segurança, corrupção de dados ou quebra de contrato não intencional). O Finding 1 (M-02: sitemap limitado à janela de 72h do feed, por herdar `itens_publicaveis()`) é `major` porque contradiz silenciosamente o próprio objetivo de negócio declarado para este item sem decisão explícita documentada nem teste cobrindo o limite. Findings 2 e 3 são observações de baixo risco, não bloqueantes.
