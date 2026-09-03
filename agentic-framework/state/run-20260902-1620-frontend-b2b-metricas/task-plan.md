# Task Plan — 20260902-1620-frontend-b2b-metricas

Solicitado por: usuário (continuação de "aplique DDD... e siga na implementação do meu MVP", confirmada via AskUserQuestion: "Continuar implementando mais funcionalidades"). Formato conciso.

## Objetivo
Última lacuna de frontend do MVP+Premium completo: painel corporativo (B2B) e painel de métricas de negócio (admin). Com isso, todos os 13 módulos do BRD passam a ter alguma superfície web, mesmo que sem validação por execução real.

## Lacuna de backend encontrada e corrigida nesta execução
`b2b` tinha `services.adicionar_membro`/`remover_membro` prontos (Critério de aceite 2/6 da spec) mas nenhuma view/rota os expunha — sem isso, "convidar outros usuários da minha empresa" (história de usuário da spec) não tinha como acontecer pela UI. Adicionado:
- `MembrosView` (`GET/POST/DELETE /api/b2b/membros/`) em `b2b/views.py`, com `MembroOrganizacaoSerializer` novo em `b2b/serializers.py`.
- Guarda extra não coberta antes: usuário convidado que já pertence a outra organização agora recebe 409 em vez de estourar `IntegrityError` (constraint `OneToOneField` em `MembroOrganizacao.user`) — mesma classe de bug já visto antes nesta sessão (`GoogleLoginView`/e-mail duplicado), corrigida preventivamente aqui.
- 3 testes novos em `b2b/tests/test_sanity.py` (convite via API por admin, bloqueio para membro comum, conflito de usuário já vinculado a outra organização).

Nenhuma migração é necessária — nenhum campo de modelo mudou, só view/serializer novos sobre modelos já existentes.

## Escopo desta execução (frontend)
1. `frontend/lib/api.ts` — seções `b2b` (`CriterioMonitoramento`, `MembroOrganizacao`, `ItemMonitorado`, `ResumoExecutivo`, `obterCriteriosB2B`, `criarCriterioB2B`, `obterItensMonitoradosB2B`, `obterResumoExecutivoB2B`, `obterMembrosB2B`, `convidarMembroB2B`, `removerMembroB2B`) e `metricas` (`PainelMetricas`, `obterPainelMetricas`).
2. `frontend/app/empresa/page.tsx` — painel corporativo: resumo executivo, criação de critério de monitoramento, itens monitorados por critério, lista de membros + convite/remoção (só visível a quem é admin da própria organização, deduzido client-side a partir da lista de membros retornada).
3. `frontend/app/admin/metricas/page.tsx` — painel de métricas de negócio, filtro de período (7/30/90 dias), visível só a `usuario.papel === "admin"`.
4. `frontend/components/Header.tsx` — links "Empresa" (todo usuário autenticado — a própria página trata "não pertence a organização") e "Métricas" (só admin).

## Critérios de aceite
1. Usuário vinculado a uma organização acessa `/empresa` e vê o resumo executivo dos critérios monitorados.
2. Usuário cria um novo critério de monitoramento (empresa/concorrente/setor/palavra-chave) pela UI.
3. Admin da organização convida outro usuário (por e-mail já cadastrado no Portal) e remove um membro.
4. Usuário sem organização recebe mensagem clara em vez de erro travado.
5. Admin da plataforma acessa `/admin/metricas` e vê os indicadores agregados (cadastros, assinaturas ativas, conversão, receita, churn, organizações B2B ativas).

## Risco conhecido (mesma limitação de toda a sessão)
Ferramentas de execução (Bash rodando node/python/pytest, Agent, Browser) seguem indisponíveis por falha do classificador de segurança desde o meio da remediação de `ingestao-noticias`. Nada deste código — backend ou frontend — foi executado de fato nesta execução. Validação feita por leitura cuidadosa (endpoint por endpoint, tipo por tipo, contra o backend real).
