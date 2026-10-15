<!--
CONTRACT: task-plan
DONO: orchestrator
QUANDO É CRIADO: no início de toda execução (agentic-run), antes de qualquer implementação.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/task-plan.md
-->

# Task Plan — 20261014-2113-correcao-seo

## Metadados
- **run_id:** 20261014-2113-correcao-seo
- **Data de abertura:** 2026-10-14
- **Solicitado por:** Alex Buttielie (usuário, via chat)
- **Spec de origem:** N/A — origem são dois relatórios de auditoria de SEO externos fornecidos pelo usuário (PDFs em ~/Downloads): "Analisador de SEO - Gere um relatório de SEO gratuito para o seu site.pdf" (Rank Math SEO Analyzer, 66/100) e "relatorio_analise_seo_portal_noticias.pdf" (leitura consolidada do relatório anterior, 64/100). Relaciona-se à run anterior `agentic-framework/state/run-20260903-1134-seo-lgpd-design-system/` que estabeleceu a base de SEO técnico (lib/site.ts, JSON-LD, etc.) — esta run corrige lacunas detectadas depois daquela entrega.

## Objetivo
Corrigir, no código do frontend (Next.js 14), todos os problemas de SEO on-page e de performance acionáveis apontados pelos dois relatórios de auditoria, elevando a pontuação técnica de SEO sem introduzir regressões visuais ou funcionais, e documentar explicitamente os achados que não podem ser corrigidos apenas no código da aplicação (infraestrutura, contas de terceiros).

## Escopo
### Dentro do escopo
- Adicionar tag H1 única e natural na página inicial (e confirmar H1 único em páginas de categoria/notícia).
- Adicionar `<link rel="canonical">` self-referencing em todas as páginas indexáveis via `alternates.canonical` do Next.js Metadata API.
- Adicionar `alt` descritivo em todas as imagens informativas que hoje renderizam `alt=""` (cards/listas de notícias agregadas).
- Completar meta tags OpenGraph (`og:title`, `og:description`, `og:image`, `og:url`, `og:type`, `og:locale`) em `generateMetadata`.
- Completar `openGraph.images` usando `IMAGEM_OG_PADRAO` (hoje definida em `lib/site.ts` mas nunca consumida).
- Investigar redirect consistente entre `www` e não-`www`; corrigir se houver um ajuste de baixo risco, senão documentar como pendência de infra com o motivo técnico exato (ver achado do explorador: Caddy serve `www` e apex como aliases do mesmo bloco, sem 301 entre eles — restructurar isso é mudança de roteamento de borda para o site inteiro, não um one-liner).
- Adicionar o header `Strict-Transport-Security` no bloco `header` do `Caddyfile` SE a investigação confirmar que ele hoje só é enviado pelo Django (rotas `/api/*`) e não alcança as páginas servidas por `frontend:3000` (a maioria do site, incluindo a home que a auditoria avaliou) — mudança de uma linha, mesmo padrão dos headers de segurança já presentes ali, mas sinalizar claramente no report que precisa de deploy/validação antes de valer em produção.
- Revisar carregamento de scripts/CSS não essenciais (usar `next/script` com estratégia adequada) SE houver um bloqueante concreto identificável — não especular.
- Investigar por que Google Analytics não é detectado (sem criar conta/ID fictício); o projeto já tem analytics first-party próprio (`AnalyticsTracker.tsx`/`lib/analytics.ts`) — documentar isso como contexto e a decisão de GA4 como pendência humana.

### Fora do escopo (explicitamente)
- Migrar `<img>` para `next/image`. Decisão arquitetural já registrada e deliberada em `frontend/components/ImagemNoticia.tsx` (comentário): (1) máquina de estados de fallback própria incompatível com o ciclo do `next/image`; (2) domínios de RSS de fontes agregadas são arbitrários e não enumeráveis em `remotePatterns`; (3) a rota `/_next/image` do Next.js tem uma CVE crítica sem patch na versão usada (GHSA-2xp9-vwfh-vxw4). Reverter essa decisão está fora do escopo desta run de SEO — o achado "imagens pesadas" do relatório é mitigado pelo `loading="lazy"` já presente em todas as imagens (confirmado no HTML do próprio relatório Rank Math) e documentado como pendência de otimização adicional (ex. serviço de proxy/resize de imagem), não resolvido aqui.
- Criar conta real do Google Analytics/GA4 ou inserir ID de tracking fictício.
- Restructurar o `Caddyfile` para redirect 301 entre `www`/apex (ver item de escopo acima — é investigado, mas só corrigido se a correção for de baixo risco; caso exija reestruturar blocos de site, fica como pendência documentada).
- Produzir conteúdo editorial novo (página de metodologia, expansão de Sobre/Contato, autoria editorial) — são recomendações editoriais do relatório consolidado, não achados técnicos de SEO.
- Alterar configuração de servidor/proxy em produção além do ajuste pontual de HSTS descrito acima — mudanças maiores de infra ficam documentadas como pendência, não aplicadas às cegas.
- Rodar novamente a ferramenta Rank Math (não há acesso a produção/ferramenta externa) — critério de sucesso é técnico/verificável no código, não repetir a pontuação externa.

## Suposições assumidas
- O domínio canônico (sem `www`, conforme `NEXT_PUBLIC_SITE_URL`/`lib/site.ts` já usam `portal-noticias.com` sem www) é o padrão correto a reforçar — motivo: é o que a infraestrutura de SEO existente (run anterior) já assume; mudar para `www` exigiria decisão de negócio que não foi pedida.
- Onde o H1 sugerido pelo relatório ("As principais notícias do Brasil e do mundo") não bater com o tom real do conteúdo do portal, o executor pode adaptar o texto mantendo a intenção (headline central da home), desde que permaneça natural — motivo: o próprio relatório classifica o H1 sugerido como "proposta inicial" a validar antes de publicar.

## Restrições
- Stack obrigatória: Next.js 14 (App Router), TypeScript, Tailwind — seguir convenções já estabelecidas em `frontend/`.
- Não quebrar LGPD/consentimento de cookies já implementado (`BannerConsentimentoCookies.tsx`) ao mexer em analytics/scripts.
- Mudanças visuais (H1, alt text) devem seguir o design system do portal — aplicar a skill `frontend-portal` se houver trabalho visual relevante.
- Sem prazo externo definido; priorizar os itens CRÍTICO/ALTA do relatório primeiro.

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | código + implementation-history.md |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked |
| 3 | reviewer (obrigatório — ver justificativa abaixo) | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

Revisão obrigatória: embora nenhum gatilho específico de `review-triggers.md` (auth, pagamento, dados pessoais, schema de banco) se aplique diretamente, a mudança toca múltiplos arquivos e componentes compartilhados (layout, metadata, next.config.js, componentes de imagem usados em toda a home) — volume e superfície de impacto justificam revisão por precaução, mesmo sem gatilho obrigatório específico.

## Critérios de aceite (nível de negócio/produto)
1. A página inicial tem exatamente uma tag H1 visível e semanticamente correta.
2. Toda página indexável do frontend expõe um `<link rel="canonical">` correto apontando para sua própria URL absoluta.
3. Nenhuma imagem informativa de notícia é renderizada com `alt=""` vazio.
4. As meta tags OpenGraph aparecem completas (title, description, image, url, type, locale) ao inspecionar o HTML renderizado da home e de uma página de notícia.
5. Nenhuma nova tag `<img>` crua é migrada para `next/image` (decisão arquitetural preservada); o achado de peso de imagem fica documentado com a mitigação já existente (lazy loading) e a pendência real (proxy/resize de imagem, fora de escopo).
6. O comportamento de www/não-www é investigado e documentado com precisão técnica — corrigido no código apenas se de baixo risco, senão listado como pendência de infraestrutura com o motivo exato.
7. Nenhuma regressão visual ou funcional é introduzida na home, páginas de categoria e página de notícia (validado via preview no browser).
8. O relatório final (`report.md`) lista claramente o que foi corrigido vs. o que ficou como pendência que exige decisão humana (GA4, infra HSTS/HTTP2/www), com o motivo de cada pendência.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Adicionar H1 pode duplicar visualmente o título já exibido (ex. logo/hero) ou conflitar com H1 implícito de outro componente | Médio | Confirmado pelo explorador: a home (`app/page.tsx`/`HomeClient.tsx`) não tem nenhum `<h1>` hoje — usar H1 visualmente oculto (`sr-only`, padrão já usado no projeto) para não alterar o visual |
| Mudar `alt=""` para `alt={titulo}` em miniaturas pode ser redundante quando o título já aparece como texto visível ao lado — risco de poluir leitura de tela | Baixo | Usar `alt={titulo}` mesmo assim (é a prática padrão de SEO/acessibilidade recomendada pelo próprio relatório); já é o padrão usado em outros componentes corretos do projeto (`categoria/[slug]/page.tsx`, `SecaoRegiao.tsx`) |
| Editar o `Caddyfile` para adicionar HSTS pode ter efeito em produção sem teste prévio | Médio | Mudança de uma linha no bloco `header` já existente, seguindo o mesmo padrão dos headers de segurança já ativos; sinalizar claramente no `report.md` que precisa de deploy e validação humana antes de confiar no efeito em produção |
| Mudança de redirect www/não-www em `next.config.js` pode não ter efeito se o domínio é roteado por Caddy/nginx antes de chegar ao Next.js | Médio | Investigar Caddyfile/infra/nginx primeiro; se o redirect já deveria viver lá, documentar em vez de duplicar/mascarar em next.config.js |
| Escopo tocar muitos componentes de imagem (cards, listas, destaques) pode estourar o limite de revisão por volume | Baixo | Agrupar mudanças por padrão repetido (mesmo componente reutilizado) em vez de editar N componentes únicos, quando possível |

## Dependências
- Resultado da investigação de código já em andamento (exploração do layout.tsx, home, componentes de imagem, next.config.js, GA, sitemap/robots) — necessário antes de o `implementation-contract.md` ser finalizado com caminhos de arquivo exatos.
- Decisão humana pendente, fora desta run: criação de conta Google Analytics/GA4 real (ID de produção) e validação de configuração HSTS/HTTP2/redirect www em infraestrutura de produção.
