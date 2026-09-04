# Report — 20260902-1506-comunidade-blog

## Metadados
- **run_id:** 20260902-1506-comunidade-blog
- **Período:** 2026-09-02 15:06 → 2026-09-04 (fechamento após remediação de blocker)
- **Tarefa:** Comunidade e Blog
- **Resultado final:** entregue

## Resumo executivo
App `comunidade`: publicações de autores credenciados, comentários, seguir autores, perfis públicos, destaques editoriais. Uma revisão de segurança dedicada encontrou um **blocker real de PII**: os endpoints públicos (`AllowAny`, sem autenticação) de listagem de publicações e comentários expunham o e-mail real do autor/comentarista — e o frontend chegava a exibir esse e-mail publicamente como se fosse o "nome" da pessoa em `/comunidade` e `/comunidade/[id]`. Qualquer visitante anônimo conseguia coletar uma lista de e-mails de usuários reais só varrendo esses dois endpoints. Corrigido: o campo passou a ser `autor_nome` (mesmo campo já usado publicamente em outros lugares do sistema), no backend e no frontend, com um teste de regressão dedicado.

## Métricas
| Métrica | Valor |
|---|---|
| Iterações (implementação ↔ revisão/remediação) | 1 |
| Findings de revisão — abertos | 0 |
| Findings de revisão — resolvidos | 1 (blocker) |
| Arquivos alterados | comunidade/serializers.py, comunidade/views.py, comunidade/models.py, frontend/lib/api.ts, frontend/app/comunidade/page.tsx, frontend/app/comunidade/[id]/page.tsx |
| Testes adicionados | 1 (`test_listagem_publica_nao_expoe_email_do_autor`) |
| Veredito final do tester | passed (257/257) |
| Veredito final do reviewer | blocked → approve após remediação |

## Linha do tempo resumida
- 2026-09-02 15:06–15:10 — implementação (7/7 critérios).
- 2026-09-04 — revisão de segurança dedicada encontra o vazamento de e-mail.
- 2026-09-04 — remediação (backend + frontend) e teste de regressão; suíte completa validada (257 passed).

## Desvios do plano original
Nenhum desvio de escopo de produto.

## Follow-ups / pendências
- Fluxo de aprovação editorial humana antes de publicar (além do credenciamento) é uma extensão futura possível, não implementada.
- Paginação ainda ausente nas listagens públicas — achado minor da revisão, não corrigido nesta passada para não arriscar quebrar o contrato de resposta hoje consumido pelo frontend sem revisar todos os consumidores primeiro.

## Artefatos desta execução
- task-plan.md
- implementation-contract.md
- implementation-history.md
