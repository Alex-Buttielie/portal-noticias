<!--
CONTRACT: implementation-contract
DONO: orchestrator (preenche) / executor, tester, reviewer (leem)
QUANDO É CRIADO: logo após o task-plan.md ser aceito.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/implementation-contract.md
-->

# Implementation Contract — 20261013-1048-home-radar-central-ux

## Metadados
- **run_id:** 20261013-1048-home-radar-central-ux
- **Deriva de:** task-plan.md (20261013-1048-home-radar-central-ux)
- **Versão do contrato:** 1

## O que deve ser construído

### Bloco H — Home (frontend/components/home/*, frontend/app/noticia/*)
- **H-01 Slider de manchete:** `ManchetesGrid.tsx` hoje pega `itens[0]` como destaque fixo. Trocar por um componente de slider (ex. novo `ManchetePrincipalSlider.tsx`) que gira automaticamente entre as N primeiras manchetes (sugestão: 3-5), com: troca automática por intervalo (ex. 6-8s), pausa ao hover/foco/interação, controles de navegação (anterior/próximo + indicadores clicáveis), `aria-live="polite"` ou `role="region"` com label, `prefers-reduced-motion` desativando autoplay. Sem libs novas pesadas — CSS transitions + `useEffect`/`setInterval` client-side é suficiente.
- **H-02/H-06 Correção de corte/sobreposição:** Em `NewsCard.tsx` (variante não-destaque, linha ~153-225) adicionar `min-w-0` nos containers que faltam e `flex-wrap`/`gap` adequado na `linhaFonte` (linha ~153-189) para ela nunca overflow em cards estreitos. Ajustar `line-clamp` do título/resumo para não cortar palavra no meio de forma visualmente ruim, sem alterar a altura/largura física do card.
- **H-03 Grid mobile 2 colunas em "Por editoria":** Em `PortfolioCategorias.tsx`, trocar a lista empilhada de `NewsCard` dentro de cada bloco por um grid responsivo (`grid-cols-2` no mobile, mantendo ou ajustando desktop). Como o layout denso atual (thumbnail fixo 112px) não cabe em meia-tela mobile, criar uma variante de card compacta (nova prop de variante em `NewsCard.tsx`, ex. `"grade"`) com imagem proporcional menor/no topo e título mais curto, usada só nesse grid 2 colunas.
- **H-04 Destaque visual moderno:** melhorar hierarquia visual (tipografia, espaçamento, estados de hover/foco) dos blocos de "informação importante" da Home usando os tokens de `frontend/app/globals.css` já existentes — sem introduzir cores novas fora do design system.
- **H-05 Fotos pequenas:** garantir que a nova variante `"grade"` (H-03) e o slider (H-01) também renderizam `ImagemNoticia` quando a notícia tiver `imagem_url`.
- **H-07 Resumo editorial sem redundância:**
  - Backend: em `backend/feed/serializers.py`, adicionar campo calculado `resumo_e_fallback` (booleano) em `FonteDetalheSerializer` e `SecaoHomeSerializer`/`FeedEntrySerializer` onde fizer sentido, usando `catalogo_noticias/providers/fallback_local.py::origem_fallback_local` (via tags do item) ou comparação direta ao texto fixo — NÃO alterar o texto nem `verificar_sem_fabricacao`.
  - Frontend: em `frontend/app/noticia/LeituraPremium.tsx`, quando `resumo_e_fallback` for `true`: mostrar o aviso **uma única vez** (ex. uma nota pequena/discreta próxima ao título, não como lead com drop-cap em `text-lg`/`first-letter`), suprimir a repetição no preview truncado (linha ~107) e na lista por fonte (linha ~201) quando o resumo de cada fonte também for fallback.

### Bloco R — Radar (frontend/app/radar/*, frontend/components/RadarLocalSimples.tsx, frontend/components/CompartilharLocalizacao.tsx, backend/radar/*, backend/enderecos/*)
- **R-01 Um clique para detectar:** Em `RadarLocalSimples.tsx`, o botão "Detectar" hoje só faz `setMostrarCompartilhar(v => !v)` (revela `CompartilharLocalizacao` compacto, que tem seu próprio botão "Detectar"). Unificar: o primeiro clique já deve chamar o fluxo real de geolocalização (reaproveitando a lógica de `CompartilharLocalizacao`/`regiao.ts::obterRegiaoPorGeolocation`, incluindo os estados de erro/fallback por IP já tratados) — sem exigir um segundo clique com o mesmo rótulo.
- **R-02 Busca por estado real:**
  - Backend (`backend/radar/`): trocar o filtro de `cidade__iexact` por filtro de `estado` (normalizado, ex. sigla UF). Quando o filtro vier de texto livre (não só UF), resolver via `backend/enderecos/` (ex. `listar_estados`/busca de endereço já existente) para a UF correspondente antes de filtrar — nunca inventar estado quando a resolução falhar (nesse caso, retornar vazio com mensagem clara, não erro 500).
  - Adicionar um módulo/tabela estática com a coordenada (lat/lon) de cada UF brasileira (capital ou centróide — dado público, documentado como fonte no código). Expor no endpoint do Radar a distância (Haversine) entre a coordenada resolvida do usuário (quando houver, via `Regiao.lat/lon` que o frontend já coleta mas hoje não envia) e a coordenada da UF de cada item retornado; ordenar os resultados por essa distância crescente quando a coordenada do usuário estiver disponível (fallback: ordenar por recência quando não houver coordenada do usuário).
  - Frontend: `RadarClient.tsx`/`lib/api.ts` passam a enviar `lat`/`lon` (quando disponíveis em `Regiao`) além de `estado`, e a UI reflete "notícias de {UF}" em vez de prometer filtro por cidade que não existe.
- **R-03 Redesenho estilo marketplace:** Reconstruir a página `/radar` com um layout de grid de cards (foto + título + UF + tempo + categoria) e uma barra de filtros (categoria, UF/estado, período) + busca textual + seletor de ordenação (proximidade/recência), preservando como estão (ou integrando visualmente) as abas/funcionalidades existentes: Tendências (público), Evolução (gated `radar_avancado`), localidades salvas (`obterLocalidadesSalvas`/`salvarLocalidade`/`removerLocalidade`). Sem mapa interativo.

### Bloco C — Central/Admin (frontend/app/admin/*, backend/painel_admin/*, backend/catalogo_noticias/robos_*, backend/gating/*)
- **C-01 Usuários:**
  - Backend: novo endpoint de criação de usuário pelo admin (ex. `POST /api/admin/usuarios/`) em `painel_admin/views.py`, delegando a criação real a `backend/identidade/services.py` (reaproveitar validações existentes de e-mail/senha), auditado via `painel_admin/services.py::auditar`. Papel inicial e bloqueio (`is_active`) via `UsuarioUpdateSerializer` (já existe, só precisa de UI).
  - Frontend (`frontend/app/admin/usuarios/page.tsx`): paginação real (usar `?page=` já suportado por `AdminPagination`), filtro por papel na UI, seletor completo de papel (free/premium/admin) em vez do toggle binário atual, ação de bloquear/desbloquear (`is_active`), formulário de criação de usuário.
- **C-02/C-03/C-04 Responsividade:** Em `frontend/app/admin/robos/page.tsx`: adicionar `min-w-0` nos containers de grid/flex que hoje têm filhos `truncate` sem conseguir encolher (cards de métricas ~linha 293-313, barras "sucesso por fonte" ~linha 340, lista de fontes ~linha 347-417); corrigir `TabsList` (`frontend/components/ui/tabs.tsx` + uso em `robos/page.tsx` ~linha 316-322) para não travar em `h-10` quando `flex-wrap` estiver ativo (usar `h-auto`/`min-h-10` condicional). Validar em viewport de 375px de largura.
- **C-05 Histórico:**
  - Backend: em `catalogo_noticias/robos_views.py::_executar_ingestao_em_background`, persistir também execuções que falharam (novo registro `RegistroExecucaoIngestao` com o erro, ou campo/flag indicando falha — decidir o modelo mínimo necessário sem migração destrutiva).
  - Nova view/serializer de leitura para `AuditoriaAdmin` (`painel_admin/models.py`) — paginada, filtrável por tipo de ação (`acao`)/por quem alterou.
  - Frontend: nova seção/aba (ou expansão da aba "Histórico" existente em `robos/page.tsx`) exibindo esse histórico de ações administrativas, cronológico, filtrável, expansível para detalhe — sem poluir a tela.
- **C-06 Configurações:**
  - Unificar o CRUD de fontes: manter a implementação completa em um lugar só (recomendado: `robos/page.tsx`, já mais completo) e `FontesIsland.tsx` em `/admin/configuracoes` passa a ser um link/atalho em vez de duplicar a lógica.
  - Nova view/serializer de leitura para `FeatureLimitAlteracaoLog` (`gating/models.py`), exposta em `/admin/limites` ou `/admin/configuracoes`.
- **C-07 Métricas:**
  - Backend: campo `last_seen` (ou equivalente) atualizado de forma barata (throttle — só grava se passou N minutos desde o último valor) em requisições autenticadas; endpoint/contagem de usuários com `last_seen` dentro da janela de "ativo agora" (ex. 5 min).
  - Dashboard raiz (`frontend/app/admin/page.tsx`): exibir essa métrica; popular "Atividade recente" com dados reais de `AuditoriaAdmin` + `RegistroExecucaoIngestao` (mesclados por timestamp); considerar expor custo/execuções de robôs também aqui ou na Central de Inteligência (`/admin/metricas`).

## Áreas/arquivos esperados
- `frontend/components/home/ManchetesGrid.tsx`, novo `ManchetePrincipalSlider.tsx`, `NewsCard.tsx`, `PortfolioCategorias.tsx`, `ConteudoBombando.tsx` (se precisar ajuste de grid)
- `frontend/app/noticia/LeituraPremium.tsx`, `backend/feed/serializers.py`
- `frontend/app/radar/*`, `frontend/components/RadarLocalSimples.tsx`, `frontend/components/CompartilharLocalizacao.tsx`, `frontend/lib/regiao.ts`, `frontend/lib/api.ts`, `backend/radar/*`, `backend/enderecos/*`
- `frontend/app/admin/usuarios/page.tsx`, `backend/painel_admin/*`, `backend/identidade/services.py`
- `frontend/app/admin/robos/page.tsx`, `frontend/components/ui/tabs.tsx`, `backend/catalogo_noticias/robos_views.py`, `backend/catalogo_noticias/models.py`
- `frontend/app/admin/configuracoes/*`, `backend/gating/*`
- `frontend/app/admin/page.tsx`, `frontend/app/admin/metricas/page.tsx`, `backend/metricas/*`
- Migrações Django novas conforme necessário (ex. `last_seen` em `identidade/models.py`, flag de falha em `RegistroExecucaoIngestao`)

## Interfaces afetadas
- API: `GET /api/radar/tendencias/` e `GET /api/radar/evolucao/` passam a aceitar/usar `estado` (em vez de depender de `cidade`) e opcionalmente `lat`/`lon`.
- API: novo `POST /api/admin/usuarios/` (criação de usuário pelo admin).
- API: novo endpoint de leitura de `AuditoriaAdmin` e de `FeatureLimitAlteracaoLog`.
- Serializers: `FonteDetalheSerializer`/`SecaoHomeSerializer` ganham `resumo_e_fallback`.
- Modelo: novo campo `last_seen` em `identidade.User` (ou modelo auxiliar); possível novo campo/flag em `RegistroExecucaoIngestao` para marcar falha.

## Critérios de aceite (técnicos, testáveis)
1. Dado o feed de Home com ≥3 manchetes, quando a página carrega, então o slider troca de manchete automaticamente após o intervalo configurado e pausa ao focar/hover; com `prefers-reduced-motion: reduce`, não troca automaticamente.
2. Dado um card `NewsCard` (qualquer variante) renderizado em viewport de 320-375px, quando inspecionado, então nenhum texto/elemento ultrapassa a largura do card (sem overflow horizontal da página).
3. Dado o bloco "Por editoria" em viewport mobile, quando renderizado, então os cards aparecem 2 por linha sem overflow horizontal da página.
4. Dado um item cujo resumo é exatamente o texto fixo de fallback, quando a página de notícia é renderizada, então o aviso aparece exatamente uma vez na página inteira (contagem de ocorrências do texto no DOM == 1).
5. Dado o Radar sem localização salva, quando o usuário clica em "Detectar" uma vez e concede permissão de geolocalização, então a localização é resolvida sem exigir um segundo clique.
6. Dado um usuário que define uma localidade cujo estado é resolvível (ex. "Trindade" → GO), quando aplica o filtro, então o Radar retorna notícias com `estado="GO"` (ou equivalente), ordenadas por distância crescente até a UF quando houver coordenada do usuário.
7. Dado as abas Tendências/Evolução/localidades salvas do Radar antes da reconstrução, quando a página é reconstruída, então elas continuam funcionando (teste de regressão).
8. Dado um admin autenticado, quando acessa `/admin/usuarios`, então consegue paginar, filtrar por papel, promover/despromover para premium/admin, bloquear/desbloquear e criar um novo usuário — cada ação reflete no backend (`UsuarioUpdateSerializer`/novo endpoint de criação) e é auditada em `AuditoriaAdmin`.
9. Dado `/admin/robos` em viewport de 375px, quando renderizado em qualquer aba (Visão geral/Fontes/Configuração/Histórico), então não há overflow horizontal e as abas não se sobrepõem ao conteúdo.
10. Dado uma execução de ingestão que falha, quando finaliza, então aparece um registro no histórico (não fica silenciosa).
11. Dado o histórico de ações administrativas (`AuditoriaAdmin`) com registros existentes, quando o admin acessa a nova tela, então consegue visualizar e filtrar por tipo de ação.
12. Dado um usuário autenticado fazendo requisições, quando `last_seen` é verificado no dashboard admin, então a contagem de "ativos agora" reflete usuários com atividade nos últimos 5 minutos (ajustável, mas documentado).
13. Suite de testes backend existente (pytest, cobertura ≥80%) e frontend (typecheck/build/lint) continuam passando após todas as mudanças.

## Não-objetivos
- Popular `cidade`/lat-lon por notícia via NLP/geocoding de conteúdo (fora de escopo — ver task-plan).
- Backfill retroativo de localização nas notícias já ingeridas.
- Mapa interativo com pins por notícia.
- Logo oficial de qualquer fonte/veículo de notícia.
- Sistema de presença em tempo real via WebSocket para "usuários ativos agora" (usar `last_seen` por polling/requisição é suficiente).
- Qualquer alteração em `_FRASE_SEM_RESUMO_EDITORIAL` ou `verificar_sem_fabricacao`.

## Restrições técnicas
- **Performance:** atualização de `last_seen` não pode gerar um `UPDATE` em toda requisição autenticada — usar throttle (ex. só atualizar se passaram ≥60s desde o último valor).
- **Segurança/privacidade:** coordenadas do usuário (`lat`/`lon`) usadas só para calcular distância na resposta do Radar, nunca persistidas em texto claro associadas ao usuário sem necessidade; qualquer nova chamada HTTP externa usa `SessaoEgress`. Criação/bloqueio de usuário pelo admin deve ser auditada (`AuditoriaAdmin`).
- **Dependências permitidas:** nenhuma biblioteca nova de mapa/geolocalização paga. Bibliotecas de slider/carrossel leves (ex. CSS puro ou algo já presente em `package.json`) são preferíveis a uma nova dependência — se uma nova dependência for estritamente necessária, justificar aqui antes de adicionar.
- **Estilo/convenções:** seguir `models.py`→`services.py`→`serializers.py`→`views.py`→`urls.py` no backend; gating via `gating.services`; tokens de design de `frontend/app/globals.css`.

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite técnicos (1-13) implementados
- [ ] Testes escritos e passando (tester)
- [ ] Revisão de código aprovada (obrigatória — gatilhos: dados de geolocalização, dados pessoais de usuário/controle de acesso, diff >300 linhas)
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente
