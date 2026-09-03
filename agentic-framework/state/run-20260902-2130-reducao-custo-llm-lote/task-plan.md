# Task Plan — 20260902-2130-reducao-custo-llm-lote

Solicitado por: usuário, após configurar uma `CATALOGO_NOTICIAS_LLM_API_KEY` real (OpenAI): "preciso de uma abordagem que diminua consideravelmente o custo e as chamadas" (referindo-se ao comentário de que o pipeline chama o `SummarizationProvider` uma vez por notícia).

## Contexto e restrição central
`services/ingestao.py` chama o `SummarizationProvider` uma vez por `NewsItem`, NUNCA uma vez por grupo/cluster — essa é uma correção estrutural deliberada (code-review-contract.md run 20260902-0727-ingestao-noticias, 3a passada, Finding 1) contra misattribution de conteúdo (BRD seção 18): compartilhar um resumo entre itens de fontes diferentes cria risco de atribuir o resumo de um fato a uma fonte que noticiou outro fato. **Essa garantia não pode ser revertida** só para reduzir custo — seria reintroduzir um bug já corrigido depois de 3 rodadas de revisão.

## Abordagem escolhida: batching de chamadas, não de conteúdo
Em vez de "1 chamada por item", agora é "N itens INDEPENDENTES por chamada, cada um com seu PRÓPRIO resumo, nunca combinados". Implementado via:
1. Novo método `SummarizationProvider.resumir_e_classificar_em_lote(itens) -> list[ResultadoResumo]` (não-abstrato na base, com implementação padrão que chama `resumir_e_classificar` item a item — preserva 100% o comportamento de todos os dublês/mocks de teste já existentes, que não sobrescrevem este método).
2. `LLMHttpSummarizationProvider` sobrescreve com uma chamada HTTP real em lote: prompt numera cada notícia, resposta esperada é uma lista JSON com um objeto `{"id", "resumo", "categoria", "urgente"}` por notícia. Mapeamento da resposta feito por `id`, nunca por posição — um id ausente/inválido vira fallback (resumo vazio, força revisão humana) isolado para AQUELE item, sem afetar os demais do lote.
3. `services/ingestao.py::executar_ingestao` reestruturado em 3 fases: (a) determinar, por grupo, quais itens são novos (inalterado); (b) juntar os itens novos de TODOS os grupos numa lista única e resumir em lotes de `CATALOGO_NOTICIAS_LLM_TAMANHO_LOTE` (novo setting, padrão 10); (c) persistir grupo a grupo como antes, usando os resultados já calculados. A decisão de cluster/NewsCluster continua 100% por grupo — o lote de chamadas é só um detalhe de eficiência da chamada ao provider, dissociado de qual cluster um item pertence.
4. Novo setting `CATALOGO_NOTICIAS_LLM_MAX_TOKENS_POR_ITEM` (padrão 220): teto de tokens de resposta, multiplicado pelo tamanho do lote — gap real encontrado (nenhum teto existia antes, resposta prolixa custava mais que o necessário).

## Validação
- Comparação item a item do teste `test_registro_persistido_com_metricas_corretas_incluindo_erro_de_fonte` (test_acceptance_criteria.py) e `test_registro_execucao_ingestao_registra_metricas_observaveis` (test_sanity.py) confirmou que a implementação padrão (trampolim) preserva `provider.chamadas` (contador interno dos dublês) exatamente como antes — só `registro.chamadas_summarization_provider` muda de significado (agora conta chamadas HTTP em lote, não itens) e essas DUAS assertions foram atualizadas para refletir isso explicitamente.
- Novo arquivo `tests/test_summarization_provider.py`: cobertura direta de `LLMHttpSummarizationProvider` (que antes tinha ZERO testes dedicados — só era exercitado indiretamente via dublês injetados em `executar_ingestao`), incluindo o caso central de correção (item ausente da resposta não contamina os demais; resposta fora de ordem mapeada por id, não por posição).
- **Não foi possível rodar `pytest` de verdade nesta sessão** (ferramentas de execução do agente voltaram a ficar intermitentes/bloqueadas pelo classificador de segurança no meio desta mudança, depois de terem funcionado momentos antes) — toda a validação foi por revisão manual cuidadosa, campo a campo. Pedido explícito ao usuário para rodar `pytest catalogo_noticias/` e reportar o resultado antes de confiar nisso em produção.

## Critérios de aceite
1. `resumir_e_classificar_em_lote` reduz o número de chamadas HTTP reais proporcionalmente ao tamanho do lote, sem quebrar a garantia de resumo independente por item.
2. Toda a suíte de testes pré-existente de `catalogo_noticias/` continua passando (2 assertions atualizadas conscientemente, documentadas acima — nenhuma removida/enfraquecida).
3. Nova cobertura de teste para o caminho HTTP real (antes inexistente).
4. `README.md` documenta os dois novos parâmetros de configuração e como verificar a redução de chamadas via o admin.
