# Task Plan — 20260902-1409-feed-consumo

## Metadados
- **run_id:** 20260902-1409-feed-consumo
- **Data de abertura:** 2026-09-02
- **Solicitado por:** usuário ("continue a implementação do meu software até que eu tenha um MVP para iniciar")
- **Spec de origem:** `agentic-framework/specs/feed-consumo-noticias.md`

## Objetivo
Ao final desta execução, um visitante ou usuário autenticado deve conseguir navegar pelo feed de notícias (com categoria/urgência), filtrar por categoria, buscar por palavra-chave, e abrir a página de detalhe de um acontecimento (resumo, fontes agrupadas com link, categoria, timestamp) — via API backend testável. Publicidade é sinalizada como ativa para visitante/Free e ausente para Premium.

## Escopo

### Dentro do escopo
- App Django `feed/` (novo) consumindo os modelos `NewsItem`/`NewsCluster` já existentes em `catalogo_noticias` (run `20260901-0727-ingestao-noticias`) — sem duplicar modelo, só leitura.
- Endpoint de feed principal: lista paginada de `NewsCluster`/`NewsItem` publicáveis (`status_revisao` em `aprovado` ou `nao_aplicavel` — nunca `pendente`/`rejeitado`), ordenados por relevância/recência, com categoria e flag `urgente`.
- Filtro por categoria.
- Busca textual por palavra-chave (título/resumo).
- Endpoint de detalhe de um `NewsCluster`/`NewsItem` isolado: resumo, lista de fontes (quando agrupado), categoria, timestamps, link para cada fonte original.
- Campo `exibir_publicidade` no payload de resposta: `true` para visitante/usuário `free`, `false` para `premium` — usa o campo `papel` do `User` já existente no módulo `identidade/`, sem esperar o módulo `gating-free-premium` completo (a matriz completa de limites fica para a execução daquela spec; aqui só o "sim/não anúncio", que é direto).
- Testes automatizados cobrindo os critérios de aceite abaixo.

### Fora do escopo (explicitamente)
- Linha do tempo de assuntos de longa duração (BRD §22) — extensão futura do agrupamento.
- Personalização avançada do feed (ordenação por interesse do usuário, histórico) — fica para `gating-free-premium.md`.
- Newsletter (BRD §27) — spec própria futura.
- Frontend (Next.js) consumindo esta API — mesma decisão já tomada no run de `identidade/`: API primeiro, UI em execução futura dedicada.
- Radar de tendências por localização.

## Suposições assumidas
- **Lista inicial de categorias** (questão em aberto da própria spec): Política, Economia, Esportes, Tecnologia, Saúde, Cultura, Cidades, Mundo, Ciência — lista de referência para o filtro de categoria, não travada em código (mesmo padrão já usado em `catalogo_noticias`: strings livres armazenadas no campo `categoria` do `NewsItem`, o filtro aceita qualquer valor existente nos dados, não uma lista fechada validada). **Motivo:** a spec marcava isso como questão em aberto sem bloquear a execução; optei por não travar uma enumeração fixa no banco (ficaria rígido demais para o estágio do produto), e sim documentar uma lista de referência para o conteúdo inicial.
- **Itens com `status_revisao=pendente` nunca aparecem no feed público** — decisão consistente com o propósito da fila de revisão humana (`ingestao-curadoria-noticias.md`), mesmo não estando escrito literalmente nesta spec. **Motivo:** a spec de feed não repete essa regra porque ela já pertence ao módulo de curadoria — mas a ausência de enforcement aqui tornaria a fila de revisão inútil (itens pendentes vazariam para o público antes de aprovação).

## Restrições
- Stack obrigatória: Python/Django + DRF, PostgreSQL (`ARCHITECTURE.md` seção 1) — mesmo projeto/backend já existente, novo app.
- Sem autenticação obrigatória para o feed público básico (spec, requisito funcional 6) — mas a API deve funcionar tanto para visitante quanto para usuário autenticado, sem tratamento de erro diferente entre os dois.

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | código + implementation-history.md |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked |
| 3 | reviewer (ver review-triggers.md) | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. Um visitante (sem login) consegue listar o feed de notícias publicáveis, sem erro de autenticação.
2. É possível filtrar o feed por categoria.
3. É possível buscar notícias por palavra-chave e receber resultados relevantes (título ou resumo contém o termo).
4. Ao abrir o detalhe de um acontecimento coberto por múltiplas fontes, o usuário vê o resumo e a lista de todas as fontes agrupadas, cada uma com link para a matéria original.
5. Nenhum item com `status_revisao=pendente` ou `rejeitado` aparece no feed público ou na busca, em nenhuma circunstância.
6. Um usuário Premium autenticado recebe `exibir_publicidade=false`; um visitante ou usuário Free recebe `exibir_publicidade=true`.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Dependência dos modelos `NewsItem`/`NewsCluster` de `catalogo_noticias`, cuja última alteração (run `20260902-0727-ingestao-noticias`) ainda não foi validada por execução de testes nesta sessão | Médio | Esta execução não altera `catalogo_noticias`, só lê — mas ambas devem ser validadas pela suíte de testes assim que possível; registrado como follow-up em ambos os `run-state.json` |
| Falta de índice de busca full-text real (banco pode não ter extensão de busca configurada) | Baixo/Médio | MVP usa busca simples (`icontains`/`Q` objects do Django ORM); busca full-text (ex: Postgres `SearchVector`) fica como otimização futura, não critério de aceite |
| Execução de código/testes possivelmente ainda indisponível nesta sessão (ver run `20260902-0727-ingestao-noticias`) | Alto | Implementação será feita com o mesmo rigor de leitura manual já demonstrado; validação por execução assim que as ferramentas normalizarem, antes de considerar esta run fechada |

## Dependências
- Nenhuma decisão humana adicional pendente — a única questão em aberto da spec (lista de categorias) foi resolvida como suposição registrada acima, de baixo risco/reversível.
- Depende tecnicamente de `catalogo_noticias.NewsItem`/`NewsCluster` (código já existe); depende operacionalmente da validação por teste do run `20260902-0727-ingestao-noticias` para ter confiança total no dado subjacente, mas isso não bloqueia iniciar a implementação desta camada de leitura.
