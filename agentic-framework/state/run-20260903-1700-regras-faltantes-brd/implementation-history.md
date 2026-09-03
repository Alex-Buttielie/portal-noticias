# Implementation History — 20260903-1700-regras-faltantes-brd

Solicitado por: usuário — "realize as regras no meu arquivo de requisitos... veja se todas as regras foram implementadas, as que não foram, organize um plano de análise e depois implementação... implemente as regras de negócio faltando".

## Método
Extraído o texto completo do `BRD_portal_noticias_versao_1.docx` (34 seções) e cruzada CADA seção com o código real (não com specs/memória) via leitura de models/services/views/frontend e greps direcionados. Identificados gaps reais, verificados um a um antes de implementar (evitando falsos positivos — ex.: "destaques editoriais" já tinha suporte no backend, só faltava a tela).

## Achados e implementações (todas validadas por pytest real após cada uma)

1. **BRD §18/§25 — Termos de Uso / Política Editorial**: páginas não existiam (`frontend/app/privacidade` era uma pasta vazia). Descoberto que outra sessão paralela já tinha construído Política de Privacidade e Preferências de Cookies como páginas estáticas — não duplicadas. Adicionado: `moderacao/migrations/0002_seed_paginas_legais.py` (seed de `PaginaEditorial` para `termos-de-uso` e `politica-editorial`, reaproveitando o modelo já existente e editável pelo admin), rota genérica `frontend/app/paginas/[slug]/page.tsx`, links no `Rodape.tsx` e na tela de cadastro.

2. **BRD §16 — bug real de governança**: `AcaoModeracao` registrava bloqueios temporário/permanente, mas nada impedia um usuário bloqueado de continuar publicando/comentando. Adicionado `moderacao.services.usuario_esta_bloqueado()` (ponto único de verdade) e enforcement em `comunidade.services` (`criar_rascunho`, `enviar_para_publicacao`, `comentar`). 5 testes novos em `moderacao`, 3 em `comunidade`.

3. **BRD §11 — Radar sem link para o acontecimento agrupado**: `radar.services.tendencias()` passou a devolver `cluster_id`/`item_id` do item mais recente de cada categoria em alta; `/radar` agora linka para `/noticia/cluster/<id>` ou `/noticia/item/<id>`.

4. **BRD §27 — Newsletter incompleta**: não incluía Radar de tendências, e "manhã"/"noite" eram só rótulos sem efeito (1 agendamento a cada 12h corridas). Adicionado campo `periodo` (manha/noite) em `InscricaoNewsletter`, 2 agendamentos Celery Beat via `crontab` (7h/19h, timezone America/Sao_Paulo), `montar_corpo_email` agora inclui as 3 categorias em alta do Radar. Seletor de período adicionado em `minha-conta`.

5. **BRD §10 — Feed sem equilíbrio entre categorias**: `feed.services.equilibrar_por_categoria()` (intercalação round-robin, preserva recência dentro de cada categoria) aplicado só ao feed geral (não a buscas/filtros explícitos).

6. **BRD §14 — autor não podia editar publicação nem gerenciar perfil**: `comunidade.services.editar_publicacao` (só o próprio autor, só campos de conteúdo) + `PATCH /api/comunidade/publicacoes/<id>/` + UI de edição em `/comunidade/[id]`. `credenciamento`: `PerfilJornalista` ganhou `foto`/`mini_bio`/`dados_profissionais` (copiados da solicitação na aprovação), `services.atualizar_perfil` + `GET/PATCH /api/credenciamento/meu-perfil/` + seção de edição em `/jornalista/status`.

7. **BRD §13 — campo `telefone` opcional faltando** no cadastro de credenciamento — adicionado ao modelo, serializer e formulário.

8. **BRD §12 — "destaques editoriais" invisíveis**: backend já suportava `?destaque=true`, nenhuma tela usava. Seção "Destaques editoriais" adicionada em `/comunidade`.

9. **BRD §19 — B2B sem alertas**: `b2b.services.verificar_e_enviar_alertas()` (novo campo `ultimo_alerta_em` em `CriterioMonitoramento` evita reenviar o mesmo item), task Celery periódica (`B2B_INTERVALO_VERIFICAR_ALERTAS_MINUTOS`, padrão 60min).

10. **BRD §21 — métricas de negócio incompletas**: adicionados `usuarios_ativos_diarios`/`usuarios_ativos_mensais` (DAU/MAU), `retencao_periodo`, `taxa_renovacao_periodo`, `receita_media_por_assinante` ao painel — todos calculáveis com dados já existentes. Pré-requisito descoberto e corrigido: `LoginView`/`GoogleLoginView` nunca atualizavam `User.last_login` (o fluxo de login por token não passa por `django.contrib.auth.login()`), o que teria tornado DAU/MAU sempre zero.

## Deliberadamente NÃO implementado (fora de escopo, documentado ao usuário)
- CAC, LTV, margem, custo médio por usuário, receita publicitária real por usuário Free — exigem integração de anúncios/marketing real, nenhum dado existe hoje; não fabricado.
- Pesquisa periódica de satisfação (BRD §8) — feature nova grande (sistema de survey), não uma correção pontual.
- Timeline para assuntos de longa duração (BRD §22) — feature nova grande.
- Monitoramento de legislação B2B (BRD §19) — já documentado como fora de escopo na spec original ("quando houver fontes adequadas").
- Relatórios periódicos B2B automatizados — já documentado como operação manual do admin na spec original.
- Cupons/promoções de assinatura (BRD §6) — BRD explicitamente diz "poderão ser adicionados futuramente".
- Identificação de conteúdo patrocinado (BRD §17) — não há anunciantes/patrocinadores reais ainda.

## Validação
- `pytest -q` (suíte completa): **221 passed** (era 190 antes desta execução — 31 testes novos).
- `manage.py check`: sem problemas. `makemigrations --check --dry-run`: sem diferenças.
- `npx tsc --noEmit`: limpo. `npm run build`: build de produção completo, todas as rotas (incluindo `/paginas/[slug]` novo) compiladas sem erro.

## Status
Todos os achados classificados como "regra de negócio faltando" (não decisão de produto/infra pendente) foram implementados e validados por execução real.
