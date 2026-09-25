<!--
CONTRACT: code-review-contract
DONO: reviewer
QUANDO É CRIADO: sempre que review-triggers.md indicar revisão obrigatória, ou sob demanda (skill agentic-review).
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/code-review-contract.md
-->

# Code Review Contract — 20260924-2136-ingestao-noticias

## Metadados
- **run_id:** 20260924-2136-ingestao-noticias
- **Escopo revisado:** (4 arquivos, ~1207 linhas — só estes; o restante da árvore suja é de outras runs paralelas e foi ignorado)
  1. `backend/catalogo_noticias/management/commands/agendar_ingestao.py` (novo, 163 linhas)
  2. `backend/catalogo_noticias/services/deduplicacao.py` (otimização v2 — `git diff`, +197/-17)
  3. `subir-localhost.sh` (bloco do agendador, `--stop`, usage/banner — `git diff`, +28/-5; restante do arquivo pré-existente)
  4. `backend/catalogo_noticias/tests/test_command_agendar_ingestao.py` (novo, 819 linhas)
- **Contrato de referência:** `agentic-framework/state/run-20260924-2136-ingestao-noticias/implementation-contract.md` (versão 2, critérios 1-10)
- **Gatilhos aplicados (de review-triggers.md):**
  - (a) "regras de moderação de conteúdo ou nos critérios que decidem o que é publicado sem revisão prévia" — `deduplicacao.py` decide o agrupamento que vira `NewsCluster`/`status_revisao`; BRD §18 (risco de misattribution). Mesmo sendo comportamento-preservante por desenho, era obrigatório provar que a otimização não muda o agrupamento.
  - (b) "diffs acima de ~300 linhas" — ~1207 linhas no escopo.
  - (c) comportamento visível ao usuário: a ingestão deixa de rodar sozinha e passa a rodar (agendador novo, disparado pelo `subir-localhost.sh`).
  - AUTH, ASSINATURA, DADOS PESSOAIS, MIGRAÇÕES e APIs PÚBLICAS **não** foram tocados por esta run (confirmado por `git diff` do escopo).
- **Verificação executada por esta revisão** (tudo em `/tmp`, nada editado no repo):
  - `backend/.venv/bin/python -m pytest catalogo_noticias/ -q` → **171 passed**; `feed/ painel_admin/` → **85 passed** (consumidores do dedup).
  - `/tmp/opencode/verifica_bound.py` + `verifica_bound2.py` — o `_bound_similaridade` é **limite superior**? (1.950.117 pares, 12.585.197 podas testadas contra 14 limiares).
  - `/tmp/opencode/verifica_equivalencia.py` — equivalência groupings antigo-vs-novo com **gerador independente** do do arquivo de testes (inclui títulos degenerados: só stopwords, vazios, tokens curtos).
  - `/tmp/opencode/verifica_decisao_grupo.py` — o caminho de risco (grupo **MISTO**: membros viáveis + não-viáveis) e o *skip* de grupo 100% não-viável, exaustivamente.
  - `/tmp/opencode/verifica_misto.py` — o caminho MISTO aparece ou não em lotes aleatórios (para saber se a cobertura existente o exercita).
  - `/tmp/opencode/verifica_pior_caso.py` — custo do pré-filtro quando ele **não poda nada**.
  - `/tmp/opencode/verifica_dupla_instancia.sh` — sandbox com o bloco do agendador e o laço de `--stop` **extraídos do script real**.
  - `grep` de consumidores: `deduplicacao` só é importado por `services/ingestao.py` e testes (o LRU não aterrissa no request path do servidor web).

### Conclusão da pergunta central (limite superior do pré-filtro)

**O `_bound_similaridade` É um limite superior válido, e a margem de segurança é suficiente.** A conta fecha, item por item:

| parcela | limite usado | por que é upper bound |
|---|---|---|
| `peso_comuns` | `Σ w(t)` para `t ∈ tokens_a ∩ tokens_b` | exato — todo token comum sempre vira par `(t, t)` em `_tokens_fuzzy_pareados`, com contribuição `max(w,w)=w` |
| acréscimo fuzzy | soma dos `k` maiores pesos da **união** das duas listas pré-calculadas, `k = min(|a|,|b|) − |comuns|` | cada par fuzzy consome 1 token de cada lado e contribui `max(w_x, w_y)` — ou seja, o peso de **um** token; tokens de um par são distintos dos de outro (a∩b = ∅ nos restantes), logo há no máximo `k` contribuições, e a soma dos `k` maiores da união é ≥ qualquer soma realizável |
| denominador | `peso_uniao_a + peso_uniao_b − peso_comuns` | é exatamente `Σ_{t ∈ a∪b} w(t)` (a interseção contada uma vez) |
| ordenação | `sorted(..., reverse=True)` nas DUAS listas + merge two-pointer | ordem decrescente em ambas é a precondição do merge; conferi em `deduplicacao.py:479-481` |
| sem `IndexError` | `i+j ≤ k−1 ≤ min(|a|,|b|)−1` nos dois lados | 0 exceções em 1,95M de chamadas, incluindo `tokens_a`/∅ e 8×8 disjuntos |
| tokens vazios | `if not tokens_a or not tokens_b: return 0.0` | `_similaridade_ponderada` também retorna 0.0 nesse caso |
| união de peso 0 | `if peso_uniao <= 0: return 0.0` | idem no score real |
| pesos default | `pesos_tokens.get(token, 1.0)` no pré-cálculo, no `peso_comuns` e no `_similaridade_ponderada` | mesma fonte de peso nos três pontos — **sem divergência**, inclusive com item repetido no lote (o pré-cálculo é por token de conjunto, a frequência continua vindo de `_pesos_por_frequencia_no_lote` sobre TODOS os itens) |

Único desvio medido: **`real − bound` chega a 2,22e-16** (1 ULP), vindo do erro de arredondamento de float na subtração do denominador (erro absoluto máx. 8,9e-16). A margem de 1e-12 é ~4 ordens de grandeza maior — `bound < limiar − 1e-12` implica `real < limiar`. Resultado da verificação: **0 podas indevidas** em 1.950.117 pares. O critério de equivalência 9 **não é quebrado** por este caminho.

Equivalência nos caminhos secundários (onde a poda muda a *decisão*, não só o custo):
- **cache LRU**: `_ratio_sequence_matcher_canonico` é pura (`SequenceMatcher(None, a, b).ratio()`), chave canônica `(min,max)` idêntica à do dict antigo; a política de despejo só muda retenção, nunca valor. `lru_cache` da C é thread-safe, e o dedup roda na thread principal (o `ThreadPoolExecutor` é só do fetch). **18,3 MB** medidos com as 65.536 entradas cheias — limitado, não é vazamento, e o docstring ("~15MB") erra por ~20%, o que é aceitável.
- **pré-cálculo** `dados_por_item`: usado **só** no bound; `_similaridade_ponderada` continua calculando o denominador exato. Valores float bit-idênticos: 23.400 pares comparados com `==`, 0 divergências.
- **skip de grupo (`if not algum_viavel: continue`)**: prova direta de que a decisão é a mesma mesmo quando o grupo é misto — 1.200.000 casos (item × grupos × pesos × limiar) com **667.953 grupos MISTOS** e 649.693 grupos 100% não-viáveis, **0 divergências de decisão**. O argumento: um membro não-viável tem `real ≤ bound < limiar`, logo nunca pode ser o `max` que cruza o limiar; e como `melhor_score` só é consultado por `>= limiar`, um grupo pulado com `real < limiar` não muda nem o grupo escolhido nem a criação de grupo novo. Ordem dos grupos preservada (nada foi reordenado).
- **equivalência de groupings ponta a ponta**: 360 comparações (60 lotes × limiares 0.0/0.3/0.55/0.7/0.9/1.0) com gerador independente → 0 divergências; `catalogo_noticias` 171/171 verde.

## Findings

### Finding 1
- **Arquivo:** `subir-localhost.sh` (laço de `--stop`, linhas 179-189) em conjunto com o guard do agendador (linhas 411-429) e `backend/catalogo_noticias/management/commands/agendar_ingestao.py` (linhas 79-91, 110-148)
- **Linha:** 179-189 / 411-429 / 79-91
- **Categoria:** correctness
- **Severidade:** major
- **Resumo:** o `--stop` remove o pid file **antes** o processo realmente sair, e o comando trata SIGTERM como "terminar a rodada atual" — a combinação abre uma janela em que o guard do script não impede uma segunda instância concorrente.
- **Cenário de falha:** usuário roda `./subir-localhost.sh --stop` durante uma rodada em curso. O `--stop` faz `kill "$pid"` e, **sem esperar**, `rm -f /tmp/brd-agendador.pid`, imprimindo "parado pid N". O `agendar_ingestao` instalado o próprio handler (linhas 90-91): o SIGTERM apenas marca `parada_solicitada` e a **rodada em curso roda até o fim** (medido hoje: 1,1-1,5 min; no cenário de backlog da Iteração 3, uma única rodada levou **7h54m**). O usuário roda `./subir-localhost.sh` de novo logo depois: o guard não acha pid file, sobe uma **segunda** instância, e as duas passam a executar `executar_ingestao()` em paralelo sobre os mesmos 91 feeds e o mesmo sqlite. **Reproduzido** em sandbox com os dois blocos extraídos do script real (`/tmp/opencode/verifica_dupla_instancia.sh`): "DUAS INSTANCIAS CONCORRENTES: o guard NAO impediu", pids 710246 e 710288 vivos ao mesmo tempo. Consequências: 91 feeds RSS baixados duas vezes, `SummarizationProvider` chamado 2× (custo de LLM), contenção de CPU (exatamente o que transformou a rodada em 7h54m na Iteração 3) e, como `settings.py` declara sqlite **sem** `OPTIONS={"timeout": ...}`, risco de `OperationalError: database is locked` numa das instâncias. Agrava: o segundo sinal é engolido (`if parada_solicitada is None`, linha 83) — `kill $(cat /tmp/brd-agendador.pid)` não "desiste", só `kill -9` sai. Isto é o mesmo cenário de dupla instância que **já ocorreu** nesta run (Iteração 6: pids 363955 e 364572 com overlap real de ~31s) — o guard do script não o impediria.
- **Sugestão:** três correções baratas e independentes — (a) no `--stop`, após `kill`, aguardar `kill -0` por um tempo limitado (ou usar `pkill -TERM -f agendar_ingestao` + espera) **antes** de `rm -f`; (b) no segundo SIGTERM/SIGINT, sair imediatamente (escalonamento), para o `--stop` ter uma saída previsível; (c) `flock` no pid file (ou um lockfile com PID) fecha a classe toda do problema, inclusive duas execuções simultâneas do script e o caso "pid file apagado com o processo vivo".

### Finding 2
- **Arquivo:** `backend/catalogo_noticias/management/commands/agendar_ingestao.py` (linhas 120-142, 145-148) e `subir-localhost.sh` (linhas 424-429, 439)
- **Linha:** 120-142 / 424-429
- **Categoria:** correctness
- **Severidade:** major
- **Resumo:** a falha do agendador é invisível: o script anuncia o agendador sem verificar que ele subiu, e o loop repete a mesma falha indefinidamente sem backoff, contador ou sinal em lugar nenhum — a mesma classe de falha silenciosa que esta run existe para eliminar.
- **Cenário de falha:** dois caminhos concretos, ambos já vistos nesta run. (1) `./subir-localhost.sh` grava o pid e imprime "agendador de ingestão em background (pid N)" **sem checar** que o processo sobreviveu aos primeiros milissegundos. Foi exatamente o que a Iteração 5 documentou: com o `settings.py` corrompido, `manage.py agendar_ingestao` morria **imediatamente** com `IndentationError` — o banner teria anunciado a ingestão como agendada com um processo morto, e o usuário só descobriria ao `tail` do log. (2) Com `executar_ingestao()` falhando sempre (banco travado, provider de resumo quebrado, DNS), o loop loga `logger.exception` e repete a cada 15 min, **para sempre**: sem contador de falhas consecutivas, sem backoff, sem nível de log distinto, sem nada em `/healthz`, e **cada tentativa paga o sweep completo dos 91 feeds** antes de falhar (o banco só é tocado no fim do pipeline) — 4 varreduras de rede por hora, indefinidamente, sem ninguém notar. Nada cresce sem limite (LRU ≤ 18,3 MB, log ~3 KB/h, `RegistroExecucaoIngestao` só em sucesso), mas o sintoma é o do bug original: "ingestão parada e ninguém sabe".
- **Sugestão:** (a) no script, após `nohup`, `sleep 1` + `kill -0` e/ou `grep -q "Agendador de ingestão iniciado"` no log, e falhar com `die`/`warn` alto se não aparecer; (b) no command, contar falhas consecutivas e, a partir de N (ex.: 3), logar em `ERROR` com mensagem própria ("N rodadas consecutivas falharam — checar /tmp/brd-agendador.log") e/ou a orientar a parada manual. O contrato não pede alerta (e "persistir falha no banco" é não-objetivo), mas o banner afirmativo do script deveria ser verificável.

### Finding 3
- **Arquivo:** `backend/catalogo_noticias/management/commands/agendar_ingestao.py`
- **Linha:** 132-140
- **Categoria:** correctness
- **Severidade:** minor
- **Resumo:** o isolamento de falha cobre só a chamada de `executar_ingestao()`; o log de sucesso da rodada está **fora** do `try/except` e uma exceção ali mata o processo, contradizendo a garantia "nunca mata o processo" do contrato.
- **Cenário de falha:** `registro.id`, `registro.total_itens_ingeridos` e `registro.erros_por_fonte` são acessados no bloco `else:` (linhas 137-139), que só é coberto pelo `finally` (linhas 141-142) — e `finally` não captura exceção. Se qualquer um desses acessos levantar (renomeação de campo do modelo, `executar_ingestao` devolvendo algo inesperado num monkeypatch/injeção, erro de formatação do logging), a exceção escapa do `while` e o processo morre; como o agendador é iniciado por `nohup` sem supervisor, a ingestão para em silêncio até alguém notar. Hoje os campos existem (`models.py:288-306`), então a probabilidade é baixa — é uma lacuna de robustez, não um bug ativo.
- **Sugestão:** mover o corpo do `else` para dentro do `try` (ou envolvê-lo no próprio `try/except` com `logger.exception`), para que a garantia do contrato valha para a rodada inteira e não só para a chamada do pipeline.

### Finding 4
- **Arquivo:** `backend/catalogo_noticias/services/deduplicacao.py`
- **Linha:** 500-518
- **Categoria:** performance
- **Severidade:** minor
- **Resumo:** o pré-filtro é líquido quando ele poda; no caso degenerado em que **nada** é podado, ele adiciona custo puro (medido: até 0,63× — ou seja, ~37% mais lento que a versão antiga).
- **Cenário de falha:** medido com a implementação antiga (fonte do `git HEAD` carregado via `exec`) contra a nova, mesmo lote, melhor de 3 repetições: (A) 60 títulos quase idênticos, bound não poda nada → antiga 0,008s / nova 0,009s (**0,86×**); (B) 120 títulos em 2 templates quase iguais → antiga 0,030s / nova 0,049s (**0,63×**); (C) 300 títulos típicos bem distintos → 0,801s / 0,461s (**1,74×**); e o lote de 3000 itens do benchmark do contrato → 8,6-10,3× (medido pelo executor/tester). O caso de regressão tem custo absoluto irrisório (49 ms), então o impacto prático é desprezível; fica registrado porque o diff não é "nunca mais lento" e o critério 8 do contrato mede só o caminho feliz.
- **Sugestão:** nenhuma correção necessária — registrar o número. Se quiser blindar, um teste de performance do pior caso (ou um comentário no docstring) documenta o trade-off para quem mexer no limiar depois.

### Finding 5
- **Arquivo:** `subir-localhost.sh`
- **Linha:** 426
- **Categoria:** maintainability
- **Severidade:** minor
- **Resumo:** `nohup ... >/tmp/brd-agendador.log` **trunca** o log a cada execução do script, e esse log é a única observabilidade da ingestão que a run entregou.
- **Cenário de falha:** rodar `./subir-localhost.sh` de novo (cenário comum: reiniciar só o backend) apaga todo o histórico de rodadas. Aconteceu de fato na Iteração 6 — a instância duplicada iniciada com `>` apagou 88 KB de histórico (rodadas 1-24) e o executor/tester tiveram de reconstruir a partir do banco. As linhas de banner (439-441) inclusive propagate o log como onde se olha a ingestão.
- **Sugestão:** `>>` (o próprio executor acabou fazendo isso na mão na Iteração 6). Manter `>` é coerente com o padrão pré-existente de backend/frontend, mas o log do agendador tem peso diferente.

### Finding 6
- **Arquivo:** `subir-localhost.sh`
- **Linha:** 415-423
- **Categoria:** maintainability
- **Severidade:** nit
- **Resumo:** o guard aceita qualquer pid vivo como "o agendador" e usa nome fixo em `/tmp`, compartilhado por qualquer clone do repo na mesma máquina.
- **Cenário de falha:** (a) pid reciclado → o script recusa iniciar ("já ativo") com um pid que não é o agendador; `--stop` nesse estado mata um processo alheio; (b) dois clones do portal na mesma máquina → o clone B lê o pid file do clone A, recusa iniciar o seu e o `--stop` do clone B derruba o agendador do clone A. Limitação já registrada na Iteração 1 e **aceita explicitamente** pelo contrato ("mesmo padrão do `--stop` existente"), então é nit — mas é o mesmo parcel de código que o Finding 1 corrige com `flock`.
- **Sugestão:** validar a linha de comando do pid (`ps -p "$pid" -o args=` contendo `agendar_ingestao`) e/ou nomear o pid file com o hash do caminho do repo.

### Finding 7
- **Arquivo:** `backend/catalogo_noticias/services/deduplicacao.py`
- **Linha:** 389-397
- **Categoria:** maintainability
- **Severidade:** nit
- **Resumo:** a assinatura de `_bound_similaridade` intercala dados de `a` e `b` (`... pesos_ordenados_a, peso_uniao_a, pesos_ordenados_b, peso_uniao_b`), o que torna um erro de chamada silencioso e **catastrófico** (bound que deixa de ser upper bound).
- **Cenário de falha:** a fórmula é simétrica, então trocar `a`↔`b` inteiro é inofensivo — mas uma troca **parcial** (passar `peso_uniao_b` onde se espera `peso_uniao_a`) produz um denominador errado, com o `_soma_k_maiores_pesos` continuando correto, e nada no código ou nos testes denuncia isso: os testes só exercitam call sites corretos e a equivalência só se quebra se o erro aparecer em algum lote. É a função de segurança do diff inteiro.
- **Sugestão:** agrupar os dados pré-calculados por item numa tupla/objeto (`dados_item = (pesos_ordenados, peso_uniao)`) e passar `dados_item_a, dados_item_b` — elimina a classe de erro sem custo de performance.

### Finding 8
- **Arquivo:** `backend/catalogo_noticias/management/commands/agendar_ingestao.py`
- **Linha:** 69-70, 71, 110
- **Categoria:** correctness
- **Severidade:** nit
- **Resumo:** `--intervalo-segundos <= 0` é validado com `CommandError`, mas `--rodadas 0` e `--rodadas -1` são aceitos em silêncio e não executam nada (saída 0, "Agendador finalizado (0 rodada(s))"); não há teste para esse caso.
- **Cenário de falha:** `--rodadas -1` (typo) ou `--rodadas 0` (expectativa de "nenhuma") dão a impressão de que o agendador rodou, quando nada foi executado; `--rodadas 1000000000` é indistinguível de "infinitas" no log. O contrato só especifica o caso positivo e o padrão infinito, então não há violação de critério — é assimetria de validação. O tester registrou a lacuna de cobertura equivalente na Iteração 7.
- **Sugestão:** validar `--rodadas >= 0` com `CommandError` (ou ao menos `warn` no log para 0/negativo), por simetria com o intervalo.

## Resumo quantitativo (1ª passada — superseded pela 2ª passada)
| Severidade | Quantidade |
|---|---|
| blocker | 0 |
| major | 2 |
| minor | 3 |
| nit | 3 |

## Veredito (1ª passada — superseded)
**changes_requested**

O núcleo da run está sólido e foi verificado de forma independente: o pré-filtro por limite superior é matematicamente um upper bound (0 podas indevidas em 1,95M de pares, desvio máximo de 1 ULP contra margem de 1e-12), a decisão de agrupamento é idêntica inclusive no caminho de risco (0 divergências em 1,2M de casos com 668 mil grupos mistos), o cache LRU não muda valores de função pura e o-limitado (18,3 MB), e os critérios 1-10 têm evidência real (171 testes verdes, 12+ rodadas do agendador com o código novo, 8,6-10,3× de ganho). O que impede `approve` são os dois **major** do agendador, ambos no mesmo eixo "uma segunda execução concorrente ou uma falha silenciosa": o `--stop` remove o pid file antes do processo sair e o guard do script não fecha essa janela (Finding 1, reproduzido em sandbox — e é o cenário de dupla instância que já aconteceu nesta run), e nada verifica que o agendador realmente subiu nem escala o alerta quando a ingestão falha em definitivo (Finding 2), devolvendo exatamente o sintoma "ingestão parada e ninguém sabe" que a run existe para corrigir. Ambos têm correção barata e localizada; depois deles, os 3 minor e 3 nit são Enhancements, não bloqueios.

---

# Segunda passada — 2026-09-25T19:15:00-03:00

## Escopo e método
- **Escopo:** apenas o diff da remediação (Iteração 8): `subir-localhost.sh` (helpers do agendador 181-284, `--stop` 288-320, bloco de subida 542-607, banner 617-628), `backend/catalogo_noticias/management/commands/agendar_ingestao.py` (257 linhas, novo) e os 6 testes novos de `test_command_agendar_ingestao.py`. **O núcleo do dedup não foi reaberto** (ver confirmação abaixo).
- **Verificação executada (tudo em `/tmp/opencode/rev2/`, nada editado no repo):**
  - `cd backend && .venv/bin/python -m pytest catalogo_noticias/ -q` → **177 passed** (171 da 1ª passada + 6 novos da remediação; nenhum teste existente foi ajustado).
  - `/tmp/opencode/rev2/q2_lock.sh` — herança do `flock` pelo filho, arquivo de lock compartilhado, fluxo sem `flock` no PATH.
  - `/tmp/opencode/rev2/q3_banner.sh` — 5 cenários do banner verificável (normal, banner atrasado 3s, processo morre no start, vivo sem banner, **log com banner de execução anterior**).
  - `/tmp/opencode/rev2/q5_stop.sh` — 4 cenários do `--stop` com **observador independente a cada 0,1s** (o que procura é exatamente o estado proibido: *pid file ausente com o processo vivo*).
  - `/tmp/opencode/rev2/q1_race.sh` — replay do Finding 1 (start durante a espera do `--stop`) e corrida de dois starts, **com e sem `flock`**.
  - Sandbox com a mesma técnica da 1ª passada: os blocos do script são extraídos **verbatim** por `sed` (181-284, 288-320, 542-607) e exercitados em paths isolados; o "agendador" é um shim cujo comportamento de sinal é modelado. O **escalonamento do command real** é coberto pelo teste de subprocesso `test_segundo_sinal_escala_e_encerra_na_hora` (rodei na suíte: passa, `returncode == 143` em <10s).
  - Leitura dirigida de `services/ingestao.py` (granularidade transacional), `config/settings.py` (handler de log), `ps`/`pgrep` (identidade de processo).
- **Estado real do agendador durante a revisão:** pid **775406**, **uma única instância**, 2 rodadas concluídas com o código remediaído (registro_id 54 e 55), 0 alertas de falha, intervalo de 15,0 min preservado. Meus sandboxes foram encerrados e nenhum `/tmp/brd-*` de produção foi tocado.

## Confirmação: `deduplicacao.py` intocado desde a 1ª passada
**Fato comprovado.** `stat` do arquivo: mtime **2026-09-25 10:05:59** — **8h45min antes** do primeiro arquivo tocado pela remediação (`test_command_agendar_ingestao.py`, 18:33:29) e **8h45min antes** do início da remediação (18:41). `sha256 = dafe6080…ef4f99`, 26.518 bytes. A 1ª passada do reviewer rodou depois das 17:50 (Iteração 7 do tester) e antes das 18:20 (mtime do `code-review-contract.md`), ou seja **dentro da mesma janela de 8h45min em que o arquivo já estava parado**. Nenhum arquivo da remediação toca o dedup. A conclusão da 1ª passada (0 podas indevidas em 1,95M de pares; equivalência groupings 0 divergências) permanece válida sem re-análise.

## Respostas às perguntas centrais (fato medido × hipótese)

### 1. O escalonamento com `os._exit(128+signum)` é seguro?
**Sim, é seguro neste contexto, e o 1º sinal continua gracioso — fato medido.**
- **1º sinal continua gracioso:** o handler só marca `parada_solicitada`; o teste de subprocesso prova que o processo **permanece vivo** 2s após o 1º SIGTERM e que a rodada em curso termina (nada no `while` foi abortado). O log de produção mostra as duas paradas graciosas reais: 14:39:35 ("Sinal SIGTERM recebido" → "encerrado por SIGTERM, rodadas executadas=2") e 18:44:28 (rodadas executadas=17). Critério 5 preservado.
- **O que deixa de acontecer com `os._exit`:** (i) o `finally: close_old_connections()` — as conexões sqlite não são fechadas explicitamente, mas o OS fecha os fds e o próximo processo faz o *hot journal rollback* de qualquer transação aberta (sqlite é crash-safe nos dois journal modes); (ii) `signal.signal(...)` de restauração — irrelevante, o processo morre; (iii) a linha final `Agendador finalizado (N rodada(s))` no stdout — ninguém a parseia; (iv) `atexit`/fechamento das threads do `ThreadPoolExecutor` de fetch — elas são mortas em `os._exit`; nenhuma delas escreve no banco (`_buscar` só busca, o `invalidar_validadores_apos_erro` roda na thread principal). **O `logging.shutdown()` não perde nada:** o handler de log do projeto é um `logging.StreamHandler` (`config/settings.py`, raiz `console`) e `StreamHandler.emit()` faz `flush()` a cada registro — o `logger.error("Segundo sinal…")` já está no arquivo **antes** das chamadas de flush.
- **Código de saída > 128 é aceito?** **Sim, e é a convenção correta.** 143 (SIGTERM) e 130 (SIGINT) são exatamente os códigos que o shell reportaria para "morto pelo sinal". **Fato:** nada no repositório inspeciona esse código — `agendar_ingestao` só é invocado por `subir-localhost.sh` em background (`nohup … &`, cujo status é descartado); não há `ecosystem.config`/PM2, o comando não entra em docker-compose, e `grep` por `wait $`/`$?` no script não achou checagem. Docker/PM2 tratam qualquer saída não-zero igual, e `set -euo pipefail` não é afetado por um job em background.
- **Hipótese (não medida, risco teórico):** `logging.shutdown()` dentro de um handler de sinal adquire o lock de cada handler; se uma thread do `ThreadPoolExecutor` estivesse emitindo log naquele instante, o shutdown **poderia** bloquear por microssegundos (o portador do lock é liberado assim que o `emit` termina; não há caminho em que uma thread de log espere a thread principal). Se isso acontecesse, a consequência seria voltar ao limbo pré-remediação (o `--stop` acabaria no `kill -9` que ele próprio sugere), **nenhum risco de dado**. Não medi um stress desse caso; registro como hipótese, abaixo de nit.
- **Contrapartida real do escalonamento:** a persistência **não** é atômica por rodada — ver **Finding 1 (novo, 2ª passada)**.

### 2. O `flock` opcional fecha mesmo a classe do Finding 1 (1ª passada)?
**Sim, mas ele não é o que fecha o Finding 1 — a espera é. Fato medido nos dois eixos.** (aqui "Finding 1" = o major da 1ª passada, janela de 2ª instância)
- **O que o `flock` fecha:** a corrida de **duas execuções do script ao mesmo tempo** (R3: 1 instância, as duas veem "já ativo") e o caso "pid file apagado com o processo vivo". Sem `flock` (R4), a janela existe de novo — nesta execução ela não materializou, mas não há garantia estrutural. Então o `flock` é o **fecho de segurança** da subclasse "scripts concorrentes", não da classe original.
- **A classe original do Finding 1 está fechada sem `flock` (fato medido):** R1 (com `flock`) e R2 (**sem `flock` no PATH**, macOS-like) — nos dois, um `./subir-localhost.sh` disparado **2s depois** do `--stop`, enquanto o processo antigo está vivo e o `--stop` ainda espera, resultou em `OK agendador de ingestão já ativo (pid …)` e **1 instância**. Quem fecha a janela é (a) o pid file só ser removido **depois** da morte, com (b) o escalonamento dando um desfecho previsível e (c) a identidade impedindo sinal em processo alheio.
- **O filho não herda o lock — sintaxe verificada:** `nohup … >>"$AGENDADOR_LOG" 2>&1 9>&- &` (linha 574). `9>&-` é fecha-de-fd válido e vem por último, depois de `>>` e `2>&1`, então nenhum redirecionamento anterior usa o fd 9. **Medido:** com o pai segurando o lock no fd 9, o filho lançado com `9>&-` **não tem fd 9** em `/proc/<pid>/fd`; um terceiro shell não consegue o lock enquanto o pai vive; e o lock fica livre **imediatamente** quando o pai solta, **antes** do filho morrer (o filho nunca o retém). A preocupação do remediator era correta e a implementação está certa.
- **O `--stop` usa o mesmo arquivo de lock:** **sim** — `travarlock_agendador` (234-241) usa `AGENDADOR_LOCK` e é chamada nos dois blocos (`--stop` 314, start 543), com o mesmo `AGENDADOR_LOCK="/tmp/brd-agendador.lock"` (linha 36).
- **Se `flock` não existir, o guard ainda está correto?** **Sim, e o aviso é honesto.** `command -v flock` falha → `travarlock_agendador` retorna 1 → o script **avisa** ("flock indisponível/ocupado — a proteção de instância única … fica só no pid file + identidade do processo") e segue o fluxo normal, que R2 provou estar correto. O mesmo caminho é usado quando o lock está **ocupado** (`flock -w 10` estourou), situação real observada em R1/R2: o `--stop` segura o lock enquanto espera, e o start concorrente cai no fallback — e ainda assim disse "já ativo".

### 3. O banner verificável gera falso positivo ou falso negativo?
**Falso negativo por log antigo: impossível (medido). Falso positivo: só numa janela estreitíssima (Finding 3 novo, 2ª passada).**
- **Isolamento da execução corrente: funciona.** O `log_offset` é o tamanho do arquivo **antes** do `nohup` e a busca é `tail -c +$((log_offset+1))`. Cenário S5: log com **160 bytes de histórico** contendo o banner de uma execução anterior + processo novo que **nunca** loga → **`AGENDADOR_FALHOU=1`**. O banner antigo foi corretamente ignorado. Sem o offset isso seria um falso positivo garantido.
- **Atraso de I/O: não é uma fonte de falso negativo (fato).** (i) O handler é `StreamHandler` e faz flush por registro; (ii) o loop de verificação (`for _ in $(seq 1 10)`, ~10s, com `sleep 1`) **relê o arquivo** a cada iteração. Cenário S2: banner chegando com **3s de atraso** → confirmado. Mesmo um atraso de até ~10s seria absorvido.
- **Verificação de liveness antes do log:** o `if ! _pid_vivo …; then break` roda **antes** do grep em cada iteração, então o caso que de fato importa (processo morre no start, como o `settings.py` corrompido da Iteração 5) é corretamente reprovado: S3 → `AGENDADOR_FALHOU=1` + as 15 últimas linhas com o `IndentationError` + "a ingestão está PARADA", e o banner final (620) troca a linha de ingestão por "ATENÇÃO — agendador NÃO subiu". **Finding 2(a) fechado.**
- **Falso positivo residual:** a confirmação é `vivo + banner`, **sem reconferir a vivacidade depois** de encontrar a linha. Se o processo morrer nos microssegundos seguintes ao banner (p.ex. banco travado já no começo da 1ª rodada), o script imprime `OK agendador NO AR — primeira rodada iniciada` e `AGENDADOR_FALHOU` fica 0, enquanto o banner final cairia no ramo "NÃO confirmado como vivo" (626). Janela de ~1ms e direção segura (o banner final ainda é honesto) — ver Finding 3 (novo, 2ª passada).

### 4. O contador de falhas consecutivas
**A taxa de falso positivo é estruturalmente baixa, e o reset está correto.**
- **O que conta como "falha" (fato, lido em `ingestao.py`):** falha de **uma fonte** é capturada por fonte (`erros_por_fonte`, `logger.error`, segue) e a **rodada termina com sucesso**; `SummarizationProviderError` também é capturada **por lote** com fallback local. Ou seja, DNS ruim, RSS lento, provider de LLM fora do ar **não** incrementam o contador. Só entra no contador o que realmente impede a rodada de produzir (erro de banco, falha em `transaction.atomic`, bug). Isso reduz muito o alerta indevido: as 3 falhas seguidas que disparam o `logger.error` significam "3 rodadas não produziram nada", que é literalmente o que a mensagem afirma.
- **O reset está correto:** o `falhas_consecutivas = 0` está no `else:` do `try` — só quando a rodada **inteira** passou (pipeline + log de sucesso). O teste `test_contador_de_falhas_reseta_apos_rodada_com_sucesso` cobre F F S F F e afirma **zero** alertas; é a garantia de que o alerta não vira alarme falso recorrente.
- **Some no reinício: aceitável.** É estado em memória, e o reinício do processo já é o evento que o usuário percebe. Pior caso: uma causa permanente é reacusada 3 vezes em ~30 min após cada restart. O que compensa: o Finding 2(a) cobre o modo de falha mais grave (processo morre no start) **sem depender do contador**. Aceito como limitação conhecida, não como defeito.
- **Sem backoff (resíduo herdado da 1ª passada):** as 3 falhas que precedem o alerta custam 3 varreduras completas dos 91 feeds. O alerta é o que a 1ª passada pediu; backoff é *enhancement* (e mudaria o tempo de recuperação). Registrado como follow-up, não como finding.
- **Canto raro, abaixo de nit:** com o log de sucesso agora **dentro** do `try` (Finding 3 da 1ª passada), uma falha só de *formatação/acesso* ao `registro` conta a rodada como falha **mesmo com tudo já persistido** — 3 dessas e o alerta diz "a INGESTÃO ESTÁ PARADA de fato" sobre uma ingestão que está funcionando. Exige renomear campo/quebrar o `logging`; a própria mensagem de alerta é derivada do contador, não do estado do banco.

### 5. O `--stop` pode travar o script por muito tempo?
**Não: o bloqueio é limitado e medida — no pior caso 20,1s, e a espera é de 15s, não 15s × N pid files.**
- `ESPERA_PARADA_SEGUNDOS=15` (linha 41) vale **só para o agendador**; o laço de backend/frontend (297-311) manteve o comportamento pré-existente (SIGTERM best-effort, sem espera). O custo adicional do `--stop` é, portanto, **um** `ESPERA_PARADA_SEGUNDOS` (+5s após o 2º sinal) — não 15s por pid file.
- **Medido:** T1 (agendador no intervalo entre rodadas, sai no 1º sinal) → **1,04s**; T2 (rodada longa, escalonamento) → **16,1s**; T3 (processo travado que ignora os dois sinais) → **20,1s**; T4 (sem pid file) → instantâneo. Nenhum travamento.
- **O caminho "processo não saiu" está descrito corretamente.** T3: o pid file é **mantido** e o aviso é explícito e contém a ação ("ATENÇÃO: … continua VIVO após o 2º sinal — pid file MANTIDO de propósito … Para encerrar à força: `kill -9`"). O observador (0 violações em 196 amostras) confirma que o estado proibido — *pid file ausente com o processo vivo* — **nunca** ocorreu, em nenhum dos 4 cenários. A única nit de UX: o `--stop` termina imprimindo "Pronto." logo abaixo do "ATENÇÃO", o que é uma contradição de tom (não de conteúdo). O `usage()`/banner continuam corretos (não prometem parada imediata).

### 6. Alguma mudança introduziu risco de REGRESSÃO nos critérios 1-10?
**Nenhuma regressão encontrada. Fatos:**
- **Suíte:** `177 passed` (a 1ª passada tinha 171; os 6 novos são da remediação e nenhum teste existente precisou de ajuste — nenhuma correção invalidou uma verdade afirmada por um teste).
- **Critérios 1-5** (rodada/log/saída 0, isolamento de falha, intervalo, default da setting, sinal gracioso): o caminho do 1º sinal é **intocado**; a validação de `--rodadas` só acrescenta `CommandError` para negativo e um `WARNING` para 0, sem tocar no laço. `test_sigterm_em_processo_real_encerra_sem_traceback_e_rapido` e `test_rodada_unica_em_processo_real_sai_com_codigo_zero` passam.
- **Critério 6** (sem 2ª instância, `--stop` encerra): R1-R4 acima — 1 instância em todos os cenários, com e sem `flock`.
- **Critério 7** (docker/Celery intocados, opt-in): `git diff`/`git status` de `*docker-compose*` vazios; `CELERY_BEAT_SCHEDULE` na **mesma linha 703** no HEAD e na árvore; o bloco do agendador (542) está **depois** do `fi` do ramo docker (407) — só no modo nativo.
- **Critérios 8-9** (dedup): `deduplicacao.py` intocado (ver acima) + os testes de equivalência passam.
- **Critério 10** (rodada real no agendador novo): produção com pid 775406, rodadas 1 e 2 concluídas (registro_id 54 e 55) com o código remediaído.
- **Não-vacuidade dos 6 testes novos:** conferi por construção, não só pelo mutation check do remediator. `test_segundo_sinal_escala_e_encerra_na_hora` só passa se `os._exit(128+15)` executar (afirma `returncode == 143` **e** <10s); `test_falha_no_log_de_sucesso_nao_mata_o_loop` usa `SimpleNamespace()` sem campos e afirma `executar.call_count == 2` (com o log fora do `try` o processo morre na 1ª rodada → falharia); os dois de `--rodadas` afirmam `CommandError`/aviso; o do alerta afirma **exatamente 1** registro ERROR na 3ª falha e o do reset afirma **zero** alertas no padrão F F S F F.

## Findings novos (2ª passada — numeração reiniciada, não colide com a 1ª passada)

### Finding 1 (novo) — o escalonamento aborta a rodada e a justificativa "nada é persistido" está imprecisa
- **Arquivo:** `backend/catalogo_noticias/management/commands/agendar_ingestao.py` (135-146) em conjunto com `services/ingestao.py` (468, 542, 1019) e `subir-localhost.sh` (41, 252-282)
- **Linha:** 135-146 / 41
- **Categoria:** correctness
- **Severidade:** minor
- **Resumo:** a justificativa do `os._exit` ("a ingestão é transacional, então a rodada abandonada não persiste nada") e a mensagem de log "a rodada em curso foi abandonada e NÃO foi registrada" superestimam a atomicidade: `executar_ingestao` **não** é atômica por rodada — a persistência é por grupo (`@transaction.atomic` em `_persistir_grupo`/`_persistir_grupo_mesclado`) e o `RegistroExecucaoIngestao` é fechado só no fim.
- **Cenário de falha (concreto):** `ESPERA_PARADA_SEGUNDOS=15` < duração atual das rodadas (1,1-1,5 min medidas na Iteração 7). Então **todo** `--stop` durante uma ronda **interrompe a rodada** no 2º sinal (antes da remediação, o 1º sinal sozinha deixava a rodada terminar — nada se perdia). Se a rodada já tiver persistido 400 dos 700 grupos, o `os._exit` deixa: (a) 400 grupos/`NewsItem` **commitados**; (b) um `RegistroExecucaoIngestao` com `total_itens_ingeridos=0` e `erros_por_fonte={}` (ele só recebe os totais no `registro.save()` final), embora `_atualizar_metricas_execucao` já tenha gravado custo/tokens parciais — e `metricas/services.py:175,282` soma custo a partir desse registro; (c) `confirmar_validadores` nunca chamado para as fontes processadas (o próprio código trata isso como seguro: a próxima rodada rebaixa o XML em vez de perder lote). **Não há corrupção** (atomicidade por grupo + idempotência por `url_fonte_original` + rollback de journal no crash), e o operador tem o aviso. O defeito é de **precisão**: um operator lê "NÃO foi registrada" como "nada foi escrito" e um painel de custo lê uma rodada como 0 itens. Já está registrado como follow-up na Iteração 8 (ponte 3), mas a redação do log e do comentário do código merecem acerto.
- **Sugestão:** (a) reescrever a mensagem para algo como "a rodada em curso foi ABORTADA no meio; grupos já confirmados permanecem e o registro da rodada fica incompleto" (uma linha); (b) se quiser o registro fiel, gravar no `RegistroExecucaoIngestao` um marcador de rodada abortada (ex.: `erros_por_fonte={'__abortada__': ...}`) antes do `os._exit` — opcional, o contrato trata persistir falha no banco como não-objetivo; (c) alternativa de política, se a perda da ronda for inaceitável em algum contexto: aumentar `ESPERA_PARADA_SEGUNDOS` acima da duração típica da rodada, ou fazer o 2º sinal só quando o processo estiver **no intervalo** entre rodadas.

### Finding 2 (novo) — a identidade do pid casa por substring e inclui processos que não são o agendador
- **Arquivo:** `subir-localhost.sh`
- **Linha:** 200-205
- **Categoria:** correctness
- **Severidade:** nit
- **Resumo:** `_pid_e_o_agendador` testa `case "$(_pid_args "$1")" in *agendar_ingestao*)`, o que casa qualquer processo cuja linha de comando **contenha** essa string — inclusive a suíte desta run.
- **Cenário de falha (medido):** um `python -m pytest catalogo_noticias/tests/test_command_agendar_ingestao.py` tem `ps -o args=` = `python -m pytest catalogo_noticias/tests/test_command_agendar_ingestao.py` e é classificado como "o agendador". Combinado com um pid file obsoleto + reciclagem de pid, o `--stop` manda SIGTERM na suíte de testes do desenvolvedor e o guard recusa subir ("já ativo") — exatamente a proteção que o Finding 6 pediu, com um furo. É estritamente **melhor** que o pré-remediação (que sinalizava qualquer pid do arquivo, sem checar nada), e o cenário exige a coincidência de recycling + nome de arquivo, então é nit.
- **Sugestão:** exigir os dois tokens na mesma linha de comando (`*manage.py*agendar_ingestao*` ou `*"manage.py agendar_ingestao"*) — uma linha, sem custo.

### Finding 3 (novo) — a confirmação do banner não reconfirma a vivacidade depois de encontrar a linha
- **Arquivo:** `subir-localhost.sh`
- **Linha:** 582-604
- **Categoria:** correctness
- **Severidade:** nit
- **Resumo:** `AGENDADOR_CONFIRMADO=1` é gravado assim que o banner aparece no log, sem um segundo `_pid_vivo` — o "OK … NO AR" pode ser impresso para um processo que morreu logo depois.
- **Cenário de falha:** o agendador loga o banner e entra na 1ª rodada; o banco está travado (`database is locked`) e o processo morre ~1ms depois. O `for` já achou a linha e sai com `AGENDADOR_CONFIRMADO=1` → `AGENDADOR_FALHOU=0` → a linha `OK agendador de ingestão NO AR (pid N) — primeira rodada iniciada` anuncia como no ar um processo morto. O banner final (626) cai no ramo "NÃO confirmado como vivo; confira o log", o que atenua; e a próxima execução do script limpa o pid órfão. Janela de milissegundos.
- **Sugestão:** um `_pid_vivo` no `if [ "$AGENDADOR_CONFIRMADO" = "1" ]` antes do `ok` (uma linha). Nota conexa: a afirmação da Iteração 8 (d)(iii) — "a seção crítica é curta (a verificação 'subiu?' fica fora do lock)" — está **errada**: o loop de verificação está **dentro** da seção crítica (o `destravarlock_agendador` só é chamado em 606, depois dele); o efeito prático é benigno e o fallback de lock ocupado avisa corretamente (medido em R1/R2), mas o comentário deve ser corrigido para quem mexer no lock depois. **Acoplamento relacionado:** o `grep -F "Agendador de ingestão iniciado"` amarra o script a uma string exata do log Python; se ela for reescrita, todo `./subir-localhost.sh` passa a acusar "NÃO subiu" mesmo com o agendador no ar — direção de falha segura (aviso, não falso sucesso), mas silenciosa.

## Findings da 1ª passada — status (6 resolvidos, 2 enhancements fora do escopo)
| # | Sev. | Assunto | Status | Como confirmei |
|---|---|---|---|---|
| 1 | major | janela para 2ª instância | **RESOLVIDO** (a,b,c,d) | R1/R2 (com e sem `flock`): start durante a espera do `--stop` → "já ativo", 1 instância. T1-T3 com observador: 0 violações do estado proibido em 364 amostras. Escalonamento: T2 (log com as duas mensagens) e teste de subprocesso real (`returncode == 143`, <10s). Identidade: T5 (processo alheio sobrevive, aviso com a linha de comando real). `flock`: filho não herda (sem fd 9), mesmo arquivo nos dois blocos, R3 → 1 instância. |
| 2 | major | falha do agendador invisível | **RESOLVIDO** (a,b) | Banner: S1-S5 (inclui o caso real da Iteração 5 e o log com histórico de execução anterior → `AGENDADOR_FALHOU=1` + traceback + banner "ATENÇÃO"). Contador: 2 testes (alerta na 3ª falha; reset no padrão F F S F F) + semântica de "falha" em `ingestao.py` (erro de fonte e de provider **não** contam). |
| 3 | minor | log de sucesso fora do try | **RESOLVIDO** | `logger.info` de sucesso agora dentro do `try` (linha 190) e o `test_falha_no_log_de_sucesso_nao_mata_o_loop` passa (não-vacuoso por construção). Resíduo teórico **pré-existente** e não coberto: `close_old_connections()` no `finally` continua fora de qualquer `except` — no caminho normal do Django ele não levanta (`close_if_unusable_or_obsolete`/`close` engole a exceção), então não é finding. |
| 4 | minor | pré-filtro 0,63× quando não poda nada | **NÃO TRATADO — enhancement fora do escopo** (decisão do orchestrator) | `deduplicacao.py` intocado; o próprio finding dizia "nenhuma correção necessária, registrar o número" (números registrados na Iteração 8). Custo absoluto irrisório (49 ms) contra 8,6-10,3× no caso de ganho. Fora do escopo desta revisão: tocar o dedup seria risco sem ganho, e o run-state já o registra como follow-up. |
| 5 | minor | `>` truncava o log | **RESOLVIDO** | `>>` na linha 574. S5 provou o efeito (o histórico de 160 bytes sobreviveu e o offset leu só a região nova); produção: 317 → 320 linhas no restart da Iteração 8. |
| 6 | nit | pid file sem validar identidade | **RESOLVIDO** (com o nit 2 acima) | `_pid_e_o_agendador` por `ps -p -o args=`, usado no guard e no `--stop`; T5 provou que nenhum sinal vai para processo alheio e que o pid reciclado é tratado como órfão. |
| 7 | nit | assinatura entrelaçada de `_bound_similaridade` | **NÃO TRATADO — enhancement fora do escopo** (decisão do orchestrator) | É a função de segurança do diff inteiro e está provadamente correta (1ª passada); mexer agora seria risco sem ganho de comportamento. Follow-up mecânico já registrado no run-state. |
| 8 | nit | validação assimétrica de `--rodadas` | **RESOLVIDO** | `CommandError` para negativo + `WARNING` explícito para 0, com 2 testes novos passando; ajuda de `--rodadas` atualizada. |

## Resumo quantitativo (final)
| Severidade | Quantidade |
|---|---|
| blocker | 0 |
| major | 0 |
| minor | 1 (nova) + 3 resolvidos (3, 4-não-tratado, 5) → **1 minor em aberto** |
| nit | 3 (novas) + 1 não tratado (7) → **3 nit em aberto** |

- Findings da 1ª passada: 8 (2 major, 3 minor, 3 nit) → **6 corrigidos**, **2 deliberadamente não tratados** (4 e 7) como enhancements fora do escopo, ambos com o motivo registrado e sem risco de comportamento.
- Findings da 2ª passada: **4** (0 blocker, 0 major, 1 minor, 3 nit).
- **Em aberto no fechamento: 1 minor + 3 nit** — nenhum bloqueia a entrega.

## Veredito
**approve_with_comments**

Os dois **major** que motivaram `changes_requested` estão **comprovadamente resolvidos** por medição independente, não por leitura: a janela de segunda instância está fechada nos dois eixos (espera antes de remover o pid file + escalonamento + identidade + `flock`), com 0 amostras do estado proibido em 364 observações e 1 instância em todos os replays, com e sem `flock`; e a falha invisível está fechada nos dois pontos (banner verificável com `AGENDADOR_FALHOU=1` reprovando até o caso com log de execução anterior, e alerta em ERROR a partir de 3 falhas consecutivas com reset correto). Nenhum dos 10 critérios de aceite regrediu (177 testes verdes, `CELERY_BEAT_SCHEDULE` byte-idêntico, bloco do agendador ainda só no modo nativo, dedup intocado, agendador real com 2 rodadas do código novo). Restam 1 **minor** e 3 **nit** — todos de precisão de mensagem/política ou de refino, nenhum com caminho de corrupção ou de comportamento incorreto: a justificativa do `os._exit` superestima a atomicidade por rodada (a persistência é por grupo), a identidade do pid casa por substring, a confirmação do banner não reconfere a vivacidade e o comentário sobre o lock está desatualizado. Veredito **`approve_with_comments`** (não `approve` porque o Finding 1 novo é uma imprecisão real em mensagem de operador e em comentário de código, e vale acerto antes de fechar a documentação), sem necessidade de uma terceira rodada de remediação.
