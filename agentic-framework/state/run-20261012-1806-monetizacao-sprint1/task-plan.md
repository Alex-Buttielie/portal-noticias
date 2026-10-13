# Task Plan — 20261012-1806-monetizacao-sprint1

## Metadados
- **run_id:** 20261012-1806-monetizacao-sprint1
- **Data de abertura:** 2026-10-12
- **Solicitado por:** humano (sessão de chat "Detalhes da VPS"), após validação técnica do plano feita nesta mesma sessão
- **Spec de origem:** docs/monetizacao/PLANO_MONETIZACAO.md (seções 1-2, itens M-01 a M-10)

## Objetivo
Implementar os 10 itens do Sprint 1 do plano de monetização (M-01 a M-10,
nenhum deles depende de conta Google AdSense), levar o resultado até
produção (merge em `develop` → deploy automático em HOMOLOG saudável → tag
de versão → deploy em PROD saudável), sem expor dados pessoais/conteúdo
raspado além do já existente, sem quebrar a regra de consentimento de
anúncio (LGPD) e sem mostrar anúncio ou cartão de assinatura a usuário
Premium.

## Escopo
### Dentro do escopo
- M-01 — remover a chave `conteudo` (texto raspado) do JSON público de notícia.
- M-03 — não indexar (`noindex, follow`) notícia sem resumo próprio.
- M-02 — sitemap passa a listar notícias publicáveis (depende de M-03 já estar pronto).
- M-04 — `AdsSlot` passa a aceitar slot por posição (não só por formato).
- M-05 — remover o placeholder textual de anúncio em produção; cartão Premium no lugar.
- M-06 — reduzir densidade de `AdsSlot` na home, leitura, planos, categoria.
- M-07 — plano semestral cadastrado + destaque "Economize X%" na página de planos.
- M-08 — CTA de assinatura dentro da leitura da notícia, só para Free.
- M-09 — componente `CartaoPremium` reutilizável, usado por M-05.
- M-10 — app `backend/patrocinio/` (modelo, admin, endpoint, componente, rótulo "Patrocinado").
- Merge para `develop`, verificação do deploy automático de HOMOLOG, criação de tag `vX.Y.Z` e verificação do deploy de PROD saudável (confirmado via SSH na VPS).

### Fora do escopo (explicitamente)
- M-11 a M-23 (Sprint 2 e 3 do plano) — dependem de conta AdSense, GA4, parecer jurídico ou decisão comercial que não foram dadas nesta run.
- Definir preço/tabela comercial de patrocínio (M-10) — não há decisão do responsável; o endpoint e o modelo são genéricos, sem número inventado.
- Qualquer mudança em `deploy-pm2.yml` (achado de possível código morto, registrado no plano, não é escopo desta run).
- Qualquer mudança nos arquivos que a sessão "Redesenho do frontend do portal" tocou fora do que M-04/M-06 exigem em `HomeClient.tsx` (essa sessão já mergeou em produção antes desta run abrir — ver notas de planning).

## Suposições assumidas
- M-10 ("Patrocinado") usa o mesmo texto/estilo visual do rótulo já usado em `CartaoPremium`/`AdsSlot` para badges, sem inventar um design novo — motivo: o plano não especifica um layout exato, e o `SKILL.md` de frontend-portal já define os tokens a reutilizar.
- O plano semestral de M-07 é cadastrado via Django admin/fixture com preço R$20 (conforme BRD §6, já citado no próprio plano) — motivo: o BRD é a fonte oficial do preço, citada no próprio documento validado.
- "Produção saudável" (critério de fechamento) significa: os 3 containers de prod (`frontend`, `web`, `celery-worker`/`celery-beat`) reportando `healthy` no `docker ps` da VPS após o deploy da tag — motivo: é o mesmo critério usado nesta sessão para confirmar o deploy anterior (tag v1.0.47).

## Restrições
- Stack obrigatória: Next.js 14 (frontend/) e Django (backend/), sem novas dependências externas sem justificar em `implementation-contract.md`.
- LGPD: nenhum script de anúncio antes do consentimento (`frontend/scripts/verificar-consentimento-anuncios.mjs` é a guarda de regressão; não pode parar de passar).
- Nunca fabricar conteúdo, número, preço ou fonte para preencher espaço.
- Conteúdo patrocinado sempre identificado como tal (BRD §17).
- Mudança visual segue `.claude/skills/frontend-portal/SKILL.md`.
- Infraestrutura: host de produção com só 3,8 GB de RAM compartilhados entre dev/homolog/prod, sem observabilidade própria — endpoints GET públicos novos (M-02, M-10) devem reaproveitar os includes de rate-limit/cache do nginx já existentes (`portal-location-cache*.conf`), não criar regra solta.
- Trabalho deve ficar neste worktree isolado (`.claude/worktrees/monetizacao-sprint1`) até a abertura do PR, para não colidir com o checkout compartilhado usado por outras sessões.
- Deploy de PROD só acontece por push de tag `v*` — nunca automático por merge.

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | código dos 10 itens (M-01..M-10), 10 commits (`monetizacao(M-XX): ...`), implementation-history.md |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked por critério de aceite |
| 3 | reviewer (obrigatório — ver review-triggers.md) | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas (ex: `docs/monetizacao/RESULTADOS.md`) |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |
| 7 | orchestrator (self) | testes/review aprovados | PR → develop, merge, verificação HOMOLOG, tag vX.Y.Z, verificação PROD via SSH |

## Critérios de aceite (nível de negócio/produto)
1. `GET /api/noticias/<id>` (e o equivalente de cluster) não contém mais a chave `conteudo` com o texto raspado.
2. Notícia sem resumo próprio gera `<meta name="robots" content="noindex, follow">` e não aparece no sitemap; notícia com resumo aparece em `/sitemap.xml`.
3. Cada posição de anúncio (`AdsSlot`) pode receber um ID de slot próprio, diferente de outras posições do mesmo formato, sem mudar quem vê anúncio (Premium continua sem ver nada).
4. Em produção, nenhum texto "Google AdSense"/"slot" aparece para o leitor; no lugar, aparece um cartão de assinatura quando o anúncio não pode ser exibido.
5. Home tem no máximo 5 `AdsSlot`; leitura de notícia tem no máximo 2; `/planos` não tem nenhum.
6. `/planos` mostra 3 planos ativos (free, premium semestral, premium anual) com destaque de economia calculado a partir do preço real dos planos.
7. Leitor Free vê uma chamada para assinar dentro da leitura da notícia; Premium não vê.
8. Existe um anunciante patrocinado cadastrável via admin, com data de início/fim, que aparece rotulado como "Patrocinado" só dentro do período ativo, com registro de view/click respeitando consentimento de analytics.
9. Toda a suíte de frontend (`npm run typecheck && npm test && npm run build`) e de backend (`pytest`) passa.
10. O conjunto termina mergeado em `develop`, implantado e saudável em HOMOLOG, e implantado e saudável em PROD sob uma tag nova.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| M-04 (refatorar slot por posição) quebrar algum ponto de montagem não listado no plano | Médio | `grep -rn "<AdsSlot"` no início da implementação para ter a lista completa e exaustiva, não só a do plano |
| M-02/M-10 (endpoints públicos novos) aumentarem carga no host com só 3,8 GB de RAM | Médio | Reaproveitar cache de borda do nginx já existente (ver §0.1 do plano); medir em homolog antes do prod |
| M-07 mexer em preço/assinatura dispara revisão obrigatória e pode exigir mais de uma rodada de remediação | Médio | Revisão já marcada como obrigatória desde a abertura desta run (não esperar o executor terminar para descobrir) |
| M-10 não ter preço/anunciante real para popular o teste de aceite "fim a fim" | Baixo | Testar com dado fictício controlado em teste automatizado (não em produção) e documentar como follow-up a necessidade de um anunciante real |
| Deploy em PROD concorrer com a janela de backup do cron (03h-03h04) | Baixo | Esta run não deve agendar o merge/tag para essa janela |

## Dependências
- Nenhuma decisão humana pendente bloqueia o início: preço do semestral (BRD §6) e regra de consentimento (LGPD) já estão definidos em specs existentes.
- M-10 depende de, no futuro (fora desta run), alguém definir o que é um "espaço" comercial vendável e a tabela de preço real — isso não bloqueia a implementação do mecanismo, só o uso comercial dele.
