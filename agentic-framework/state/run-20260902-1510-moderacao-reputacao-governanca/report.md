# Report — 20260902-1510-moderacao-reputacao-governanca

## Metadados
- **run_id:** 20260902-1510-moderacao-reputacao-governanca
- **Período:** 2026-09-02 15:10 → 2026-09-04 (fechamento após remediação de blocker)
- **Tarefa:** Moderação, Reputação e Governança Editorial
- **Resultado final:** entregue

## Resumo executivo
App `moderacao`: denúncia, fila, ações de moderação, canal de recurso, reputação, política editorial pública. Uma revisão de segurança dedicada (gatilho obrigatório por BRD §16) encontrou um **blocker real**: a ação "remoção de conteúdo" só descontava reputação do autor — o comentário/publicação denunciado continuava 100% visível ao público, mesmo depois de um moderador confirmar a denúncia e aplicar a ação. Corrigido nesta run: conteúdo denunciado e removido agora sai de fato das listagens públicas (sem apagamento — auditável e visível ao próprio autor, conforme BRD §16 "não apagar silenciosamente"). Dois findings minor também corrigidos: a fila de moderação agora prioriza de verdade por reputação do denunciante (era FIFO, contrariando o próprio docstring), e denúncias agora têm rate limit por usuário.

## Métricas
| Métrica | Valor |
|---|---|
| Iterações (implementação ↔ revisão/remediação) | 1 |
| Findings de revisão — abertos | 0 |
| Findings de revisão — resolvidos | 3 (1 blocker, 2 minor) |
| Arquivos alterados | comunidade/models.py, comunidade/views.py, moderacao/services.py, config/throttling.py, config/settings.py + migration comunidade 0003 |
| Testes adicionados | 1 (regressão de e-mail, no mesmo lote de comunidade) |
| Veredito final do tester | passed (257/257) |
| Veredito final do reviewer | blocked → approve após remediação |

## Linha do tempo resumida
- 2026-09-02 15:10–15:14 — implementação (7/7 critérios).
- 2026-09-04 — revisão de segurança dedicada encontra o blocker de conteúdo não removido.
- 2026-09-04 — remediação: campo `oculto` em Comentario/Publicacao, `aplicar_acao` passa a ocultar de fato via `denuncia.alvo`, fila prioriza por reputação, throttle em denúncia.
- 2026-09-04 — suíte completa validada (257 passed), fechamento formal.

## Desvios do plano original
Nenhum desvio de escopo de produto — a correção foi de um gap de implementação, não uma mudança de requisito.

## Follow-ups / pendências
- Papel de "moderador" dedicado não existe — moderação usa `papel=admin` como simplificação.
- Fórmula/pesos de reputação são valores de referência, a calibrar com produto/operação.
- `TIPO_BLOQUEIO_PERMANENTE` não oculta retroativamente todo o histórico do usuário bloqueado, só o item vinculado à denúncia que originou a ação — decisão de escopo, revisitar se o produto quiser algo mais amplo.

## Artefatos desta execução
- task-plan.md
- implementation-contract.md
- implementation-history.md
