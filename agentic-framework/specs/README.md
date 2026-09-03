# Specs

Specs são a fonte de requisitos de **produto/negócio** que alimentam o `task-plan.md` de uma execução. Ficam aqui as especificações de features específicas — não é o lugar do BRD completo (`BRD_portal_noticias_versao_1.docx`, na raiz do projeto), mas o lugar onde se recorta, de forma acionável, um pedaço do BRD (ou uma ideia nova, fora do BRD) em algo que o `orchestrator` consiga transformar em `task-plan.md` sem precisar adivinhar nada.

## Quando criar uma spec

- Antes de abrir uma execução (`agentic-run`) para uma feature não-trivial que ainda não tem recorte claro.
- Quando uma seção do BRD precisa ser desdobrada em requisitos técnicos antes de virar trabalho executável (ex: seção 13 do BRD — Credenciamento de Jornalistas — vira `specs/credenciamento-jornalistas.md` com fluxo, estados e critérios de aceite específicos).

## Quando NÃO criar uma spec

Para pedidos pequenos e já bem definidos (ver exemplos "bons" em `agentic-framework/prompts/request-exemplos.md`), o pedido em si já é suficiente — não crie uma spec só para depois copiar o mesmo conteúdo no `task-plan.md`.

## Como usar

1. Copie `_template.md` para um novo arquivo nomeado pela feature (`kebab-case.md`).
2. Preencha referenciando a seção do BRD, quando aplicável.
3. No pedido ao `orchestrator`, referencie o caminho da spec — ele vai usá-la como `source_spec` no `run-state.json` e como base do `task-plan.md`.

## Decisões técnicas transversais

Decisões de stack, modelo de dados macro, papéis/permissões, eventos de domínio e integrações externas (que valem para todas as specs, não só uma) ficam em `../../ARCHITECTURE.md`, não devem ser repetidas dentro de cada spec.

## Specs existentes

MVP + Assinatura Premium (implementadas):
- `cadastro-autenticacao-onboarding.md`
- `ingestao-curadoria-noticias.md`
- `feed-consumo-noticias.md`
- `gating-free-premium.md`
- `assinatura-premium.md`

Restante do BRD (fases Comunidade/Inteligência/B2B/Escala do roadmap §31) — backend implementado, validação por execução pendente (ver `agentic-framework/state/run-*` de cada um):
- `credenciamento-jornalistas.md`
- `comunidade-blog.md`
- `moderacao-reputacao-governanca.md`
- `radar-tendencias-localizacao.md`
- `newsletter.md`
- `landing-lista-espera.md`
- `b2b-corporativo.md`
- `painel-metricas-negocio.md`

Todo o BRD agora tem spec, backend implementado e alguma tela de frontend (13/13 apps). Pendência real única e crítica: validação por execução de TUDO — backend e frontend — nunca realizada nesta sessão inteira (Bash/Agent/Browser bloqueados pelo classificador de segurança desde o meio de `ingestao-curadoria-noticias`; ver `agentic-framework/state/run-*/implementation-history.md` de cada módulo para o detalhe). Antes de qualquer lançamento: `manage.py check`, `makemigrations --check --dry-run`, `migrate`, `pytest -q` no backend e `npm install && npm run build` no frontend, seguidos de teste manual de cada fluxo — nada disso rodou de fato até aqui.
