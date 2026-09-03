<!--
CONTRACT: task-plan
DONO: orchestrator
QUANDO É CRIADO: no início de toda execução (agentic-run), antes de qualquer implementação.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/task-plan.md
-->

# Task Plan — 20260903-1134-seo-lgpd-design-system

## Metadados
- **run_id:** 20260903-1134-seo-lgpd-design-system
- **Data de abertura:** 2026-09-03
- **Solicitado por:** usuário (via chat, aprovando lista de features derivada do BRD e proposta pelo assistente)
- **Spec de origem:** BRD_portal_noticias_versao_1.docx (múltiplas seções, ver critérios de aceite) + backlog consolidado pelo assistente na conversa (não é uma spec formal em agentic-framework/specs/)

## Objetivo
Esta é a **Run 1 de N** de uma iniciativa maior ("inserir todo o backlog de UX/produto proposto e deixar finalizado"). Esta run entrega a base transversal que as próximas runs vão consumir: SEO técnico completo (metadata, schema.org, sitemap, RSS, canonical, Open Graph), conformidade de privacidade/cookies (LGPD) e a camada de design system (tokens, componentes reutilizáveis, estados, tipografia/grid) evoluindo a base já existente em `frontend/app/globals.css` e `frontend/components/`.

## Escopo
### Dentro do escopo
- SEO técnico: URLs amigáveis (revisão de slugs de rota já existentes em `frontend/app/noticia/`), `sitemap.xml` dinâmico, `robots.txt`, feed RSS, `<link rel="canonical">`, Open Graph/Twitter Card via Next.js Metadata API.
- Dados estruturados schema.org: `NewsArticle`, `Article`, `BreadcrumbList`, `Organization`, `Person`, `ImageObject` nas páginas relevantes (artigo, autor, home).
- Privacidade/LGPD: banner de consentimento de cookies (aceitar/recusar/gerenciar por categoria), página de gestão de preferências de cookies, texto de política de privacidade referenciando LGPD.
- Rate limiting básico nos endpoints públicos de escrita (DRF throttling) — mínimo necessário para não deixar a base sem proteção antes das próximas runs adicionarem mais endpoints públicos.
- Design system: tokens de design (cores, espaçamento, tipografia, raio, sombra) formalizados como variáveis CSS documentadas, componentes reutilizáveis de UI genéricos (Badge, Chip, Tooltip, Dropdown, Modal, Tabs, Accordion) com estados (normal/hover/ativo/carregando/erro/desabilitado), grid system consistente, tipografia editorial responsiva.

### Fora do escopo (explicitamente)
- Login social (fica para a run de Segurança/Autenticação avançada, junto com o restante do backlog de segurança).
- Pipeline de IA/crawlers/radar (runs futuras dedicadas a IA e automação).
- Qualquer item de "Monetização"/anúncios (run futura de B2B/monetização).
- Qualquer item de "Multimídia" (vídeo, áudio, podcasts) — run futura dedicada.
- Uso de bibliotecas de terceiros para os componentes de UI — mantém a convenção já estabelecida no projeto de CSS+componentes React "hand-written", sem adicionar dependência nova de design system.

## Suposições assumidas
Executando em modo não supervisionado (usuário pediu explicitamente "pode inserir tudo, finalizado" sem detalhar prioridades técnicas) — as suposições abaixo foram necessárias para não bloquear a execução:
- **Ordem de execução em múltiplas runs, começando por esta base transversal** — motivo: SEO/design tokens/LGPD são pré-requisitos usados por praticamente todas as páginas futuras; construir isso primeiro evita retrabalho.
- **Texto de política de privacidade em português, genérico e não revisado por jurídico** — motivo: não há input jurídico disponível; o texto deve ser tratado como rascunho, não como peça jurídica final validada.
- **Rate limiting usa o throttling nativo do Django REST Framework (sem Redis/infra externa)** — motivo: manter consistente com o stack atual (sem cache distribuído configurado no projeto), evitando introduzir nova dependência de infraestrutura sem aprovação.

## Restrições
- Stack obrigatória: Django+DRF/PostgreSQL (backend), Next.js/React/TypeScript (frontend) — sem novas dependências de terceiros para os componentes de UI.
- Seguir DDD: qualquer mutação de estado (ex: gravar preferência de cookies do usuário logado) passa por `services.py` do app responsável.
- Se um endpoint de backend necessário não existir (ex: endpoint para persistir preferências de cookies de usuário autenticado), corrigir na mesma execução (convenção já validada no projeto).
- Requisitos de privacidade/LGPD são requisito funcional desta run, não apenas texto — o consentimento deve efetivamente bloquear cookies não essenciais até aceite.

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | código + implementation-history.md |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked |
| 3 | reviewer (gatilho: dados pessoais/LGPD) | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. Uma página de notícia publicada expõe Open Graph, Twitter Card e JSON-LD `NewsArticle` válidos (verificáveis via view-source), e a home expõe `Organization`.
2. `sitemap.xml` e `robots.txt` respondem publicamente e o sitemap lista as notícias publicadas.
3. Um visitante novo vê o banner de cookies antes de qualquer cookie não essencial ser gravado; ao recusar, nenhum cookie de rastreamento é definido; a escolha é lembrada em visitas futuras.
4. Existe uma página de gestão de preferências de cookies acessível a qualquer momento (ex: rodapé).
5. Endpoints públicos de escrita (ex: cadastro, comunidade) respondem 429 após exceder um limite de requisições configurado, em vez de aceitar volume ilimitado.
6. Os componentes de UI genéricos (Badge, Chip, Tooltip, Dropdown, Modal, Tabs, Accordion) existem em `frontend/components/`, usam os tokens de design (não cores/espaçamentos hardcoded) e têm ao menos os estados normal/hover/carregando documentados no `documentation-update.md`.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Texto de política de privacidade não revisado juridicamente | médio | Marcar explicitamente como rascunho no próprio texto e no report.md; recomendar revisão jurídica antes de produção real |
| Rate limiting mal calibrado pode bloquear uso legítimo | médio | Usar limites conservadores (folgados) documentados, ajustáveis via settings |
| Escopo de "design system" é subjetivo e pode crescer sem limite | médio | Limitar esta run aos 7 componentes listados + tokens; qualquer componente adicional vira follow-up |

## Dependências
Nenhuma dependência externa pendente. Esta run é a base; as runs seguintes (CMS/admin, artigo/navegação/busca, personalização/engajamento, multimídia, IA/radar, analytics, monetização/b2b, itens avançados) dependem dos tokens de design e componentes produzidos aqui.
