# Implementation Contract — 20260924-2136-ingestao-noticias

## Metadados
- **run_id:** 20260924-2136-ingestao-noticias
- **Deriva de:** task-plan.md (20260924-2136-ingestao-noticias)
- **Versão do contrato:** 2 (escopo expandido na Iteração 2 — ver seção "Versão 2 — expansão de escopo" no fim; mudança NÃO silenciosa, justificada por finding novo que bloqueia o objetivo)

## O que deve ser construído
1. **Management command `agendar_ingestao`** em `backend/catalogo_noticias/management/commands/agendar_ingestao.py`: loop de agendamento sem Celery/Redis que executa `executar_ingestao()` periodicamente.
   - Primeira rodada **imediata** ao iniciar; rodadas seguintes a cada intervalo.
   - Intervalo: `CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS * 60` segundos por padrão, sobrescrevível por `--intervalo-segundos N` (para testes/uso avançado).
   - `--rodadas N` limita o número de rodadas (padrão: infinitas) — necessário para testes e para execução única.
   - Isolamento de falha: exceção em uma rodada é logada com traceback (`logger.exception`) e o loop segue para a próxima — nunca mata o processo.
   - `django.db.close_old_connections()` no início e fim de cada rodada (mesmo padrão de `_executar_ingestao_em_background` em `robos_views.py`).
   - Logging claro de início/fim de rodada com `registro.id`, itens ingeridos e erros de fonte (mesmo estilo de `catalogo_noticias/tasks.py`).
   - Encerramento gracioso em SIGINT/SIGTERM (parar de agendar e sair).
   - Deve reutilizar `executar_ingestao()` de `catalogo_noticias/services/ingestao.py` — **sem duplicar lógica de pipeline**.
2. **Integração no `subir-localhost.sh` (modo nativo):**
   - Antes de subir backend/frontend (ou junto), inicia o agendador em background: `nohup "$VENV_PY" "$BACKEND_DIR/manage.py" agendar_ingestao >/tmp/brd-agendador.log 2>&1 &` com pid file `/tmp/brd-agendador.pid`.
   - Não inicia se já houver um agendador ativo (checar pid file + `kill -0`, matando pid órfão se necessário — mesmo padrão do `--stop` existente).
   - `--stop` também encerra o agendador (pid file `/tmp/brd-agendador.pid`).
   - Atualizar mensagens de uso/`--help`/banner final para mencionar o agendador e seu log.
3. **Execução imediata na sessão atual** (passo operacional do executor, documentado no implementation-history): rodar uma ingestão agora via `manage.py ingerir_noticias` (venv do projeto) e iniciar o agendador em background na sessão atual, deixando a ingestão funcionando de imediato.

## Áreas/arquivos esperados
- `backend/catalogo_noticias/management/commands/agendar_ingestao.py` (novo)
- `subir-localhost.sh` (edição)
- `backend/catalogo_noticias/tests/test_command_agendar_ingestao.py` (novo, para o tester)
- Qualquer mudança fora daqui deve ser justificada no implementation-history.md.

## Interfaces afetadas
- Nenhuma API HTTP, nenhum schema de banco, nenhum contrato de dados.
- Nova interface de CLI interna (management command) — não consumida por outros sistemas.

## Critérios de aceite (técnicos, testáveis)
1. Dado o comando `agendar_ingestao --rodadas 1`, quando executado, então `executar_ingestao()` é chamada exatamente uma vez, o início/fim da rodada é logado e o processo sai com código 0.
2. Dado que `executar_ingestao()` levanta exceção na primeira rodada, quando o comando roda com `--rodadas 2`, então a exceção é logada (traceback), o loop não morre e a segunda rodada executa.
3. Dado `--intervalo-segundos 1` e `--rodadas 2`, quando o comando roda, então a segunda rodada acontece após ~1s (não 15 min) — o intervalo configurado é respeitado.
4. Dado o padrão sem flags, quando o intervalo é lido, então vem de `CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS * 60` (15 min por padrão).
5. Dado SIGTERM/SIGINT durante o loop, quando recebido, então o processo para de agendar e sai sem traceback não tratado.
6. Dado o `subir-localhost.sh` modo nativo, quando executado com o agendador já ativo, então uma segunda instância NÃO é iniciada; e `--stop` finaliza o processo do agendador (validação via bash, sem pytest).
7. Dado o código final, quando inspecionado, então nenhuma mudança afeta o comportamento de `CELERY_BEAT_SCHEDULE`/docker-compose (o agendador é opt-in, não iniciado pelo startup do Django nem pelo docker).

## Não-objetivos
- Migrar o disparo manual (thread) para Celery.
- Agendar newsletter/vencimentos/alertas B2B em dev.
- Popular `FonteRobo` com todas as fontes do settings.
- Persistir falha de ingestão no banco.
- Alterar o pipeline de ingestão (busca/dedup/resumo/fila de revisão).
- Configurar Redis/Celery no modo nativo ou alterar docker-compose.

## Restrições técnicas
- **Performance:** loop dorme entre rodadas (sem polling agressivo); nenhuma consulta desnecessária fora das rodadas.
- **Segurança/privacidade:** N/A — comando local sem dados pessoais; sem novas superfícies de rede.
- **Dependências permitidas:** nenhuma biblioteca nova (stdlib + Django + pipeline existente).
- **Estilo/convenções:** seguir o padrão dos commands existentes (`ingerir_noticias`, `criar_usuario_carga`): docstrings em pt-BR com referências ao framework, logging em pt-BR, `close_old_connections()` por rodada.

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Testes escritos e passando (tester)
- [ ] Revisão de código aprovada (reviewer — incluída à critério do orchestrator)
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente
- [ ] Ingestão funcionando de fato no ambiente atual (execução fresca + agendador ativo)

---

## Versão 2 — expansão de escopo (Iteração 2, 2026-09-25)

**Justificativa (finding novo, bloqueia o objetivo do contrato):** durante a execução operacional descobriu-se que uma rodada de ingestão NUNCA completa no ambiente atual: o disparo manual de 23:57 de 24/09 está há 7h37m (1h19m de CPU) sem concluir; as duas threads de disparo manual de 21:09 de 24/09 estão há 10h+ sem completar nem logar falha (0 conclusões em todo o log do backend). Causa raiz: `agrupar_itens_brutos` (`catalogo_noticias/services/deduplicacao.py`) é O(n²) sobre o lote (`itens_para_agrupar` = itens novos + persistidos recentes, `ingestao.py` linhas 809-821), com comparacão caríssima por par (pareamento fuzzy de tokens via SequenceMatcher, cache `_CACHE_FUZZY_RATIO` que se LIMPA inteiro a cada 8000 entradas — thrash). Com o backlog de 3 dias × 91 fontes (milhares de itens no lote), a rodada leva horas. Em 21/09 as rodadas eram rápidas (~31s) porque o conjunto novo era pequeno (175 itens). Sem esta correção, o objetivo ("ingestão funcionando corretamente") não é atendido: a rodada nunca termina e o registro nunca é gravado.

### O que deve ser construído (v2)
1. **Otimização de performance em `catalogo_noticias/services/deduplicacao.py`, comportamento-PRESERVANDO** (mesmos grupos de saída para qualquer entrada):
   - **Pré-filtro por limite superior (upper bound) exato** na comparação (item, membro de grupo) e (item, grupo): antes de calcular `_similaridade_ponderada` (caro), calcular um limite superior barato do score possível (peso máximo de interseção por tokens exatamente comuns + limite do acréscimo fuzzy ≤ min(Σ pesos dos tokens restantes de cada lado) — cada par fuzzy consome um token de cada lado e contribui ≤ max(w_a, w_b); o executor deve garantir que o bound é UM VERDADEIRO limite superior, nunca inferior). Se o upper bound < limiar, pular a comparação cara — o resultado é garantidamente idêntico (score impossível de atingir o limiar).
   - **Cache LRU real** para `_CACHE_FUZZY_RATIO` (substituir o clear-total a cada 8000 entradas por LRU com capacidade fixa — `functools.lru_cache` com maxsize ou OrderedDict): mesmos valores, retenção melhor, sem thrash.
   - **Pré-cálculo de somas de peso e uniões de tokens por item/grupo** (evitar recomputação O(n) repetida dentro do loop).
   - NÃO mudar a semântica de similaridade, limiares, ponderação ou agrupamento single-linkage — os testes existentes (calibração Finding 2/3 em `test_acceptance_criteria.py`) são a régua.
2. **Benchmark antes/depois** (evidência): gerar um lote sintético realista (≥ 3000 itens com títulos jornalísticos variados, algumas duplicatas) e medir o tempo de `agrupar_itens_brutos` com a implementação antiga vs nova. Target: de horas → minutos (redução de pelo menos 10x).
3. **Operacional:** encerrar o processo de ingestão travado (pid 73054 — carrega o código antigo em memória; mantê-lo vivo desperdiça CPU e ele nunca concluirá), iniciar o agendador com o código novo, e verificar que uma rodada fresca completa em tempo razoável e cria registro em `RegistroExecucaoIngestao`. Observação: o servidor roda COM autoreload (pids 29876/29914, sem --noreload) — editar arquivo de backend recarrega o servidor e mata as threads daemon travadas de 21/09 automaticamente; NÃO reiniciar o servidor manualmente.

### Critérios de aceite adicionais (v2, testáveis)
8. Dado um lote sintético de ≥ 3000 itens, quando `agrupar_itens_brutos` (nova) roda, então conclui em menos de 60s (benchmark registrado com números antes/depois).
9. Dado qualquer entrada, quando a nova implementação roda, então os grupos de saída são IDÊNTICOS aos da implementação antiga (teste de equivalência: tester compara as duas implementações no conjunto de testes existente e em lotes aleatórios).
10. Dado o processo travado (pid 73054), quando encerrado e o agendador iniciado com o código novo, então uma rodada completa criando registro em `RegistroExecucaoIngestao` (evidência no banco).

### Não-objetivos adicionais (v2)
- Mudar a semântica de similaridade/dedup (limiares, pesos, algoritmo de agrupamento).
- Dedup semântica via embeddings (upgrade futuro já registrado).
- Otimizar `ingestao.py` linha 296 (`SequenceMatcher` resumo vs bruto por item): com o fallback local (resumo ~100 chars) o custo por item é baixo — analisado e excluído.
- Paralelizar/mudar o fetch (já é paralelo, 8 workers).

### Critérios 1-7 da versão 1
Permanecem válidos e exigidos (ver seção acima).
