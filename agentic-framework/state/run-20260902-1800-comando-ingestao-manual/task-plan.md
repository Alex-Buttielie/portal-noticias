# Task Plan — 20260902-1800-comando-ingestao-manual

Solicitado por: usuário ("preciso que os motores que vão monitorar as notícias na internet funcionem para que minha aplicação começa a ter dados para eu validar as funcionalidades"). Formato conciso — pedido operacional, não uma nova feature de negócio, mas expôs uma lacuna real de operação do pipeline já implementado.

## Contexto
A aplicação já está rodando localmente (backend + frontend, via `scripts/init-local.ps1`, validado pelo usuário em ambiente real pela primeira vez nesta sessão). O pipeline de ingestão (`catalogo_noticias/`, spec `agentic-framework/specs/ingestao-curadoria-noticias.md`) já estava implementado e coberto por testes, mas só era acionável via task Celery periódica (`tasks.ingerir_noticias`, `CELERY_BEAT_SCHEDULE`) — sem Redis/Celery rodando (nenhum dos dois faz parte do bootstrap padrão do `init-local.ps1`), não havia como o usuário disparar uma ingestão real para começar a validar o resto do sistema com dados de verdade.

## Lacuna encontrada e corrigida
Nenhum management command expunha `services.executar_ingestao()` para execução manual/síncrona. Adicionado `catalogo_noticias/management/commands/ingerir_noticias.py` — roda uma rodada do pipeline sob demanda (mesma função de serviço que a task Celery chama, sem duplicar lógica) e imprime um resumo legível (itens por fonte, grupos formados, erros de fonte, chamadas ao SummarizationProvider).

## Decisão de produto que o usuário precisa tomar (não é código)
Sem uma `CATALOGO_NOTICIAS_LLM_API_KEY` real (nenhum provedor de LLM tem credencial neste ambiente — questão em aberto documentada desde `ARCHITECTURE.md` seção 8 e a spec deste módulo), o `SummarizationProvider` falha para todo item, forçando `status_revisao=pendente` (nunca publicação automática) — os itens SÃO ingeridos de verdade (RSS real: G1, UOL, CNN Brasil, Folha) mas ficam invisíveis no feed público até aprovação manual no admin ou até uma chave real ser configurada. Documentado no README (nova seção "Como popular o feed com notícias reais") com os dois caminhos: (a) aprovar manualmente pela fila do admin para validar o resto do sistema já, ou (b) configurar uma chave real para validar o fluxo completo de resumo automático.

## Critérios de aceite
1. `python manage.py ingerir_noticias` roda uma ingestão real sem depender de Celery/Redis.
2. Saída do comando é legível e mostra: itens por fonte, grupos formados, erros de fonte, contagem de chamadas ao SummarizationProvider.
3. README documenta o comando, o efeito da ausência de `CATALOGO_NOTICIAS_LLM_API_KEY`, e como aprovar itens manualmente no admin como caminho alternativo imediato.
4. `scripts/init-local.ps1` aponta para o comando na mensagem final, já que é o próximo passo natural depois do bootstrap.
