<!--
CONTRACT: code-review-contract
DONO: reviewer
QUANDO E CRIADO: sempre que review-triggers.md indicar revisao obrigatoria, ou sob demanda (skill agentic-review).
PARA ONDE VAI A INSTANCIA: agentic-framework/state/run-<run_id>/code-review-contract.md
-->

# Code Review Contract - 20260903-1211-teto-gasto-diario-llm

## Metadados
- **run_id:** 20260903-1211-teto-gasto-diario-llm
- **Escopo revisado:** diff do executor (iteracao 1) contra implementation-contract.md e task-plan.md.
- **Contrato de referencia:** implementation-contract.md (20260903-1211-teto-gasto-diario-llm)
- **Gatilhos aplicados:** revisao marcada obrigatoria pelo orchestrator devido ao risco de negocio "Custo de IA/infraestrutura" (BRD secao 30) e por reabrir area adjacente ja sensivel a direitos autorais/compliance (BRD secao 18, run 20260902-0727-ingestao-noticias). Verificacao explicita de escopo: nenhuma mudanca em services/deduplicacao.py, _resumo_e_copia_ou_quase_copia ou _proporcao_do_resumo_copiada_literalmente (confirmado por grep do run_id nos 6 arquivos tocados e por mtime: deduplicacao.py com ultima modificacao em 2026-09-02, um dia antes desta execucao).
- **Metodologia:** leitura direta do codigo de producao (nao apenas o relato do executor/tester em implementation-history.md), execucao independente dos testes relevantes (test_orcamento.py, test_summarization_provider.py, test_custo_llm.py, test_acceptance_criteria.py - 83 passed, confirmando o comportamento verde relatado), e um script Python adhoc rodado com django.setup() para reproduzir empiricamente o comportamento real de timezone.now() neste projeto (USE_TZ=True, TIME_ZONE="America/Sao_Paulo"), que revelou o Finding 1 abaixo.

## Findings

### Finding 1
- **Arquivo:** backend/catalogo_noticias/services/orcamento.py
- **Linha:** 48-53 (gasto_llm_hoje_usd, calculo de inicio_do_dia/fim_do_dia)
- **Categoria:** correctness
- **Severidade:** major
- **Resumo:** inicio_do_dia = agora.replace(hour=0, minute=0, second=0, microsecond=0) opera sobre timezone.now(), que no Django (com USE_TZ=True, como esta configurado neste projeto) sempre devolve um datetime em UTC, nunca no fuso local (TIME_ZONE = "America/Sao_Paulo", UTC-3). O .replace(hour=0...) portanto calcula meia-noite UTC, nao meia-noite de Sao Paulo - a janela do "dia corrente" usada para somar custo_estimado_summarization_usd fica deslocada em 3 horas em relacao ao calendario local que o resto do sistema usa (CELERY_TIMEZONE = TIME_ZONE, agendamento da task periodica em horario local).
- **Cenario de falha (reproduzido empiricamente, nao e suposicao):** rodei django.setup() neste projeto e chamei timezone.now()/timezone.localtime() diretamente - as 16:07 (horario de Sao Paulo) de hoje, agora.replace(hour=0,...) produziu 2026-09-03 00:00:00+00:00, que equivale a 2026-09-02 21:00:00-03:00 em horario local - ou seja, a "meia-noite" que o codigo usa como inicio do dia corrente e, na pratica, 21:00 do dia anterior em Sao Paulo. Isso significa que a janela [inicio_do_dia, fim_do_dia) usada por gasto_llm_hoje_usd() vira sempre [21:00 de ontem, 21:00 de hoje) em horario local, nunca [00:00, 00:00). Consequencia de negocio concreta: as 21:00:00 (horario de Sao Paulo) de qualquer dia, a janela "salta" para frente automaticamente (porque agora cruzou a meia-noite UTC), zerando de fato o acumulado considerado por gasto_llm_hoje_usd() - mesmo que, pelo calendario de Sao Paulo (o fuso que a propria task periodica usa para se agendar), ainda faltem 3 horas para o "dia" realmente acabar. Um cenario direto: se ate as 20:00 (horario de Sao Paulo) o sistema ja acumulou USD 4,99 de gasto (perto do teto default de USD 5,00) ao longo do dia, as 21:00:01 (horario de Sao Paulo) gasto_llm_hoje_usd() passa a devolver ~USD 0,00 (a janela virou para o "dia seguinte" em termos UTC), e a task periodica (tasks.ingerir_noticias, que roda a cada CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS = 15 min por padrao) volta a chamar o provedor de LLM normalmente entre 21:00 e 23:59 (horario de Sao Paulo) - permitindo gastar ate outro teto_diario_usd inteiro (ate USD 5,00 adicionais) dentro do MESMO dia-calendario de Sao Paulo, exatamente o cenario que esta execucao inteira existe para prevenir (BRD secao 30, "Observabilidade e limites de consumo"). O mesmo desalinhamento tambem distorce metricas.services.painel()::custo_llm_hoje_usd exibido ao admin: as 22:00 (horario de Sao Paulo), o painel mostraria um valor baixo/quase zero como "gasto de hoje", escondendo a maior parte do que, pelo calendario local, e de fato o gasto do dia (acumulado entre meia-noite e 21:00 local).
- **Por que nao e um caso hipotetico/edge case irrelevante:** o desalinhamento nao depende de nenhuma condicao rara - ele ocorre todo dia, exatamente as 21:00 (horario de Sao Paulo), de forma deterministica, sempre que ha execucoes da task periodica proximas desse horario (janela de 3h, todo dia). Nao e um bug de precisao de milissegundos; e um deslocamento fixo de fuso horario inteiro.
- **Sugestao:** converter agora para o fuso local ANTES de truncar a hora - ex.: inicio_do_dia_local = timezone.localtime(agora).replace(hour=0, minute=0, second=0, microsecond=0), usar esse valor (que ja fica com o tzinfo de America/Sao_Paulo) diretamente no filtro do ORM, e o mesmo para fim_do_dia = inicio_do_dia_local + timedelta(days=1). Alternativa equivalente: django.utils.timezone.localdate() combinado com datetime.combine(...) + timezone.make_aware(...).

### Finding 2
- **Arquivo:** backend/catalogo_noticias/services/ingestao.py
- **Linha:** 662-688 (loop de lotes em executar_ingestao)
- **Categoria:** correctness / concorrencia
- **Severidade:** minor
- **Resumo:** a checagem do teto e "check-then-act" sem nenhum lock/transacao - gasto_llm_hoje_usd() le o estado atual do banco e a decisao de chamar (ou nao) o provedor e tomada com base nessa leitura, mas o RegistroExecucaoIngestao desta execucao so e persistido ao FINAL de executar_ingestao (linha 734). Se duas execucoes de executar_ingestao rodarem de fato em paralelo (ex.: mais de um worker Celery processando a mesma task, ou uma execucao anterior ainda em andamento quando a proxima do agendamento periodico dispara), cada uma le o mesmo gasto_llm_hoje_usd() "desatualizado" (sem o gasto que a outra execucao concorrente ja esta acumulando em custo_total, que so vira visivel ao banco quando aquela outra execucao terminar) e ambas podem concluir independentemente que o teto nao foi excedido, cada uma gastando ate proximo do teto - o gasto real do dia pode ultrapassar o teto configurado pela soma das execucoes concorrentes.
- **Cenario de falha:** teto = USD 5,00; duas instancias de executar_ingestao comecam quase simultaneamente (ex.: dois workers Celery consumindo a mesma fila, ou uma execucao anterior demorada ainda rodando quando o agendamento periodico dispara a proxima); ambas leem gasto_llm_hoje_usd() == 0 (nenhum registro persistido ainda de nenhuma das duas) e cada uma gasta ate quase USD 5,00 antes de qualquer uma persistir seu RegistroExecucaoIngestao - gasto real do dia proximo de USD 10,00, o dobro do teto configurado.
- **Por que e minor, nao major:** o task-plan.md e o implementation-contract.md desta execucao nao identificam concorrencia entre execucoes como risco (a preocupacao explicita e "meio de uma execucao com multiplos lotes", que esta corretamente resolvida - ver verificacoes positivas abaixo) e a configuracao padrao observada no projeto (CELERY_BEAT_SCHEDULE com uma unica entrada periodica, sem evidencia de multiplos workers/filas concorrentes documentados neste run) torna esse cenario menos provavel na configuracao atual - mas e uma lacuna real caso o deploy venha a escalar workers Celery horizontalmente (mencionado como possibilidade na arquitetura de infra do projeto).
- **Sugestao:** se escalonamento horizontal de workers Celery for uma possibilidade real, considerar um lock distribuido (ex.: select_for_update numa linha de controle, ou lock via cache/Redis) em torno da leitura-e-decisao do teto; nao bloqueante para esta execucao especifica, registrar como risco residual conhecido se nao for endereçado agora.

## Verificacoes positivas (para nao serem esquecidas em favor so dos findings)

- Escopo respeitado: confirmado por grep + mtime que services/deduplicacao.py, _resumo_e_copia_ou_quase_copia e _proporcao_do_resumo_copiada_literalmente nao foram tocados nesta execucao - nenhum finding reaberto do run 20260902-0727-ingestao-noticias.
- Risco 1 do task-plan (posicionamento da checagem do teto) mitigado corretamente: a checagem ocorre ANTES de cada chamada ao provedor, dentro do loop de lotes; uma vez excedido, a flag teto_ja_excedido_nesta_execucao permanece True para todos os lotes seguintes da mesma execucao (nao so o lote que cruzou o limite) - confirmado lendo o codigo e revalidando o teste test_ac3_teto_ultrapassado_no_meio_da_execucao_so_o_primeiro_lote_chama_o_provedor (cenario real de 3 lotes, so o 1o chama o provedor).
- Risco 2 do task-plan (fail-open) mitigado corretamente: gasto_llm_hoje_usd() envolve todo o corpo da funcao (incluindo o calculo de timezone.now()/janela, nao so a query) num unico try/except Exception, loga logger.warning(exc_info=True) e devolve 0.0 - nenhum caminho de excecao escapa da funcao. Revalidado com teste de ponta a ponta (TestFailOpenPropagaParaExecutarIngestao) mockando RegistroExecucaoIngestao.objects.filter para lancar RuntimeError.
- Risco 3 do task-plan (garantia anti-misattribution) preservado: _interpretar_resposta_lote usa o MESMO tokens_por_item ja dividido proporcionalmente (nao redivide), e custo_estimado_usd e derivado desse mesmo valor por item - nenhuma mudanca na logica de correspondencia posicional id -> item nem no fallback ResultadoResumo(resumo="") para itens sem entrada valida na resposta.
- Risco 4 do task-plan (metricas.services.painel() aditivo) confirmado: as 3 chaves novas sao adicionadas ao dicionario de retorno sem remover/renomear nenhuma chave existente; PainelMetricasView devolve o dict inteiro sem serializer que filtre campos, confirmado tambem via teste de endpoint HTTP real que checa a presenca de um campo pre-existente (usuarios_cadastrados_total) junto dos 3 novos.
- Sem migracao de banco nova: confirmado (nenhum arquivo novo em catalogo_noticias/migrations/, campo custo_estimado_summarization_usd ja existia).
- Suite de testes: reexecutei de forma independente test_orcamento.py + test_summarization_provider.py + test_custo_llm.py + test_acceptance_criteria.py (83 passed) - nao reexecutei a suite completa (245 testes) por ja ter sido confirmada pelo tester nesta mesma sessao, sem alteracao de codigo entre as duas verificacoes.

## Resumo quantitativo
| Severidade | Quantidade |
|---|---|
| blocker | 0 |
| major | 1 |
| minor | 1 |
| nit | 0 |

## Veredito
**changes_requested**

O nucleo do enforcement do teto (posicionamento da checagem por lote, fail-open, preservacao da garantia anti-misattribution, natureza aditiva de painel()) esta correto e bem testado - inclusive nos cenarios mais dificeis (teto cruzado no meio da execucao, falha simulada de banco). Porem, o Finding 1 (major) e um defeito real e deterministico (nao hipotetico) no calculo da janela de "dia corrente" usada tanto para o enforcement quanto para a metrica exibida ao admin: por operar sobre timezone.now() (UTC) sem converter para o fuso local do projeto (America/Sao_Paulo) antes de truncar a hora, a janela usada e [21:00 de ontem, 21:00 de hoje) em vez de [00:00, 00:00) local - todo dia, as 21:00 horario de Sao Paulo, o acumulado considerado "zera" prematuramente, permitindo que a task periodica volte a chamar o provedor de LLM e gaste ate outro teto inteiro dentro do mesmo dia-calendario local, o que contraria diretamente o objetivo de negocio desta execucao (BRD secao 30). Isso e corrigivel com uma mudanca pequena e local (usar timezone.localtime() antes do .replace(hour=0...)), sem exigir nova rodada de design - recomendo uma unica iteracao de remediacao focada nesse ponto (mais, opcionalmente, uma nota sobre o Finding 2/concorrencia como risco residual aceito, se nao for corrigido agora) antes de aprovar.

---

## Reverificação (2ª passada) — 2026-09-03 — reviewer

- **Motivo:** remediator aplicou correção do Finding 1 (Iteração 3 de `implementation-history.md`) e registrou Finding 2 como risco residual aceito sem alteração de código. Esta seção reverifica ambos por leitura direta do código/testes e execução independente da suíte — não por confiança no relato do remediator.

### Finding 1 (major) — **resolved**

- Lido `backend/catalogo_noticias/services/orcamento.py::gasto_llm_hoje_usd()` na íntegra (não só o trecho citado pelo remediator): a função agora calcula `agora_local = timezone.localtime(timezone.now())` e só então faz `.replace(hour=0, minute=0, second=0, microsecond=0)` sobre `agora_local` — exatamente a correção sugerida no Finding 1 original (converter para o fuso local ANTES de truncar a hora). `fim_do_dia = inicio_do_dia + timedelta(days=1)` e o filtro `executado_em__gte=inicio_do_dia, executado_em__lt=fim_do_dia` continuam corretos com o novo `inicio_do_dia` (aware, tzinfo de `America/Sao_Paulo`), e a docstring da função foi atualizada explicando o porquê da conversão — reduz risco de regressão futura por manutenção descuidada.
- Lido `backend/catalogo_noticias/tests/test_orcamento.py::TestGastoLlmHojeUsd::test_considera_fuso_local_e_nao_meia_noite_utc_ao_calcular_o_dia_corrente` na íntegra: o teste congela `timezone.now()` via `patch.object` em `2026-09-03 23:00:00 UTC` (= 20:00 em São Paulo, ainda "hoje" no calendário local) e cria dois registros com `executado_em` explícito e timezone-aware: um às 22h de ontem em SP (`2026-09-02 22:00:00-03:00`) e outro às 00:30 de hoje em SP (`2026-09-03 00:30:00-03:00`). Isso exercita exatamente a fronteira UTC/local descrita no Finding 1 original (não é um teste que passaria de qualquer forma com meia-noite UTC): com o bug antigo, a janela `[00:00 UTC, 00:00 UTC seguinte)` inclui o registro de ontem-à-noite-em-SP (que vira `01:00 UTC` de hoje) e soma erradamente `5.0`; com a correção, só o registro de `00:30 em SP` conta, somando `1.0`. O teste faz `assert resultado == pytest.approx(1.0)` — asserção específica o suficiente para capturar o deslocamento de 3h, não uma checagem frouxa de "não lançou exceção" ou de intervalo amplo.
- Reproduzi eu mesmo a reversão descrita pelo remediator: reli o diff mental do "antes" (`agora = timezone.now(); inicio_do_dia = agora.replace(...)`) contra este teste — com esse código, o registro de ontem-à-noite-em-SP (`2026-09-02 22:00:00-03:00` = `2026-09-03 01:00:00 UTC`) cairia dentro de `[2026-09-03 00:00 UTC, 2026-09-04 00:00 UTC)`, confirmando algebricamente que o teste de fato falharia contra o código antigo (`4.0 + 1.0 = 5.0 != 1.0`), consistente com o `assert 5.0 == 1.0` relatado pelo remediator. Não preciso reexecutar a reversão fisicamente para validar essa álgebra — o teste é fechado o suficiente (datas e fuso explícitos, sem ambiguidade) para confirmar a lógica por inspeção.
- **Veredito do finding:** resolvido. A correção é a mudança mínima e correta (converter para fuso local antes de truncar), aplicada no único ponto do defeito, com teste de regressão específico para a fronteira UTC/local que motivou o finding original.

### Finding 2 (minor) — **still-open, aceito como risco residual (conforme já registrado)**

- Não houve mudança de código em `backend/catalogo_noticias/services/ingestao.py` (loop de lotes em `executar_ingestao`) — confirmado que este finding continua tecnicamente presente (check-then-act sem lock/transação entre execuções concorrentes). Isso é o comportamento esperado: o veredito original já classificava este finding como não-bloqueante e sugeria tratá-lo como risco residual se não endereçado nesta rodada, e a Iteração 3 de `implementation-history.md` documenta essa decisão explicitamente. Nenhuma reabertura de escopo necessária — apenas confirmação de que a decisão permanece válida e devidamente registrada.

### Suíte completa — execução independente

```
cd backend && DJANGO_DB_ENGINE=sqlite3 DJANGO_DEBUG=true DJANGO_CACHE_BACKEND=locmem ./.venv/Scripts/python.exe -m pytest -q
# -> 256 passed, 7 warnings in 115.75s
```

256 passed, 0 failed, 0 errors — bate exatamente com o número relatado pelo remediator (não apenas "nenhuma falha", o total numérico também confere). Os 7 warnings são os mesmos `DeprecationWarning` pré-existentes de `feedparser` já observados nas iterações anteriores (não relacionados a esta mudança). `catalogo_noticias` e `metricas` (áreas tocadas por esta execução) estão 100% verdes dentro desse total.

### Resumo quantitativo atualizado

| Severidade | Quantidade | Status |
|---|---|---|
| blocker | 0 | — |
| major | 1 | resolved |
| minor | 1 | still-open (risco residual aceito) |
| nit | 0 | — |

## Veredito final (2ª passada)

**approve**

O Finding 1 (major, bloqueante) foi corrigido corretamente — verificado por leitura direta do código de produção (não só o relato do remediator) e por leitura do teste de regressão novo, que exercita de forma específica e não-trivial a fronteira UTC/horário local que causava o defeito original. O Finding 2 (minor) segue como risco residual conhecido e aceito, exatamente como definido no veredito da 1ª passada — não é impeditivo para aprovação. Suíte completa reexecutada de forma independente: 256 passed, 0 failed, 0 errors, sem nenhuma regressão em `catalogo_noticias`/`metricas` nem em nenhum outro app do projeto. Nenhum novo finding identificado nesta reverificação. Escopo permanece fechado conforme 1ª passada (não reaberto).
