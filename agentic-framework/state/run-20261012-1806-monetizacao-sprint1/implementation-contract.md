# Implementation Contract — 20261012-1806-monetizacao-sprint1

## Metadados
- **run_id:** 20261012-1806-monetizacao-sprint1
- **Deriva de:** task-plan.md (20261012-1806-monetizacao-sprint1)
- **Versão do contrato:** 1

## O que deve ser construído
Os 10 itens do Sprint 1 de `docs/monetizacao/PLANO_MONETIZACAO.md`, na ordem
definida na seção 3 do próprio documento: **M-01, M-03, M-02, M-04, M-05,
M-06, M-07, M-08, M-09, M-10**. Cada item é uma unidade de commit própria
(`monetizacao(M-XX): <resumo>`), com `npm run typecheck && npm test`
(frontend) e/ou `pytest` (backend) passando antes do commit do item
seguinte. O "Como" de cada item, como descrito no plano, é a especificação
técnica — não repetir aqui, mas o executor deve ler o arquivo inteiro antes
de começar, e revalidar cada item contra o código atual do zero (o plano já
tem duas correções registradas como "[revalidado em 12/10/2026]" em M-07 e
M-11 — confira-as antes de tocar M-07).

## Áreas/arquivos esperados
- `backend/feed/services.py`, `backend/feed/tests/` (M-01, M-02)
- `frontend/lib/api.ts` (M-01 — tipos de `FeedDetalhe`)
- `frontend/app/sitemap.ts`, `frontend/testes/` (M-02)
- `frontend/app/noticia/[id]/page.tsx` (M-03)
- `frontend/components/AdsSlot.tsx`, `frontend/lib/anuncios.ts`, `.env.example`/`.env.local` (comentário) (M-04, M-05, M-09)
- Todos os pontos de montagem de `<AdsSlot` — levantar com `grep -rn "<AdsSlot" frontend/` no início, não confiar só na lista do plano (`HomeClient.tsx`, `LeituraPremium.tsx`, `categoria/[slug]/page.tsx`, `buscar/page.tsx`, `arquivo/page.tsx`, `planos/page.tsx`, `SecaoRegiao.tsx`, `comunidade/*`, `radar/RadarClient.tsx`) (M-04, M-06)
- `frontend/components/` — novo componente `CartaoPremium.tsx` (M-09)
- `frontend/app/planos/page.tsx`, `backend/assinatura/views.py`, `backend/assinatura/models.py` ou fixture/admin (M-07)
- `frontend/app/noticia/LeituraPremium.tsx` (M-08)
- Novo app `backend/patrocinio/` (models, admin, views/urls, migrations, tests), `backend/config/urls.py` ou equivalente para registrar as rotas, `frontend/components/PatrocinioSlot.tsx`, `backend/metricas/models.py` (novos tipos de evento) (M-10)
- Configuração de nginx (`infra/` ou onde os templates de `portal-location-cache*.conf` vivem) — só se M-02/M-10 precisarem registrar a rota nova na allowlist existente; não criar regra nova do zero

## Interfaces afetadas
- `GET /api/noticias/<id>` e endpoint de cluster (`detalhe_cluster`/`detalhe_item`) — remove campo `conteudo` do JSON público (M-01). **Mudança de contrato de API pública — qualquer consumidor externo que dependa de `conteudo` quebra; é intencional, documentar em `documentation-update.md`.**
- Novo endpoint leve em `backend/feed/` para listagem de IDs publicáveis (M-02).
- Novo endpoint público `GET /api/patrocinio/ativo/?posicao=...` (M-10).
- `backend/assinatura` — novo registro de `Plan` (semestral) via admin/fixture, sem mudança de schema (M-07).
- `EventoSite` (`backend/metricas/models.py`) — novos valores em `TIPO_CHOICES`: `patrocinio_view`, `patrocinio_click` (M-10). Migração de dados (choices), não de schema.
- `AdsSlot` ganha prop `slot` opcional e passa a usar variáveis de ambiente por posição em vez de só por formato (M-04) — consumido por todo componente que já usa `AdsSlot` hoje.

## Critérios de aceite (técnicos, testáveis)
1. **M-01** — Dado um `GET` ao endpoint de detalhe de notícia/cluster, quando a resposta é serializada, então o JSON não contém a chave `conteudo` em nenhuma entrada de `fontes`. Teste: `backend/feed/tests/` novo, afirma ausência da chave.
2. **M-03** — Dado `d.fontes[0].resumo` vazio, quando `generateMetadata` roda para `/noticia/[id]`, então o metadata resultante inclui `robots: { index: false, follow: true }`. Teste: `frontend/testes/` novo ou em `jsonld.test.mjs`.
3. **M-02** — Dado um conjunto de notícias publicáveis (algumas com resumo, outras não — ver M-03), quando `/sitemap.xml` é gerado, então só as publicáveis **e indexáveis** aparecem, cada uma com `lastModified` igual ao timestamp real. Teste: `frontend/testes/` novo, valida XML e contagem.
4. **M-04** — Dado `NEXT_PUBLIC_ADSENSE_SLOT_<POSICAO>` definido no ambiente, quando `AdsSlot` com `id="<posicao>"` é renderizado e pode exibir anúncio, então `data-ad-slot` usa o valor dessa variável (não mais o valor por formato). Dado a env ausente, usa o padrão do formato (sem quebrar o comportamento atual). Teste: `verificar-consentimento-anuncios.mjs` cobre que nenhum slot novo carrega script sem consentimento; teste unitário novo cobre o mapeamento posição → env var.
5. **M-05** — Dado `NODE_ENV === "production"` e `podeExibirAnuncio()` falso, quando `AdsSlot` renderiza, então não aparece nenhum texto "Google AdSense"/"slot {id}"; aparece o cartão de M-09 (ou nada, se M-09 ainda não aplicável ao caso). Dado `NODE_ENV !== "production"`, o placeholder de debug pode continuar. Teste: snapshot/renderização cobrindo os dois ambientes.
6. **M-06** — Dado o arquivo `HomeClient.tsx`, quando contado `<AdsSlot`, então o total é ≤ 5. Mesmo critério para `LeituraPremium.tsx` (≤ 2) e `planos/page.tsx` (= 0). Verificação: `grep -c "<AdsSlot" <arquivo>` documentado no implementation-history.md; `npm run build` sem erro.
7. **M-07** — Dado 3 planos ativos no banco (`free`, premium semestral, premium anual), quando `/planos` renderiza, então aparecem 3 cartões e o de maior duração tem destaque com "Economize X%" calculado a partir do preço/duração reais (não número fixo no código). Teste: `frontend/testes/` com 1, 2 e 3 planos ativos.
8. **M-08** — Dado um usuário Free lendo uma notícia, quando a página renderiza, então aparece exatamente um cartão/CTA com link para `/planos` e `aria-label`. Dado um usuário Premium (via `usePremiumAtivo`), o cartão não aparece. Teste: renderização com os dois papéis.
9. **M-09** — Dado `formato` e a lista de planos ativos, quando `CartaoPremium` renderiza, então mostra o preço do plano mais barato ativo e não usa as palavras "publicidade"/"AdSense". Teste unitário + teste de contraste (AA) documentado manualmente no implementation-history.md (contraste não é automatizável no CI atual — registrar como verificação manual, não pular).
10. **M-10** — Dado um registro `Patrocinio` com `data_inicio <= hoje <= data_fim` e `ativo=True` numa posição, quando `GET /api/patrocinio/ativo/?posicao=<pos>` é chamado, então retorna esse registro; fora do intervalo ou `ativo=False`, retorna vazio/404. Dado o componente `PatrocinioSlot` recebe esse dado, então renderiza com rótulo "Patrocinado" visível e `rel="sponsored nofollow noopener"`. Dado um clique/view com consentimento de `analytics` concedido, registra `EventoSite` do tipo correspondente; sem consentimento, não registra. Teste: `backend/patrocinio/tests/` (datas, ativo) + teste de frontend (rótulo, rel, consentimento).

## Não-objetivos
- Criar conta Google AdSense, preencher slot IDs reais ou qualquer coisa de M-11/M-12 (está bloqueado por aprovação do Google e é escopo de outra sessão — ver nota em M-11 do plano).
- Implementar GA4/Consent Mode v2 (M-13) ou trial (M-14) — fora do Sprint 1.
- Definir preço/tabela comercial real de patrocínio — só o mecanismo (M-10).
- Tocar `deploy-pm2.yml` (achado de possível legado, registrado no plano como item de limpeza separado).
- Redesenhar visualmente além do que M-05/M-09 exigem — não é escopo de redesign (isso já foi feito e mergeado por outra sessão antes desta run abrir).

## Restrições técnicas
- **Performance:** endpoints novos (M-02, M-10) devem ser GET cacheáveis e reaproveitar os includes de rate-limit/cache do nginx já existentes (ver §0.1 do plano) — não introduzir query N+1 nem endpoint sem paginação para listagem de notícias.
- **Segurança/privacidade:** M-01 remove dado que não deveria ser público (risco de direito autoral, BRD §18) — confirmar que nenhum teste existente depende da presença de `conteudo` na resposta pública antes de removê-lo. M-10 registra eventos de analytics só com consentimento (mesma guarda usada em `anuncios.ts`/`analytics.ts`).
- **Dependências permitidas:** nenhuma biblioteca nova sem justificar aqui antes de instalar (nenhum item do Sprint 1 deveria precisar).
- **Estilo/convenções:** `.claude/skills/frontend-portal/SKILL.md` (tokens `--cor-*`, acessibilidade, `prefers-reduced-motion`, 360-1440px) para qualquer componente novo ou alterado (M-05, M-08, M-09, M-10).

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite 1-10 implementados e com teste automatizado correspondente
- [ ] Testes escritos e passando (tester) — frontend (`typecheck`, `test`, `build`) e backend (`pytest`)
- [ ] Revisão de código aprovada (reviewer) — obrigatória por review-triggers.md (cobrança/assinatura, API pública, direitos autorais/compliance)
- [ ] Documentação atualizada (documenter) — `docs/monetizacao/RESULTADOS.md` e qualquer doc de API pública afetada por M-01
- [ ] `implementation-history.md` completo e coerente, um registro por item M-01..M-10
- [ ] PR aberto e mergeado em `develop`, deploy de HOMOLOG saudável
- [ ] Tag `vX.Y.Z` criada, deploy de PROD saudável (confirmado via SSH na VPS, containers `healthy`)
