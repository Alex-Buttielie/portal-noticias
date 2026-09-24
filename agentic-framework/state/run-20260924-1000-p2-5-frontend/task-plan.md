<!--
CONTRACT: task-plan
DONO: orchestrator
QUANDO É CRIADO: no início de toda execução (agentic-run), antes de qualquer implementação.
-->

# Task Plan — 20260924-1000-p2-5-frontend

## Metadados
- **run_id:** 20260924-1000-p2-5-frontend
- **Data de abertura:** 2026-09-24 10:00 (America/Sao_Paulo)
- **Solicitado por:** sessão pai (subagent executor) — itens de frontend P2-5 de `ANALISE_CUSTO_PERFORMANCE.md`
- **Spec de origem:** `ANALISE_CUSTO_PERFORMANCE.md`, seção 5, “Outros (🟢)” e tabela P2-5 da seção 7; não há spec separada em `agentic-framework/specs/`.

## Objetivo
Reduzir o tráfego e o trabalho repetidos no frontend da Home sem mudar contratos de backend nem introduzir uma nova camada de cache: carregar colunistas no Server Component/ISR, simplificar o polling de últimas notícias, condicionar o AdSense ao consentimento e deixar uma única fonte de `news_view`, preservando métricas, UX e compatibilidade.

## Escopo
### Dentro do escopo
- **P2-5a:** mover a carga de `SecaoColunistas` para o servidor/ISR da Home, removendo as requisições client-side em cascata; preservar a ordenação, os cards, o fallback e os dados de perfil.
- **P2-5b:** revisar o polling de `UltimasNoticias`, que já pausa quando a aba está oculta, e aumentar o intervalo padrão para 180 s sem impedir atualização manual nem a atualização automática de última hora.
- **P2-5c:** fazer `AdsScript` consultar `permiteCategoria` e responder ao evento de consentimento; usar `lazyOnload`; manter placeholders e ausência de script quando não há publisher ID.
- **P2-5d:** eliminar a duplicação de `news_view` entre `AnalyticsTracker` e `NoticiaReporter`, mantendo a fonte que preserva `entry_tipo`, `entry_id`, categoria, tempo de leitura e scroll.
- Validar contratos contra `agentic-framework/prompts/contract-checklist.md`, executar `npx tsc --noEmit` e `npm run build`, fazer smoke HTTP se viável e registrar evidências em `implementation-history.md`.

### Fora do escopo (explicitamente)
- Backend, Django, migrations, `backend/**`, `.github/workflows/**`, `infra/nginx/**`, `docker-compose.yml` e qualquer API/cache do servidor.
- Reintroduzir `@tanstack/react-query`, `lib/queries.ts`, `lib/query-client.ts`, `@tanstack/react-table` ou `embla-carousel-react`; o fetching continua via `fetch`/`lib/api.ts` em `useEffect` ou Server Components.
- Criar endpoint agregado de colunistas ou alterar payloads/contratos de API.
- Alterar a semântica editorial do polling, remover o botão “Atualizar”, alterar o layout dos cards ou modificar a política de consentimento existente.
- Adicionar dependências, suíte de testes artificial ou alterações em mudanças de outras runs.

## Suposições assumidas
- O conteúdo da Home continua sendo revalidado pelo ISR de 60 s em `app/page.tsx`; portanto, o polling client-side não é a única forma de a Home receber conteúdo novo. — motivo: o próprio código define `export const revalidate = 60` e o requisito permite aumentar o polling.
- A menor mudança segura para colunistas é carregar os dados no servidor e passá-los como props ao componente client-only de apresentação. — motivo: `SecaoColunistas` depende de `ImagemNoticia` (client), mas não precisa ser client-side para buscar dados; não há endpoint agregado nem alteração de API autorizada.
- Consentimento para publicidade deve ser tratado pela categoria `personalizacao`, já que AdSense é publicidade/personalização de terceiros. — motivo: as categorias existentes são `analytics` e `personalizacao`, e a documentação de LGPD exige bloquear scripts não essenciais por padrão.
- `NoticiaReporter` é a fonte única de `news_view` porque já envia o evento inicial e o evento de saída com tempo/scroll; remover a derivação URL do tracker global não perde a categoria nem os identificadores da notícia. — motivo: o backend trata `news_view` como uma interação de feed e os campos da reporter são mais completos.

## Restrições
- Não fazer commit; não tocar backend, workflows, Nginx, Compose ou arquivos de outras runs.
- Preservar SSR/hidratação, estados de loading/erro/vazio, acessibilidade, links, fallbacks e telemetria existente; não introduzir dependências.
- Não carregar AdSense antes de consentimento explícito; a ausência de `NEXT_PUBLIC_ADSENSE_CLIENT_ID` deve continuar sem chamada externa e com placeholders.
- Não transformar a remoção da duplicidade de `news_view` em perda de `tempo_leitura_seg`/`scroll_max_pct`; validar por inspeção estática e, se viável, smoke.
- Registrar arquivos e linhas efetivamente alterados, decisões, evidências e limitações em `implementation-history.md`.

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | código + `implementation-history.md` |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked; `tsc`, build e smoke |
| 3 | reviewer (se `review-triggers.md` aplicar) | diff do executor | `code-review-contract.md` |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | `documentation-update.md` + docs atualizadas, se necessário |
| 6 | historian | todos os artefatos acima | `report.md` + entrada em `HISTORY.md` |

## Critérios de aceite (nível de negócio/produto)
1. Uma visita client-side à Home não executa a cascata de até seis requisições de colunistas; os cards continuam sendo renderizados com dados reais ou se ocultam honestamente quando não há dados.
2. A atualização de “Últimas notícias” continua disponível por botão e, quando automática, ocorre em uma frequência que não competes desnecessariamente com o ISR de 60 s; nenhuma requisição é disparada com a aba oculta.
3. O script do AdSense não é criado antes de consentimento de `personalizacao`, reage a uma mudança de preferências, usa `lazyOnload` e não altera o fallback quando não há ID.
4. Uma visita a uma página de notícia gera uma única instrumentação de `news_view`, preservando a categoria e os sinais de leitura/scroll; as demais métricas globais permanecem intactas.
5. `npx tsc --noEmit` e `npm run build` passam, e as páginas tocadas são verificadas por smoke HTTP quando o build standalone estiver disponível.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Buscar colunistas no servidor aumenta o tempo do ISR ou falha em ambiente sem API | médio | `Promise.all`/fallback isolado, retorno `[]` e nenhum mock de pessoas; manter a Home funcional se a seção falhar |
| Serializar dados do servidor para um client component cria props grandes ou quebra algum consumidor | médio | reutilizar o mesmo tipo `Colunista`, limitar a 4, smoke de `/` e `tsc`; nenhuma mudança de contrato de `lib/api.ts` |
| Remover polling pode deixar “Últimas” sem frescor percebido | médio | preservar atualização manual e escolher intervalo/evento de visibilidade que nãoDisable o botão |
| Consentimento forçado tarde pode perder o clique em slots já renderizados | baixo | `AdsScript` e `AdsSlot` observarem o mesmo estado/evento; manter placeholders e não inicializar slots sem permissão |
| Remover `news_view` do tracker global pode perder eventos em rotas não cobertas pela reporter | alto | inventariar todos os usos de `NoticiaReporter` e manter a reporter em todas as rotas de notícia; verificar que o tracker deixou de derivar somente `news_view` |
| Alterações preexistentes em outras runs serem confundidas com esta | alto | limitar o diff a `frontend/` nos alvos e aos artefatos desta pasta; registrar `git status`/diff sem tocar nos demais arquivos |

## Dependências
- `ANALISE_CUSTO_PERFORMANCE.md` e a implementação atual de P1-6 (camada React Query removida; não reintroduzir).
- `frontend/package.json`/lockfile e a toolchain Node/Next já instalados; nenhuma dependência nova.
- Backend/Redis/P1-A são dependências de ambiente para smoke de dados, mas não serão editados nesta run.
- A validação de `npm run build` depende das variáveis `NEXT_PUBLIC_*` já disponíveis; se a API estiver offline, registrar a limitação sem mascará-la como falha de frontend.
