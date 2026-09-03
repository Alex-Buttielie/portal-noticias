# Implementation History — 20260902-1600-frontend-radar-newsletter-landing

## Iteração 1 — 2026-09-02 — orchestrator agindo como executor

`lib/api.ts` estendido (na virada da execução anterior) com tipos/funções de `radar` (`AssuntoEmAlta`, `RadarTendencias`, `RadarEvolucao`, `LocalidadeSalva`, `obterTendenciasRadar`, `obterEvolucaoRadar`, `obterLocalidadesSalvas`, `salvarLocalidade`, `removerLocalidade`), `newsletter` (`TipoNewsletter`, `inscreverNewsletter`, `cancelarNewsletter`) e `landing` (`inscreverListaEspera`). Todos os tipos foram conferidos campo-a-campo contra `radar/views.py`+`services.py`, `newsletter/views.py`+`models.py` e `landing` serializers antes de escrever as páginas.

Páginas/seções novas:
- `frontend/app/radar/page.tsx` — filtro país/estado/cidade, lista de assuntos em alta com aviso de metodologia, botão "Ver evolução" visível só a `usuario.papel === "premium"` (Free vê aviso textual em vez de botão — evita a chamada ao endpoint gated na UI, embora o gate real seja sempre no backend), botão "Salvar localidade".
- `frontend/app/minha-conta/page.tsx` — nova seção "Newsletter" (select de tipo padrão/categoria/personalizada — personalizada só listada para Premium — mais campo de categorias e botões inscrever/cancelar). Reaproveita o padrão visual das seções "Assinatura"/"Histórico" já existentes na mesma página.
- `frontend/app/lista-de-espera/page.tsx` — página pública nova: bloco curto de proposta de valor + "como funciona" (3 passos, conforme Requisito Funcional 1 da spec) + formulário completo (nome, e-mail, interesses, localidade, canal preferido, aceite de comunicação obrigatório antes de enviar). Fecha o Critério de aceite 5 deixado pendente em `run-20260902-1517-landing-lista-espera/implementation-history.md`.
- `frontend/components/Header.tsx` — link `/radar` adicionado à navegação principal.

**Status:** 5/5 critérios de aceite implementados. Validação: não realizada — mesma limitação de sessão (ferramentas de execução com o classificador de segurança indisponível desde o meio da remediação de `ingestao-noticias`; nunca recuperou até este ponto). Revisão manual: tipos TS conferidos linha a linha contra `lib/api.ts`; assinaturas de função (`obterEvolucaoRadar` é GET com querystring, não POST) conferidas antes do uso.

**Arquivos:** `frontend/app/radar/page.tsx` (novo), `frontend/app/lista-de-espera/page.tsx` (novo), `frontend/app/minha-conta/page.tsx` (modificado — seção Newsletter), `frontend/components/Header.tsx` (modificado — link Radar).

**Follow-up:** frontend de `b2b/` (dashboard de organização) e `metricas/` (painel admin) ainda não existe — é a última lacuna de frontend do MVP+Premium completo. `lib/api.ts` ainda não tem funções para esses dois módulos.
