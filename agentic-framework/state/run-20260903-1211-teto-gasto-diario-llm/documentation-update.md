<!--
CONTRACT: documentation-update
DONO: documenter
QUANDO É CRIADO: depois que testes passam e a revisão (se exigida) está aprovada.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/documentation-update.md
-->

# Documentation Update — 20260903-1211-teto-gasto-diario-llm

## Metadados
- **run_id:** 20260903-1211-teto-gasto-diario-llm
- **Baseado em:** implementation-history.md (20260903-1211-teto-gasto-diario-llm), implementation-contract.md, code-review-contract.md (veredito final: **approve**, após 1 rodada de correção do remediator para o Finding 1 major)

## Documentos afetados
| Documento | Tipo de mudança | Resumo |
|---|---|---|
| `README.md` (raiz) | nova seção | Nova seção "Teto de gasto diário com o provedor de LLM" dentro de "Como popular o feed com notícias reais (ingestão)", logo após a seção existente sobre lotes/tamanho de lote. Documenta as duas settings novas/afetadas (`CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS`, nova; `CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD`, já existia mas agora é de fato aplicada), o comportamento observável (ingestão continua, resumo automático para, itens caem na fila de revisão humana do admin) e como consultar o gasto do dia via `GET /api/metricas/painel/` (`custo_llm_hoje_usd`, `teto_llm_diario_usd`, `teto_llm_excedido_hoje`). |
| `ARCHITECTURE.md` | atualização | 3 pontos ajustados para refletir que o enforcement é real (antes só a setting existia): (1) seção 7 "Custo de IA controlado" ganhou uma frase confirmando que a observabilidade/teto descritos como requisito já estão implementados, com referência a `catalogo_noticias/services/orcamento.py` e `metricas.services.painel()`; (2) seção 8 "Decisões em aberto", item 3 (provedor de LLM ainda em aberto) ganhou uma frase esclarecendo que o preço usado para estimar custo é configurável e não a tabela real de nenhum provedor; (3) seção 9.3, linha "Custo" da tabela — reescrita para deixar explícito que o teto agora é **aplicado de fato** (antes a frase "chamadas ao LLM em lote com teto de tokens (já existente) + teto de gasto diário" podia ser lida como se o teto de gasto diário já estivesse em vigor, quando na verdade só a setting existia sem nenhum código a aplicando). |

## Sem impacto em documentação?
Não aplicável integralmente — houve mudanças reais em `README.md` e `ARCHITECTURE.md` (ver tabela acima). Registrando explicitamente os documentos que **foram considerados e não precisaram de mudança**, com o motivo em cada caso:

- [x] Confirmado: **`agentic-framework/specs/painel-metricas-negocio.md`** não precisa de atualização porque não enumera os campos exatos retornados por `metricas.services.painel()` (nenhuma lista fechada de chaves que ficaria desatualizada com a adição de `custo_llm_hoje_usd`/`teto_llm_diario_usd`/`teto_llm_excedido_hoje`) — é uma spec de requisitos de alto nível, não uma referência de API campo a campo.
- [x] Confirmado: **`agentic-framework/specs/ingestao-curadoria-noticias.md`** não precisa de atualização pelo mesmo motivo — não menciona `CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD`, `CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS` nem `custo_estimado_usd` (grep confirmado sem resultados).
- [x] Confirmado: **não existe `CHANGELOG.md` no projeto** (só em `node_modules/`, irrelevante) — não há changelog de projeto para adicionar entrada. Se o projeto vier a adotar um CHANGELOG no futuro, esta mudança deveria constar como algo como "Aplicado teto de gasto diário do provedor de LLM (antes só a configuração existia); painel de métricas passa a expor gasto/teto do dia".
- [x] Confirmado: **não existe `backend/README.md`** dedicado (o único README de setup é o da raiz, já atualizado) — nenhuma duplicação de documentação de variáveis de ambiente a manter sincronizada.
- [x] Confirmado: nenhuma doc de frontend (`frontend/`) precisa de mudança — o painel de métricas (`GET /api/metricas/painel/`) já era consumido antes desta execução (se houver consumidor no frontend); a mudança é puramente aditiva (3 chaves novas no dicionário de retorno, nenhuma removida/renomeada — confirmado no `code-review-contract.md`, "Verificações positivas"), então nenhum exemplo de consumo existente fica desatualizado ou incorreto.

## Exemplos/snippets novos ou atualizados
`README.md`, nova subseção "Teto de gasto diário com o provedor de LLM" (dentro de "Como popular o feed com notícias reais (ingestão)"):

```markdown
### Teto de gasto diário com o provedor de LLM

Cada chamada ao provedor de resumo tem seu custo estimado a partir dos tokens
efetivamente consumidos, multiplicados por um preço configurável em
`backend/.env`:

- `CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS` (padrão `0.15`): estimativa
  de custo em dólares por 1000 tokens (entrada + saída somados). É uma
  estimativa — não a tabela de preços exata de nenhum provedor específico.
  Ajuste esse valor para refletir o preço real do provedor de LLM escolhido.
- `CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD` (padrão `5.0`): teto de gasto
  diário, em dólares. Assim que o gasto estimado acumulado do dia corrente
  atinge esse valor, a ingestão **para de chamar o provedor de LLM** pelo
  restante do dia — as notícias continuam sendo buscadas e ingeridas
  normalmente, só sem resumo automático: caem na mesma fila de revisão
  humana do admin usada quando o resumo automático falha por outro motivo
  (`status_revisao=pendente`). Nenhuma notícia é descartada ou trava a
  ingestão por causa do teto.

O gasto acumulado do dia (e se o teto já foi atingido) pode ser consultado
sem precisar olhar o banco diretamente, no painel de métricas
(`GET /api/metricas/painel/`, autenticado como admin): os campos
`custo_llm_hoje_usd`, `teto_llm_diario_usd` e `teto_llm_excedido_hoje`
mostram, respectivamente, o gasto estimado já feito hoje, o teto configurado
e se ele já foi ultrapassado.
```

## Entrada de changelog
Não aplicável — o projeto não mantém um `CHANGELOG.md` (verificado: nenhum arquivo desse tipo existe fora de `frontend/node_modules/`). Nenhuma entrada foi criada.

## Verificação
- [x] Nenhum exemplo/trecho de documentação existente ficou contraditório com a mudança — revisado especificamente o trecho de `ARCHITECTURE.md` seção 9.3 apontado como potencialmente ambíguo ("teto de gasto diário (já existente)"), que foi reescrito para não sugerir que o enforcement já estava em vigor antes desta execução. Nenhum outro `.md` do projeto (fora de `agentic-framework/state/`, que é histórico de execução, não documentação viva) menciona `CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD`, `CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS` ou `custo_estimado_usd` (confirmado por grep).
- [x] Build/lint de documentação rodado (se o projeto tiver um) — não aplicável: o projeto não tem markdown linter nem build de documentação configurado (nenhum `.markdownlint*`, nenhum script de docs em `frontend/package.json`, nenhum equivalente encontrado).

## Não-objetivos desta atualização de documentação
- Não documentei o comportamento de concorrência entre workers Celery (Finding 2, minor, do `code-review-contract.md`) como uma limitação ao usuário final — é um risco residual técnico interno (check-then-act sem lock), aceito explicitamente pelo `reviewer`/`orchestrator` como não-bloqueante nesta configuração (uma única entrada em `CELERY_BEAT_SCHEDULE`, sem workers concorrentes documentados). Não é comportamento que o usuário do README precisa saber para operar o sistema hoje; se o deploy vier a escalar workers Celery horizontalmente, esse ponto deve ser revisitado tanto no código quanto na documentação.
- Não criei documentação nova de arquitetura para `catalogo_noticias/services/orcamento.py` além das referências já adicionadas em `ARCHITECTURE.md` — o módulo é pequeno (3 funções) e autoexplicativo via docstrings no próprio código (confirmado por `tester`/`reviewer`), consistente com o padrão já usado para os demais módulos de `services/` do app.
