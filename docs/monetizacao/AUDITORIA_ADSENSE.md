# Auditoria de conformidade — Google AdSense

Feita em 2026-10-12, contra as políticas oficiais do Google (AdSense Program
Policies, motivos documentados de reprovação de site, e a EU User Consent
Policy), lidas diretamente de `support.google.com/adsense` nesta mesma noite —
não é um resumo de memória. Objetivo: o portal passar na revisão de aprovação
do AdSense (hoje "em preparação" no painel do Google) e não violar política
depois de aprovado.

## O que o Google exige, e onde o portal está

| Exigência do Google | Situação encontrada | Ação |
|---|---|---|
| Conteúdo original, suficiente, sem texto raspado reproduzido | `conteudo` (texto raspado de terceiros) era exposto na API pública e renderizado na leitura da notícia | **Corrigido pelo Sprint 1 do plano de monetização (M-01)**, em paralelo a esta auditoria — ver `docs/monetizacao/PLANO_MONETIZACAO.md` |
| Páginas indexáveis/navegáveis, sem conteúdo "em construção" ou fabricado | `/paginas/[slug]` fabricava HTTP 200 com texto "em preparação" para slug inexistente | **Já corrigido antes desta auditoria** (ver comentário "P0-08" no próprio arquivo `frontend/app/paginas/[slug]/page.tsx`) — hoje devolve 404 real ou um estado de erro honesto, nunca inventa conteúdo |
| Sitemap/indexação cobrindo o conteúdo real do site | `/sitemap.xml` não lista nenhuma notícia (`/noticia/[id]`), só rotas fixas | **Já é o item M-02 do Sprint 1** — não duplicado aqui |
| `ads.txt` correto | Existe, devolve 404 propositalmente enquanto não há publisher ID configurado (evita que um `ads.txt` vazio prejudique a própria revisão) | Nenhuma ação — já está certo |
| Política de privacidade declarando cookies de anúncio, fornecedor (Google), opt-out | `/privacidade` já cobre tudo isso, nominando "Google AdSense" e linkando `adssettings.google.com` | Nenhuma ação — já está certo |
| Página de cookies listando categorias | `/cookies` lista Essenciais/Analytics/Personalização, com anúncio dentro de "Personalização" | Nenhuma ação agora (ver follow-up de granularidade abaixo) |
| Termos de uso/contato referenciando cookies e publicidade de terceiros | `/termos` não mencionava cookies nem AdSense | **Corrigido nesta auditoria** — nova seção "4. Cookies e publicidade" com link para `/cookies` e `/privacidade` |
| HTTPS em produção | Forçado no Django (`SECURE_SSL_REDIRECT` default `True`) quando `DEBUG=False`; certificado Let's Encrypt válido confirmado na VPS | Nenhuma ação |
| Sem conteúdo de categoria proibida (adulto, violência, apostas, etc.) | Produto é agregador de ~91 fontes de imprensa mainstream brasileira; nenhuma indicação de categoria proibida | Nenhuma ação |
| Identificação de quem opera o site (página "Sobre") | `/sobre` descreve o produto, mas não identifica a entidade/pessoa responsável (razão social, CNPJ, editor responsável) — busquei em todo o repositório e não existe esse dado em nenhum lugar hoje | **Não corrigido — ver follow-up abaixo.** Não inventei nome de empresa/CNPJ; isso violaria a mesma regra que motivou o M-01 (nunca fabricar dado) |
| EU User Consent Policy (CMP certificado Google/IAB TCF para tráfego EEA/UK/Suíça) | O banner de consentimento (`BannerConsentimentoCookies.tsx`) é customizado, não é um CMP certificado pelo Google/IAB TCF | **Não corrigido — ver follow-up abaixo.** Não é uma falha de código a "arrumar", é escolher e contratar um CMP terceiro |

## O que foi alterado nesta auditoria

- `frontend/app/termos/page.tsx` — nova seção "4. Cookies e publicidade", com link para `/cookies` e `/privacidade`, mencionando o uso de cookies e de publicidade de terceiros (Google AdSense). Mudança de copy estático, sem lógica nova — `npm run typecheck` limpo.

## Follow-ups que precisam de você (não posso decidir nem inventar)

1. **Identidade do operador do site (`/sobre`).** O Google valoriza (e alguns contextos jurídicos exigem) que um site identifique quem o opera — razão social, CNPJ/CPF, ou ao menos o nome do responsável editorial. Não existe esse dado em nenhum lugar do repositório hoje. Preciso que você me diga o que colocar (pode ser pessoa física, MEI, ou empresa) para eu adicionar em `/sobre` e, se fizer sentido, no rodapé.
2. **CMP certificado para tráfego da UE/Reino Unido/Suíça.** Desde 2024 o Google exige um CMP certificado (registrado no IAB Europe, TCF — a versão atual exigida é a 2.3) para servir anúncio nesses países; sem isso, o Google serve "Limited Ads" (anúncio não-personalizado, menos receita) para esses visitantes — não é um bloqueio da conta, é perda de receita nesse recorte de tráfego. Se o portal não tem audiência relevante na Europa, isso é baixa prioridade; se tiver, a correção é contratar um CMP (ex. Cookiebot, Usercentrics, Google Funding Choices) e integrá-lo — é decisão de produto/fornecedor, não uma correção de código que eu deva fazer sem combinar com você.
3. **Granularidade da categoria "Personalização" em `/cookies`.** Hoje ela cobre feed personalizado E publicidade de terceiros sob o mesmo toggle. É transparente (está documentado), mas uma categoria "Anúncios" separada seria mais granular. Essa mudança toca os mesmos arquivos que o Sprint 1 de monetização já está alterando (`frontend/lib/anuncios.ts`, `BannerConsentimentoCookies.tsx`) — não fiz aqui para não colidir; fica como item para uma próxima rodada, coordenado com o resultado do Sprint 1.
4. **M-18 do plano de monetização (parecer jurídico sobre anúncio não-personalizado)** segue como estava: precisa de advogado, não é algo que eu resolvo.

## Itens que o Sprint 1 do plano de monetização já cobre (não duplicados aqui)

M-01 (remover conteúdo raspado), M-02 (sitemap com notícias), M-03 (noindex em
notícia sem resumo), M-05 (remover placeholder "Google AdSense" visível), M-06
(densidade de anúncio), M-19 (banner sem padrão escuro) — ver
`docs/monetizacao/PLANO_MONETIZACAO.md` e a run
`agentic-framework/state/run-20261012-1806-monetizacao-sprint1/` para o
andamento real dessas correções.
