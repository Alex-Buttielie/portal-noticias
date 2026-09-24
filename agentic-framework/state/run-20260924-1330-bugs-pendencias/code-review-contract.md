<!--
CONTRACT: code-review-contract
DONO: reviewer
QUANDO: revisão obrigatória da run 20260924-1330-bugs-pendencias
-->

# Code Review Contract — 20260924-1330-bugs-pendencias

## Metadados
- **run_id:** `20260924-1330-bugs-pendencias`
- **branch:** `perf/custo-performance-p0-p2`
- **estado da revisão:** **concluída — iteração 1**
- **escopo revisado:** diff contra `HEAD` de `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`, `Caddyfile`, `README.md`, `CI-CD.md`, `backend/.dockerignore`, `backend/catalogo_noticias/admin.py`, `backend/config/middleware.py`, `backend/config/settings.py`, `backend/config/tests/test_request_id.py`, `backend/painel_admin/services.py`, `backend/painel_admin/tests/test_sanity.py`, `backend/requirements.txt`, `backend/requirements-dev.txt`, `backend/requirements-lock.txt`, `frontend/lib/datas.ts`, `frontend/scripts/verificar-datas-tz.mjs` e `scripts/init-local.ps1`; `task-plan.md`, `implementation-contract.md` e `implementation-history.md` foram lidos apenas para consistência de escopo.
- **contrato de referência:** `agentic-framework/state/run-20260924-1330-bugs-pendencias/implementation-contract.md`.
- **gatilhos aplicados:** dados privados/edge; API e contrato público de `X-Request-ID`; regra de moderação; deploy e smoke; volume superior a 300 linhas.
- **exclusões preservadas:** `agentic-framework/state/run-20260924-1400-tls-ingestao/run-state.json`, `agentic-framework/state/loteA-bugs/` e qualquer arquivo não listado. O `run-state.json` desta run não foi editado.
- **método:** leitura integral do diff e do código circundante; probes Caddy reais com caminhos diretos, percent-encoded e traversal; execução do check de datas em UTC/Tokyo e casos civis adicionais; ensaio de resposta HTTP 200 truncada com curl; ensaio de header WSGI/Gunicorn com byte de controle; 14 testes focais; `manage.py check`; `actionlint` 1.7.12; e `git diff --check`.
- **limitações:** não houve GitHub Actions, VPS nem ambiente real de DNS/TLS, conforme os não-objetivos; `pwsh` não estava disponível. A suíte completa de 476 testes do tester foi considerada evidência de entrada, não substituída por confiança automática.

## Findings

### Finding 1
- **Arquivo:** `.github/workflows/deploy.yml`
- **Linha:** `497-503, 519-521`
- **Categoria:** correctness
- **Severidade:** major
- **Resumo:** o probe descarta o exit code do `curl` e pode promover `.deployed-sha` mesmo quando a transferência HTTP falhou depois de recibir status 200.
- **Cenário de falha:** um serviço responde `HTTP 200`, declara `Content-Length: 100`, envia apenas parte do body e encerra a conexão. Nesse caso, o comando real `curl -s -o /dev/null -w '%{http_code}'` imprime `200` e termina com rc 18; como `|| true` neutraliza esse rc, `API_OK`/`WEB_OK` ainda é 1. Se os demais gates e o SHA conferirem, o marker é promovido apesar de o smoke ter falhado. A matriz 6×6 do tester cobriu `000`, mas não o estado `código=200 + rc!=0`.
- **Sugestão:** capturar separadamente rc e código e considerar o probe saudável somente quando ambos forem válidos, com rc 0 e código exatamente `200`; preservar stderr/código para diagnóstico sem mascará-los.

### Finding 2
- **Arquivo:** `backend/catalogo_noticias/admin.py`
- **Linha:** `82-94`
- **Categoria:** correctness
- **Severidade:** major
- **Resumo:** a edição de status no admin nativo invalida o autocomplete antes do commit da transação que enclose o `ModelAdmin.changeform_view`.
- **Cenário de falha:** um título aprovado já está nas três chaves. Ao submeter o formulário para `rejeitado`, o Django envolve o POST em `transaction.atomic`; `save_model` faz o UPDATE e executa o delete enquanto a transação ainda está aberta. Um autocomplete concorrente consulta o banco antes do commit, vê o item ainda aprovado e regrava o título no cache; o commit termina sem nova invalidação e o título permanece sendo sugerido por até 300 s. Na transição para aprovado, a corrida inversa pode manter o título ausente. O teste atual verifica o cache somente depois da resposta e não exercita essa janela.
- **Sugestão:** registrar a invalidação com `transaction.on_commit(...)`, preservando a semântica best-effort, para que a remoção só ocorra depois de a mudança ficar visível e não possa ser repopulada por uma leitura do estado anterior.

### Finding 3
- **Arquivo:** `backend/config/middleware.py`
- **Linha:** `42-46`
- **Categoria:** correctness
- **Severidade:** major
- **Resumo:** `strip()` é aplicado antes da validação de imprimibilidade, então um ID não imprimível pode ser truncado nas bordas e propagado como se fosse válido, em vez de gerar UUID4.
- **Cenário de falha:** em Gunicorn real, os bytes WSGI `b"\x85trusted-id\x85"` (U+0085 + `trusted-id` + U+0085) chegam em `HTTP_X_REQUEST_ID`; U+0085 é não imprimível, mas `str.strip()` o remove. A resposta observada foi `X-Request-ID: trusted-id`, propagando o núcleo fornecido pelo cliente em request, log e DB, enquanto o contrato exige UUID4 para valor não imprimível. As formas `"\ntrusted-id\n"` e `"trusted-id"` também colapsam no mesmo valor final. Não há injeção CRLF na resposta, mas a negação e a preservação da proveniência exigidas pelo contrato não são respeitadas.
- **Sugestão:** validar a imprimibilidade do valor recebido antes de remover apenas OWS permitido, ou aplicar uma política de bordas que gere UUID para qualquer controle; adicionar o caso de controle nas bordas ao teste do middleware.

### Finding 4
- **Arquivo:** `frontend/lib/datas.ts`
- **Linha:** `84-92`
- **Categoria:** correctness
- **Severidade:** major
- **Resumo:** a data civil está estável no fuso, mas `Intl.DateTimeFormat` não preserva o ano de quatro dígitos para os anos 0–99 aceitos pelo regex.
- **Cenário de falha:** a execução real do módulo produz `01/01/1` tanto para `0000-01-01` quanto para `0001-01-01`, e `29/02/96` para o ano civil válido `0096-02-29`. Portanto, dois anos civis distintos colapsam no mesmo texto e `formatarDataCurta`, que promete `DD/MM/AAAA`, não retorna `AAAA` nesse intervalo. A validação de calendário e a neutralização UTC estão corretas; a perda ocorre na apresentação do ano.
- **Sugestão:** formatar os componentes civis sem depender da regra de padding/era de `Intl` para ano, ou tratar explicitamente o intervalo 0–99, e cobrir os mesmos limites no check de datas.

### Finding 5
- **Arquivo:** `frontend/scripts/verificar-datas-tz.mjs`
- **Linha:** `52-65`
- **Categoria:** test-coverage
- **Severidade:** minor
- **Resumo:** o check executa o módulo de produção real, mas a maioria das saídas é verificada apenas como string não vazia, contrariando a garantia de falhar quando qualquer saída divergir.
- **Cenário de falha:** uma alteração em `formatarDataPorExtenso` que continue devolvendo qualquer texto, ou em `formatarDataHoraCompacta` que passe a devolver ISO em vez do formato pt-BR esperado, satisfaz `typeof valor === "string" && valor.length > 0` e o CI termina com exit 0. A adulteração feita pelo tester alterou o literal esperado de `23/09/2026`; ela prova apenas que essa asserção específica está conectada, não que todas as saídas declaradas no resultado sejam validadas.
- **Sugestão:** comparar cada função a uma expectativa exata e incluir os limites civis que permitiriam detectar o Finding 4, mantendo as duas execuções de TZ no CI.

### Finding 6
- **Arquivo:** `README.md`; `scripts/init-local.ps1`
- **Linha:** `README.md:54`; `scripts/init-local.ps1:87`
- **Categoria:** docs
- **Severidade:** minor
- **Resumo:** a documentação local declara Python 3.13+, enquanto o contrato da run, o job de CI e o lock de runtime tratam Python 3.12 como versão suportada/validada.
- **Cenário de falha:** um desenvolvedor que possui exatamente o Python 3.12 usado em CI recebe a instrução de que o projeto exige 3.13 e não consegue saber se deve trocar o interpretador ou se o bootstrap local é oficialmente compatível; o bootstrap, na prática, instala os manifestos em 3.12 e o tester validou runtime e dev nessa versão. A inconsistência faz a documentação local e a versão coberta pelo gate divergirem.
- **Sugestão:** alinhar README e script à versão realmente suportada e coberta pelo CI, ou documentar e executar deliberadamente uma versão local diferente.

## Resumo quantitativo

| Severidade | Quantidade |
|---|---:|
| blocker | 0 |
| major | 4 |
| minor | 2 |
| nit | 0 |

## Itens verificados sem finding

- **Caddy:** em Caddy real, `/media/public/photo.txt` preservou o nome e retornou 200; caminhos privados, percent-encoded, dot-segment, encoded-dot e double-encoded retornaram 404 sem conteúdo privado. `handle_path` removeu `/media/public/` e usou `/srv/media/public`; a negação privada aparece antes da allowlist e o fallback permanece fail-closed.
- **Cache:** as três chaves realmente usadas (`categorias`, `titulos`, `populares`) são invalidadas pelo helper; imports locais evitam ciclo e falhas de cache são engolidas. A única falha encontrada é a janela de commit do admin nativo.
- **Request ID:** IDs internos com controle, CRLF, tamanho excessivo e o limite de 64 caracteres Unicode foram tratados conforme o modelo `varchar(64)`; o task mantém idempotência por `get_or_create`. A exceção residual é a validação após `strip()`.
- **Requirements e CI:** o lock runtime não contém ferramentas de teste; PM2 instala apenas o lock, Docker usa `requirements.txt`, o manifesto dev inclui o runtime e o CI executa o check de datas antes de `tsc`/build. `actionlint` permaneceu limpo e a chave de cache inclui lock e dev.

## Veredito

**`changes_requested`**

O Caddy e a separação runtime/dev atendem ao objetivo central, mas há quatro majors que impedem a aprovação: o smoke pode promover um marker apesar de erro de transferência; a invalidação nativa pode ser reintroduzida antes do commit; IDs não imprimíveis nas bordas não são negados; e datas civis 0–99 perdem identidade. Os dois minors complementares devem ser corrigidos junto da remediação.

## Estado final da revisão

- **status:** `completed`
- **iteration:** `1`
- **verdict:** `changes_requested`
- **remediation_required:** `true`
- **run_state_updated:** `false`
- **commit_created:** `false`

## Re-revisão — iteração 2 (2026-09-24)

### Escopo e método

- **Escopo:** diff completo contra `HEAD` dos mesmos arquivos da iteração 1, mais `backend/catalogo_noticias/services/ingestao.py` e `backend/catalogo_noticias/tests/test_p2_ingestao_performance.py` porque a remediação do Finding 2 alterou esses dois paths e o reviewer foi solicitado a verificar o `on_commit` da ingestão.
- **Exclusões preservadas:** `agentic-framework/state/run-20260924-1400-tls-ingestao/run-state.json` e `agentic-framework/state/loteA-bugs/`; o SHA do run-state concorrente continuou `7c57ea9bfe8ebe2920247f94aa9d73b9b1efd152a3286b226a8ab20954f5dc4f`.
- **Leitura:** contrato, histórico da implementação/tester/remediação/reteste, relatório anterior, diff integral e código circundante de Caddy, datas, request ID, cache, ingestão, workflows, requirements e documentação.
- **Validação independente:** `bash -n` no script real renderizado de `validate`; execução do mesmo script com servidor local, mocks e resposta `200` + `Content-Length: 100` + corpo parcial; `actionlint` 1.7.12; parser YAML com chaves duplicadas; 24 testes focais de request ID/cache/ingestão; `manage.py check`; `tsc --noEmit`; check de datas em Node 18/20 × UTC/Tokyo; harness civil adicional; Caddy real; e `git diff --check`.
- **Limitações:** o reviewer não repetiu a suíte completa de 486 nem o build 59/59; ambos são evidência do reteste, não prova presumida. Não houve GitHub Actions, VPS, Redis real, `pwsh`, DNS ou TLS real.

### Resultado dos seis findings da iteração 1

| Finding | Status na re-revisão | Evidência independente |
|---|---|---|
| **1 — probe mascarava rc do `curl`** | **RESOLVIDO** | O script real passou em `bash -n`. Um servidor local produziu `http_code=200`, rc 18: em modo warn o script terminou 0, em modo strict terminou 1 e ambos preservaram `OLD-SHA`; o diagnóstico contém `curl_rc=18 http_code=200`. `actionlint` permaneceu limpo. |
| **2 — cache invalidado antes do commit** | **RESOLVIDO** | `changeform_view` realmente envolve o POST do formulário em `transaction.atomic`; `save_model` registra um callback somente quando o status anterior difere. Commit/rollback e as três chaves foram exercitados. A ingestão agenda após os commits de `_persistir_grupo` e `_persistir_grupo_mesclado`; a busca confirmou que o helper tem somente esses dois callers e o rollback real descartou o callback. O painel continua fora de `ATOMIC_REQUESTS` e mantém a invalidação imediata após o UPDATE autocommit. |
| **3 — `strip()` antes de validar `X-Request-ID`** | **RESOLVIDO** | A ordem real é `str` → `isprintable` no bruto → `strip(" ")` → sentinel/vazio → limite. Gunicorn real com bytes C1 nas bordas respondeu UUID ASCII; tab, newline e C1 interno também viraram UUID. Header, request, log e DB tiveram o mesmo valor; OWS ASCII foi tratado sem colisão. |
| **4 — anos civis 0000–0099 perdiam identidade** | **RESOLVIDO** | `formatToParts` substitui somente a parte `year` e preserva literais. `0000-01-01`, `0001-01-01` e `0096-02-29` produziram anos distintos com quatro dígitos; `0095-02-29` e `1900-02-29` ficaram vazios. Instante com fuso, `Date` e número permaneceram estáveis. |
| **5 — asserts do check de datas eram frouxos** | **RESOLVIDO** | As 12 saídas exportadas têm expectativas exatas e independentes; os casos `0000`, `0001`, `0096` e `0095` exercitam todos os formatadores com ano. Node 18/20 × UTC/Tokyo terminou 4/4. Não há dependência nova. |
| **6 — documentação Python 3.13 versus 3.12** | **RESOLVIDO** | README, bootstrap, CI e Docker agora apontam para Python 3.12; não restou afirmação ativa de 3.13 nos caminhos pesquisados. Requirements runtime/dev e o cache do setup-python continuam separados como na iteração 1. |

### Não-regressão dos demais caminhos

- **Ações nativas:** há no máximo um callback por invocação de approve/reject. A probe mostrou `callback_count=1`; `save_model` sem mudança registrou zero callback. A observação de que uma action idempotente ainda invalida uma vez está registrada como nit abaixo.
- **Ingestão:** há um callback por grupo persistido, nunca por item; rollback não executa callback e falha de cache continua contida no helper best-effort. Imports permanecem locais e não criam ciclo no carregamento dos apps.
- **Caddy:** `validate` passou; arquivo público retornou 200, enquanto privado, percent-encoded, traversal e subtree desconhecido retornaram 404 sem conteúdo privado.
- **Probe/marker:** rc e código são exigidos simultaneamente; `000`, 3xx, 4xx, 5xx e rc não zero não marcam OK. O resultado do deploy, o SHA verificado e a promoção/escrita do marker permanecem sob as barreiras anteriores.
- **Requirements:** lock runtime não contém ferramentas de teste; PM2 instala o lock, Docker usa `requirements.txt`, CI instala dev e o cache referencia lock + dev; `frontend/package*.json` não mudou.

### Finding 7
- **Arquivo:** `backend/catalogo_noticias/admin.py`
- **Linha:** `105-106`
- **Categoria:** maintainability
- **Severidade:** nit
- **Resumo:** o comentário afirma que `response_action` envolve actions em `transaction.atomic`, mas no Django 5.2 essa view não abre essa transação.
- **Cenário de falha:** uma ação real executada fora de atomic é confirmada por `connection.in_atomic_block=False`; o UPDATE já fez commit e o `on_commit` dispara imediatamente uma única vez. Se uma etapa posterior da requisição falhar, status e invalidação permanecem aplicados, contrariando a garantia transacional que o novo comentário registra. O comportamento atual do cache está correto; o defeito é a descrição falsa da semântica e o risco de uma futura alteração tomar decisões com base nela.
- **Sugestão:** corrigir o comentário para registrar que a ação atual é autocommit e que `on_commit` é imediato nesse caminho, ou envolver explicitamente a ação em `transaction.atomic` se a intenção for tornar atômicas futuras operações com múltiplas escritas.

### Finding 8
- **Arquivo:** `backend/catalogo_noticias/admin.py`
- **Linha:** `100-106, 108-113`
- **Categoria:** performance
- **Severidade:** nit
- **Resumo:** as actions em lote registram a invalidação mesmo quando todos os itens selecionados já têm o status destino.
- **Cenário de falha:** um item já `aprovado` selecionado em “Marcar selecionados como aprovado” sofre um UPDATE para o mesmo valor e mesmo assim executa uma vez o helper, apagando as três chaves sem qualquer transição editorial. A observação independente confirmou `save_same=0` e `action_same=1`; o impacto é limitado a uma limpeza desnecessária, sem dados desatualizados.
- **Sugestão:** decidir explicitamente se uma action idempotente deve ser no-op; nesse caso, filtrar itens já no destino ou registrar o callback apenas quando houver transição efetiva.

### Resumo quantitativo final

| Severidade | Quantidade |
|---|---:|
| blocker | 0 |
| major | 0 |
| minor | 0 |
| nit | 2 |

## Veredito final — iteração 2

**`approve_with_comments`**

Os seis findings anteriores estão resolvidos e não há blocker, major ou minor residual. A aprovação fica com dois nits no mesmo caminho de actions do admin: um comentário afirma uma atomicidade inexistente e actions idempotentes ainda causam uma limpeza de cache desnecessária; nenhum dos dois quebra correção, rollback, moderação ou o marker de deploy. Nenhum código foi alterado nesta re-revisão e nenhum commit foi criado.

## Estado final da revisão — iteração 2

- **status:** `completed`
- **iteration:** `2`
- **verdict:** `approve_with_comments`
- **remediation_required:** `false`
- **run_state_updated:** `false`
- **commit_created:** `false`

## Reconciliação final — iteração 3 (2026-09-24)

### Escopo e método

- **Escopo:** releitura do diff completo contra `HEAD` para o escopo original e para os dois paths de ingestão adicionados pela revisão anterior; leitura do histórico atualizado, do contrato e das revisões 1 e 2 preservadas neste arquivo.
- **Exclusões preservadas:** `agentic-framework/state/run-20260924-1400-tls-ingestao/run-state.json` e `agentic-framework/state/loteA-bugs/`.
- **Validação independente:** 4 testes focais dos nits e 34 testes de `painel_admin`; 13 testes de request ID; `manage.py check`; `tsc --noEmit`; check de datas Node 18/20 × UTC/Tokyo; `actionlint` 1.7.12; parser YAML sem duplicatas; `bash -n` e execução do probe com `200` + rc 18; `caddy validate`; requisitos/docs; e `git diff --check`.
- **Evidência complementar considerada:** o reteste independente reportou 490 passed em PostgreSQL 16, cobertura 88,75%, build 59/59 e actionlint limpo. O reviewer não repetiu a suíte completa nem o build; não houve GitHub Actions/VPS, Redis real, `pwsh`, DNS ou TLS real.

### Resultado dos dois nits da iteração 2

| Finding anterior | Status final | Evidência da reconciliação |
|---|---|---|
| **7 — comentário atribuía atomicidade inexistente ao `response_action`** | **RESOLVIDO** | `admin.py:107-110` descreve corretamente o Django 5.2/autocommit e explica o uso forward-safe de `on_commit`. A inspeção da biblioteca instalada confirmou que `response_action` não abre `transaction.atomic`; no caminho real o callback ocorre após o UPDATE, enquanto o teste dentro de atomic confirma adiamento até o commit. |
| **8 — action invalidava cache sem mudança efetiva** | **RESOLVIDO** | Approve/reject excluem o status destino antes do UPDATE e registram `on_commit` somente quando `atualizados > 0`. Os testes approve/reject no-op confirmaram retorno `None`, update 0, zero callback e as três chaves preservadas; seleções mistas confirmaram um UPDATE, um callback depois do commit, todas as três chaves limpas e retorno `None`. |

### Reconciliação dos fixes anteriores

- **Probe/marker:** o script final continua exigindo `curl rc=0` e HTTP 200; a repetição do cenário `200` + corpo parcial preservou o marker em modo warn e retornou 1 em modo strict. API TLS/não-TLS, web, resultado do deploy, SHA e escrita atômica do marker permanecem íntegros.
- **Cache/rollback:** `save_model` e ingestão continuam usando `on_commit`; rollback descarta callbacks; painel autocommit permanece correto; imports locais não introduzem ciclo. O novo filtro das actions não altera `save_model` nem a ingestão.
- **Request ID:** ordem bruto → `isprintable` → OWS ASCII → sentinel/vazio → limite permanece íntegra; os 13 testes focais passaram.
- **Datas civis:** `formatToParts` continua substituindo apenas `year`; datas 0000/0001/0096, datas impossíveis, instantes e entradas já `Date`/numéricas permanecem corretos. As quatro combinações Node 18/20 × UTC/Tokyo passaram, e todas as 12 saídas continuam com asserção exata.
- **Requirements/docs:** lock runtime, manifesto dev, PM2, Docker, cache do setup-python e Python 3.12 permanecem coerentes; nenhuma dependência frontend nova foi adicionada.
- **Caddy:** matcher privado → allowlist pública → fallback fail-closed e raízes `handle_path` não sofreram regressão; a configuração final passou no Caddy.
- **Workflows:** sintaxe, YAML, `verify`, `tls_enabled`, `concurrency` e rollback permanecem coerentes; `actionlint` permaneceu limpo.

### Findings finais

Nenhum finding residual ou nova regressão foi identificado.

### Resumo quantitativo final da reconciliação

| Severidade | Quantidade |
|---|---:|
| blocker | 0 |
| major | 0 |
| minor | 0 |
| nit | 0 |

## Veredito final — iteração 3

**`approve`**

Os dois nits da iteração 2 foram resolvidos de forma efetiva e sem regressão nos paths transacionais, de cache ou de moderação. A releitura integral do escopo e as validações executáveis não encontraram blocker, major, minor ou nit residual; a implementação está aprovada para o fechamento desta run.

## Estado final da reconciliação — iteração 3

- **status:** `completed`
- **iteration:** `3`
- **verdict:** `approve`
- **final_approval:** `true`
- **remediation_required:** `false`
- **run_state_updated:** `false`
- **commit_created:** `false`
