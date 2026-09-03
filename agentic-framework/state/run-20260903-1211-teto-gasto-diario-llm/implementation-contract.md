<!--
CONTRACT: implementation-contract
DONO: orchestrator (preenche) / executor, tester, reviewer (leem)
QUANDO É CRIADO: logo após o task-plan.md ser aceito.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/implementation-contract.md
-->

# Implementation Contract — 20260903-1211-teto-gasto-diario-llm

## Metadados
- **run_id:** 20260903-1211-teto-gasto-diario-llm
- **Deriva de:** task-plan.md (20260903-1211-teto-gasto-diario-llm)
- **Versão do contrato:** 1

## O que deve ser construído

1. **Estimativa real de custo por chamada** em `backend/catalogo_noticias/providers/summarization.py`:
   - Nova setting `CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS` (float, env var, default ~0.15 — faixa de modelo econômico tipo `gpt-4o-mini`, mesmo padrão de comentário/documentação das demais settings `CATALOGO_NOTICIAS_LLM_*` em `config/settings.py`).
   - `LLMHttpSummarizationProvider._interpretar_resposta` e `_interpretar_resposta_lote` passam a calcular `custo_estimado_usd = (tokens_utilizados / 1000) * preco_usd_por_1k_tokens` quando `tokens_utilizados` é conhecido (`None` continua sendo o valor quando o provedor não devolve `usage.total_tokens`, como já acontece hoje — não inventar tokens).
   - Não alterar a divisão proporcional de tokens por item já existente em `_interpretar_resposta_lote` (linha ~291-293) — o custo por item deriva do MESMO `tokens_por_item` já calculado ali.

2. **Módulo de orçamento** novo em `backend/catalogo_noticias/services/orcamento.py` (segue o padrão já estabelecido no app: módulos dedicados dentro de `services/`, não um único `services.py`):
   - `gasto_llm_hoje_usd() -> float`: soma `RegistroExecucaoIngestao.custo_estimado_summarization_usd` (ignorando `None`) de registros cujo `executado_em` cai no dia corrente (`timezone.now()`, mesmo fuso já usado pelo resto do projeto — ver `_itens_recentes_persistidos` para o padrão de uso de `timezone.now()`). Usar agregação do ORM (`Sum`), não iteração em Python — mesmo cuidado de performance já aplicado em `metricas/services.py::painel`.
   - `teto_diario_usd() -> float`: retorna `settings.CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD`.
   - `teto_excedido(gasto_acumulado_usd: float) -> bool`: `gasto_acumulado_usd >= teto_diario_usd()`.
   - Qualquer exceção ao calcular `gasto_llm_hoje_usd()` (ex.: problema de banco) deve ser capturada dentro da própria função, logada como `logger.warning`, e a função deve devolver `0.0` (fail-open — nunca deixar uma falha de leitura de métricas interromper a ingestão; ver task-plan.md, risco "Falha ao persistir/consultar gasto do dia").

3. **Enforcement em `backend/catalogo_noticias/services/ingestao.py::executar_ingestao`**:
   - No loop que monta lotes (`for inicio in range(0, len(todos_itens_novos), tamanho_lote): ...`, linha ~651), antes de cada chamada a `summarization_provider.resumir_e_classificar_em_lote(lote)`, calcular o gasto acumulado = `orcamento.gasto_llm_hoje_usd() + custo_total` (custo_total = o que esta própria execução já acumulou até agora, variável já existente no código) e checar `orcamento.teto_excedido(...)`.
   - Se excedido: **não chamar o provedor** para este lote nem para os lotes seguintes desta execução — aplicar `_resultado_fallback_erro` (função já existente) a cada item do lote, sem incrementar `chamadas_summarization` (nenhuma chamada HTTP foi feita), e logar `logger.warning` uma vez informando quantos itens restantes foram pulados por teto de gasto.
   - O `RegistroExecucaoIngestao` resultante deve continuar sendo criado normalmente ao final (itens pulados por teto entram como qualquer outro item sem resumo confiável: `status_revisao=pendente`, via `_persistir_grupo`/`_persistir_grupo_mesclado`, caminho já existente — nenhuma mudança nessas duas funções).
   - Não alterar o comportamento para lotes que ocorrem ANTES do teto ser ultrapassado (critério de aceite 1 do task-plan).

4. **Observabilidade via `metricas`**: `backend/metricas/services.py::painel()` passa a incluir no dicionário retornado:
   - `custo_llm_hoje_usd` (chamando `catalogo_noticias.services.orcamento.gasto_llm_hoje_usd()`),
   - `teto_llm_diario_usd` (chamando `catalogo_noticias.services.orcamento.teto_diario_usd()`),
   - `teto_llm_excedido_hoje` (booleano, mesma checagem `teto_excedido`).
   - Import de `catalogo_noticias.services.orcamento` no topo do arquivo, mesmo padrão dos imports já existentes de `assinatura.models`/`b2b.models`.

## Áreas/arquivos esperados
- `backend/config/settings.py` (nova setting de preço por 1k tokens, documentada com o mesmo estilo de comentário das demais `CATALOGO_NOTICIAS_LLM_*`)
- `backend/catalogo_noticias/providers/summarization.py`
- `backend/catalogo_noticias/services/orcamento.py` (novo arquivo)
- `backend/catalogo_noticias/services/ingestao.py`
- `backend/metricas/services.py`
- `backend/catalogo_noticias/tests/` (novo(s) teste(s) para `orcamento.py` e para o enforcement em `executar_ingestao`; `backend/catalogo_noticias/tests/test_summarization_provider.py` ganha cobertura para o cálculo de `custo_estimado_usd`)
- `backend/metricas/` testes (se existirem — verificar; se não existirem testes para `painel()`, adicionar cobertura mínima para os 3 novos campos)

Qualquer mudança fora desta lista (em especial `services/deduplicacao.py` ou as funções `_resumo_e_copia_ou_quase_copia`/`_proporcao_do_resumo_copiada_literalmente` em `ingestao.py`) deve ser justificada explicitamente em `implementation-history.md` — não é esperada.

## Interfaces afetadas
- `ResultadoResumo.custo_estimado_usd`: passa a vir preenchido (float) em vez de sempre `None` quando `LLMHttpSummarizationProvider` é o provedor real e `tokens_utilizados` é conhecido. Nenhum dublê/mock de teste existente é obrigado a mudar (continuam podendo devolver `None`).
- `metricas.services.painel()`: dicionário de retorno ganha 3 chaves novas — aditivo, não remove nem renomeia chaves existentes (não quebra nenhum consumidor atual do painel, incluindo frontend se houver).
- Nenhuma migração de banco nova.

## Critérios de aceite (técnicos, testáveis)
1. Dado um dia sem nenhum `RegistroExecucaoIngestao` anterior e um teto de $5.00, quando `executar_ingestao` roda com itens cujo custo total estimado fica abaixo de $5.00, então todos os lotes chamam `summarization_provider.resumir_e_classificar_em_lote` normalmente e nenhum item cai em fallback por causa do teto.
2. Dado um gasto já acumulado hoje (via `RegistroExecucaoIngestao` existente(s)) igual ou acima do teto configurado, quando `executar_ingestao` roda, então NENHUMA chamada a `summarization_provider.resumir_e_classificar_em_lote` é feita, e todos os itens novos entram com `status_revisao=pendente` (via fallback).
3. Dado um teto que é ultrapassado NO MEIO da execução atual (ex.: 3 lotes necessários, o 2º lote faz o acumulado cruzar o teto), quando `executar_ingestao` roda, então o 1º lote chama o provedor normalmente, e o 2º e 3º lotes NÃO chamam o provedor (fallback).
4. Dado `CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD` sobrescrito via `override_settings`/env var para um valor mais alto, quando o mesmo cenário do critério 2 roda, então o comportamento muda de acordo (comprova configurabilidade sem alteração de código — mesmo padrão de teste já usado para outras settings deste app, ver `TestAC7ConfiguravelSemAlterarCodigo` em `test_acceptance_criteria.py`).
5. Dado tokens_utilizados conhecido numa resposta simulada de `LLMHttpSummarizationProvider`, quando `resumir_e_classificar` ou `resumir_e_classificar_em_lote` processam essa resposta, então `custo_estimado_usd` é `(tokens/1000) * preco_configurado`, não `None`.
6. Dado uma falha simulada (ex.: mock lançando exceção) dentro de `gasto_llm_hoje_usd()`, quando `executar_ingestao` roda, então a execução NÃO lança exceção e se comporta como se o gasto acumulado fosse `0.0` (fail-open, critério técnico do task-plan).
7. `metricas.services.painel()` devolve `custo_llm_hoje_usd`, `teto_llm_diario_usd` e `teto_llm_excedido_hoje` consistentes com o estado atual de `RegistroExecucaoIngestao` e da setting.

## Não-objetivos
- Não escolher/implementar o provedor concreto de LLM de produção nem sua tabela de preços real.
- Não alterar `services/deduplicacao.py`, `_resumo_e_copia_ou_quase_copia`, `_proporcao_do_resumo_copiada_literalmente` ou qualquer heurística de agrupamento/direitos autorais já revisada no run `20260902-0727-ingestao-noticias`.
- Não adicionar endpoint administrativo novo para resetar/visualizar o gasto (a exposição via `metricas.services.painel()` é suficiente para esta execução — um endpoint HTTP dedicado, se desejado, é um follow-up separado).
- Não pausar/cancelar a task Celery periódica quando o teto é excedido — ela continua rodando e ingerindo itens, só sem chamar o LLM.
- Não alterar `chamadas_summarization_provider`, `total_itens_ingeridos`, `total_grupos_formados` ou `total_duplicatas_agrupadas` além do necessário para refletir corretamente lotes pulados (não incrementar `chamadas_summarization_provider` para lotes pulados, já que nenhuma chamada HTTP ocorreu).

## Restrições técnicas
- **Performance:** `gasto_llm_hoje_usd()` deve ser uma única query agregada (`Sum`), chamada no máximo uma vez por lote dentro de `executar_ingestao` (não uma vez por item).
- **Segurança/privacidade:** N/A — não envolve dados pessoais de usuário.
- **Dependências permitidas:** nenhuma biblioteca nova — apenas Django ORM (`django.db.models.Sum`) e `django.utils.timezone`, já usados no projeto.
- **Estilo/convenções:** seguir o estilo de docstring/comentário já estabelecido em `services/ingestao.py` e `providers/summarization.py` (explicar o "porquê", referenciar este `run_id` e o `implementation-contract.md` quando a decisão não for óbvia). Nomes de função em português, consistente com o restante do app.

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Testes escritos e passando (tester)
- [ ] Revisão de código aprovada (reviewer — obrigatória por decisão do orchestrator, ver task-plan.md)
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente
- [ ] Suíte completa do backend (204 testes + os novos desta execução) passando via `cd backend && DJANGO_DB_ENGINE=sqlite3 DJANGO_DEBUG=true DJANGO_CACHE_BACKEND=locmem ./.venv/Scripts/python.exe -m pytest -q`
