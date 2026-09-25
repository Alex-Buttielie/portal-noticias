<!--
CONTRACT: documentation-update
DONO: documenter
QUANDO É CRIADO: depois que testes passam e a revisão (se exigida) está aprovada.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/documentation-update.md
-->

# Documentation Update — 20260924-2136-ingestao-noticias

## Metadados
- **run_id:** 20260924-2136-ingestao-noticias
- **Baseado em:** implementation-history.md (20260924-2136-ingestao-noticias, iterações 1-9), implementation-contract.md (v2) e code-review-contract.md (2ª passada, veredito `approve_with_comments`)
- **Escopo documentado:** (a) o management command `agendar_ingestao` + a integração no `subir-localhost.sh`; (b) a otimização do agrupamento de duplicatas em `services/deduplicacao.py`; (c) o runbook de diagnóstico da ingestão
- **Estado do código documentado:** 177 testes verdes no app `catalogo_noticias`, 12+ rodadas reais do agendador com o código novo, `CELERY_BEAT_SCHEDULE` e `docker-compose` intocados
- **Fora do escopo (não documentado por não ter sido implementado):** overlap-guard no agendador, backoff de falha, agrupamento da assinatura de `_bound_similaridade`, marcador de rodada abortada no banco

## Documentos afetados
| Documento | Tipo de mudança | Resumo |
|---|---|---|
| `README.md` — seção "Como popular o feed com notícias reais (ingestão)" | atualização + 2 subseções novas | O item 5 dizia que automatizar localmente exigia Celery Beat + Redis local — virou item 5 (agendador nativo sobe com o `./subir-localhost.sh`), item 6 (Celery Beat continua sendo o mecanismo de produção/`--docker`, lendo o mesmo intervalo) e item 7 (como rodar o Celery manualmente, com o aviso de não deixar os dois agendadores juntos). Acrescentado parágrafo "Desempenho do agrupamento" e as subseções **"Agendador local de ingestão (modo nativo)"** e **"Diagnóstico da ingestão"** (runbook) |
| `ARCHITECTURE.md` — §1, logo após "Fonte de verdade da ingestão" | nova seção | Um parágrafo (`**Execução local sem broker (2026-09-25):**`) explicando que o modo nativo agenda pelo `agendar_ingestao` e que produção/Docker seguem no `CELERY_BEAT_SCHEDULE`, com o mesmo intervalo. Edição pontual (10 linhas inseridas entre dois parágrafos existentes) — nada foi reescrito |
| `subir-localhost.sh` — cabeçalho de comentários e `usage()` | atualização | `--stop` documentado como quem encerra o agendador esperando a saída; linha nova de `Pid files` no cabeçalho e no `usage()`; `--docker` anotado como "ingestão via Celery Beat". Nenhuma linha de lógica tocada |
| `agentic-framework/state/run-20260924-2136-ingestao-noticias/documentation-update.md` | novo | Este contrato |

## Sem impacto em documentação?
- [x] Confirmado: **nenhum** arquivo `CHANGELOG*` existe no projeto (verificado na raiz e em todo o repositório), então **não há entrada de changelog a adicionar** — ver a seção "Entrada de changelog" abaixo. Nenhum arquivo de changelog foi inventado.
- [x] Confirmado: os demais documentos do repositório foram relidos e **não estão contraditórios** com a mudança; ver "Varredura dos demais documentos" para o que foi checado e por que ficou intacto.

## Exemplos/snippets novos ou atualizados

**README.md — como disparar a ingestão (substituiu o trecho que exigia Celery local):**
```
# primeira rodada imediata e depois a cada intervalo (padrão: 15 min)
backend/.venv/bin/python backend/manage.py agendar_ingestao

# uma única rodada e sai com código 0
backend/.venv/bin/python backend/manage.py agendar_ingestao --rodadas 1

# intervalo customizado, em segundos
backend/.venv/bin/python backend/manage.py agendar_ingestao --intervalo-segundos 60
```

**README.md — como o agendador é ligado/parado (comportamento real do script, já implementado):**
```
./subir-localhost.sh            # nativo: sobe backend + frontend + agendador de ingestão
./subir-localhost.sh --stop     # para containers e processos nativos (o agendador entre eles)
tail -f /tmp/brd-agendador.log  # início/fim de cada rodada, registro_id, itens, erros
kill -0 "$(cat /tmp/brd-agendador.pid)" && echo "agendador vivo"
```

**README.md — runbook de diagnóstico (seção "Diagnóstico da ingestão"), tabela de onde olhar:**
| Onde olhar | O que mostra |
|---|---|
| `tail -f /tmp/brd-agendador.log` | início/fim de cada rodada, `registro_id`, itens, erros de fonte, alerta de falha consecutiva |
| `kill -0 "$(cat /tmp/brd-agendador.pid)"` | se o agendador está vivo |
| `GET /api/admin/robos/execucoes/` (admin) | histórico de `RegistroExecucaoIngestao`; `POST /api/admin/robos/executar/` dispara uma rodada |
| `http://localhost:8000/admin/catalogo_noticias/registroexecucaoingestao/` | o mesmo histórico na tela de admin, com chamadas ao provedor de resumo e custo |

**ARCHITECTURE.md — parágrafo inserido (10 linhas, entre "Fonte de verdade da ingestão" e "Corte de cache e execução local"):**
```markdown
**Execução local sem broker (2026-09-25):** o modo local nativo (venv +
SQLite, sem Docker) não sobe worker/beat do Celery, então o disparo periódico
da ingestão é feito pelo management command `agendar_ingestao`
(`catalogo_noticias/management/commands/agendar_ingestao.py`), que chama o
mesmo `services/ingestao.py::executar_ingestao` em loop e é iniciado pelo
`subir-localhost.sh` nativo (log em `/tmp/brd-agendador.log`). Ele não entra no
`docker-compose` nem é iniciado pelo startup do Django: em produção e no modo
Docker o agendamento segue sendo do `CELERY_BEAT_SCHEDULE`, e os dois leem o
mesmo intervalo (`CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS`).
```

## Entrada de changelog
**O projeto não mantém CHANGELOG** — verificado: nenhum arquivo `CHANGELOG*` na raiz nem em qualquer subdiretório (`git ls-files` + `ls`). Não foi criado um arquivo novo para esta entrega, porque inventar um histórico de versões sem que o projeto o mantenha seria um registro falso. As mudanças de comportamento que entrariam num changelog estão descritas em `README.md` (seção de ingestão) e em `ARCHITECTURE.md` §1; o registro datado do trabalho está em `agentic-framework/state/run-20260924-2136-ingestao-noticias/`.

## Verificação
- [x] Nenhum exemplo/trecho de documentação existente ficou contraditório com a mudança — o `git diff` dos três arquivos toca só o que está na tabela acima; o texto antigo que afirmava "para automatizar localmente é preciso Redis + Celery Beat" foi **reescrito**, não deixado ao lado do novo
- [x] Build/lint de documentação rodado (se o projeto tiver um) — não há linter de markdown no projeto (nenhum `markdownlint`, `vale` ou equivalente em `package.json`/`.pre-commit-config.yaml`/`.github/workflows/`); a verificação foi sintaxe + leitura do diff
- [x] Comandos executados:
  ```
  $ bash -n subir-localhost.sh
  bash -n OK
  $ ./subir-localhost.sh --help
  OK (banner/usage conferidos: Pids adicionados, --docker anotado)
  $ git diff --numstat -- README.md ARCHITECTURE.md subir-localhost.sh
  10  0  ARCHITECTURE.md
  47  2  README.md
  242 8  subir-localhost.sh      # 240/5 eram do executor/remediator; +2 linhas novas e 3 linhas
                                  # reescritas são desta fase, todas no cabeçalho/usage
  ```
- [x] Fatos citados na documentação conferidos contra o código, não de memória: nome e flags do command (`backend/catalogo_noticias/management/commands/agendar_ingestao.py`), defaults (`CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS * 60`, limiar de 3 falhas), rotas (`backend/catalogo_noticias/robos_urls.py` + `config/urls.py` → `/api/admin/robos/execucoes/`, `/api/admin/robos/executar/`), paths de log/pid no `subir-localhost.sh`, e que o bloco do agendador está **depois** do `fi` do ramo docker (logo, só no modo nativo)
- [x] Nenhuma alteração de outra run foi sobrescrita — ver "Integridade com as outras runs" abaixo

## Varredura dos demais documentos (o que foi encontrado e decidido)

`grep -rniE "celery|ingest|ingerir_noticias"` em todos os `*.md` do repositório (fora de `agentic-framework/state/`), `ARCHITECTURE.md`, `PROD_DECISOES.md`, `backend/.env.example`:

| Documento | O que diz hoje | Decisão |
|---|---|---|
| `README.md` §Ingestão | "Em produção (ou se quiser automatizar localmente) … via Celery Beat — exige um Redis local rodando" | **Corrigido** (era o único lugar de fato contraditório/incompleto) |
| `ARCHITECTURE.md` §1 / §5 | "Django, PostgreSQL e Celery formam a única topologia executável de ingestão"; "operações locais, periódicas por Celery" | **Não contraditório** em produção/Docker; acrescido um parágrafo explicitando o caso do modo nativo, sem tocar na frase original |
| `PROD_DECISOES.md` | Decisões de produção (TLS, arquivamento do `ingestao-service/`, Celery fail-open no systemd) | **Intocado** — todas as afirmações continuam verdadeiras em produção; nada nesta run muda a topologia de produção. O arquivo tem edições de outra run no working tree: por isso não foi tocado |
| `CI-CD.md` | Deploy, units systemd do Celery, canal durável `portal_job_*` | **Intocado** — só descreve produção; o `README` aponta para `infra/DEPLOY.md` §9.4 em vez de duplicar |
| `infra/DEPLOY.md`, `infra/observability/README.md`, `infra/observability/alerts/README.md` | Operação de produção (Celery no systemd, alertas `PortalJobAtrasado`/`PortalJobTaskFalha`) | **Intocado** — a runbook nova do README apenas referencia (`infra/DEPLOY.md` §9.4, alerta `PortalJobAtrasado`), sem contradizer nem duplicar. São documentos de outra run (observabilidade), com edições não commitadas |
| `ANALISE_CUSTO_PERFORMANCE.md` | Análise pontual (2026-09-24) com recomendações M1/I1 sobre Celery e ingestão | **Intocado** — é um documento de análise datado, com afirmações que continuam válidas (`celery.py` não define `acks_late`; o custo por chamada de LLM em lote). A otimização do dedup é interna ao agrupamento e não contradiz nenhuma recomendação dele |
| `agentic-framework/specs/ingestao-curadoria-noticias.md` | Spec de requisitos (pré-implementação) | **Intocado** — não menciona Celery/agendamento (conferido por grep); specs são registro de requisitos, não documentação de operação |
| `backend/.env.example` | `CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS=15` sem comentário próprio, dentro do bloco "Celery + Redis" | **Intocado por decisão** — não é contraditório (a variável continua sendo lida pelo beat e agora também pelo agendador nativo, com o mesmo valor). Registrado aqui como observação: quem mexer nesse arquivo pode querer uma linha de comentário dizendo que a setting é compartilhada pelos dois agendadores |
| `docs/` | Diretório inexistente | Nada a fazer |

## Integridade com as outras runs

- Só três arquivos de fora do diretório de estado foram tocados: `README.md`, `ARCHITECTURE.md` e `subir-localhost.sh`. Os três estavam **sem modificação pendente** no início desta fase (`git diff --stat` inicial: apenas `subir-localhost.sh`, com o bloco do agendador do executor), então não havia trabalho de outra run para preservar neles.
- `ARCHITECTURE.md` e `PROD_DECISOES.md` têm histórico de edições de outras runs, então o `ARCHITECTURE.md` recebeu **uma inserção pontual** (10 linhas entre dois parágrafos existentes) e nenhuma regeneração; `PROD_DECISOES.md` não foi tocado.
- Arquivos de outras runs com edição não commitada que **continuam intactos** (verificado por `git status` ao final): `.github/workflows/deploy*.yml`, `backend/config/{health,metrics,observability_views}.py`, `backend/feed/views.py`, `infra/observability/**`, `backend/catalogo_noticias/services/deduplicacao.py` (otimização desta run, mantida), `backend/identidade/management/commands/criar_usuario_carga.py`.

## O que ficou de fora, de propósito
- Não documentado como "solucionado": overlap-guard, backoff de falha, marcador de rodada abortada no `RegistroExecucaoIngestao` — são follow-ups abertos, não comportamento entregue.
- Não documentado: benchmark, mutation check, sandboxes e identidade de pid — são evidência de verificação, não operação para o desenvolvedor. O único número que entrou no README é o ganho do agrupamento (8,6x-10,3x), porque é o que explica por que a rodada ficou rápida.
