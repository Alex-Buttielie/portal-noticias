# Implementation History — 20260902-1800-comando-ingestao-manual

## Iteracao 1 — 2026-09-02 — orchestrator agindo como executor

Adicionado `backend/catalogo_noticias/management/commands/ingerir_noticias.py` (+ `management/__init__.py` e `management/commands/__init__.py`). Chama `services.executar_ingestao()` sem argumentos — mesma funcao que `tasks.ingerir_noticias` (Celery) usa em producao, nenhuma logica duplicada. Imprime um resumo legivel (itens por fonte, grupos formados, duplicatas agrupadas, chamadas ao SummarizationProvider, erros de fonte se houver) e um lembrete final sobre o efeito de nao ter `CATALOGO_NOTICIAS_LLM_API_KEY` configurada.

README.md ganhou a secao "Como popular o feed com noticias reais (ingestao)", explicando: como rodar o comando, por que sem uma chave real de LLM os itens ficam presos em `status_revisao=pendente` (nunca aparecem no feed publico, so na fila do admin), e como aprovar manualmente pela fila do admin como caminho alternativo imediato para validar o resto do sistema sem depender de uma credencial externa.

`scripts/init-local.ps1` ganhou uma linha na secao final ("Ambiente pronto") apontando para o comando.

**Validacao real desta vez:** diferente de quase todo o resto do projeto, esta mudanca PODE ser validada de verdade pelo proprio usuario, que agora tem um ambiente local funcional (confirmado nesta sessao: venv real com Django/DRF/Celery/etc. instalados, `manage.py migrate` rodou de verdade, `pip install` confirmou `django-cors-headers`/`python-dotenv` instalaveis). Nao rodei o comando eu mesmo (Bash/PowerShell do agente seguem bloqueados pelo classificador de seguranca), mas o pedido para o usuario rodar `manage.py ingerir_noticias` e testar contra os feeds RSS reais (G1/UOL/CNN Brasil/Folha) foi passado a ele.

**Status:** 4/4 criterios de aceite implementados. Pendente: usuario rodar o comando e confirmar o resultado (itens realmente aparecendo, com ou sem chave de LLM).

**Arquivos:** `backend/catalogo_noticias/management/commands/ingerir_noticias.py`, `backend/catalogo_noticias/management/__init__.py`, `backend/catalogo_noticias/management/commands/__init__.py` (novos); `README.md`, `scripts/init-local.ps1` (modificados).
