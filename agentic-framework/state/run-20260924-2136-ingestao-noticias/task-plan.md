# Task Plan — 20260924-2136-ingestao-noticias

## Metadados
- **run_id:** 20260924-2136-ingestao-noticias
- **Data de abertura:** 2026-09-24 21:39 (-03:00)
- **Solicitado por:** humano (Alex) via conversa OpenCode
- **Spec de origem:** N/A — pedido direto de correção de bug (sem spec/BRD específica; comportamento esperado deriva do desenho existente do sistema)

## Diagnóstico (evidências coletadas na fase de planning)
- A ingestão de notícias é agendada via **Celery beat** (`config/settings.py`, `CELERY_BEAT_SCHEDULE`, task `catalogo_noticias.tasks.ingerir_noticias`, a cada `CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS` = 15 min) e executada por um **worker Celery**.
- O ambiente atual roda **nativo** (`subir-localhost.sh` modo nativo: venv + sqlite + locmem), que sobe apenas `runserver` (backend) e `next dev` (frontend) — **nunca inicia celery-worker, celery-beat ou Redis**. Confirmado: nenhum processo celery/redis existe (`ps aux`), e `redis-server`/`redis-cli` não estão instalados.
- Resultado: a task agendada simplesmente **nunca executa** — nada falha, nada loga erro (por isso "sem erros na tela"). Última execução registrada em `RegistroExecucaoIngestao`: **2026-09-21 23:18** (disparo manual durante testes).
- O pipeline em si está saudável: a execução de 2026-09-21 23:17 ingeriu 175 itens de 3 fontes (G1, UOL, CNN). A execução de 23:18 (0 itens, sem erros de fonte) foi deduplicação esperada 31s depois (janela de 24h).
- O disparo manual via `POST /api/admin/robos/executar/` funciona sem Celery (thread daemon). O provider de sumarização tem fallback local quando `CATALOGO_NOTICIAS_LLM_API_KEY` está vazia (estado atual do `.env`) — a ingestão funciona sem a chave.

## Objetivo
A ingestão de notícias volta a rodar periodicamente no ambiente atual (modo nativo), sem Celery/Redis e sem intervenção manual, reutilizando o pipeline existente sem alterá-lo; o agendador sobrevive a reinícios do ambiente via `subir-localhost.sh`, e há evidência verificável de ingestão fresca (novos `NewsItem` + registros de execução atuais).

## Escopo
### Dentro do escopo
- Novo management command `agendar_ingestao` em `catalogo_noticias`: loop de agendamento sem broker que chama `executar_ingestao()` a cada intervalo configurado, com a primeira rodada imediata no início, falha de rodada isolada (não derruba o loop) e parâmetros de teste (`--intervalo-segundos`, `--rodadas`).
- Integração no `subir-localhost.sh` (modo nativo): inicia o agendador em background (log + pid file dedicados) e o encerra no `--stop`.
- Execução imediata na sessão atual: rodar uma ingestão agora (restaura conteúdo fresco) e deixar o agendador ativo.

### Fora do escopo (explicitamente)
- Migrar o disparo manual (thread daemon em `robos_views.py`) para Celery.
- Agendar as demais tasks do beat (newsletter, vencimentos de assinatura, alertas B2B) em dev — fica como follow-up.
- Popular `FonteRobo` com todas as ~20 fontes de `settings.CATALOGO_NOTICIAS_FONTES_RSS` (hoje só 3 seedadas são usadas).
- Persistir falha de ingestão no banco (backlog já documentado em `robos_views.py`).
- Qualquer mudança no pipeline de ingestão em si (busca, dedup, resumo, fila de revisão).
- Configurar Redis/Celery no modo nativo.

## Suposições assumidas
- A ingestão deve funcionar no **ambiente nativo atual** (não só no modo docker) — motivo: o sintoma foi reportado no ambiente rodando nativamente; produção docker já tem celery-beat/worker/redis.

## Restrições
- **Sem novas dependências**: nenhum Redis, nenhum pacote novo.
- **Produção intocada**: no modo docker, celery-beat permanece o único agendador; o agendador novo é opt-in (não ligado ao startup do Django, não iniciado pelo docker-compose).
- Nenhuma mudança de contrato de API HTTP, schema de banco ou dados expostos.
- Compatibilidade: o comando deve respeitar `CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS` (configurável sem código).

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | código + implementation-history.md |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked |
| 3 | reviewer (à critério do orchestrator — subsistema de ingestão) | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. Com o agendador ativo, uma rodada de ingestão executa automaticamente a cada intervalo configurado (15 min por padrão), sem intervenção manual e sem Celery/Redis.
2. Novas notícias dos feeds configurados aparecem em `catalogo_noticias_newsitem` com `timestamp_ingestao` recente, e `RegistroExecucaoIngestao` registra as rodadas.
3. Uma falha em uma rodada (ex: fonte indisponível, erro de rede) não derruba o agendador — a próxima rodada acontece.
4. `./subir-localhost.sh` (nativo) sobe o agendador junto com backend/frontend; `--stop` o encerra.
5. No modo docker/produção, o comportamento não muda: celery-beat continua o agendador da ingestão.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Duas instâncias do agendador simultâneas (reinício sem `--stop`) → ingestões concorrentes | médio | Pipeline idempotente (constraint única de `url_fonte_original`, dedup 24h, grupos transacionais) + pid file + checagem de processo já ativo no script |
| Rodada do agendador concorrente com disparo manual (endpoint) | médio | Mesma idempotência do pipeline (defesa já existente); sem mudança necessária |
| Sem `CATALOGO_NOTICIAS_LLM_API_KEY`, resumo cai no fallback local | baixo | Comportamento já existente e documentado; ingestão continua funcionando |
| Feeds RSS externos indisponíveis/anti-bot | baixo | Erros por fonte já isolados e registrados pelo pipeline; rodada seguinte tenta de novo |

## Dependências
- Nenhuma bloqueante. Feeds RSS públicos externos devem responder (G1, UOL, CNN hoje).
