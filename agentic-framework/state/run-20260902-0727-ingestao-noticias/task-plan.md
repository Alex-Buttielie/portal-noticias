# Task Plan — 20260902-0727-ingestao-noticias

## Metadados
- **run_id:** 20260902-0727-ingestao-noticias
- **Data de abertura:** 2026-09-02
- **Solicitado por:** usuário, via `agentic-run` (referenciando a spec abaixo)
- **Spec de origem:** `agentic-framework/specs/ingestao-curadoria-noticias.md`

## Objetivo
Ao final desta execução, o sistema deve conseguir ingerir notícias de um conjunto inicial de fontes RSS públicas, deduplicar/agrupar cobertura do mesmo acontecimento em `NewsCluster`, gerar resumo próprio via `SummarizationProvider` (LLM de terceiros, atrás de interface abstrata), classificar relevância/urgência, e encaminhar itens de alta relevância para uma fila de revisão humana — tudo com fonte original sempre rastreável.

## Escopo

### Dentro do escopo
- App Django `catalogo-noticias/` (ver `ARCHITECTURE.md` seção 2): modelos `NewsItem` e `NewsCluster`.
- `NewsSourceProvider`: implementação concreta para ingestão via RSS (feedparser ou equivalente), plugável, com as 4 fontes-semente abaixo.
- Job periódico (Celery + Redis, já decidido em `ARCHITECTURE.md` seção 1) de ingestão.
- Deduplicação/agrupamento por acontecimento (`NewsCluster`).
- `SummarizationProvider`: interface abstrata + uma implementação concreta via API de LLM de terceiros, usada para gerar resumo próprio (nunca reproduzir o texto original) e apoiar a classificação de relevância/urgência.
- Fila de revisão humana (flag `status_revisao` no `NewsItem`) para itens que baterem no critério de alta relevância.
- Critério de alta relevância como regra parametrizável (`FeatureLimit`-like, mas específico deste módulo — ver "Suposições assumidas").
- Observabilidade mínima: contagem de itens ingeridos por fonte, taxa de deduplicação, custo/uso do `SummarizationProvider` por execução.
- Resiliência: falha de uma fonte não pode travar a ingestão das demais.

### Fora do escopo (explicitamente)
- Frontend/feed de consumo (spec `feed-consumo-noticias.md`, execução futura).
- Radar de tendências por localização (fase "Inteligência" do roadmap).
- Painel administrativo dedicado para a fila de revisão humana (esta execução expõe os dados via Django admin nativo, não uma UI customizada — suficiente para o admin operar no MVP).
- Fontes além das 4 listadas abaixo — adicionar fonte nova é operação de configuração, não escopo desta execução.
- Validação jurídica formal dos termos de uso de cada fonte (ver "Suposições assumidas" — decisão do usuário foi usar RSS público para viabilizar o pipeline técnico agora; validação jurídica antes de produção real continua pendente, conforme BRD §18).

## Suposições assumidas
- **Fontes-semente (RSS público):** G1 (`https://g1.globo.com/rss/g1/`), UOL (`https://rss.uol.com.br/feed/noticias.xml`), CNN Brasil (`https://www.cnnbrasil.com.br/feed/`), Folha "Em Cima da Hora" (`https://feeds.folha.uol.com.br/emcimadahora/rss091.xml`) — escolhidas pelo usuário como opção "RSS público de grandes veículos brasileiros" para viabilizar o pipeline técnico do MVP. **Motivo/ressalva:** o próprio BRD (seção 18) exige validação jurídica dos termos de uso de cada fonte antes do lançamento comercial — essa validação NÃO foi feita aqui, é uma decisão técnica para desenvolvimento/teste, registrada como follow-up obrigatório antes de qualquer uso em produção real. As URLs de RSS não foram verificadas ao vivo nesta etapa de planejamento; o executor deve validar/ajustar se algum feed estiver indisponível ou tiver mudado de endereço.
- **Critério de alta relevância (aciona revisão humana):** regra simples e parametrizável, conforme decisão do usuário — nesta execução, definida como: (a) categoria pertence a uma lista parametrizável de categorias sensíveis (default sugerido: política, economia, segurança pública), OU (b) o cluster agrega cobertura de 3 ou mais fontes distintas sobre o mesmo acontecimento. Ambos os parâmetros (lista de categorias, limiar de fontes) devem ser configuráveis pelo admin, não hardcoded. **Motivo:** é um ponto de partida funcional, não a definição final de produto — o usuário optou por não travar a execução nisso agora.

## Restrições
- Stack obrigatória: Python/Django + Celery + Redis, PostgreSQL (`ARCHITECTURE.md` seção 1).
- Direitos autorais: nenhum `NewsItem` pode ser publicado sem referência rastreável à fonte original; resumo deve ser conteúdo próprio via `SummarizationProvider`, nunca cópia integral do texto da fonte (BRD §18) — este é o critério de aceite mais crítico desta execução.
- Observabilidade de custo de IA desde já (BRD §30, risco "Custo de IA/infraestrutura").

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | código + implementation-history.md |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked |
| 3 | reviewer (obrigatório — ver review-triggers.md) | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. O sistema ingere notícias das 4 fontes RSS configuradas periodicamente, sem que a falha de uma fonte impeça a ingestão das demais.
2. Um mesmo acontecimento coberto por múltiplas fontes aparece agrupado em um único `NewsCluster`, não como itens duplicados soltos.
3. Todo `NewsItem` mantém URL e identificação da fonte original, de forma rastreável.
4. Todo `NewsItem` publicado tem um resumo próprio gerado via `SummarizationProvider` — nunca o texto integral da fonte copiado.
5. Itens que atendem ao critério de alta relevância (parametrizável) entram em fila de revisão humana antes de ficarem visíveis publicamente; os demais podem ser publicados automaticamente.
6. É possível saber, por execução de ingestão, quantos itens vieram de cada fonte, qual a taxa de deduplicação, e o custo/uso do `SummarizationProvider`.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Feeds RSS escolhidos como semente podem estar desatualizados/indisponíveis no momento da implementação | Médio | Executor valida e ajusta a lista, documentando qualquer substituição em `implementation-history.md` |
| Uso de conteúdo de fontes sem validação jurídica formal dos termos de uso (BRD §18) | Alto (mas explicitamente aceito para fins de desenvolvimento/teste, não produção) | Follow-up obrigatório registrado no `run-state.json`: validação jurídica antes de qualquer uso em produção real |
| Custo variável de chamadas ao provedor de LLM de terceiros | Alto (risco já listado no BRD §30) | Observabilidade de uso/custo desde esta execução (critério de aceite 6) |
| Ausência de credenciais reais de um provedor de LLM neste ambiente de execução | Médio | `SummarizationProvider` implementado com interface abstrata + implementação concreta testável via mock; teste de integração real com o provedor fica como follow-up manual, análogo ao que já ocorreu com Google OAuth no run anterior |

## Dependências
- Nenhuma decisão humana adicional bloqueia esta execução — as duas questões em aberto da spec (lista de fontes e threshold de relevância) foram resolvidas pelo usuário e estão registradas em "Suposições assumidas".
- Depende do módulo `identidade/` já entregue (run `20260901-2135-cadastro-auth`) apenas indiretamente (nenhuma dependência de código direta nesta execução — `catalogo-noticias/` é um app novo e independente).
