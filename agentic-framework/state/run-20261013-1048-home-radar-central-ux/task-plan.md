<!--
CONTRACT: task-plan
DONO: orchestrator
QUANDO É CRIADO: no início de toda execução (agentic-run), antes de qualquer implementação.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/task-plan.md
-->

# Task Plan — 20261013-1048-home-radar-central-ux

## Metadados
- **run_id:** 20261013-1048-home-radar-central-ux
- **Data de abertura:** 2026-10-13
- **Solicitado por:** usuário (buttielle3@gmail.com), em chat direto com a sessão principal
- **Spec de origem:** N/A — pedido direto do usuário, sem BRD/spec específica referenciada. Escopo fechado em chat (pergunta de esclarecimento sobre logos de fonte respondida: "descarta essa modificação").

## Objetivo
Corrigir problemas de responsividade/UX na Home e na área administrativa "Central", tornar o Radar de busca por localidade de fato funcional (hoje não retorna resultados), e adicionar melhorias de produto (slider de manchete, destaque visual moderno, CRUD de usuários mais completo, histórico de execuções e auditoria administrativa visível, mais métricas operacionais) — mantendo 100% das funcionalidades hoje existentes.

## Escopo
### Dentro do escopo
- **H-01:** Slider automático para a manchete principal da Home (hoje estática).
- **H-02:** Corrigir corte/sobreposição de dados nos cards de "Por editoria".
- **H-03:** Grid de 2 colunas no mobile para os cards de "Por editoria", sem estourar a tela.
- **H-04:** Destaque visual moderno (hierarquia/UI) para informações importantes da Home.
- **H-05:** Garantir foto pequena nos cards quando a notícia tiver imagem (validar nas novas variantes).
- **H-06:** Melhor enquadramento de texto nas manchetes sem cortar informação e sem aumentar o card.
- **H-07:** Remover a redundância do aviso de "resumo editorial não gerado" na página de notícia — mostrar uma única vez, de forma discreta.
- **R-01:** Corrigir o fluxo do Radar que hoje exige 2 cliques para detectar localização (deve ser 1).
- **R-02:** Corrigir a busca por localidade no Radar (hoje sempre vazia) — filtrar por ESTADO (não cidade, que nunca é populada) e ordenar por proximidade real (distância entre a localização do usuário e a UF de cada notícia).
- **R-03:** Reconstruir a página /radar em estilo "marketplace" (grid + filtros + busca + ordenação), preservando as funcionalidades existentes (Tendências/Evolução/localidades salvas).
- **C-01:** Central → Usuários: paginação, filtro por papel, seletor completo de papel, bloquear/desbloquear, criação de usuário pelo admin.
- **C-02/C-03:** Central → Robôs/Fontes: corrigir overflow mobile dos cards de métricas e das listas.
- **C-04:** Central → corrigir quebra/sobreposição do agrupamento de abas (Visão geral/Fontes/Configuração/Histórico) no mobile.
- **C-05:** Central → Histórico: persistir execuções que falham (hoje só grava sucesso) e expor leitura do histórico de ações administrativas (`AuditoriaAdmin`, hoje sem UI).
- **C-06:** Central → Configurações: unificar o CRUD de fontes duplicado e expor leitura do log de alterações de limites (`FeatureLimitAlteracaoLog`, hoje sem UI).
- **C-07:** Central → Métricas: adicionar "usuários ativos agora" e mais métricas/gráficos operacionais no dashboard raiz.

### Fora do escopo (explicitamente)
- **Logo real de cada fonte (G1, UOL, etc.) nas notícias** — descartado pelo usuário por risco de marca registrada sobre 91 veículos agregados; não reproduzir arte oficial de nenhuma marca de terceiro.
- Granularidade de cidade/bairro no Radar (exigiria popular `NewsItem.cidade`/lat-lon via NLP de extração de local no texto da notícia, para 55.817+ itens — fora de escopo desta execução; o Radar vai operar por ESTADO, que é o dado real disponível).
- Backfill retroativo de geolocalização/cidade nas notícias já existentes no banco.
- Mapa interativo com pins por notícia no Radar (sem dado de coordenada por notícia que o justifique).
- Qualquer alteração no texto fixo `_FRASE_SEM_RESUMO_EDITORIAL` ou na lógica anti-fabricação `verificar_sem_fabricacao` (só a apresentação no frontend muda, nunca o texto/regra).

## Suposições assumidas
- **Seletor de papel completo em vez de toggle binário (C-01):** o usuário pediu "mais funcionalidades" de forma geral para a aba usuários; assumi que isso inclui poder definir Premium diretamente pela Central (o backend já suporta `papel=premium` via PATCH) — motivo: já é suportado pelo backend, só falta UI, e é a lacuna mais óbvia do CRUD atual.
- **Critério de "usuário ativo agora" (C-07):** usuário pediu a métrica mas não definiu a janela; assumi "ativo nos últimos 5 minutos" (via `last_seen` atualizado em requisição autenticada) — motivo: janela padrão de mercado para "online agora", evita infraestrutura de presença em tempo real (websocket) fora de escopo.
- **Ordenação por proximidade no Radar (R-02):** usuário pediu ordenação "do mais próximo pro mais distante"; como não há coordenada por notícia, assumi distância Haversine entre a coordenada resolvida do usuário e a coordenada da capital/centróide de cada UF presente no resultado — motivo: é o dado geográfico real disponível sem fabricar nada, e o próprio usuário já havia dito "ver todas as notícias do estado" (confirmando granularidade de estado).
- **Criação de usuário pelo admin (C-01):** assumi fluxo simples (admin define e-mail + papel inicial, sistema gera senha temporária ou envia link de definição de senha, reaproveitando o que já existe em `backend/identidade/`) em vez de inventar um fluxo de convite novo — motivo: menor superfície nova, reaproveita infraestrutura de auth existente.
- Execução em modo não supervisionado quanto a detalhes de implementação (o usuário pediu explicitamente para não ser interrompido); decisões de design/arquitetura dentro do escopo acima são do orchestrator/executor, documentadas no `implementation-history.md`.

## Restrições
- Não alterar o texto/lógica anti-fabricação do resumo editorial (`fallback_local.py`), só a apresentação.
- Gating de feature Premium sempre via `gating.services.exigir_feature`/`has_feature`, nunca checando `papel` diretamente.
- Qualquer chamada HTTP externa nova deve usar `config.egress.SessaoEgress`.
- Sem novas dependências de mapa/geolocalização pesadas (ex. Google Maps com chave paga) — Radar não usa mapa interativo nesta execução.
- Compatibilidade retroativa: nenhuma funcionalidade hoje existente (Tendências, Evolução, localidades salvas, CRUD de fontes, etc.) pode regredir.
- Entrega deve ficar íntegra e passável pelo pipeline normal do projeto (dev→homolog→main/tag→prod) ao final — a promoção em si é conduzida pela sessão principal, não por este run.

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor (3 chamadas: Home, Radar, Central) | implementation-contract.md | código + implementation-history.md |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked |
| 3 | reviewer (obrigatório — ver review-triggers.md) | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. A manchete principal da Home alterna automaticamente entre várias notícias de destaque (slider), sem travar a navegação do usuário.
2. Nenhum card da Home ("Por editoria" e demais) corta texto ou sobrepõe elementos em nenhuma largura de tela, incluindo mobile (2 por linha em "Por editoria" sem estourar a viewport).
3. A página de notícia mostra o aviso de "resumo não gerado" no máximo uma vez, de forma discreta, quando aplicável — nunca repetido.
4. No Radar, 1 clique é suficiente para detectar a localização do usuário.
5. No Radar, buscar por uma localidade (texto, CEP ou GPS) retorna notícias reais do estado correspondente, ordenadas da mais próxima para a mais distante.
6. A página /radar tem uma experiência de descoberta em grid com filtros (categoria, estado, período) e busca textual, sem perder Tendências/Evolução/localidades salvas.
7. Na Central, um admin consegue: paginar/filtrar usuários por papel, promover/despromover (free/premium/admin), bloquear/desbloquear conta, e criar um novo usuário — tudo pela UI.
8. Na Central, os cards de robôs/fontes e o agrupamento de abas não estouram nem se sobrepõem em tela de celular (375px).
9. A aba Histórico da Central mostra execuções que falharam (não só sucesso) e um histórico de ações administrativas legível.
10. A Central mostra "usuários ativos agora" e métricas/gráficos operacionais adicionais no dashboard raiz.
11. Nenhuma funcionalidade hoje existente deixou de funcionar (regressão zero) — validado por testes automatizados.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Escopo grande (17 frentes) num único run pode gerar diff difícil de revisar | Alto | Executor divide a implementação em 3 blocos coerentes (Home, Radar, Central), cada um registrado como iteração própria em implementation-history.md; reviewer avalia o diff completo ao final |
| Radar mexe em dados de geolocalização do usuário (gatilho obrigatório de review) | Alto | Review obrigatória (ver review-triggers.md), com foco em privacidade (não persistir lat/lon do usuário sem necessidade, não logar coordenadas) |
| CRUD de usuário (criar/bloquear) toca dados pessoais e controle de acesso | Alto | Review obrigatória; reaproveitar `UsuarioUpdateSerializer`/fluxo de auth existente em vez de criar caminho novo de autenticação |
| "Usuários ativos agora" pode introduzir escrita em toda requisição autenticada (custo de performance) | Médio | Atualizar `last_seen` de forma barata (ex. só quando passou N minutos desde a última atualização, não em toda request) |
| Reescrever /radar por completo pode regredir Tendências/Evolução | Médio | Tester cobre explicitamente que as abas existentes continuam funcionando após a reconstrução visual |

## Dependências
- Nenhuma decisão humana pendente — escopo fechado em chat antes da abertura deste run (logo de fonte descartado).
- Depende da infraestrutura já existente em `backend/enderecos/` (geocoding) e `backend/painel_admin/` (usuários/auditoria) permanecer estável durante a execução.
