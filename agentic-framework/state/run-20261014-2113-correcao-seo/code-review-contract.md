<!--
CONTRACT: code-review-contract
DONO: reviewer
QUANDO É CRIADO: sempre que review-triggers.md indicar revisão obrigatória, ou sob demanda (skill agentic-review).
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/code-review-contract.md
-->

# Code Review Contract — 20261014-2113-correcao-seo

## Metadados
- **run_id:** 20261014-2113-correcao-seo
- **Escopo revisado:** diff de working tree (não comitado) produzido pelo executor/validado pelo tester — 27 arquivos: `Caddyfile`, `frontend/app/layout.tsx`, `frontend/app/page.tsx`, 18 demais `frontend/app/**/page.tsx` (canonical), `frontend/components/home/NewsCard.tsx`, `frontend/components/home/UltimasNoticias.tsx`, `frontend/components/HomeClient.tsx`, `frontend/components/SecaoColunistas.tsx`, `frontend/app/noticia/LeituraPremium.tsx`. Confirmado via `git diff --stat` (71 inserções / 27 deleções) que bate 1:1 com a seção "Áreas/arquivos esperados" do contrato — nenhum arquivo fora do escopo foi tocado.
- **Contrato de referência:** implementation-contract.md (20261014-2113-correcao-seo), v2 — nota de amendamento sobre o rebaixamento do critério #4 (`og:image`) já incorporada; não reaberta aqui como finding, conforme instrução explícita do chamador e regra geral de não revisar decisão de escopo já tomada pelo orchestrator.
- **Gatilhos aplicados (de review-triggers.md):** nenhum dos gatilhos obrigatórios por categoria sensível (auth, cobrança, dados pessoais, schema, API pública, moderação, credenciamento, B2B, direitos autorais) se aplica — é SEO on-page + um header HTTP de infraestrutura. O gatilho que se aplica é o genérico de volume ("diffs acima de ~300 linhas" não é atingido — são 95 linhas líquidas —, mas a revisão já estava marcada como obrigatória no `task-plan.md`/`implementation-contract.md` por volume de arquivos tocados, conforme Definição de Pronto). Atenção redobrada dada mesmo assim ao `Caddyfile` por ser infraestrutura versionada com efeito em produção.

## Verificação independente realizada (não aceito o que executor/tester reportaram sem reexecutar)
- `cd frontend && npx tsc --noEmit` → limpo, sem erros.
- `npx eslint` nos arquivos `.tsx`/`.ts` tocados (via `git diff --name-only`) → limpo, sem erros.
- `npm run build` → sucesso, todas as rotas geradas (inclui `ECONNREFUSED 127.0.0.1:8001` esperado, backend fora do ar).
- Inspeção do HTML gerado: exatamente 1 `<h1>` em `/`; `<link rel="canonical">` auto-referente confirmado em 5 rotas (`/`, `/categoria/politica`, `/noticia/1`, `/sobre`, `/autor/1`); `og:type`/`og:locale` presentes, `og:image` ausente (conforme pendência já formalmente aceita na v2 do contrato — não reaberta).
- `grep -rn 'alt=""' frontend/components frontend/app` → zero ocorrências; os 8 pontos do contrato usam a variável de título correta no escopo de cada arquivo (`entrada.titulo`, `n.titulo`, `u.titulo`, `item.titulo`, `c.recente.titulo`, `r.titulo` — sem copy/paste cruzado de nome de variável entre componentes).
- `Caddyfile`: validado com `docker run caddy:2-alpine caddy validate/adapt`, reexecutado de forma independente (não copiado da Iteração 1/2) nos dois cenários (prod com `DOMAIN_EXTRA=", www.portal-noticias.com"` e dev com `DOMAIN_EXTRA=""`). Inspeção do JSON adaptado confirma: rota 0 = `headers` (inclui HSTS, sem `match`, aplica a toda resposta), rota 1 = `static_response` 301 com `match host=www.portal-noticias.com` para `https://portal-noticias.com{http.request.uri}`, última rota (catch-all, sem `match`) = `reverse_proxy frontend:3000`. Confirma de forma estrutural (não só leitura do arquivo-fonte) que o redirect roda antes do catch-all, sem risco de loop (apex nunca re-casa o matcher `@www`).

## Findings

### Finding 1
- **Arquivo:** `Caddyfile`
- **Linha:** 47-56 (comentário do bloco `header`)
- **Categoria:** docs
- **Severidade:** nit
- **Resumo:** O comentário novo diz que o HSTS é "duplicado" para "cobrir as duas origens" (Django e Next.js), dando a impressão de que os dois valores coexistem independentemente por rota. Na prática, como o `header` do site roda sem `match` (aplica-se a toda resposta do bloco, inclusive às rotas proxiadas para `web:8000`), ele sobrescreve/normaliza o `Strict-Transport-Security` que o Django também envia nessas rotas (`SECURE_HSTS_SECONDS` do Django = 30 dias por padrão em `backend/config/settings.py:222`, vs. `max-age=31536000` = 1 ano no Caddyfile) — ou seja, a partir desta mudança, o valor do Django nunca chega de fato ao cliente em nenhuma rota; o Caddy sempre "ganha".
- **Cenário de falha:** Não é um bug funcional (o cliente recebe HSTS consistente de 1 ano em toda rota, o que é estritamente mais seguro, não menos) — é só um comentário que pode levar um mantenedor futuro a acreditar, incorretamente, que ajustar `DJANGO_SECURE_HSTS_SECONDS` no backend ainda tem efeito observável em `/api/*`, `/livez` etc. quando na verdade deixou de ter.
- **Sugestão:** Ajustar o comentário para deixar explícito que o valor do Caddy agora é o que efetivamente chega ao cliente em todas as rotas do site (o do Django fica redundante, não complementar). Não bloqueia merge.

## Resumo quantitativo
| Severidade | Quantidade |
|---|---|
| blocker | 0 |
| major | 0 |
| minor | 0 |
| nit | 1 |

## Veredito
**approve_with_comments**

Todas as mudanças tocadas nesta run foram verificadas de forma independente (tsc, eslint, build, grep, inspeção de HTML gerado, `caddy validate`/`adapt` via Docker) e estão tecnicamente corretas: cada `alternates.canonical` aponta para o path real da própria página (nenhum valor fixo copiado de outra rota), o H1 da home é `sr-only` e não disputa com o H2 "Destaques do dia", as 8 trocas de `alt=""` usam a variável de título correta em cada escopo (sem mistura entre componentes), e o `Caddyfile` tem o redirect `www→apex` rodando estruturalmente antes do `handle` catch-all, sem risco de loop (confirmado via inspeção do JSON adaptado do Caddy, não só leitura do arquivo-fonte) e sem quebrar `/api/*`, `/livez`, `/readyz`, `/healthz`, `/health-detail`, `/metrics`. Nenhum arquivo fora do escopo do `implementation-contract.md` foi tocado. Único achado é um `nit` de documentação (comentário do Caddyfile levemente impreciso sobre a relação entre o HSTS do Django e o do Caddy) — não impede merge.
