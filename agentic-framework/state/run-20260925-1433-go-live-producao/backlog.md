# Backlog de produção — 20260925-1433-go-live-producao

Este backlog é derivado do `task-plan.md` (v2) e do `implementation-contract.md` (v2). Ele é a ordem de execução proposta para o programa de go-live. Cada item precisa de um contrato de lote antes de ser delegado ao executor.

**Acordo de escopo vigente (2026-09-25):** o CI/CD existente **permanece como está** no lote P0-1/F0 e nesta fase do programa · o risco **R-1** (supply chain PR → VPS) é **ACEITO, ABERTO, não mitigado, não coberto pelo gate e NÃO BLOQUEANTE**, com aceite assinado no go/no-go · o **domínio canônico** é `https://portal-noticias.com/` e os hostnames de ambiente ainda não estão decididos · o WIP da run `20260925-1020-observabilidade` é **isolado** · `settings.py` é **apenas verificado** no lote P0-1 (gate G1), nunca corrigido.

A coluna **WS / gate** liga cada item ao workstream e ao gate do `action-plan.md`; é ela que impede backlog e plano de divergirem.

## P0 — bloqueia qualquer tráfego público

| ID | Item | Dependências | Saída verificável | WS / gate |
|---|---|---|---|---|
| P0-01 | Reconciliar working tree e runs abertas | Nenhuma | Inventário com **atribuição por run** de cada item; run `20260925-1020-observabilidade` **separada como WIP isolado**; nenhum arquivo de outra run sobrescrito; decisões G0, G2, G3, G4, G5 registradas; **re-verificação fresca de G0–G5** (branch, `HEAD`, `origin/*`, paridade, refs, `status`, presença de `4c57ff04` por SHA) registrada **com timestamp** antes de GP-0 passar; inventário/ownership do diretório de estado desta run, **fora de release** e **sem edição de `.gitignore`** | WS-00 / **GP-0** |
| P0-01b | Re-derivação detalhada do estado Git e baseline de release | P0-01, GP-0 `pass` | Estado Git re-derivado **no início do lote** (branch, `HEAD`, `origin/*`, `rev-list --left-right --count`, todas as refs, `status -uall`, `4c57ff04` por SHA, worktree, `stash`), com **timestamp** e comando de reprodução por linha; SHA de release **re-derivado** (`git rev-parse HEAD`); divergência de claims antigos registrada, sem reaproveitar snapshot | WS-01 / **GP-1** |
| P0-02 | Verificar `settings.py` (gate **G1**) | P0-01 | `ast.parse`/`compile()` bem-sucedidos, sem `__pycache__`, **sem edição do arquivo**; resultado em `lote-p0-1-evidencias.md` | WS-01 / **GP-1** |
| P0-02b | Integridade funcional de `settings.py` (correção, se necessária) | P0-02 | `manage.py check` e import verdes no SHA de release, **ou** item encerrado por evidência; nenhum arquivo de outra run sobrescrito | WS-02 / **GP-1b** |
| P0-03 | Rotação root e SSH por chave | Domínio não é dependência; acesso humano seguro | Root por senha desabilitado; usuário non-root criado; auditoria feita | WS-03 / **GP-2a** |
| P0-04 | Fechar portas e proteger bind | P0-03 | `ss`/firewall mostram apenas Nginx e SSH; 3101–3103/5101–5103 inacessíveis | WS-04 / **GP-2b** |
| P0-05 | Domínio canônico, DNS e TLS | Compra do domínio; decisão D-01 | `https://portal-noticias.com/` resolve; HTTPS válido; redirect e HSTS testados; **nenhum hostname de ambiente inventado** | WS-05 / **GP-3** |
| P0-06 | Backup externo e restore | Storage externo | Backup diário enviado; restore em ambiente isolado; RPO de 24h comprovado; runbook de restore recorrente (P2-06) publicado | WS-07 / **GP-4b** |
| P0-07 | Isolamento DEV/HOMOLOG/PROD | P0-01, P0-04 | Bancos, Redis, filas, mídia e chaves sem leitura cruzada | WS-06 / **GP-4a** |
| P0-08 | Remover conteúdo fictício | Contrato de frontend | Nenhum `MOCK`/preço/assinante falso como conteúdo real | WS-11 / **GP-8** |
| P0-09 | Gate de release e provenance (sem tocar em CI/CD) | P0-01 | Working tree sujo/untracked é **rejeitado** pelo gate read-only; `.github/` inalterado; **o caminho PR → VPS permanece ativo e R-1 está registrado como aceito e aberto, com aceite assinado no go/no-go** (nunca como resolvido) | WS-01 / **GP-1** |
| P0-10 | Hardening de segurança da aplicação | P0-02, P0-04 | XSS/JSON-LD, SSRF, uploads, métricas e health/readiness com testes | WS-08..WS-13 / **GP-10** |
| P0-11 | Validação e *pinning* de host key (`known_hosts`) | P0-03, acesso humano seguro | Impressão digital da host key fixada para o acesso humano e o usuário de deploy; **teste negativo de chave divergente rejeitada**; divergência do caminho de CI registrada (R-16) | WS-03 / **GP-2a** |

## P1 — bloqueia o go-live funcional

| ID | Item | Dependências | Saída verificável | WS / gate |
|---|---|---|---|---|
| P1-01 | Ingestão e limites de campos | P0-01, P0-02 | Valores grandes não causam `DataError`; erro não aborta todos os grupos | WS-08 / **GP-5** |
| P1-02 | Fallback local do OpenAI | P1-01, credencial OpenAI | Fallback executa, publica e é distinguível em métrica/log | WS-08 / **GP-5** |
| P1-03 | Workers, beat e filas do portal | P0-07 | Task registrada, consumida e monitorada por ambiente | WS-06 / **GP-4a** |
| P1-04 | Resend | Domínio, credencial | Cadastro, verificação e reset entregam email real | WS-09 / **GP-6** |
| P1-05 | Login Google | Domínio, credencial | OAuth funciona em DEV/HOMOLOG/PROD | WS-09 / **GP-6** |
| P1-06 | Newsletter e descadastro | P1-04, P1-03 | Formulário funcional, envio e descadastro testados | WS-09 / **GP-6** |
| P1-07 | Mercado Pago sandbox | Credencial, P1-03 | Assinar, webhook, cancelar, renovar e reconciliar | WS-10 / **GP-7** |
| P1-08 | Ativação condicional do Premium | P1-07, plano na Central | Premium só abre após todos os gates de pagamento; caso contrário, fechado com fallback | WS-10 / **GP-7** |
| P1-09 | AdSense e Consent Mode | Conta AdSense, domínio, consentimento | Free mostra ads; Premium não; fallback Free sem ads funciona | WS-11 / **GP-8** |
| P1-10 | GA4 e métricas internas | Consentimento, P1-04 | Eventos externos só após consentimento; sem token/query string | WS-11 / **GP-8** |
| P1-11 | Community e cache | Correção do bug de invalidação | Publicação/comentário invalida a query correta; logout limpa sessão | WS-12 / **GP-9** |
| P1-12 | Credenciamento | Upload security | Upload allowlist, anexo seguro e acesso testado | WS-12 / **GP-9** |
| P1-13 | B2B completo | P1-03, P1-04 | Papéis, isolamento e alertas testados | WS-12 / **GP-9** |
| P1-14 | Admin/Central/robôs | P1-01, P0-09 | Ações administrativas e kill switch testados | WS-12 / **GP-9** |
| P1-15 | Rotas e formulários | Frontend | Contato, lista de espera e newsletter sem submissão vazia | WS-11 / **GP-8** |
| P1-16 | Dependências frontend | P0-09 | Next.js sem advisory crítico; lint funcional; typecheck e build verdes | WS-11 / **GP-8** |

## P2 — necessário antes de escala

| ID | Item | Dependências | Saída verificável | WS / gate |
|---|---|---|---|---|
| P2-01 | Observabilidade operacional | P1-03, P1-09, P1-10 | Logs, métricas, release, request ID, filas e alertas pesquisáveis | WS-14 / **GP-10** |
| P2-02 | Retenção e expurgo | P1-10 | Eventos antigos removidos de forma idempotente e auditável | WS-13/WS-14 / **GP-10** |
| P2-03 | Recursos e OOM | Métricas de produção | Alertas de memória, CPU, disco e fila; limites ajustados | WS-14 / **GP-10** |
| P2-04 | Acessibilidade e revisão visual dos ads | P1-09 | Layout de ads, contraste, foco, teclado e consented state revisados | WS-11 / **GP-8** |
| P2-05 | Testes de carga | P2-01, P2-03 | Comportamento sob tráfego inicial e picos conhecidos **medido e documentado** no SHA de release | WS-14 / **GP-10** |
| P2-06 | Runbook de restore recorrente | P0-06 | Runbook publicado em GP-4b; restore mensal agendado e **evidência arquivada** durante o soak/go-live | WS-07 + WS-14 / **GP-4b**, **GP-10** |
| P2-07 | Decisões editoriais e de direitos | Registro jurídico | Canal de denúncia, atribuição e retirada de conteúdo operacionais; decisão D-04 registrada no go/no-go | WS-12 + WS-14 / **GP-9**, **GP-11** |

## Dependências humanas que não são código

- Compra e DNS de `portal-noticias.com`.
- Decisão **D-01**: `www` e **nomes de host de DEV/HOMOLOG/PROD** (nenhum hostname é inventado por agente).
- Decisão sobre o **alinhamento dos valores de domínio** hoje divergentes nos workflows (`portal-noticias.com.br` × canônico `.com`) — **R-15**, lote posterior, sem mudar estrutura nem gatilhos.
- Credenciais de Mercado Pago, Resend, OpenAI, Google OAuth, GA4 e AdSense.
- **Contas de telemetria — RESPONDIDO em 2026-10-08: o solicitante NÃO possui Grafana Cloud nem Better Stack.** Consequência: **P2-01 não é observabilidade**; é configuração em arquivo sem nada rodando. Sem detecção de incidente, sem painel, e as 14 regras de alerta não avaliam nada. Registrado em `plano-de-arre-regular-20261008.md`, seção "BLOQUEIO — telemetria sem conta", com o custo medido da alternativa self-hosted (~2 GB livres de 3915 MB) e o motivo de não ser recomendada agora.
- Storage externo para backup.
- Status da conta AdSense.
- Cadastro do plano Premium na Central.
- **Aceite assinado de R-1** (supply chain PR → VPS): o que está sendo aceito, o escopo, até quando e quem assina. **Não bloqueia o go-live; bloqueia o go/no-go sem assinatura.**
- Evidência de *pinning* de host key e teste negativo (P0-11) e reconhecimento da divergência do caminho de CI (**R-16**).
- Decisões de proveniência **G0, G2, G3, G4, G5** (custódia do WIP, refs, worktree, política de promoção, atribuição), com **re-verificação fresca** registrada antes de GP-0 passar.
- Inventário e **ownership** do diretório de estado não rastreado desta run (`agentic-framework/state/run-20260925-1433-go-live-producao/`): **fora de release**, re-derivado a cada gate, **sem editar `.gitignore`**.
- Responsáveis por deploy, curadoria, suporte e incidentes.
- Registro da decisão de lançamento sem revisão jurídica formal.

## Regra de corte

Nenhum item P1 começa sem os itens P0 correspondentes. Nenhum item P2 substitui um P0/P1 pendente. Nenhum deploy de PROD começa sem que o lote esteja testado, revisado, documentado e com rollback.

Nenhum gate depende de um item executado apenas depois dele: o gate de custódia/proveniência fecha com **G0, G2, G3, G4, G5** — mais a **re-verificação fresca** desses mesmos itens, feita com comandos de leitura dentro da própria workstream de reconciliação —, e a validação **G1** de `settings.py` (P0-02) é executada no lote seguinte, alimentando **GP-1** e **GP-1b**. **GP-0 não exige nenhum artefato produzido por P0-01b/WS-01.**

Risco **aceito** (hoje, R-1) não bloqueia item algum deste backlog; risco aceito **sem aceite assinado no go/no-go** bloqueia o go-live.

## Estado inicial

- P0: planejado.
- P1: planejado.
- P2: planejado.
- Implementação: não iniciada nesta etapa.
- VPS: não alterada.
- Domínio: não configurado; único valor de domínio adotado é o canônico `https://portal-noticias.com/`.
- `.github/`: intocado no lote P0-1/F0 e nesta fase do programa; caminho PR → VPS **ativo** e R-1 **aceito e aberto**.
- WIP da run `20260925-1020-observabilidade`: **isolado**, não adotado por esta run.
- `settings.py`: apenas verificado, nunca corrigido no lote P0-1.
- Diretório de estado desta run (`agentic-framework/state/run-20260925-1433-go-live-producao/`): **não rastreado**, **fora de release**, com ownership desta run, **re-derivado** a cada gate; `.gitignore` **intocado**.
- Estado Git: **snapshot datado** de 2026-09-25T18:32:47Z (`develop` e `origin/develop` **iguais** em `7715dae8`, paridade `0/0`, `948a5b5`/`645aca3` **já no remoto**, `4c57ff04` ***dangling*, recuperável só por SHA**); **re-derivado** em P0-01b e antes de GP-0. Nenhum SHA de ref é SHA de release.
- Credenciais: não fornecidas nesta etapa.

---

## Addendum de remediação de planejamento — 2026-09-25

**Histórico preservado:** a estrutura P0/P1/P2 e as saídas verificáveis da versão anterior foram mantidas; a tabela ganhou a coluna **WS / gate**, e as linhas que descreviam um estado hoje falso foram **reescritas com a divergência explícita** (não apagadas). Nenhuma implementação foi feita; nenhuma data de calendário foi criada.

| Achado | Correção neste backlog |
|---|---|
| **B1** — gate circular | "Regra de corte": GP-0 = **G0, G2, G3, G4, G5**; **G1** (P0-02) executada no lote seguinte, alimentando GP-1/GP-1b; P0-02 e P0-02b separados |
| **B2** — R-1 padronizado | P0-09 reescrito (o gate é entregue; o caminho PR → VPS **permanece ativo** e R-1 é **aceito, aberto, com aceite assinado no go/no-go**, nunca resolvido); "Acordo de escopo vigente"; "Dependências humanas"; "Regra de corte"; "Estado inicial" |
| **M1** — `run-state.json` | Nenhum item de backlog exige que um executor escreva `run-state.json`; a atualização é do orchestrator, fora do diff do lote, e o historian só o escreve no **fechamento F9** (desfecho já decidido) |
| **M2** — host key sem dono | **P0-11** criado, atribuído a WS-03 / **GP-2a**, com teste negativo de chave divergente e registro da divergência do caminho de CI (R-16) |
| **M3** — caminho crítico | Coluna **WS / gate** + GP-10 explícito nas entradas (GP-5, GP-6, GP-8); GP-7 e GP-9 marcados como **não** pré-requisito de GP-10 |
| **m2** — P0-09 não podia prometer o que o gate não faz | Saída verificável de P0-09 corrigida |
| **m3** — subdomínios | P0-05 exige apenas o canônico e proíbe hostname inventado; D-01 listada como dependência humana |
| **m5/m6** — soak e cobertura de P2 | P2-05, P2-06 e P2-07 agora têm workstream e gate; P2-06 aparece também em P0-06 |
| **m7** — snapshot `645aca3` | P0-01 fala em inventário/atribuição e **re-verificação fresca**; a **re-derivação detalhada e a baseline de release** foram para **P0-01b** (WS-01/GP-1), sem fixar `645aca3` nem qualquer SHA como release |
| **m8** — texto corrompido | Nenhum texto corrompido permanece neste arquivo |

*Editado apenas em planejamento. Nenhum código, workflow, VPS, run anterior ou `run-state.json` foi alterado; nenhum comando Git de escrita foi executado.*

*Acabamento documental pós-revisão independente (2026-09-25): aplicadas as ressalvas **R1–R11** do reviewer **sem mudar item, dependência, gate ou escopo** — neste arquivo, apenas o addendum **M1** (ownership único de `run-state.json`: orchestrator durante o programa, historian só no F9, executor nunca). Nenhum código, workflow, VPS, `settings.py`, run anterior ou `run-state.json` foi tocado; nenhum comando Git de escrita; nenhum `implementation-history.md` criado.*

*Acabamento documental — segunda rodada de remediação de planejamento (2026-09-25), **sem mudar item, dependência, gate ou escopo** neste arquivo:*** **P0-01** foi desmembrado — a **reconciliação/inventário/atribuição/ownership** e as decisões **G0, G2, G3, G4, G5**, com a **re-verificação fresca** exigida antes de GP-0, ficaram em **P0-01** (WS-00/GP-0), e a **re-derivação detalhada do estado Git + baseline de release** passou para o **novo item P0-01b** (WS-01/GP-1, dependente de P0-01 e de GP-0 `pass`) — assim **GP-0 não exige mais um artefato que só WS-01 produz**, sem criar gate circular; a "Regra de corte" explicita a re-verificação e a não-circularidade; "Dependências humanas" e "Estado inicial" passaram a registrar o **estado Git re-derivado** (snapshot de 2026-09-25T18:32:47Z: `develop` e `origin/develop` **iguais** em `7715dae8`, paridade `0/0`, `948a5b5`/`645aca3` **já no remoto** — **sem push pendente** — e `4c57ff04` ***dangling*, ausente do reflog, recuperável só por SHA**) e a declaração do diretório de estado desta run como **não rastreado, fora de release, com ownership e sem edição de `.gitignore`**. Nenhum código, workflow, VPS, `settings.py`, `provenance-reconciliation.md`, run anterior ou `run-state.json` foi tocado — este último **não** foi editado nesta rodada e será atualizado pelo **orchestrator após a revisão final**, com timestamp posterior; nenhum comando Git de escrita; nenhum `implementation-history.md` criado.
