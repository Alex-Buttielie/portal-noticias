# Documentation Update — 20260923-0943-p0-correcoes-criticas

Documenter (run 20260923-0943-p0-correcoes-criticas). Escopo: consistência da
documentação com o implementado pelo executor (Parte A: default
`CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS` 0.15 → 0.0003; Parte B: remoção
do `headers()` do root layout). Sem commit; sem testes; nenhum `.py`/`.tsx`
alterado — só `.md`.

## Documentos verificados

- `backend/.env.example` (linhas 124-129)
- `README.md` (seção "Teto de gasto diário com o provedor de LLM", linhas 212-221)
- `ARCHITECTURE.md` (§7 "Custo de IA controlado", §8 item 3, §9.3 linha "Custo", §10)
- `frontend/app/admin/robos/page.tsx` (linha 405)
- `frontend/.env.local.example` (sem referências a preço de LLM)
- `agentic-framework/specs/` (`ingestao-curadoria-noticias.md`,
  `painel-metricas-negocio.md` — só menções conceituais, sem valor)
- `ANALISE_CUSTO_PERFORMANCE.md` (§2 A1 — relatório diagnóstico pré-fix)

## Alterações aplicadas

1. `README.md:221` (novo, seção "Teto de gasto diário com o provedor de LLM") —
   antes: nada (o executor atualizou o default para `0.0003` mas não cobriu o
   aviso operacional do follow-up) → depois: bloco `> **Nota operacional:**`
   de 2 linhas: instalações com linha `ConfiguracaoRobo` já persistida no banco
   mantêm `llm_preco_por_1k_tokens = 0.15` até ajuste manual via tela admin de
   robôs; o default novo (`0.0003`) só vale para instalações sem override no
   banco.

Nenhuma outra alteração foi necessária: todo o restante já estava consistente
com o implementado (ver itens confirmados abaixo).

## Itens confirmados (já consistentes, sem edição)

- `backend/.env.example:124-129` — já documenta
  `CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS=0.0003` com derivação. O
  `$0.15/1M` na linha 126 é componente da derivação (preço de entrada por
  milhão), não o valor antigo — correto como está.
- `README.md:216` — já traz padrão `0.0003` com derivação resumida + volume
  (~16M tokens/dia com teto de $5). O `$0.15/1M` no mesmo parágrafo é
  componente da derivação — correto.
- `ARCHITECTURE.md` §7 (linha 78) — cita
  `CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS` **sem nenhum valor
  numérico** ("tokens × preço configurável"); §8 item 3 e §9.3 também não
  citam valor. Continua preciso após a mudança — nenhuma edição.
- `frontend/app/admin/robos/page.tsx:405` — dica de exemplo já atualizada pelo
  executor (`Ex: 0.0003.`).
- `frontend/.env.local.example` — nenhuma referência a preço de LLM (só URLs).
- `agentic-framework/specs/` — `ingestao-curadoria-noticias.md:4,22` e
  `painel-metricas-negocio.md:13,21` mencionam custo de IA em nível conceitual,
  sem fixar nenhum valor — nenhuma edição.

## Intencionalmente NÃO alterados + motivo

- `ANALISE_CUSTO_PERFORMANCE.md:41-46` (`0.15` como default + comentário
  "incorreto por 3 ordens de magnitude") — é o **relatório diagnóstico
  pré-fix** que motivou esta run; descreve o estado encontrado, não o estado
  atual. Reescrevê-lo apagaria o registro do achado. Fora da lista de escopo
  da tarefa.
- `ingestao-service/` (`app/config.py:40`, `app/schemas.py:96`,
  `app/pipeline/summarizer.py:149`, `.env.example:12`, `README.md:37`,
  `tests/test_pipeline.py:36,252` — todos com `0.15`) — fora do escopo
  (microserviço desligado por padrão; contrato limitava o grep a `backend/`);
  executor já registrou como follow-up para run dedicada. Não mexido.
- `backend/catalogo_noticias/models.py:195` (`default=0.15`) +
  `migrations/0003_*` — código-fonte/schema, fora do meu escopo (só
  `.md`/`.example`); contrato veda mudança de schema. O aviso operacional do
  README (item 1 acima) cobre a consequência para o operador.
- `0.15` como peso de dedup (`backend/.../deduplicacao.py:89,122`,
  `ingestao-service/.../dedup.py`), `0.15rem` em `README.md:328`/CSS,
  `0.15` em `frontend/lib/editorial.ts:238,242`, `rgba(...,0.15)` em
  `frontend/app/planos/page.tsx:118` — parâmetros não relacionados a preço de
  LLM. Não mexidos.
- `agentic-framework/state/run-*/` históricos (ex.: run 20260903-1211, que
  documenta o default `0.15` da época) — histórico de execução imutável, não
  documentação viva. Não mexidos.
- Parte B (ISR): nenhuma doc viva descrevia o `headers()` no root layout ou
  prometia prerenderização afetada por ele; `ARCHITECTURE.md` não trata de
  estratégia de renderização do frontend — nenhuma atualização de docs
  exigida por essa parte.
