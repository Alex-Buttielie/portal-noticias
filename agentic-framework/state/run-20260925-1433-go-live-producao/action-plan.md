<!--
CONTRACT: action-plan (documento de execução do programa)
DONO: orchestrator
QUANDO É CRIADO: durante a fase de planejamento da run, antes de qualquer lote
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-20260925-1433-go-live-producao/action-plan.md
NATUREZA: SOMENTE PLANEJAMENTO. Nenhuma tarefa deste documento foi executada. Nenhum comando Git de
escrita, nenhum acesso à VPS, nenhum deploy. Nenhuma data de calendário é definida aqui.
-->

# Action Plan — 20260925-1433-go-live-producao

## 0. Metadados e regra de leitura

- **run_id:** `20260925-1433-go-live-producao`
- **Deriva de:** `task-plan.md`, `implementation-contract.md`, `backlog.md`, `provenance-reconciliation.md` e `lote-p0-1-proveniencia.md` da mesma run.
- **Dono:** orchestrator. **Consumidores:** executor, tester, reviewer, remediator, documenter, historian, e o solicitante (Alex/equipe) para os gates de decisão humana.
- **Natureza:** documento de **execu sequenciado**, não de escopo. O escopo está em `task-plan.md`; os critérios testáveis, em `implementation-contract.md`. Aqui estão **ordem, dependências, gates, rollback, evidência e responsabilidade**.
- **Cronologia:** nenhuma. Este plano é **sequencial, não cronológico**. Não há datas, prazos ou janelas definidas; janelas são aprovadas pelo solicitante no momento do lote correspondente (ver `HD` na §13).
- **Estado do repositório, da VPS e das integrações quando este plano foi escrito:** desconhecido. Nenhum agente desta fase acessou a VPS, o DNS, o GitHub remoto nem qualquer serviço externo. **Nada aqui presume que algo já foi feito.**

### 0.1 Regra de delegação (bloqueante, vale para todo o documento)

> **Nenhum código, configuração, infraestrutura, banco, credencial ou comando de VPS é delegado sem (a) contrato de lote próprio, aprovado, e (b) aprovação explícita do gate de passagem da fase correspondente.**

Consequências operacionais:

1. Este documento **não autoriza** nenhum lote. Ele autoriza a **emissão** de contratos de lote e a execução dos gates.
2. Um lote só é delegado depois que: o `WS` tem entrada satisfeita, o gate anterior está registrado como `pass`, o contrato de lote está escrito e o solicitante aprovou o lote específico.
3. Um lote é executado por **um subagente por vez**, com diff limitado à lista de escrita autorizada do seu contrato.
4. Lotes que tocam a VPS exigem, além do contrato, um **runbook de mudança** e confirmação de backup válido no mesmo lote.
5. Divergência entre o que este plano diz e o que um lote faria ⇒ o lote é **devolvido ao orchestrator**, nunca improvisado.
6. Nada em `.github/` é alterado no lote P0-1/F0 nem nesta fase do programa, por decisão do solicitante registrada no `lote-p0-1-proveniencia.md` (revisões 2 e 3). O caminho PR → VPS permanece **ativo** e é registrado como **risco aceito, aberto, não mitigado, não coberto pelo gate e não bloqueante para o go-live**, com **aceite assinado no go/no-go** (R-1). Ver §4.6, §13.2 e §17 D-03.

---

## 1. Objetivo e estratégia de release

### 1.1 Objetivo

Colocar o Portal de Notícias em produção em `https://portal-noticias.com/`, com três ambientes isolados numa VPS reformada, backup externo recuperável, leitura pública sem cadastro, conta opcional (e-mail e Google), Premium mensal via Mercado Pago sem anúncios, anúncios AdSense apenas para Free, publicação automática de RSS com resumo por OpenAI e fallback local, e os módulos Community, credenciamento, B2B, Central e Admin funcionando — **operado por Alex/equipe**, sem revisão jurídica formal, com o risco jurídico registrado.

### 1.2 Estratégia de release

A estratégia é **promoção por SHA único, ambiente a ambiente, com rollback por ambiente**. Onde ela se apoia:

1. **Um SHA, três ambientes.** O mesmo commit é promovido DEV → HOMOLOG → PROD. Ambiente não tem código próprio: tem configuração, dados, filas e mídias próprias. Isso torna o rollback trivial (`voltar ao SHA anterior` + restaurar configuração/dados daquele ambiente) e elimina a classe de bug "HOMOLOG não reproduz PROD".
2. **Reprodutibilidade verificada por gate, não por confiança.** O release só é considerado reproduzível se o gate determinístico reprovar working tree sujo, untracked, SHA divergente, conflito de merge, segredo aparente, Python/YAML inválido, e se a prova de read-only do próprio gate for registrada. Um gate que passe em uma árvore suja é **blocker**.
3. **Ambiente como unidade de isolamento.** Banco, Redis, filas Celery, mídia, chaves de assinatura e segredos são separados por ambiente, com teste de isolamento que **tenta** a leitura cruzada e mostra que ela falha. Isolamento não declarado não é isolamento.
4. **Backfill e verificação antes do tráfego.** Nenhuma migração de schema chega a PROD sem backup verificado, teste da migration, passagem por HOMOLOG e rollback documentado.
5. **Ativação condicional por credencial.** Premium, AdSense, GA4, OpenAI, Resend e Google só entram em produção depois de credencial real + teste correspondente. Ausência de credencial = recurso fechado com mensagem segura, nunca mock e nunca valor hardcoded.
6. **Kill switches como estratégia de operação, não como afterthought.** Ingestão, Premium, ads e integrações têm desligamento manual **acionável por pessoa da equipe**, documentado, e testado antes do go-live.
7. **Sinceridade documental como critério técnico.** Nenhum artefato — plano, lote, revisão, relatório — pode afirmar que um risco foi resolvido sem evidência. O caso registrado é o caminho PR → VPS (R-1): ele é **aceito por decisão do solicitante**, portanto **não bloqueia o go-live**, e permanece **aberto**, **não mitigado** e **não coberto pelo gate** até que a decisão futura (**HD-1**/D-03) seja tomada — com aceite assinado no go/no-go.
8. **Rollback em camadas.** Código (SHA anterior), configuração (arquivo versionado anterior), dados (migration reversível ou restore do backup externo), e produto (fechar a feature: Free sem ads, Premium fechado, kill switch de ingestão). Cada camada tem critério de parada e verificação pós-rollback (§14).

### 1.3 O que a estratégia de release **não** promete

- Não promete alta disponibilidade: uma VPS, sem HA. Perda do host é evento de restore, não de failover.
- Não promete reversão de dados já validados em produção sem backup: onde a reversão é irreversível, o plano exige decisão humana explícita antes de avançar.
- Não promete que o gate de proveniência barre deploy de pull request no lote P0-1/F0 — **ele não barra** (ver §4.6).
- Não promete que o caminho PR → VPS (R-1) esteja fechado: ele está **aceito** e **aberto**, e essa é uma decisão consciente, não uma omissão (ver §4.6 e §13.2).

---

## 2. Ordem das fases e caminho crítico

### 2.1 Fases

| Fase | Nome | Workstreams | Saída da fase |
|---|---|---|---|
| **F0** | Reconciliação, custódia de proveniência e baseline de release | WS-00, WS-01, WS-02 | Proveniência com dono atribuído (G0, G2, G3, G4, G5), working tree preservado, gate de proveniência entregue e revisado, `settings.py` **verificado** por G1 |
| **F1** | Host, rede, domínio e TLS | WS-03, WS-04, WS-05 | Acesso SSH por chave com root por senha desabilitado, **host key validada e fixada**, portas de aplicação fechadas, `https://portal-noticias.com/` servindo TLS válido |
| **F2** | Isolamento de ambientes, filas, mídia e backup/restore | WS-06, WS-07 | Três ambientes sem leitura cruzada, backup externo diário, restore verificado em ambiente isolado |
| **F3** | Ingestão, editorial, OpenAI e fallback local | WS-08 | Ingestão de todas as fontes RSS sem erro de persistência, publicação automática, fallback local marcado na telemetria |
| **F4** | Identidade, Resend, Google e privacidade/LGPD | WS-09 | Cadastro/verificação/reset por e-mail real, login Google no domínio de PROD, consentimento e exclusão/anomização auditadas |
| **F5** | Premium e Mercado Pago | WS-10 | Sandbox validado, webhook assinado e idempotente, ativação condicional de Premium |
| **F6** | Ads, analytics, frontend e rotas/formulários | WS-11, WS-14(UI) | AdSense só em Free e só com consentimento, Premium sem ads, fallback Free sem ads, GA4 pós-consentimento, formulários reais, build/typecheck/lint verdes |
| **F7** | Community, credenciamento, B2B, Central e Admin | WS-12, WS-14(UI) | Cache de Community corrigido, publicação ocultada invisível, isolamento B2B por organização, uploads validados, kill switch testado |
| **F8** | Consolidação de segurança, testes, revisão, observabilidade e soak | WS-13, WS-14 | Findings major/blocker fechados, suíte completa verde no SHA de release, **soak em HOMOLOG** concluído sem incidente aberto |
| **F9** | Go/no-go e fechamento | WS-14 | Decisão de go-live registrada **com o aceite assinado de R-1**, runbooks, `report.md`, `HISTORY.md` |

### 2.2 Caminho crítico

O caminho crítico é a cadeia que **não pode ser encurtada**:

```
GP-0  custódia/proveniência (G0, G2, G3, G4, G5 — decisões humanas; sem G1)
  └─> GP-1  lote P0-1 entregue, testado e revisado  (gate de proveniência + G1: settings.py verificado)
        │     └─> GP-1b  settings.py validado funcionalmente (ou encerrado por evidência)
        └─> GP-2a  acesso ao host: root por senha desabilitado, usuário non-root,
        │          host key validada e fixada (known_hosts)      [WS-03]
              └─> GP-2b  rede: portas de aplicação fechadas, Nginx único proxy  [WS-04]
                    └─> GP-3  domínio canônico, DNS, TLS, edge headers e cookies  [WS-05]
                          └─> GP-4a  ambientes isolados (bancos, Redis, filas, mídia, chaves)  [WS-06]
                                └─> GP-4b  backup externo e restore verificado               [WS-07]

Após GP-4b, abrem-se as frentes de produto (regras de concorrência em §2.3):

  GP-5  WS-08  ingestão, publicação automática, fallback local   ──┐
  GP-6  WS-09  identidade, Resend, Google, consentimento, LGPD   ──┼─> GP-10  suíte completa,
  GP-8  WS-11  ads, analytics, rotas, formulários, frontend      ──┘          security review,
                                                                              observabilidade, soak
                                                                             └─> GP-11 go/no-go

  GP-7  WS-10  Premium e Mercado Pago                  depende de GP-4b + GP-6 · não bloqueia GP-10
  GP-9  WS-12  Community, credenciamento, B2B, Admin   depende de GP-5 + GP-6 · não bloqueia GP-10
```

Leitura do caminho crítico:

**Dependências explícitas (fonte de verdade; o desenho acima é a sua leitura):**

| Gate | Depende de | Observação |
|---|---|---|
| **GP-0** | — | G0, G2, G3, G4, G5 **+ re-verificação fresca de G0–G5** registrada antes de fechar (§4.2.1). **Não** depende de G1 (§4.2) nem de nenhum artefato do lote P0-1 |
| **GP-1** | GP-0 | Lote P0-1 (AC-1..AC-10) |
| **GP-1b** | GP-1, pelo resultado de **G1** executado no lote | Integridade funcional de `settings.py` |
| **GP-2a** | GP-1 | WS-03. Inclui **host key validada e fixada** (`known_hosts`, HD-7) |
| **GP-2b** | GP-2a | WS-04 (e **HD-4**) |
| **GP-3** | GP-2b, domínio comprado | WS-05 |
| **GP-4a** | GP-3, GP-1 | WS-06 |
| **GP-4b** | GP-4a, storage externo | WS-07 |
| **GP-5** | GP-4b | WS-08 |
| **GP-6** | GP-4a, WS-05, credenciais | WS-09 |
| **GP-7** | **GP-4 (GP-4a e GP-4b) e GP-6** | WS-10. **Não** depende de GP-10 e **não** bloqueia GP-10 |
| **GP-8** | GP-4a, WS-05, credenciais | WS-11. **Não** depende de GP-7 |
| **GP-9** | **GP-5 e GP-6** | WS-12. **Não** depende de GP-7 nem de GP-10 |
| **GP-10** | **GP-5, GP-6 e GP-8** (e GP-4b) | **GP-7 não é pré-requisito de GP-10** |
| **GP-11** | **GP-10**, com **GP-7 e GP-9 testados** (§12.2/§15.2), + §15 | Go/no-go assinado; inclui o aceite assinado de R-1 |

- **GP-0 → GP-1 → GP-2a → GP-2b → GP-3 → GP-4a → GP-4b é estritamente sequencial.** Não há paralelismo útil antes de GP-3: sem host endurecido, não há como emitir/renovar TLS com segurança; sem TLS, não há smoke por domínio; sem ambientes isolados, qualquer teste de PROD contamina HOMOLOG/DEV e torna o resultado de integração inválido.
- **WS-03 (acesso) precede WS-04 (rede)**: fechar portas e mudar bind sem usuário não-root e sem chave substituta é a forma clássica de trancar a própria porta de saída. A execução de bind em loopback depende de **HD-4** (topologia de execução) e é **separável** de P0-03.
- **GP-10 tem exatamente três entradas**: GP-5, GP-6 e GP-8. Tudo o que converge de produto precisa estar pronto antes da suíte final, porque a suíte final exercita ingestão, identidade e ads juntos.
- **GP-7 (Premium) está fora do caminho crítico do *lançamento público*:** Premium é ativação condicional. Um go-live com Premium fechado e Free funcionando é coerente com o contrato mestre (**AC-24 do `implementation-contract.md`** — plano inativo ou sem credencial ⇒ assinatura bloqueada, sem acesso Premium concedido) e com o item **`P1-08` do `backlog.md`** (ativação condicional do Premium). Mas **os lotes de pagamento precisam estar testados em sandbox antes do go-live**, mesmo que a ativação fique para depois — daí GP-7 depender de GP-4 e GP-6, e não bloquear GP-10.
- **GP-9 depende de GP-5 e GP-6** porque Community/Admin/B2B reaproveitam a ingestão e a identidade; **não** depende de GP-7, porque nada do lote de módulos depende de estado de assinatura.
- **GP-11 exige GP-7 e GP-9 testados, além de GP-10** (§12.2/§15.2): Premium e módulos **não** são pré-requisito de GP-10, mas precisam estar testados antes do go/no-go, porque o go/no-go fecha o estado de ambos.
- **GP-10 é o gate mais largo** e o único que não aceita amostragem: é lá que a suíte completa, a security review, a observabilidade e o soak se encontram.

### 2.3 Regras de concorrência entre lotes

1. **No máximo 2 lotes de código de aplicação simultâneos** após GP-4. Motivo: revisão por diff legível e ausência de conflito silencioso em migrations.
2. **Nunca dois lotes que alterem o mesmo model ou migration** ao mesmo tempo. Migração é sempre lote exclusivo, com backup verificado no mesmo lote.
3. **Nunca dois lotes que alterem estado de assinatura** (Premium, webhook, papel do usuário) ao mesmo tempo. Estado de pagamento exige exclusividade de revisão.
4. **Nenhum lote de código e nenhum lote de VPS ao mesmo tempo** na mesma janela: misturar mudança de código com mudança de host torna o rollback inambíguo.
5. Lotes que tocam PROD exigem **janela aprovada e smoke pré-aplicado em HOMOLOG no mesmo SHA**.

---

## 3. Workstreams

### 3.1 Catálogo (índice)

O detalhamento de **entradas, saídas, subagentes e gate** de cada `WS` está na seção da fase correspondente (§4–§12). Esta tabela é o índice e a fonte de verdade para dependências.

| WS | Nome | Itens de backlog | Fase | Depende de | Gate de saída |
|---|---|---|---|---|---|
| **WS-00** | Reconciliação de proveniência e custódia do WIP | P0-01 (parte) | F0 | — | GP-0 |
| **WS-01** | Baseline atribuída, gate determinístico de release e documentação do lote; **executa G1** (verificação de `settings.py`) | P0-01 (parte), P0-02 (verificação), P0-09 (parte, sem CI/CD) | F0 | WS-00 | GP-1 |
| **WS-02** | Integridade funcional de `settings.py` e integridade do release | P0-02 (completo) | F0 | WS-01 (G1) | GP-1b |
| **WS-03** | Identidade de acesso ao host: rotação root, SSH por chave, usuário non-root, **validação/pinning de host key (`known_hosts`)** | P0-03, P0-11 | F1 | GP-1, acesso humano seguro | GP-2a |
| **WS-04** | Exposição de rede: firewall, portas de aplicação, bind loopback | P0-04 | F1 | WS-03, HD-4 | GP-2b |
| **WS-05** | Domínio canônico, DNS, TLS, edge headers e cookies | P0-05 | F1 | WS-04, domínio comprado | GP-3 |
| **WS-06** | Isolamento de DEV/HOMOLOG/PROD: bancos, Redis, filas, mídia, chaves | P0-07, P1-03 | F2 | WS-01, WS-04 | GP-4a |
| **WS-07** | Backup externo, restore verificável, alerta de atraso e expurgo agendado | P0-06, P2-06 (parcial) | F2 | WS-06, storage externo | GP-4b |
| **WS-08** | Ingestão RSS, publicação automática, OpenAI com teto e fallback local | P1-01, P1-02 | F3 | WS-01, WS-06, WS-07 | GP-5 |
| **WS-09** | Identidade e-mail/Google, Resend, newsletter, consentimento e LGPD | P1-04, P1-05, P1-06 | F4 | WS-05, WS-06 | GP-6 |
| **WS-10** | Premium mensal e Mercado Pago com ativação condicional | P1-07, P1-08 | F5 | WS-09, WS-06, credencial, plano na Central | GP-7 (independente de GP-10) |
| **WS-11** | AdSense, Consent Mode, GA4, métricas internas, rotas, formulários, dependências frontend | P1-09, P1-10, P1-15, P1-16, P0-08, P2-04 | F6 | WS-05, WS-06 | GP-8 |
| **WS-12** | Community, credenciamento, B2B, Central/robôs e Admin | P1-11, P1-12, P1-13, P1-14, P2-07 (parcial) | F7 | WS-06, WS-08, WS-09 | GP-9 |
| **WS-13** | Hardening de segurança de aplicação (transversal) | P0-10, P2-02 | F3–F7 (dentro de cada lote) + consolidação em F8 | o lote que introduz a superfície | GP-10 (parcial) |
| **WS-14** | Testes, security review, observabilidade, soak, go-live e fechamento | P2-01, P2-03, **P2-05, P2-06, P2-07** | F6–F9 | **GP-5, GP-6 e GP-8 `pass` + GP-4b vigente** (entradas de GP-10); **GP-7 e GP-9 testados antes do go/no-go** (§12.2), mas **não** pré-requisito de GP-10. **Não** depende de "todos os WS anteriores": **WS-13** é transversal (executado dentro de cada lote, §12.1) e **WS-02/WS-04** entram pelos gates GP-1b e GP-2b, não por esta workstream | GP-10, GP-11 |

**Cobertura de P2 (fechada, para que nenhum item fique sem dono):** P2-01 e P2-03 em **WS-14** (GP-10); P2-02 em **WS-13**/WS-14; P2-04 em **WS-11** (GP-8); **P2-05** (testes de carga) em **WS-14** (GP-10); **P2-06** (runbook de restore recorrente) em **WS-07** (o runbook nasce em GP-4b) e **WS-14** (evidência recorrente arquivada no soak/go-live); **P2-07** (decisões editoriais e de direitos) em **WS-12** (canal de denúncia, atribuição e retirada) e **WS-14** (registro da decisão D-04 no go/no-go).

### 3.2 Modelo de subagentes (papéis, não pessoas)

Cada workstream é executado por um **encadeamento de subagentes independentes**. Nenhum papel aprova o próprio trabalho.

| Papel | Subagente | Pode | Não pode |
|---|---|---|---|
| **executor** | `executor` (1 por lote) | Escrever **apenas** os arquivos da lista de escrita autorizada do contrato do lote; rodar comandos de leitura e os comandos de validação do lote | Ampliar escopo; tocar `.github/` no lote P0-1/F0 e nesta fase do programa; escrever `run-state.json` (é do orchestrator, AC-10); acessar a VPS sem runbook aprovado; corrigir achado de teste sem novo lote |
| **tester** | `tester` (independente do executor) | Executar critérios de aceite, produzir evidência, declarar `passed`/`failed`/`blocked` | Corrigir código; aprovar o próprio lote |
| **reviewer** | `reviewer` (independente; **sem** `Write`/`Edit`) | Produzir `code-review-contract.md` com findings ordenados e veredito; checar gatilhos de `review-triggers.md` | Editar código; reimplementar o lote |
| **remediator** | `remediator` (acionado só por finding major/blocker) | Corrigir findings dentro do escopo; devolver para reteste | Introduzir escopo novo; "melhorar" código adjacente |
| **documenter** | `documenter` | Atualizar docs **a partir do que foi validado**; produzir runbooks e `documentation-update.md` | Documentar o planejado-como-feito |
| **historian** | `historian` | Fechar a run no **fechamento F9**: `run-state.json` com estado `closed`, `report.md` e linha em `state/HISTORY.md` (append-only) | Implementar ou revisar; **atualizar `run-state.json` durante o programa** — isso é do orchestrator |

> **`run-state.json` tem um dono único: o orchestrator.** A partir da revisão 3 do contrato do lote P0-1, nenhum **executor** escreve esse arquivo: ele é atualizado **depois** do lote, pelo orchestrator, com base em evidências, veredito do tester e `code-review-contract.md`. Isso elimina o conflito entre "diff confinado" (AC-9) e a antiga exigência de o executor atualizar o estado da run.
>
> **Sequência de escrita, sem sobreposição:** (1) durante todo o programa — F0 a F8 — **só o orchestrator** atualiza `run-state.json`, depois de cada lote; (2) no **fechamento F9** — **o historian** faz a **única** escrita dele próprio, registrando o desfecho **já decidido** e o estado `closed` da run; (3) o **executor nunca** escreve, em nenhuma fase. Duas lacunas de escrita em uma mesma fase são finding na revisão.

Regras de Independence e de teto:

- `executor` e `tester` **não** podem ser a mesma instância nem compartilhar contexto de execução do lote.
- `reviewer` **não** executa comandos que alterem estado e **não** edita arquivos.
- Loop de remediação tem **teto de 3 iterações** (`iteration_count` / `max_iterations: 3`). Ao estourar, o run escala para o solicitante com o finding aberto e a decisão pedida — não se insiste nem se relaxa o critério.
- Todo lote que dispare gatilho de `review-triggers.md` **precisa** de `reviewer` antes de fechar. Na prática, nesta run, os lotes de **autenticação (WS-09), cobrança (WS-10), dados pessoais (WS-09/WS-11), migrations (WS-06 e qualquer lote com migration), API pública (WS-08/WS-11/WS-12), regras de publicação sem revisão (WS-08), credenciamento/moderação (WS-12), B2B (WS-12), dependência nova (WS-11, `next` upgrade) e volume de diff > ~300 linhas** são revisão obrigatória.

### 3.3 Gates de passagem (definição)

Um gate é `pass` quando **todos** os itens abaixo são verdadeiros e registrados em artefato com evidência:

1. Contrato de lote aprovado antes da execução; diff real confinado à lista de escrita autorizada.
2. Critérios de aceite do lote verificados por `tester` independente, com evidência (saída de comando, arquivo, captura) — não com afirmação.
3. `code-review-contract.md` emitido quando houver gatilho, com **zero blocker e zero major aberto** (ou todo major explicitamente aceito pelo solicitante, por escrito, com risco nomeado).
4. `implementation-history.md` do lote completo: comandos executados, decisões, alternativas descartadas, evidência de read-only quando aplicável.
5. Documentação e runbook correspondentes atualizados por `documenter`.
6. Rollback do lote **testado** ou, se não testável no ambiente, documentado com o motivo honesto do porquê.
7. Dependências humanas do gate resolvidas, ou a fase declarada bloqueada com `blocked_reason` preenchido no `run-state.json` (pelo orchestrator).
8. Registro explícito de tudo que ficou **fora** e do que **não** foi verificado (proibido "verde por ausência de evidência").
9. **Sem gate circular:** nenhum gate pode depender, direta ou indiretamente, de um item que só pode ser executado **depois** dele. **G1** (verificação de `settings.py`) é executado em **WS-01**, depois de GP-0, e alimenta **GP-1/GP-1b**; GP-0 fecha com **G0, G2, G3, G4, G5**.
10. **Regra do risco aceito:** um gate que dependa de um risco explicitamente **aceito** fecha quando o **aceite está registrado e assinado** no go/no-go correspondente — nunca porque o risco foi "resolvido". Hoje o único caso é **R-1** (linha do go/no-go em §15.2).
11. **Estado Git é re-derivado, nunca herdado de snapshot:** todo gate cuja decisão dependa do estado do repositório re-deriva branch, `HEAD`, `origin/*`, refs, `status` e a presença do objeto `4c57ff04` **antes** de passar, e registra o **timestamp** da medição ao lado do snapshot (§4.1.1 para GP-0; §4.3 para GP-1). Gate que passa com base em SHA, paridade ou contagem **herdada** de um documento é **finding**.

**Estado dos gates hoje:** GP-0 **pendente** (decisões humanas G0, G2, G3, G4, G5 abertas e **re-verificação fresca ainda não executada**; G1 **não** faz parte de GP-0), GP-1 **pendente** (lote P0-1 não executado), demais **não iniciados**.

---

## 4. Fase 0 — Reconciliação, proveniência e execução do lote P0-1

### 4.1 Contexto e por que esta fase existe

A reconciliação (`provenance-reconciliation.md`) terminou como **inventário com conflitos abertos e não resolvidos**. Ela deixou quatro fatos que governam todo o programa:

1. O working tree contém **WIP de outra run** (`20260925-1020-observabilidade`) que **não está em nenhuma branch nem commit** — `backend/config/{observability,metrics,health}.py` são não rastreados e `middleware.py` (rastreado) depende deles. Um `git clean -fd` quebraria o backend; um `git checkout --` deixaria estado incoerente.
2. `backend/config/settings.py` foi **corrompido e depois reparado sem origem registrada** (mtime posterior à janela da run 1020). Estado atual: *parseia*, mas **não há validação funcional**. Não se afirma que está correto.
3. **`develop` × `origin/develop` × `.git/packed-refs` podem divergir entre si**, existe um worktree registrado como `prunable` (`/tmp/opencode/wt-merge`) e existe o commit `4c57ff04`, **sem qualquer branch que o contenha** — *(afirmação de planejamento, **não** confirmada no estado re-derivado: ver §4.1.1 e §4.6.1)*.
4. Modificações rastreadas de **origem não determinada** (§4.4 da reconciliação) existem e não podem ser descartadas sem decisão.

**Fase 0 não entrega nada que o usuário veja. Ela entrega a condição para que todo o resto seja auditável.** Sem ela, um rollback em produção é uma aposta.

### 4.1.1 Estado Git re-derivado — leitura apenas, carimbada em 2026-09-25T18:32:47Z (15:32:47 -03:00)

> **Este bloco é um snapshot datado, não uma verdade permanente.** O repositório pode avançar a qualquer momento (outro lote, outra run, CI, operação humana). **Todo gate que dependa do estado Git o re-deriva antes de passar** (§4.2.1 para GP-0; §4.3 para GP-1). **Nenhum SHA deste bloco é SHA de release**, e nenhum valor aqui está fixado como premissa de execução.
>
> Derivado **somente** com comandos de leitura: `git rev-parse HEAD`, `git rev-parse --abbrev-ref HEAD`, `git for-each-ref`, `git rev-parse origin/develop`, `git rev-list --left-right --count origin/develop...develop`, `git status --porcelain=v1 -uall`, `git log`, `git cat-file`, `git branch -a --contains`, `git rev-list --all`, `git reflog --all`, `git worktree list`, `git stash list`. **Nenhum comando Git de escrita foi executado** e nenhum snapshot antigo foi reaproveitado.

| Fato observado | Valor **observado** (snapshot) | Comando de leitura que o reproduz |
|---|---|---|
| Branch corrente e `HEAD` | `develop` @ `7715dae8cc1a128e5992245ba636036c8a967f28` | `git rev-parse --abbrev-ref HEAD` · `git rev-parse HEAD` |
| `origin/develop` | `7715dae8cc1a128e5992245ba636036c8a967f28` — **igual ao `HEAD`** | `git rev-parse origin/develop` |
| Divergência `develop` × `origin/develop` | `0` atrás / `0` à frente — **`develop` NÃO está à frente do remoto neste estado** | `git rev-list --left-right --count origin/develop...develop` |
| Commits `948a5b5` e `645aca3` | **já contidos em `origin/develop`** ⇒ **não há push pendente** neste estado | `git branch -a --contains 948a5b5` · `git branch -a --contains 645aca3` · `git log --oneline origin/develop..develop` |
| Refs (locais e remotas) | Locais: `develop` `7715dae8` · `main` `bb63cb3d` · `observability-20260925-1020` `d1e04564` · `fix/ingestao-timeout-500` `f2a3ae5b` · `perf/custo-performance-p0-p2` `6e61a97d`. Remotas: `origin/develop` `7715dae8` · `origin/main` `bb63cb3d` · `origin/fix/ingestao-timeout-500` `f2a3ae5b` · `origin/homolog-retest` `7eaa8bb` · `origin/HEAD` `bb63cb3d` · `origin/backup/*` (3 backpoints de 2026-09-04) | `git for-each-ref --format='%(refname) %(objectname)' refs/heads refs/remotes` |
| `origin/develop`: ref solta × `packed-refs` | Solta `7715dae8` × empacotada obsoleta `b671a86` (2026-09-19) — **a divergência "duas camadas de verdade" continua existindo**, agora com a ref solta à frente | `git rev-parse origin/develop` · leitura direta de `.git/packed-refs` |
| `origin/main`: ref solta × `packed-refs` | Solta `bb63cb3d` × empacotada obsoleta `cbe161e` | idem |
| `4c57ff04` | Objeto **existe** (`git cat-file -t` → `commit`; parent `d1e04564`; árvore idêntica à de `948a5b5`) e é ***dangling***: `git for-each-ref --contains` **vazio**, ausente de `git rev-list --all` e **ausente do reflog** (`git reflog --all` **não** o menciona) ⇒ **recuperável apenas pelo SHA**, não por reflog | `git cat-file -p 4c57ff04` · `git for-each-ref --contains 4c57ff04 --format='%(refname)'` · `git rev-list --all \| grep -c '^4c57ff04'` · `git reflog --all \| grep -c 4c57ff04` |
| Worktree `wt-merge` | Ainda **registrado** em `git worktree list` como `prunable` (`main` @ `bb63cb3d`), mas o **diretório não existe mais** em disco | `git worktree list` · `ls -d /tmp/opencode/wt-merge` |
| `stash` | vazio | `git stash list` |
| Working tree | **8 arquivos rastreados modificados** e **21 não rastreados** (29 entradas), entre eles artefatos das runs `20260924-1535-arquivar-ingestao`, `20260924-2136-ingestao-noticias`, `20260925-1020-observabilidade` e desta run | `git status --porcelain=v1 -uall` |
| `.gitignore` | **Nenhuma regra** para `agentic-framework/state/` — o diretório de estado das runs é **não rastreado por definição** | leitura de `.gitignore` |

**Leitura honesta — três afirmações do planejamento que este estado NÃO sustenta** (corrigidas neste documento, com registro em §4.6.1):

1. **`develop` não está 2 commits à frente do remoto.** Está **em paridade** (`0/0`) com `origin/develop`, e os dois apontam para `7715dae8`.
2. **`948a5b5` e `645aca3` não precisam de push.** Ambos são ancestrais de `origin/develop`/`develop`; o que ainda precisa de decisão humana é a **política de promoção**, não o envio desses commits.
3. **`4c57ff04` não está no reflog.** É ***dangling***: existe como objeto, nenhuma ref o contém e o reflog não o menciona — recuperável **por SHA** (e por árvore idêntica à de `948a5b5`), não por reflog.

**Sobre `provenance-reconciliation.md`:** é um artefato de **planejamento** e **não foi editado** nesta remediação. Ele permanece válido como inventário de arquivos, de atribuição e de riscos; **suas afirmações sobre estado Git são snapshot datado** e valem apenas o que §4.1.1 mede, devendo ser lidas junto deste bloco.

### 4.2 WS-00 — Reconciliação e custódia (P0-01, parte)

- **Objetivo:** cada arquivo modificado/não rastreado tem **dono** (run de origem ou "origem não determinada — exige decisão humana"), e o WIP não rastreado está **preservado fora da árvore** antes de qualquer discussão de limpeza. O WIP da run `20260925-1020-observabilidade` é tratado como **isolado** desta run: não é adotado, não é reaproveitado e não é fechado aqui.
- **Entradas:** `provenance-reconciliation.md` §2, §4, §7, §8 (G0–G5), §9.
- **Sequência (a ordem importa):**
  1. **G0 — custódia física do WIP (bloqueante absoluto).** Mecanismo de preservação **decidido por humano** (patch a partir de `HEAD` dos 5 arquivos de `backend/config/` + cópia dos artefatos da run 1020; ou branch dedicada; ou backup externo nomeado). Nenhum comando Git de escrita é executado por agente no lote P0-1/F0. **Enquanto G0 não estiver fechado, nenhuma operação de limpeza é discutida.**
  2. **G2 — formalização dos artefatos de estado da run 1721 e política de promoção:** fechar a fase `documentation`, versionar `run-state.json`, `ARCHITECTURE.md` e `PROD_DECISOES.md` (ou descartá-los com decisão registrada) e **decidir a política de promoção** entre `develop`, `main` e HOMOLOG. **Divergência registrada com o planejamento (addendum 2026-09-25):** no estado re-derivado (§4.1.1) `948a5b5` e `645aca3` **já estão contidos em `origin/develop`** e `develop` está **em paridade** com o remoto (`0/0`) — **não há push pendente**. O objeto de G2 é a **política de promoção** e a **atribuição dos artefatos de estado**, não "se faz push". Se a re-verificação fresca (§4.2.1) mostrar divergência entre `develop` e `origin/develop`, a decisão de push **reabre** como item de G2. *(`948a5b5`/`645aca3` são **snapshots datados**; o SHA de release é **re-derivado** e confirmado — ver **D-08** e **HD-3**.)*
  3. **G3 — decisão humana sobre refs (bloqueante, sem automação):** decidir o destino da divergência **ref solta × `.git/packed-refs`** ainda presente — `origin/develop` (`7715dae8` solta × `b671a86` empacotada, obsoleta) e `origin/main` (`bb63cb3d` × `cbe161e`) no estado re-derivado de §4.1.1 — e o destino de `4c57ff04` (***dangling*, recuperável só por SHA**, ausente do reflog), da branch `observability-20260925-1020`, `fix/ingestao-timeout-500`, `perf/custo-performance-p0-p2`. A run 1721 já registrou: limpeza de refs **somente com decisão humana**. **Os SHAs citados são snapshot:** a re-verificação fresca (§4.2.1) redefine os valores **antes** de GP-0 passar.
  4. **G4 — saneamento do worktree `wt-merge`/`main`**, estritamente após G3. No estado re-derivado (§4.1.1) `git worktree list` **ainda registra** `/tmp/opencode/wt-merge` como `prunable` (`main` @ `bb63cb3d`), embora o **diretório não exista mais** em disco: a decisão é sobre a **entrada do registro**, e **nada de conteúdo é apagado** (`prune`/`gc` seguem proibidos ao agente).
  5. **G5 — atribuição das modificações pendentes** (§4.4 da reconciliação: `subir-localhost.sh`, `backend/feed/views.py`, `backend/feed/tests/test_p1_feed_cache_indices.py`, `backend/catalogo_noticias/services/deduplicacao.py`, `agendar_ingestao.py`, artefatos da run 1535). Cada item: atribuído a uma run, versionado, ou declarado órfão com decisão registrada. **Nada é inventado e nada é descartado por agente.** *A lista acima é a do snapshot de planejamento: a re-verificação fresca (§4.2.1) reconcilia com o `git status` atual — no estado re-derivado de §4.1.1, `ARCHITECTURE.md` e `PROD_DECISOES.md` **já não** aparecem como modificados, enquanto `backend/config/settings.py` e `backend/config/middleware.py` aparecem; nenhum item novo pode ficar sem dono.* G5 **inclui** o **inventário e o *ownership* do artefato não rastreado `agentic-framework/state/run-20260925-1433-go-live-producao/`** (artefato de planejamento desta run, **fora de qualquer release**, re-derivado em cada gate) — resolvido por **inventário + decisão de ownership**, e **sem editar `.gitignore`**, que permanece **intocado** neste programa sem contrato próprio.
- **G1 não é executado aqui.** **G1 — validação de `settings.py`** é executada **dentro de WS-01/lote P0-1**, ou seja, **depois** de GP-0, e seu desfecho alimenta **GP-1** e **GP-1b** (ver §4.3 e §4.4). Mantê-lo em GP-0 tornaria o gate circular, já que o lote só pode ser delegado depois de GP-0.
- **G6 e G7 (reconciliação, §8) — o que são, e por que não são gate de decisão aqui:**
  - **G6 — formalização do WIP da run 1020 como lote próprio** (posterior ao go-live ou em janela própria), incluindo o **desfecho** da run 1020: manter aberta para continuação, ou encerrar como abandonada **preservando os artefatos**, com `run-state.json` coerente. **Não** é gate de GP-0: é follow-up de orquestração, registrado como **HD-5**. O desfecho é **decidido pelo solicitante**; o **F9 apenas registra** o desfecho já decidido — **inclusive a run 1020 mantida aberta** para continuação — e **nenhum artefato desta run afirma que a run 1020 foi fechada** por ela.
  - **G7 — critérios de aceite de proveniência do contrato mestre** (**AC-1 e AC-2** de `implementation-contract.md`, que correspondem a `P0-01` e `P0-09`). **Não** é decisão humana nem gate de GP-0. Cobertura por gate, sem exagerar o alcance:
    - **AC-1** (`implementation-contract.md`; working tree sujo/untracked é reprovado, release rejeitada com a lista de arquivos e o motivo): **coberto por GP-1** — o gate determinístico do lote reprova working tree sujo e untracked, e o resultado é lido em **GP-1b**.
    - **AC-2** (`implementation-contract.md`; mesmo SHA validado em DEV, HOMOLOG e PROD): **parcialmente coberto por GP-1** — o gate é `repo-only`, roda em um único checkout e **não** lê os três ambientes. A **evidência do mesmo SHA nos três ambientes** é coletada em **GP-4a** (isolamento e configuração por ambiente) e em **GP-10** (suíte e smoke por domínio em todos os ambientes) e verificada no **go/no-go** (§15.2: `git status` de DEV/HOMOLOG/PROD mostrando o mesmo SHA).
- **Subagentes:** `orchestrator` (orquestra e escala), `documenter` (registra decisões e devidos), `historian` (linha em `HISTORY.md` para o desfecho da 1020, se houver). **Nenhum `executor` de código.**
- **Saídas:** inventário com atribuição por run + comandos de reprodução; registro das decisões humanas G0, G2, G3, G4, G5; `run-state.json` sem `blocked_reason` pendente de provenance — **atualizado pelo orchestrator, não por executor** (AC-10).
- **Gate GP-0:** **G0, G2, G3, G4 e G5** fechados com decisão humana registrada; **re-verificação fresca de G0–G5 executada e registrada imediatamente antes de fechar** (§4.2.1); nenhum arquivo protegido tocado; nenhum comando Git de escrita executado por agente; nenhum reset/clean/stash/checkout executado. **G1, G6 e G7 não participam de GP-0.**

### 4.2.1 Re-verificação fresca de G0–G5 antes de GP-0 (sem circularidade)

As decisões G0–G5 são tomadas sobre um estado Git que **envelhece**. **GP-0 não fecha com um snapshot de planejamento:** imediatamente antes de decidir o fechamento, o `orchestrator` **re-deriva** o estado e registra o resultado, com **timestamp**, no inventário de **WS-00** — o mesmo artefato que já é saída de WS-00, de modo que **GP-0 não passa a depender de nenhum artefato do lote P0-1**.

A re-verificação é **barata e read-only** (comandos de leitura, sem escrita, sem rede):

```bash
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git rev-parse origin/develop
git rev-list --left-right --count origin/develop...develop
git for-each-ref --format='%(refname) %(objectname)' refs/heads refs/remotes
git status --porcelain=v1 -uall
git cat-file -t 4c57ff04 2>/dev/null || echo 'AUSENTE: objeto 4c57ff04 nao existe mais'
git for-each-ref --contains 4c57ff04 --format='%(refname)' 2>/dev/null
git rev-list --all | grep -c '^4c57ff04'      # esperado: 0 (dangling)
git reflog --all | grep -c '4c57ff04' || true # esperado: 0 nesta observacao
git worktree list
git stash list
```

**O que GP-0 passa a exigir, em cima do GP-0 de §4.2:**

1. branch e `HEAD` re-derivados **iguais** ao estado sobre o qual G0/G2/G3/G4/G5 foram decididos; se **divergirem**, a G correspondente é **reaberta** antes de GP-0 passar;
2. `origin/develop` re-derivado e a paridade `develop` × `origin/develop` **registrada como observação**, sem valor fixado (no snapshot de §4.1.1: `0` atrás / `0` à frente);
3. refs re-derivadas: a divergência **ref solta × `packed-refs`** continua **pendência de G3**, nunca fato resolvido;
4. `git status --porcelain=v1 -uall` re-derivado e conciliado com a atribuição de **G5** — nenhum item novo sem dono, incluindo o inventário/ownership do diretório de estado desta run (§4.2, G5);
5. `4c57ff04` reconferido **por SHA**: presente ⇒ segue ***dangling*** e o destino é o decidido em G3/**D-08**; **ausente ⇒ finding de perda de objeto**, porque a árvore é idêntica à de `948a5b5` e a origem do cherry-pick deixa de ser recuperável;
6. **timestamp** da re-verificação gravado no artefato de WS-00, ao lado do snapshot de §4.1.1.

**Sem circularidade:** GP-0 depende **apenas** de decisões humanas G0, G2, G3, G4, G5 e desta re-verificação de comandos de leitura — **nada** que só WS-01 produza. A re-derivação **detalhada** (baseline do release, inventário atribuído item a item, evidência de `settings.py`, prova de não-vazamento com literal sintético) fica em **WS-01/GP-1** (§4.3) e é executada **depois** de GP-0. **G1 continua fora de GP-0.**

### 4.3 WS-01 — Lote P0-1 "Proveniência e gate de release" (`repo-only`)

Contrato de lote já escrito: `lote-p0-1-proveniencia.md` (**revisão 3**). Este plano **não reescreve** o contrato; define ordem, gates e a divisão de papéis dentro dele.

- **Objetivo:** (1) baseline de proveniência re-derivada e atribuída, sem criar documento paralelo; (2) **verificação** (não correção) de `settings.py` — este é o gate **G1**; (3) script `scripts/release/verificar-proveniencia.sh` **read-only, determinístico e fail-closed**; (4) registro de **R-1** como risco **aceito, aberto, não mitigado, não coberto pelo gate e não bloqueante**, com assinatura exigida no go/no-go, e registro da **divergência de domínio** (canônico `.com` × `portal-noticias.com.br` dos workflows); (5) documentação restrita às decisões do lote.
- **Entrada:** GP-0 `pass` (G0, G2, G3, G4, G5 fechados); contrato `lote-p0-1-proveniencia.md` rev. 3 aprovado. **G1 é executado aqui, depois de GP-0** — não antes, e não dentro de GP-0.
- **Ordem de execução dentro do lote:**
  1. Inventário de baseline com **re-derivação detalhada** do estado Git (§4.1.1: branch, `HEAD`, `origin/*`, `rev-list --left-right --count`, todas as refs, `status --porcelain=v1 -uall`, presença de `4c57ff04`, `worktree list`, `stash list`), com **timestamp** da medição → escolha documentada entre **estender `provenance-reconciliation.md` aditivamente** ou **criar `lote-p0-1-evidencias.md`** (nunca um terceiro artefato); justificativa no `implementation-history.md`. SHA de release **re-derivado** com `git rev-parse HEAD` (o `645aca3` dos outros artefatos é snapshot datado, **não** SHA de release). **O diretório de estado desta run, `agentic-framework/state/run-20260925-1433-go-live-producao/`, é artefato de planejamento não rastreado, fora de qualquer release:** ele é **inventariado e atribuído** (ownership desta run, G5) e **re-derivado** a cada execução — **sem editar `.gitignore`**, que é intocado neste programa.
  2. **G1 —** verificação de `settings.py` com `ast.parse` + `compile()` em memória, `PYTHONDONTWRITEBYTECODE=1`; `manage.py check` **apenas** se o ambiente permitir sem rede/banco/segredo, senão `SKIP` com motivo exato. Prova de que nenhum `__pycache__`/`.pyc` foi criado. **Nenhuma edição do arquivo.** Resultado registrado para **GP-1** e **GP-1b**.
  3. Criar o script do gate, executável, sem rede, sem segredo, sem escrita, sem `jq`/`shellcheck`/`actionlint` obrigatórios. Fail-closed quando `python3`/PyYAML ausentes. Saída estável para diff: sem timestamp, sem cor fora de TTY, findings ordenados.
  4. **Caso negativo obrigatório:** no working tree atual (que tem modificados e untracked), o gate **deve falhar com exit 1** e listar as razões. Gate que passa aqui é **blocker**.
  5. Provas de read-only (`git status` antes/depois idêntico) e de **não-vazamento**: a prova usa um **literal sintético real** gravado em um **arquivo rastreado de um repositório de fixture descartável, fora do repositório do portal** (nenhum comando Git de escrita é executado dentro do repositório do portal), e exige **três** resultados: (a) o literal **está** no arquivo rastreado (controle positivo, para o teste não ser vazio); (b) o gate **reporta** o achado com identificador de regra, caminho e linha; (c) o valor **não** aparece em `stdout`, em `stderr` nem em `--json`, em nenhum modo. Comandos exatos em `lote-p0-1-proveniencia.md` §"Comandos de validação", item 3. **Não** existe placeholder de texto no lugar do literal.
  6. Prova de que `.github/` está **byte a byte idêntico** (checks por status/diff e `sha256sum` de todos os arquivos de `.github/`), incluindo **nenhum valor de domínio** alterado; registro da divergência `.com` × `.com.br` como pendência.
  7. Prova de que **`run-state.json` não aparece no diff do executor** (AC-10) — o estado da run é atualizado pelo **orchestrator depois** do lote.
  8. Documentação seccionada em `CI-CD.md`, `PROD_DECISOES.md`, `infra/DEPLOY.md`, contendo **apenas** o que este lote decide: uso, exit codes, cobertura e **não**-cobertura, o gate **não roda em nenhum pipeline**, **eficácia condicional** à branch protection (HD-2), **R-1 aceito e aberto com assinatura exigida no go/no-go**, e a divergência de domínio registrada.
- **Subagentes:** `executor` (repo-only) → `tester` (caso negativo, read-only, não-vazamento, AC-2, AC-9, AC-10) → `reviewer` (quatro eixos: **CI/CD não-regressão**, **segurança do gate**, **veracidade documental**, **custódia de `run-state.json`**; finding de "risco PR → VPS resolvido" é **blocker**) → `remediator` se houver major/blocker → `documenter`.
- **Saídas:** `implementation-history.md`, `lote-p0-1-evidencias.md`, `scripts/release/verificar-proveniencia.sh` (executável), acréscimos seccionados em `CI-CD.md`/`PROD_DECISOES.md`/`infra/DEPLOY.md`. **`run-state.json` não está entre elas.**
- **Gate GP-1:** todos os AC-1..AC-10 do contrato do lote **passed**; `.github/` inalterado; R-1 registrado como **aceito e aberto** (nunca como resolvido); revisão aprovada; `blocked_reason` preenchido pelo orchestrator se HD-2 estiver aberta (e nesse caso GP-1 passa **com pendência registrada**, não como silêncio).

### 4.4 WS-02 — Integridade funcional de `settings.py` (P0-02 completo)

- **Objetivo:** sair do estado "*reparado, origem desconhecida, requer validação*" para **verificado e atribuído**.
- **Entrada:** resultado de **G1/AC-3**, executado no lote P0-1 (§4.3) depois de GP-0. **Desvios:** se `ast.parse`/`compile()` já passarem, o item pode ser encerrado como resolvido **por evidência**, sem lote de correção — decisão registrada pelo `orchestrator`.
- **Se houver correção de conteúdo:** lote próprio, com revisão obrigatória, cobrindo os blocos `OBSERVABILITY_*`, `ANALYTICS_*`, `CORS_EXPOSE_HEADERS`, `CORS_ALLOW_HEADERS`, `TECHNICAL_TELEMETRY_*`, sem `__pycache__`, com `manage.py check` e suite backend verdes, e sem misturar com o WIP da run 1020 sem reconciliação explícita.
- **Subagentes:** `executor` → `tester` → `reviewer` → `documenter`.
- **Saídas:** registro de validação (ou de correção validada) em `implementation-history.md`; diff de release limpo.
- **Gate GP-1b:** import da aplicação e `manage.py check` bem-sucedidos no SHA de release; nenhum arquivo de outra run sobrescrito; teste cobrindo as chaves novas verde.

### 4.5 Fase 0 — O que fica explicitamente **fora** daqui

Implementar correção de `settings.py` sem validação prévia; tocar `.github/`; fazer push/merge/rebase/reset/clean/stash/checkout; normalizar refs; podar worktree; acessar a VPS; criar branch/tag; fechar a run 1020 como se estivesse reconciliada; declarar "provenance resolvida" para a run inteira; **escrever `run-state.json` pelo executor** (é do orchestrator, AC-10); validar ou fixar host key (`known_hosts`, que é de **WS-03**/GP-2a); alterar qualquer valor de domínio em workflow; **editar `.gitignore`** — a exclusão do diretório de estado das runs do release é resolvida por **inventário e ownership** (G5/D-08), **nunca** por regra de ignore.

### 4.6 Decisão de não alterar o CI/CD — registrada, com suas consequências

**Decisão do solicitante (revisões 2 e 3 do `lote-p0-1-proveniencia.md`):** o CI/CD existente **não é alterado no lote P0-1/F0 nem nesta fase do programa**. Nenhum workflow, gatilho, job, `if`, `needs`, matriz, `environment` ou `secrets` em `.github/` pode ser editado, criado, movido ou removido, e **nenhum valor de domínio** em workflow pode mudar.

**Estado factual que essa decisão preserva:** `.github/workflows/deploy-homolog.yml` dispara em `pull_request`, delega a `deploy.yml` e implanta na **VPS persistente** em `/home/apps/portal-homolog` (3102/5102) com `git_mode: pr`, `pr_number` e `verify_ref` preenchido pela expressão de SHA do head do pull request (`github.event.pull_request.head.sha`). Ou seja: **o head de um pull request não aprovado pode chegar a uma máquina que hospeda ambiente e segredos.**

**Situação padronizada de R-1 (vale para os cinco artefatos desta run):** **ACEITO** (por isso **não bloqueia o go-live**) · **ABERTO** (**não** mitigado, **não** coberto pelo gate, **não** bloqueado) · **COM ASSINATURA OBRIGATÓRIA no go/no-go** (§15.2). Nenhum artefato pode marcá-lo como resolvido.

**Consequências que este plano carrega explicitamente, sem atenuar:**

1. O caminho **continua ativo**. Não foi mitigado, bloqueado ou compensado.
2. O gate de proveniência **não cobre** esse caminho: ele é `repo-only`, não participa de pipeline e não tem poder de veto por si só. Documentação que o apresente como proteção contra deploy de PR está **incorreta** e é finding.
3. Mesmo com branch protection (HD-2), o gate **não** vira required status check, porque isso exigiria registrá-lo em um workflow — proibido no lote P0-1/F0 e nesta fase do programa. **HD-2 e HD-6 são pré-requisitos de eficácia, não de entrega, e não bloqueiam o go-live** (limitação registrada como R-11).
4. **Divergência de domínio registrada:** o canônico do programa é `https://portal-noticias.com/`, e os workflows existentes usam `portal-noticias.com.br` (hosts de DEV/HOMOLOG/PROD e `www`). Nenhum valor é alterado aqui; a correção é **lote posterior**, sem mudar estrutura nem gatilhos (risco **R-15**).
5. **Divergências entre artefatos registradas** em §4.6.1, não suavizadas.

#### 4.6.1 Divergências entre artefatos (não resolvidas, não suavizadas)

| Artefato | O que diz | Estado real no lote P0-1/F0 |
|---|---|---|
| `task-plan.md` §1, escopo "Release, proveniência e CI/CD" **(versão anterior)** | "Remover o caminho de deploy de PR para a VPS persistente" **(versão anterior)** | **Texto de versão anterior, não vigente nesta fase do programa:** a exigência antiga de remover o caminho PR → VPS **não** está em vigor no lote P0-1/F0 nem nesta fase do programa, por decisão do solicitante. O caminho **permanece ativo**; o risco é **aceito, aberto e não bloqueante** (R-1), com aceite assinado no go/no-go. A substituição futura é **D-03/HD-1**, em lote próprio. |
| `implementation-contract.md`, critério de aceite 4 **(versão anterior)** | "Dado um pull request… nenhum código não aprovado será implantado em uma VPS persistente com segredos" **(versão anterior)** | **Não satisfeito no lote P0-1/F0 nem nesta fase do programa.** O gate de proveniência não o cobre. Na v2 do contrato o critério foi reescrito como **desvio consciente de R-1** (aceito, aberto, assinatura no go/no-go): é um desvio **declarado e assinado**, não uma tarefa em aberto nesta fase. |
| `backlog.md` P0-09, saída verificável **(versão anterior)** | "PR não implanta código não aprovado" **(versão anterior)** | **Reescrito** no backlog: a saída verificável passa a ser o gate read-only entregue + o registro de que o caminho PR → VPS **permanece ativo** e de que R-1 está **aceito e aberto**. A frase antiga não descrevia o estado real. |
| `lote-p0-1-proveniencia.md`, DoD **(versão anterior)** | "`run-state.json` atualizado com o estado do lote" **(versão anterior)** | **Resolvido na revisão 3** sem tocar em código: `run-state.json` é **do orchestrator** durante o programa, atualizado **após** o lote e **fora** do diff do executor (**AC-10**), com escrita do historian apenas no fechamento F9. O conflito com AC-9 deixou de existir. |
| `action-plan.md` §4.1, item 3 **(snapshot de planejamento anterior)** | "`develop` está **2 commits à frente** do remoto" e "`4c57ff04` recuperável **só por reflog**" **(snapshot de planejamento anterior)** | **Não confirmado no estado re-derivado (§4.1.1, medido em 2026-09-25T18:32:47Z):** `develop` está **em paridade** com `origin/develop` (`0/0`, ambos em `7715dae8`); `948a5b5`/`645aca3` **já estão** em `origin/develop` (sem push pendente); `4c57ff04` é ***dangling*** — **ausente do reflog**, sem ref que o contenha, recuperável **só pelo SHA**. O texto antigo é preservado como registro do que foi observado na reconciliação de planejamento, e **não** é premissa de execução. A divergência **ref solta × `packed-refs`**, essa sim, **continua aberta** e segue em G3/D-08. |
| `action-plan.md` §2.2 **(versão anterior)** | GP-7 na frente de GP-10, GP-9 sem dependência declarada **(versão anterior)** | **Corrigido** (achado M3): GP-5/GP-6/GP-8 convergem em GP-10; GP-9 depende de GP-5+GP-6; GP-7 depende de GP-4+GP-6 e é **independente** de GP-10; GP-10 **não** depende de GP-7. Desenho e tabela de dependências em §2.2. |
| `action-plan.md` §4.2 **(versão anterior)** | GP-0 incluía G1, que só é executado depois de GP-0 **(versão anterior)** | **Corrigido** (achado B1): GP-0 = G0, G2, G3, G4, G5; G1 executado em WS-01, alimentando GP-1/GP-1b. |
| `implementation-contract.md` e `task-plan.md`, referência a "subdomínios DEV/HOMOLOG" **(versão anterior)** | nomes de subdomínio pareciam decididos **(versão anterior)** | **Corrigido:** nenhum hostname de ambiente é afirmado sem decisão. Único valor de domínio do programa: `https://portal-noticias.com/`. Nomes de ambiente e alinhamento dos workflows são **D-01**/**R-15**, em lote posterior. |
| `implementation-contract.md`, não-objetivos | — | O caminho PR → VPS é **não-objetivo do lote P0-1/F0**, mas é **objetivo do programa** (D-03), com o risco aceito e aberto. Não confundir "fora do lote" com "resolvido". |

**Leitura da coluna "O que diz":** toda entrada marcada **(versão anterior)** ou **(snapshot de planejamento anterior)** cita texto que **não está vigente** — é registro histórico do que o artefato dizia antes da remediação, preservado para auditoria. **Nenhuma delas reabre uma tarefa**, e em particular **nenhuma** mantém em vigor a exigência antiga de remover o caminho PR → VPS: essa exigência está suspensa por decisão do solicitante (D-03/HD-1, em lote próprio com revisão de CI/CD), com o risco **aceito, aberto e não bloqueante** enquanto isso. **Nenhum dado de estado Git de snapshot antigo é premissa:** o estado efetivo é o de §4.1.1 e é **re-derivado** a cada gate (§4.2.1, §4.3).

**Regra de veracidade:** nenhuma entrega de Fase 0..F9 pode fechar com R-1 marcado como resolvido. O go/no-go (§15.2) **inclui** a linha "**R-1 aceito conscientemente, aberto, não mitigado, não coberto pelo gate, com aceite assinado nesta data**", e essa linha **nunca** é escrita como "resolvido".

### 4.7 Gate GP-0/GP-1/GP-1b — checklist

**GP-0 (custódia e reconciliação — decisões humanas, sem G1)**
- [ ] WIP da run 1020 preservado fora da árvore, mecanismo decido por humano, com evidência do caminho/branch/tag usada.
- [ ] Cada item de `§2.5`/`§2.6`/`§4.4` da reconciliação tem atribuição ou marcação "exige decisão humana" com responsável.
- [ ] **G0, G2, G3, G4 e G5** com decisão registrada; `blocked_reason` vazio.
- [ ] **Re-verificação fresca de G0–G5 executada imediatamente antes de fechar** (§4.2.1), com **timestamp** registrado no inventário de WS-00: branch, `HEAD`, `origin/develop`, paridade `develop` × `origin/develop` (registrada como observação, sem valor fixado), todas as refs, `status --porcelain=v1 -uall` conciliado com G5, presença de `4c57ff04` por SHA, `worktree list` e `stash list`. **Nenhum item novo sem dono.**
- [ ] **Inventário e ownership** do diretório de estado não rastreado desta run (`agentic-framework/state/run-20260925-1433-go-live-producao/`), declarado **fora de release** e **re-derivado**; **`.gitignore` não foi editado**.
- [ ] Nenhum reset/clean/stash/checkout/prune executado; nenhum arquivo protegido tocado; nenhum segredo exposto.
- [ ] **G1, G6 e G7 não foram usados como condição de GP-0** (G1 é executado em WS-01; G6 é follow-up de HD-5; G7 é satisfeito por GP-1).

**GP-1 (lote P0-1)**
- [ ] AC-1..AC-10 do contrato do lote: `passed` com evidência.
- [ ] Caso negativo do gate demonstrado (exit 1 no working tree sujo, com razões listadas).
- [ ] Prova de read-only e de não-vazamento registradas.
- [ ] `.github/` byte a byte idêntico; nenhum gate registrado em workflow; nenhum valor de domínio alterado; documentação afirma que o gate **não roda automaticamente**.
- [ ] **`run-state.json` ausente do diff do executor** (AC-10); estado da run a ser atualizado pelo orchestrator depois do lote.
- [ ] R-1 registrado como **aceito e aberto** (nunca como resolvido) em `PROD_DECISOES.md`, `CI-CD.md` e `implementation-history.md`, com a exigência de assinatura no go/no-go.
- [ ] Divergência de domínio (canônico `.com` × `.com.br` dos workflows) registrada como pendência.
- [ ] Revisão independente concluída sem blocker/major aberto.

**GP-1b (integridade funcional de `settings.py`, a partir de G1)**
- [ ] Resultado de G1 lido: import da aplicação e `manage.py check` verdes no SHA de release, **ou** item encerrado por evidência com decisão do orchestrator registrada.
- [ ] Se houve correção de conteúdo: lote próprio, revisado, cobrindo os blocos `OBSERVABILITY_*`, `ANALYTICS_*`, `CORS_EXPOSE_HEADERS`, `CORS_ALLOW_HEADERS`, `TECHNICAL_TELEMETRY_*`, sem `__pycache__`, sem misturar com o WIP da run 1020.

---

## 5. Fase 1 — Host, rede, TLS e domínio

**Premissa deste plano:** o estado do host, do DNS e do TLS é **desconhecido**. A reconciliação não acessou a VPS, e nenhum agente desta fase verificou servidor, portas, certificado ou DNS. **Não se assume que SSH, TLS, DNS ou firewall já estejam prontos.** O primeiro passo da fase é **descobrir**, não corrigir.

### 5.1 WS-03 — Identidade de acesso ao host (P0-03, P0-11)

- **Objetivo:** root por senha desabilitado, acesso por chave, usuário non-root para deploy/operação, nenhum processo root de aplicação, rotação da credencial root exposta, **e** validação com *pinning* da **host key** da VPS em `known_hosts` para todo acesso humano e do usuário de deploy.
- **Dependências humanas:** acesso seguro à VPS; canal seguro para a chave; disponibilidade do responsável por acesso; **decisão sobre perda de acesso** (se a rotação derrubar o acesso, quem restaura e como); **HD-7** (evidência de pinning aceita e quem a valida).
- **Sequência de execução (a ordem protege contra lockout):**
  1. Inventário **somente leitura**: usuários, `authorized_keys`, `PermitRootLogin`, `PasswordAuthentication`, processos root, portas em escuta, serviços ativos. Evidência antes de mudar.
  2. **Validar e fixar a host key antes de qualquer acesso automatizado:** obter a chave pública do host por canal confiável (fora da sessão que se quer validar), inseri-la explicitamente em `known_hosts` do operador e do usuário de deploy (sem `StrictHostKeyChecking=no` e sem `UserKnownHostsFile=/dev/null`), e confirmar que uma chave **divergente** é **rejeitada** — teste negativo obrigatório. Sem esse passo, "SSH por chave" continua vulnerável a *man-in-the-middle* na primeira conexão.
  3. Criar usuário non-root com chave própria e `sudo` **escopado** (apenas o necessário para deploy/PM2, não root irrestrito).
  4. Validar login do novo usuário **em sessão separada** e confirmar que a chave funciona.
  5. **Rotacionar** a credencial root exposta (não apenas desabilitar login).
  6. Desabilitar `PasswordAuthentication` e `PermitRootLogin yes`; recarregar SSH **sem derrubar a sessão atual**.
  7. Matar/reiniciar processos root de aplicação; registrar a lista final.
- **Evidência mínima a arquivar:** linha de `known_hosts` (com **impressão digital**, `SHA256:…`, e **sem** material de chave privada); saída do teste negativo de chave divergente; inventário antes/depois; registro de rotação; confirmação de que root por senha falha e a chave do usuário non-root funciona.
- **Limite honesto:** o caminho de **CI** continua usando autenticação por senha no `ssh-action` **sem impressão digital de host key** (`deploy.yml`), e isso **não** pode ser corrigido nesta fase do programa porque `.github/` é intocado. O pinning feito aqui vale para o **acesso humano e do usuário de deploy**; a divergência do caminho de CI é registrada como **R-16** e levada ao go/no-go.
- **Subagentes:** `executor` de infraestrutura (com runbook aprovado), `tester` (provas de acesso, de bloqueio e de rejeição de host key divergente), `reviewer` (segurança), `documenter` (runbook de acesso, de recuperação de lockout e de como revalidar host key).
- **Saídas:** runbook de acesso; inventário antes/depois; registro de rotação; `known_hosts` com impressão digital validada; confirmação de que root por senha falha, chave funciona e chave divergente é rejeitada.
- **Gate GP-2a:** root por senha **desabilitado e testado** (tentativa falha registrada), usuário non-root operacional, nenhum processo root de aplicação, inventário arquivado, **host key validada e fixada com teste negativo de divergência**, e divergência do caminho de CI registrada.

### 5.2 WS-04 — Exposição de rede (P0-04)

- **Objetivo:** firewall expondo apenas o necessário (SSH gerenciado + Nginx 80/443); portas de aplicação 3101–3103/5101–5103 **inacessíveis externamente**; Gunicorn/Next em loopback ou rede privada.
- **Dependências humanas:** **HD-4** (topologia de execução: loopback `127.0.0.1` vs rede privada entre Nginx e aplicação) e impacto em HOMOLOG. Bloqueante por decisão, não por técnica.
- **Sequência:** (a) confirmar topologia com o solicitante; (b) bind em loopback/rede privada; (c) regra de firewall **permitindo** primeiro, **bloqueando** depois; (d) teste de alcançabilidade externa das portas de aplicação (deve falhar) e de Nginx (deve funcionar); (e) smoke de leitura pública.
- **Subagentes:** `executor` infra, `tester` (teste negativo de alcance), `reviewer`, `documenter`.
- **Saídas:** evidência de `ss`/firewall antes e depois; registro do bind escolhido e por quê; regra de firewall versionada em `infra/nginx/` ou equivalente.
- **Gate GP-2b:** apenas Nginx (e SSH) expostos; portas de aplicação inacessíveis de fora; leitura pública funcionando; **exceção declarada se o bind em loopback for adiado** (e nesse caso, o risco é nomeado e entra no go/no-go).

### 5.3 WS-05 — Domínio canônico, DNS, TLS e edge (P0-05)

- **Objetivo:** `https://portal-noticias.com/` é o **domínio canônico do programa**; DNS apontando para a VPS; certificado válido; redirect HTTP→HTTPS; HSTS após janela aprovada; headers de segurança e CSP; cookies `Secure`/`HttpOnly`; `ALLOWED_HOSTS`/CORS coerentes. **Nenhum hostname de ambiente é inventado aqui:** os nomes de DEV/HOMOLOG/PROD ainda não foram decididos e, junto com o alinhamento dos valores de domínio existentes nos workflows (hoje `portal-noticias.com.br`), são **D-01**/**R-15**, resolvidos no lote que permite valores de domínio, **sem** mudar estrutura nem gatilhos de workflow.
- **Dependências humanas (bloqueantes, nenhuma assumida feita):**
  - **Domínio `portal-noticias.com` comprado e titularidade confirmada** pelo solicitante. Se ainda não comprado, a fase **para aqui** e o programa espera — não há como emitir TLS nem homologar sem domínio.
  - **Controle do DNS** (provedor, credencial, quem edita registros).
  - **Decisão D-01 (`www`)**: apex canônico, e `www` redireciona para apex (recomendado) ou vice-versa. Afeta DNS, cookies, CORS, redirect URI do Google OAuth, HSTS e métricas. **Nenhuma configuração de `www` é inventada por agente.**
  - **Decisão D-11 (HSTS)**: preload ou não; CSP em `Content-Security-Policy` estrito vs `Report-Only` primeiro. Afeta rollout de frontend.
  - **Decisão sobre os hostnames de ambiente** (DEV/HOMOLOG/PROD) e o alinhamento dos valores nos workflows: só no lote que permite valores de domínio, **sem** alterar gatilhos (**R-15**).
- **Sequência:** (a) confirmar titularidade e controle DNS; (b) apontar A/AAAA e validar propagação; (c) emitir certificado e configurar renovação; (d) ativar redirect e HSTS **após a janela aprovada** (o período de teste de HSTS pode quebrar hostnames de ambiente não preparados); (e) headers de segurança e CSP; (f) cookies `Secure`/`HttpOnly` e `ALLOWED_HOSTS`/CORS por ambiente; (g) smoke externo por domínio.
- **Subagentes:** `executor` infra, `tester` (validação de DNS/TLS/smoke, incluindo teste de redirect e de headers), `reviewer` (configuração de TLS/CSP/cookies), `documenter` (runbook de DNS/TLS, incluindo renovação e recuperação).
- **Saídas:** evidência de certificado válido e da cadeia; registro de redirect e HSTS; política de headers versionada; smoke por domínio; runbook de renovação.
- **Gate GP-3:** `https://portal-noticias.com/` resolve e serve TLS válido; HTTP redireciona; headers de segurança presentes; cookies seguros; smoke de leitura pública passa; D-01 e D-11 registradas (aplicadas ou explicitamente adiadas com motivo).

### 5.4 Fase 1 — dependências humanas e pré-condições (não assumir)

| Dependência | Estado | Se ausente |
|---|---|---|
| Domínio comprado com titularidade | **a confirmar** | Fase 1 e F2 travam; sem domínio não há homologação por nome nem TLS |
| Controle de DNS (provedor + acesso) | **a confirmar** | Sem DNS, sem certificado válido |
| Acesso seguro à VPS | **a confirmar** | Nada de WS-03/WS-04/WS-05 é executável |
| Decisão D-01 (`www`) | **pendente** | Não se configura `www` por conta própria |
| Decisão D-11 (HSTS/CSP) | **pendente** | HSTS não é ativado sem aprovação; sem HSTS não há go-live |
| Decisão sobre hostnames de DEV/HOMOLOG/PROD e alinhamento dos valores de domínio nos workflows (**R-15**) | **pendente** | Não se inventa nome de ambiente nem se altera valor em workflow nesta fase do programa |
| Decisão HD-4 (bind loopback) | **pendente** | WS-04 fica parcial e o risco é nomeado no go/no-go |
| Evidência de host key fixada (HD-7) | **pendente** | WS-03 fica parcial; a divergência do caminho de CI é nomeada no go/no-go |
| Janela aprovada para HSTS/redirect | **a aprovar** | Não ativar sem janela; registrar adiamento |

Nenhuma linha desta tabela pode ser marcada como concluída por agente. **Cada uma é confirmação humana com evidência** (printout de DNS, certificado emitido, captura de `ss`).

---

## 6. Fase 2 — Backup/restore e isolamento de ambientes

### 6.1 WS-06 — Isolamento de DEV/HOMOLOG/PROD (P0-07, P1-03)

- **Objetivo:** bancos, Redis, filas Celery, mídia, chaves de assinatura e segredos **separados por ambiente**, com teste **negativo** de leitura cruzada; workers/beat dedicados por ambiente; diretórios de mídia com ownership correto; expurgo agendado resolvido (implementado ou removido, nunca "agendado e inexistente").
- **Dependências:** WS-01 (gate de proveniência: release é reproduzível por ambiente), WS-04 (rede fechada), decisão de nomes/prefixos de ambiente.
- **Sequência:** (a) inventário do que hoje é compartilhado (banco, Redis, filas, mídia, chaves); (b) definir prefixos/nomes e instâncias por ambiente; (c) criar bancos/keys/filas/mídias; (d) replicar configuração por ambiente **a partir do versionado**, não "na mão"; (e) criar workers/beat dedicados e seus consumers; (f) **teste de isolamento que tenta** ler de um ambiente no outro e mostra que falha; (g) resolver expurgo; (h) readiness refletindo worker/beat parado como degradado, com alerta.
- **Subagentes:** `executor` (app + infra), `tester` (teste negativo de isolamento, filas por ambiente, degradação de worker), `reviewer` (**migrations e dados pessoais: revisão obrigatória**), `remediator` se necessário, `documenter` (matriz de isolamento e runbook de ambiente).
- **Saídas:** matriz de isolamento (recurso × ambiente); evidência do teste negativo; configuração de workers/beat por ambiente; política de expurgo; readiness com dependências.
- **Gate GP-4a:** leitura cruzada **impossível** entre ambientes; task Celery consumida só pelo worker/fila corretos; worker parado → degradado + alerta; migrations aplicadas com backup verificado e rollback documentado; nenhuma secret compartilhada; **evidência do SHA de release registrada por ambiente** (DEV, HOMOLOG e PROD), parte do critério 2 do contrato (**G7**, §4.2).

### 6.2 WS-07 — Backup externo e restore (P0-06)

- **Objetivo:** backup **diário** com saída externa **criptografada**, verificação de dump, alerta de atraso, e **restore mensal/pré-go-live em ambiente isolado** com RPO de 24h comprovado.
- **Dependências humanas:** **storage externo** definido e provisioned (com credencial e chave de criptografia gerenciadas por humano); **responsável e canal de alerta** de atraso; **decisão D-12** sobre retenção e custódia da chave.
- **Sequência:** (a) script de backup (PM2 conforme decisão existente) com verificação de dump e `exit code` significativo; (b) cópia externa criptografada com verificação de integridade pós-cópia; (c) alerta de atraso; (d) **restore em ambiente isolado** (nunca em PROD) com verificação de banco, migrations, contagens e aplicação; (e) registrar o **RPO real observado** (o alvo é 24h; o evidenciado é o que vale); (f) repetir o restore como evidência **antes do go-live** e incluir a evidência no go/no-go.
- **Subagentes:** `executor` infra, `tester` (restore isolado, contagens, RPO), `reviewer` (segurança do backup e custódia de chave), `documenter` (runbook de restore, inclui o caso "a VPS morreu").
- **Saídas:** backup com evidência de cópia externa; relatório de restore isolado; RPO evidenciado; runbook de restore; evidência de alerta.
- **Gate GP-4b:** backup diário com `exit 0` e dump verificado; cópia externa criptografada confirmada; restore bem-sucedido em ambiente isolado sem tocar PROD; RPO de 24h demonstrado; runbook de restore publicado; se qualquer item falhar, **o go-live não acontece** (gate duro).

### 6.3 Ordem interna da fase

`WS-06` antes de `WS-07`: isolar antes de copiar. Backup de um ambiente misturado não é backup de nenhum ambiente. E o restore só é confiável depois que o alvo do restore (ambiente isolado) existe e está isolado.

---

## 7. Fase 3 — Ingestão, editorial, OpenAI e fallback local

### 7.1 WS-08 (P1-01, P1-02)

- **Objetivo:** ingestão de **todas** as fontes RSS atuais, **publicação automática sem revisão humana**, sem erro de persistência por limite de campo; falhas isoladas por grupo/fonte; OpenAI com teto de gasto; **fallback local automático** quando o OpenAI falhar, marcado na telemetria; kill switch e bloqueios técnicos por fonte/categoria; nenhum conteúdo fictício em produção.
- **Dependências:** WS-01 (release limpo), WS-06 (filas/workers), WS-07 (backup antes de reprocessar), **credencial OpenAI** (humana; se ausente, o modo é 100% fallback local, que é um estado **válido** e testado).
- **Sequência de implementação e verificação:**
  1. **Limites de campo:** reproduzir `DataError` com `categoria` (e demais campos persistidos) > 100 caracteres; normalizar/rejeitar **antes** do `bulk_create`; falha de um grupo **não aborta** os demais; erros persistidos por fonte.
  2. **Backfill/reprocessamento** dos registros afetados — só depois de backup verificado (regra de migration/dados). Idempotente.
  3. **Isolamento de falhas por grupo** com registro do erro e métrica de falha (item com erro técnico **não é publicado silenciosamente**).
  4. **Concorrência:** lock de execução; segunda execução concorrente é rejeitada ou agregada.
  5. **OpenAI com teto:** limite de gasto/custo diário, métrica de custo, kill switch. Sem chave, o sistema **não quebra** — usa fallback.
  6. **Fallback local automático:** resumo gerado localmente, item publicado conforme as regras automáticas, **origem do resumo distinguível** em métrica/log (`openai` vs `local`).
  7. **Todas as fontes RSS atuais** habilitadas; sem fila de revisão humana na v1 (decisão do solicitante), mas com validações técnicas e bloqueios por fonte/categoria.
  8. **Kill switch** testado: parar a ingestão sem deploy e sem efeito colateral; registro de uso.
  9. **Nenhum conteúdo fictício:** varredura de `MOCK`/seed/notícia de exemplo em produção (cobre também P0-08 no backend).
- **Subagentes:** `executor` backend, `tester` (casos de campo grande, falha por grupo, concorrência, fallback, kill switch), `reviewer` (**regras de publicação sem revisão prévia: revisão obrigatória**; dados pessoais se o resumo ou a telemetria os carregam), `remediator`, `documenter` (runbook de ingestão, como reverter um item publicado, política de fallback).
- **Saídas:** correção de limites com teste de regressão; backfill executado e verificado; métricas de falha e de origem do resumo; kill switch e runbook; decisão registrada de que a publicação automática foi escolhida (com o risco editorial associado).
- **Gate GP-5:** todas as fontes processadas sem `DataError`; falha por grupo isolada e registrada; fallback local **executado de fato** em teste (com OpenAI indisponível) e distinguível; concorrência travada; kill switch testado; nenhum item com erro técnico publicado em silêncio; nenhum conteúdo fictício em PROD.

### 7.2 Nota editorial (risco, não bug)

Publicação automática de RSS agregado, sem revisão humana e sem revisão jurídica formal, é uma **decisão consciente**. Ela não é bloqueada aqui. O plano exige, em troca, que: (a) o kill switch exista e seja testado; (b) bloqueios técnicos por fonte/categoria existam; (c) o canal de denúncia e a atribuição estejam operacionais (parcialmente em WS-12); (d) a decisão de risco jurídico esteja registrada (§17 D-04); (e) **não** se declare conformidade legal em lugar algum.

---

## 8. Fase 4 — Identidade, Resend, Google e LGPD

### 8.1 WS-09 (P1-04, P1-05, P1-06)

- **Objetivo:** cadastro e login por e-mail com **tokens e throttling**; verificação de e-mail e recuperação de senha **via Resend** (entrega real); login **Google** com domínio OAuth de PROD; newsletter com entrega e **descadastro**; consentimento de cookies fail-closed; exclusão/anomização de conta auditada; páginas legais e rotas quebradas corrigidas; token de sessão/CSRF com `Secure`/`HttpOnly` em PROD.
- **Dependências humanas:** domínio configurado (WS-05) para SPF/DKIM do Resend e redirect URI do Google; **credencial Resend**; **credencial Google OAuth** (client id/secret + redirect URIs de DEV/HOMOLOG/PROD); **texto legal/privacidade** aprovado por humano (não por agente) e **decisão D-04** (risco jurídico) registrada. Credenciais nunca no repositório: só referência de existência.
- **Sequência de implementação e verificação:**
  1. E-mail: cadastro, token de uso único, throttling de envio e de tentativa; verificação entregue via Resend; token **nunca** em log de produção.
  2. Recuperação de senha: resposta **não revela** se a conta existe; link de uso único; registrar auditoria de solicitante.
  3. Troca de senha e **rotação de token** de sessão; cookie `Secure`/`HttpOnly`; CORS e `ALLOWED_HOSTS` por ambiente.
  4. Google OAuth: adapter conforme contrato, domínio OAuth de PROD, usuário criado/autenticado; **fluxo testado em DEV/HOMOLOG/PROD**.
  5. Newsletter: envio real, resposta de sucesso/erro, **descadastro**; sem submissão silenciosa.
  6. Consentimento: banner + fail-closed — sem consentimento, **nenhum** evento de produto e **nenhum** script publicitário sai.
  7. LGPD: exportação e exclusão/anomização conforme política configurada, **auditadas**; retenção e expurgo alinhados (WS-14/P2-02 connectam aqui).
  8. Rotas legais/páginas quebradas: corrigidas (cobre parte de P1-15; o resto em WS-11).
- **Subagentes:** `executor` backend + frontend, `tester` (tokens, throttling, não-revelação, OAuth por ambiente, descadastro, consentimento fail-closed, exclusão auditada), `reviewer` (**autenticação, sessão, dados pessoais: revisão obrigatória**), `remediator`, `documenter` (runbook de identidade, política de privacidade, procedimento de solicitação de exclusão).
- **Saídas:** fluxos de identidade testados por ambiente; entrega Resend comprovada nos três fluxos; OAuth funcional; consentimento fail-closed com teste; operação LGPD auditada; runbook de identidade/privacidade.
- **Gate GP-6:** cadastro, verificação e reset entregam **e-mail real**; resposta de reset não revela existência de conta; Google OAuth funciona em PROD; consentimento recusado ⇒ nenhum script/evento; exclusão auditada; tokens fora de log; cookies seguros em PROD.

---

## 9. Fase 5 — Premium e Mercado Pago

### 9.1 WS-10 (P1-07, P1-08)

- **Objetivo:** plano mensal **configurável na Central** (sem valor hardcoded no código); checkout Mercado Pago; webhook com **validação de assinatura**, referência e **idempotência**; cancelamento, renovação, inadimplência e **grace period**; sincronização de papel do usuário; **ativação de Premium bloqueada** até credenciais + sandbox + plano configurado; **fallback gratuito** quando o gateway está indisponível.
- **Dependências humanas:** **credencial Mercado Pago** (produção e sandbox); **plano Premium cadastrado na Central** pelo solicitante (nome, valor, duração, benefícios) — **decisão D-07**; quem aprova a ativação; decisão sobre cobrança em cenários de borda.
- **Sequência de implementação e verificação (sandbox antes de tudo):**
  1. Planos vêm da configuração/Central; nenhum valor no código; tentativa de assinar com plano inativo/sem credencial é **bloqueada com mensagem segura** e **não** concede Premium.
  2. Checkout em sandbox: assinar (aprovado, recusado, pendente, falha).
  3. Webhook: **assinatura válida** → aplica uma única vez e atualiza histórico; **assinatura inválida / referência desconhecida / payload malformado** → rejeita/ignora **sem alterar assinatura**.
  4. Idempotência: reprocessar o mesmo webhook não duplica; concorrência de callbacks não corrompe estado.
  5. Cancelamento: estado local e estado remoto **consistentes**.
  6. Renovação vencida: cobrança, estado Premium e histórico **idempotentes**; inadimplência e grace period respeitados.
  7. Sincronização de papel: Premium reflete no papel do usuário de forma consistente (e o logout/refresh limpa sessão — WS-12 cobre a invalidação de cache relacionada).
  8. **Fallback:** Mercado Pago indisponível na página de planos ⇒ Premium **permanece fechado** e o fallback gratuito é exibido.
  9. **Ativação condicional:** o flag de Premium só liga com credencial + sandbox verde + plano na Central. Sandbox verde sem plano ⇒ ainda fechado.
- **Subagentes:** `executor` backend + frontend, `tester` (matriz de estados + concorrência + repetição de webhook), `reviewer` (**cobrança/assinatura: revisão obrigatória**; o estado de pagamento é exclusivo), `remediator`, `documenter` (runbook de pagamento, reconciliação, o que fazer se o gateway cair).
- **Saídas:** checkout e webhook testados em sandbox com assinatura; idempotência comprovada; plano na Central; flag de ativação com pré-condições; runbook de reconciliação financeira.
- **Gate GP-7:** todos os estados de assinatura e webhook testados; nenhum acesso Premium concedido sem plano ativo; gateway indisponível ⇒ Premium fechado + fallback; sincronização de papel consistente; revisão de pagamento aprovada.

### 9.2 Relação com o go-live

Premium é **ativação condicional**. O programa pode ir a produção com Premium fechado (Free + anúncios + leitura pública) desde que: (a) o lote de pagamento esteja testado em sandbox; (b) a flag de ativação exista e esteja **off**; (c) a página de planos degrade para o fallback gratuito; (d) a decisão de quando ativar (D-07) esteja registrada. Ativar Premium em produção sem o plano na Central é **blocker**.

---

## 10. Fase 6 — Ads, analytics, frontend e checklist visual/browser

### 10.1 WS-11 (P1-09, P1-10, P1-15, P1-16, P0-08)

- **Objetivo:** AdSense **somente para Free** e **somente após consentimento**; **Premium sem nenhum script/slot de ads**; **fallback Free sem anúncios**; Consent Mode + banner; **GA4 só após consentimento**; métricas internas com throttle, redaction e retenção; rotas e formulários (contato, lista de espera, newsletter) com **handler real**, sem submissão vazia; **dependências frontend** sem advisory crítico (`next` atualizado para corrigir advisory), lint funcional, typecheck e build verdes; **nenhum conteúdo fictício** em produção (P0-08).
- **Dependências humanas:** **conta AdSense** e seu **status** (aprovação real ou não) — **decisão D-05**; domínio e TC do AdSense; **credencial GA4**; domínio de medição; **ID de cliente AdSense** por ambiente; decisão sobre o que fazer enquanto o AdSense não aprova (default: Free sem ads).
- **Sequência de implementação e verificação:**
  1. **Ads condicionais:** Free+consentimento ⇒ AdSense **apenas** nos placements aprovados; Premium ⇒ **nenhum** script/slot; AdSense indisponível/não aprovado ⇒ modo **Free sem ads** sem erro de layout.
  2. **Consent Mode + banner:** consentimento recusado ⇒ nenhum evento de produto e nenhum script publicitário; GA4 **somente** após consentimento.
  3. **Métricas internas:** throttle; **redaction**; **remoção de query strings sensíveis** (token) do payload; fail-closed no endpoint público; expurgo/retenção (conecta com P2-02).
  4. **Rotas/formulários:** contato, lista de espera, newsletter com handler real, resposta de sucesso/erro, sem submissão silenciosa.
  5. **Dependências frontend:** upgrade do `next` para versão sem advisory crítico (dependência nova/upgrade = revisão obrigatória); `package-lock` fixado; **lint funcional**; `typecheck` verde; **build** com backend real e **fallback explícito** (sem `MOCK` como notícia real).
  6. **Erro de runtime:** tela de recuperação/código de suporte **sem PII, token ou stack trace**; header de request/release/ambiente presente.
  7. **P0-08 (conteúdo fictício):** varredura de manchete/plano/preço/métrica/assinante fictício; build com API real; nada de fallback fictício exibido como real.
- **Subagentes:** `executor` frontend + backend leve, `tester` (ads por papel/consentimento, payload sem token, formulários, build/typecheck), `reviewer` (**dados pessoais/consentimento + dependência nova + API pública: revisão obrigatória**), `remediator`, `documenter` (runbook de consentimento/ads/analytics; política de privacidade atualizada).
- **Saídas:** ads condicionais testados; fallback Free sem ads; Consent Mode e GA4 pós-consentimento; payload de métricas sem query sensível; formulários reais; `next` sem advisory crítico; lint/typecheck/build verdes; varredura de conteúdo fictício limpa.

### 10.2 Checklist visual e de browser (obrigatório, não substituível por teste automático)

Toda entrega visual desta fase (ads redesenhados, banner de consentimento, página de planos, formulários) passa por verificação **em browser**, registrada com evidência. Itens mínimos por tela/papel:

- [ ] **Free + consentimento:** ads aparecem **somente** nos placements aprovados, densidade reduzida, sem cobrir conteúdo, sem sobreposição com banner de consentimento; sem CLS (layout shift) inesperado.
- [ ] **Premium:** **zero** slots/scripts de ads; banner de ads ausente; espaçamento do layout não "pula" ao mudar o estado.
- [ ] **Sem consentimento:** nenhum ad, nenhum tracker; banner de consentimento legível, focável, com teclado e leitor de tela.
- [ ] **Consent Mode:** banner não bloqueia a leitura; GA4 não dispara antes do consentimento; estado do consentimento sobrevive a navegação.
- [ ] **AdSense indisponível/não aprovado:** modo **Free sem ads** renderiza limpo, **sem erro de layout** e sem "slot vazio" visível.
- [ ] **Tema claro/escuro:** contraste, foco visível, ordem de tabulação em todos os estados.
- [ ] **Formulários:** estados de envio, sucesso, erro, duplicado; teclado e leitor de tela; mensagem de sucesso **não** some rápido demais; sem submissão vazia.
- [ ] **Erro de runtime:** tela de recuperação com código de suporte, sem PII/token/stack trace.
- [ ] **Mídia (mobile/desktop):** banner e ads não quebram a dobra; navegação por teclado em todas as larguras.
- [ ] **Sem `MOCK`:** nenhuma manchete, plano, preço ou métrica fictícia em nenhum estado.

Evidência: capturas/URLs por tela e por papel, registradas em `lote-<id>-evidencias.md`. "Passou no teste automático" **não** substitui este checklist.

### 10.3 Gate GP-8

- [ ] Free+consentimento ⇒ ads apenas nos placements aprovados; Premium ⇒ nenhum ad; fallback Free sem ads sem erro.
- [ ] Consentimento recusado ⇒ nenhum script/evento; GA4 só pós-consentimento.
- [ ] Payload de métricas sem token/query sensível, com throttle e fail-closed.
- [ ] Formulários com handler real, sucesso/erro; sem conteúdo fictício.
- [ ] `next` sem advisory crítico; lint/typecheck/build verdes no SHA de release.
- [ ] Checklist visual/browser 100% executado com evidência, incluindo os papéis Free/Premium/sem-consentimento.

---

## 11. Fase 7 — Community, credenciamento, B2B, Central e Admin

### 11.1 WS-12 (P1-11, P1-12, P1-13, P1-14)

- **Objetivo:** Community com permissões, denúncias e **ocultação correta**; correção da **invalidação de query** (o bug de cache introduzido no commit `948a5b5`; `4c57ff04` é a duplicata de árvore idêntica desse commit — ***dangling*, recuperável só pelo SHA**, conforme §4.1.1); publicação `oculto=True` **ausente** de perfil público; logout limpando sessão; credenciamento com **upload seguro** (allowlist, validação, anexo seguro); **B2B completo** (organizações, membros, papéis, critérios, alertas, isolamento entre organizações, organizações inativas não concedem acesso); Central/robôs e **Admin** completos, incluindo **kill switch** de ingestão testado.
- **Dependências:** WS-06 (filas/workers para alertas B2B), WS-08 (fila de ingestão para o kill switch), WS-09 (identidade e papéis base), WS-01 (release limpo; o bug de cache é do commit já formalizado no release).
- **Sequência de implementação e verificação:**
  1. **Community/cache:** criação de publicação/comentário invalida a query correta usando a **key plana** (a chave correta, não a hierárquica); logout limpa o cache do cliente; teste de comportamento que falha antes da correção e passa depois.
  2. **Ocultação:** publicação `oculto=True` **não** aparece em perfil público nem em listagem pública; teste explícito.
  3. **Credenciamento:** upload com allowlist de tipo/tamanho, validação de conteúdo, caminho de armazenamento seguro, acesso restrito ao credenciado e ao editor; anexo não-executável; teste de upload malicioso rejeitado.
  4. **B2B:** criação de organização, membresia, papéis (membro vs administrador), **isolamento entre organizações** (membro de A não acessa dados de B), organização inativa **não** concede acesso, alertas enviados pela fila do ambiente correto.
  5. **Central/robôs:** ações administrativas auditadas, parâmetros configuráveis, kill switch de ingestão exposto e **testado**; kill switch de Premium.
  6. **Admin:** acesso restrito a papéis administrativos; auditoria de ação; nenhuma ação destrutiva sem confirmação/registro.
- **Subagentes:** `executor` backend + frontend, `tester` (cache, ocultação, upload, isolamento B2B, kill switch, sessão), `reviewer` (**credenciamento, moderação, B2B, autorização, dados pessoais: revisão obrigatória**), `remediator`, `documenter` (runbook de moderação/credenciamento/B2B/Admin; quem faz o quê).
- **Saídas:** cache Community corrigido com teste de regressão; ocultação garantida; upload validado; B2B isolado por organização; Central/Admin auditados; kill switch testado.
- **Gate GP-9:** publicação/comentário invalida a query correta; logout limpa sessão; `oculto=True` invisível publicamente; upload allowlisted e testado; B2B isola organizações e nega ação restrita a não-admin; organização inativa sem acesso; kill switch de ingestão e de Premium testados; revisão aprovada.

### 11.2 Nota de modularidade

WS-12 é o workstream com **maior superfície de revisão obrigatória** desta fase (credenciamento + moderação + B2B + autorização). Se o orçamento de revisão da fase for limitado, o caminho seguro **não é pular a revisão** — é **dividir WS-12 em lotes menores** (Community/cache | credenciamento | B2B | Central/Admin), cada um com contrato e revisão próprios. Nenhuma parte entra em PROD sem o seu gate.

---

## 12. Fase 8 e F9 — Testes, security review, observabilidade, soak e go-live

### 12.1 WS-13 — Consolidação de segurança (transversal) — P0-10

O hardening de aplicação é **dentro de cada lote** que introduz a superfície (WS-08..WS-12), **não** um lote separado no fim. A consolidação em F8 existe para verificar **fechamento transversal**:

- Sanitização de HTML editorial; escape seguro de JSON-LD; CSP em coerência com ads/GA4/consentimento.
- Allowlist anti-SSRF para RSS e LLM (endereços e esquemas bloqueados; sem fetch para rede interna/metadata).
- Validação de upload (allowlist, tamanho, sniffing; nada executável).
- Throttle + consentimento no endpoint público de métricas; redaction; fail-closed.
- Health/readiness corrigidos; **remoção de exposição de `str(exc)`** (não vazar traceback/pó de conexão com credencial).
- Retenção e expurgo de eventos antigos, idempotente e auditável.
- Dependências: sem advisory conhecido não aceito sem decisão registrada; `next` atualizado (WS-11).
- **Subagentes:** `executor` (por lote), `tester` (testes de segurança por achado), `reviewer` (**security review dedicado à consolidação F8 — revisão obrigatória de todos os itens acima**), `remediator`, `documenter` (runbook de incidente de segurança: diagnóstico, comando seguro, owner, escalonamento, rollback).
- **Gate (parcial de GP-10):** nenhum item de segurança acima em aberto; security review sem blocker/major.

### 12.2 WS-14 — Testes, observabilidade, soak, go-live e fechamento

- **Objetivo:** suíte completa (backend, frontend, integração, browser, segurança) **verde no SHA de release**; observabilidade operacional pesquisável (logs, métricas, release, request ID, filas, alertas); **soak em HOMOLOG** (o ambiente de pré-produção) com a ingestão real rodando; checklist go/no-go; `report.md` e `HISTORY.md`; runbooks completos.
- **Dependências:** GP-5, GP-6 e GP-8 `pass` (entradas de GP-10) e GP-4b vigente; **GP-7 (Premium) e GP-9 (módulos) não são pré-requisito de GP-10**, mas precisam estar testados antes do go/no-go; observabilidade suficiente para **detectar** problema durante o soak (sem ela, o soak não informa nada). **Coerente com §2.2 e §3.1: WS-14 não depende de "todos os WS anteriores"** — WS-13 é transversal (roda dentro de cada lote, §12.1) e WS-02/WS-04 entram pelos gates GP-1b e GP-2b.
- **Sequência:**
  1. **Suíte completa no SHA de release:** testes backend, coverage gate, typecheck, lint, build, testes de comportamento e browser, testes de integração (ingestão→publicação, cadastro→premium→webhook, ads por papel/consentimento). **Tudo no mesmo SHA que vai a PROD.**
  2. **Security review** fechada (WS-13).
  3. **Observabilidade** (P2-01) e **alertas de recurso** (P2-03): logs com release e request ID, métricas, filas, estado de workers, alertas de fila/memória/CPU/disco, com responsável.
  4. **Soak em HOMOLOG** (pré-produção), com a ingestão real ligada, pelo período **definido e aprovado no contrato do lote de soak** (sem duração arbitrária aqui; **HD-T**). Critérios de sucesso: nenhum erro de persistência, nenhum incidente de segurança, nenhum acesso a item indevido, nenhum vazamento entre ambientes, telemetria de fallback presente, workers estáveis, **backup e restore testados durante o período do soak**, com evidência arquivada. **Qualquer incidente durante o soak reabre o gate correspondente.**
  5. **Testes de carga** (P2-05) no mesmo SHA, com resultado documentado: comportamento sob tráfego inicial e picos conhecidos **medido**, nunca estimado.
  6. **Smoke por domínio** em `https://portal-noticias.com/` e nos hostnames de DEV/HOMOLOG **já definidos** (§5.3; se ainda não definidos, registrar a pendência em vez de inventar nomes): leitura pública, cadastro, login Google, plano/fallback, ads por papel, newsletter, B2B, Admin.
  7. **Go/no-go** (§15) — decisão do solicitante, não do agente. Inclui a linha de aceite assinado de **R-1** e as linhas de host key (**HD-7**) e de divergência de domínio (**R-15**).
  8. **Fechamento (`historian`):** `run-state.json` `closed` (única escrita do historian, sobre o desfecho já decidido); `report.md` com métricas de artefatos reais (findings, resultado de tester), sem estimativa; linha em `state/HISTORY.md` (append-only); `documentation-update.md`; e o **desfecho da run 1020 apenas registrado** — como o solicitante o decidiu, **inclusive mantida aberta**; F9 **não** afirma ter fechado a run 1020.
- **Subagentes:** `tester` (suíte + carga + soak), `reviewer` (security review), `remediator` (findings), `documenter` (runbooks: deploy, operação, incidentes, restore, consentimento, rollback, credenciais), `historian` (fechamento). O **go/no-go é do solicitante**.
- **Gate GP-10:** suíte verde no SHA de release; security review sem blocker/major; observabilidade pesquisável; soak em HOMOLOG concluído com critérios atendidos; **evidência de restore durante o soak** arquivada; testes de carga documentados; smoke por domínio verde em todos os ambientes, com **evidência do mesmo SHA de release nos três ambientes** (**G7**, §4.2); documentação e runbooks publicados.
- **Gate GP-11:** checklist go/no-go assinado pelo solicitante (§15), incluindo o aceite assinado de R-1.

### 12.3 Critério de parada do programa (reiterado)

Nenhuma promoção para PROD ocorre se **qualquer** destes for verdade:

1. Proveniência não reconciliada (GP-0 aberto — G0, G2, G3, G4, G5).
2. Working tree sujo no momento do release, ou release não reproduzível (gate de proveniência falha).
3. Backup externo não verificado **ou** restore não testado no período vigente.
4. Ambiente de destino não isolado do anterior.
5. TLS/DNS/redirect/HSTS não aprovados, ou D-01/D-11 adiadas sem registro.
6. Recurso com credencial ausente se comportar de forma insegura (mock, valor hardcoded, acesso concedido).
7. Findings major/blocker de segurança ou pagamento abertos.
8. Kill switch ausente ou não testado para um fluxo automatizado de alto impacto (ingestão, Premium, ads).
9. **Aceite de risco não assinado:** qualquer risco marcado como **aceito** (hoje, **R-1**) sem linha de aceite assinado no go/no-go. Risco aceito **não** impede a promoção; risco aceito **não assinado** impede.

---

## 13. Matriz de dependências humanas e riscos

### 13.1 Dependências humanas (nenhuma é executável por agente)

| ID | Dependência | Bloqueia | Natureza | Se ausente |
|---|---|---|---|---|
| **HD-A** | Compra e titularidade de `portal-noticias.com` | WS-05, todas as fases | compra | Programa trava; sem domínio não há go-live |
| **HD-B** | Controle do DNS (provedor + acesso) | WS-05 | acesso | Sem DNS/TLS, sem homologação por nome |
| **HD-C** | Acesso seguro à VPS (canal, chave, responsável) | WS-03, WS-04, WS-05, WS-06, WS-07 | acesso | Nada de infraestrutura é executável |
| **HD-D** | Storage externo de backup (+ chave de criptografia, retenção — D-12) | WS-07, GP-4b | provisionamento | **Go-live impossível** (sem restore) |
| **HD-E** | Credencial Resend | WS-09 | integração | Identidade por e-mail sem entrega real; não go-live |
| **HD-F** | Credencial Google OAuth (client + redirect URIs por ambiente) | WS-09 | integração | Login Google indisponível; registrar decisão |
| **HD-G** | Credencial OpenAI (opcional) | WS-08 | integração | Fallback local vira o modo **padrão** (válido), com teto e métricas |
| **HD-H** | Credencial e **status** da conta AdSense (D-05) | WS-11 | integração/política | Free **sem ads** (fallback oficial); sem ads é go-live válido |
| **HD-I** | Credencial GA4 | WS-11 | integração | Sem GA4; métricas internas seguem válidas |
| **HD-J** | Credencial Mercado Pago (sandbox + produção) | WS-10 | integração | Premium fechado; go-live válido com Free |
| **HD-K** | Plano Premium cadastrado na Central (D-07) | WS-10, GP-7 | produto | Premium **não** abre; sem valor hardcoded |
| **HD-L** | **Decisões de proveniência G0, G2, G3, G4 e G5** (custódia do WIP, refs, worktree, política de promoção, atribuição). **G1 não entra aqui** — é executado em WS-01 depois de GP-0. **Antes de GP-0 fechar, exige-se re-verificação fresca de G0–G5** (branch, `HEAD`, `origin/*`, refs, `status`, presença de `4c57ff04` por SHA), com timestamp, registrada no inventário de WS-00 (§4.2.1) | GP-0, **tudo** | decisão | **Fase 0 travada**; nenhuma implementação |
| **HD-M** | **R-1 / D-03:** **aceite explícito e assinado** do risco do caminho PR → VPS, com o que está sendo aceito, por quanto tempo e por quem. **Não bloqueia o go-live**; bloqueia apenas a alegação de "supply chain fechada". A decisão futura de substituir o caminho é follow-up | aceite assinado no go/no-go (GP-11) | registro/decisão | Sem aceite assinado, o go/no-go fica incompleto; o risco continua **aceito e aberto**, nunca resolvido |
| **HD-N** | **HD-2**: branch protection no GitHub | eficácia do gate | configuração | Gate é manual; limitação registrada como R-11; **não bloqueia o go-live** |
| **HD-O** | **HD-4**: topologia de execução (bind loopback vs rede privada) | WS-04 | decisão | WS-04 parcial; risco nomeado |
| **HD-P** | **HD-6**: onde o gate rodará recorrentemente | eficácia operacional | decisão | Gate manual; documentar; **não bloqueia o go-live** |
| **HD-Q** | **D-01** (`www`), **D-11** (HSTS/CSP) | WS-05 | decisão | Não configurar por conta própria; adiar com registro |
| **HD-R** | **D-04**: registro formal da decisão de lançar sem revisão jurídica | go-live | governança | Go/no-go sem a decisão de risco assinada |
| **HD-S** | Janela aprovada para HSTS/redirect e para promoção a PROD; responsável por deploy e canal de incidente | WS-05, WS-14, GP-11 | operacional | Ativar HSTS ou promover PROD sem janela é proibido |
| **HD-T** | Duração e critérios do soak aprovados (executado em **HOMOLOG**) | WS-14 | decisão | Soak não começa |
| **HD-U** | **HD-7:** validação e *pinning* de host key (`known_hosts`) do acesso humano e do usuário de deploy, com teste negativo de chave divergente; e reconhecimento de que o caminho de **CI** segue por senha sem impressão digital (não corrigível nesta fase do programa) | WS-03, GP-2a | decisão/ação de infraestrutura | WS-03 parcial; divergência registrada como R-16 e levada ao go/no-go |
| **HD-5** | Reconciliação formal das runs abertas `20260925-1020-observabilidade` (WIP **isolado** desta run) e `20260924-2136-ingestao-noticias` e dos arquivos não rastreados: quem é dono de cada arquivo | WS-00, GP-0 (custódia/atribuição) e o critério de parada da run mestre | decisão/orquestração | O WIP segue **isolado** e sem dono atribuído; nenhum item que dependa dele fecha; o **F9 apenas registra o desfecho já decidido** (inclusive a run 1020 mantida aberta), sem esta run declará-la fechada |

### 13.2 Riscos aceitos e riscos pendentes

| ID | Risco | Situação | Onde aparece |
|---|---|---|---|
| **R-1** | **Supply chain:** head de PR não aprovado pode ser implantado na VPS persistente de HOMOLOG (`deploy-homolog.yml` → `deploy.yml`, `git_mode: pr`). Código não aprovado pode rodar onde há segredos. | **ACEITO** por decisão do solicitante e, por isso, **NÃO BLOQUEANTE para o go-live**. **ABERTO**: **não** alterado, **não** mitigado, **não** bloqueado, **não** coberto pelo gate. **Assinatura de aceite obrigatória no go/no-go.** Nenhum artefato pode marcá-lo como **resolvido**. | `lote-p0-1-proveniencia.md` R-1/HD-1, `PROD_DECISOES.md`, `CI-CD.md`; §4.6; go/no-go §15.2 |
| **R-2** | Conteúdo RSS agregado sem aprovação jurídica e sem revisão humana | **ACEITO por decisão do solicitante**, com mitigação técnica: kill switch, bloqueios por fonte/categoria, canal de denúncia/atribuição, e **sem** declarar conformidade LGPD | §7.2, D-04 |
| **R-3** | AdSense negar a conta por conteúdo republicado | **MITIGADO por fallback** (Free sem ads é o modo oficial) e por **não bloquear o lançamento** | D-05, WS-11 |
| **R-4** | OpenAI indisponível ou caro | **MITIGADO**: teto de gasto, fallback local automático, métrica de custo, kill switch | WS-08 |
| **R-5** | Perda da VPS (host único, sem HA) | **ACEITO**: melhor nível em VPS única; mitigação = backup externo + restore testado + alerta + runbook. **Não** se promete failover | WS-07 |
| **R-6** | DNS/credenciais externas não provisionadas | **ABERTO**: matriz §13.1; gate impede go-live enquanto aberta | GP-3, GP-11 |
| **R-7** | Vazamento entre ambientes | **MITIGADO por isolamento testado** (teste negativo obrigatório) | WS-06, GP-4a |
| **R-8** | Regressão em pagamento | **MITIGADO**: sandbox, assinatura de webhook, idempotência, reconciliação, revisão obrigatória | WS-10, GP-7 |
| **R-9** | Perda de trabalho não versionado (WIP 1020, arquivos de origem desconhecida) | **MITIGADO por custódia** (G0) e atribuição (G5); **nenhum** reset/clean até G0 | WS-00, GP-0 |
| **R-10** | `settings.py` reparado sem origem (arquivo central de configuração) | **ABERTO** até validação funcional. No lote P0-1/F0 ele é **apenas verificado** (gate **G1**, AC-3), sem edição; se a validação passar, GP-1b encerra o item **por evidência** | §4.3, §4.4, GP-1, GP-1b |
| **R-11** | Gate de proveniência sem poder de veto (roda manualmente, sem check registrado) | **ACEITO**; eficácia depende de HD-2/HD-6/lote futuro de CI/CD. **Não bloqueia o go-live** | §4.6, D-02 |
| **R-12** | Densidade de anúncios/commitments visuais | **MITIGADO** por redesign de placements + checklist visual/browser obrigatório | §10.2 |
| **R-13** | Encolhimento de HSTS/redirect quebrar **hostnames de ambiente** (nomes **ainda não decididos**) | **MITIGADO** por HSTS/CSP decididos antes de ativar (**D-11**, **D-14**) e por janela aprovada; a validação/smoke por nome só é feita **depois** da decisão de hostnames (**D-01**). Nenhum hostname de ambiente é inventado, assumido ou validado **antes** de D-01; até lá, registra-se a pendência | WS-05, D-01, D-11, D-14 |
| **R-14** | Publishing automático publicar item defeituoso | **MITIGADO**: validações técnicas, falha registrada, bloqueios por fonte/categoria, kill switch, métricas | WS-08 |
| **R-15** | **Divergência de domínio:** o canônico do programa é `https://portal-noticias.com/`, e os workflows existentes usam `portal-noticias.com.br` (hosts de DEV/HOMOLOG/PROD e `www`); nenhum hostname de ambiente foi decidido | **ABERTO e registrado.** Nenhum valor de domínio é alterado no lote P0-1/F0 nem nesta fase do programa. Correção em **lote posterior**, **sem** mudar estrutura nem gatilhos, com decisão do solicitante sobre os nomes de ambiente (D-01) e linha no go/no-go | §4.6, §5.3, D-01, go/no-go |
| **R-16** | **Host key sem validação no caminho de CI:** o `ssh-action` de `deploy.yml` autentica por senha e **não** fixa impressão digital da host key; o `known_hosts` do acesso humano também não existia | **ABERTO.** O *pinning* de host key do **acesso humano e do usuário de deploy** é de **WS-03** (GP-2a, HD-7), com teste negativo. A correção do **caminho de CI** exige alterar `.github/` e, portanto, **lote posterior**; registrada no go/no-go | §5.1, GP-2a, D-03, go/no-go |
| **R-17** | WIP da run `20260925-1020-observabilidade` e arquivos de origem indeterminada (incluindo `backend/config/observability.py`, `metrics.py`, `health.py` não rastreados, dos quais o `middleware.py` rastreado depende) | **ABERTO e isolado.** Este run **não** adota nem fecha esse WIP; ele é preservado (G0) e atribuído (G5, **HD-5**). Misturar sem reconciliação é proibido pelo contrato mestre. O **F9 registra o desfeço já decidido** pelo solicitante (G6), **inclusive a run 1020 mantida aberta**; em nenhum caso esta run declara a 1020 fechada | §4.1, §4.2, §12.2, HD-5 |

---

## 14. Plano de rollback por fase

Princípios: **rollback em quatro camadas** (código, configuração, dados, produto). Cada camada tem critério de parada, ação, verificação pós-rollback e o que é **irreversível** (exige decisão humana antes de avançar). **Um gate só fecha com rollback testado ou com o motivo honesto de não testabilidade registrado.**

| Fase / WS | Critério de parada (abortar e reverter) | Ação de rollback | Verificação pós-rollback | Irreversível? |
|---|---|---|---|---|
| **F0 / WS-00, WS-01, WS-02** (repo-only) | Gate do lote reprovado; verificação de `settings.py` falha; `settings.py` ou arquivo protegido tocado; `.github/` alterado | **Auto-reversão lógica, restrita aos arquivos autorizados pelo lote:** o executor reverte o **conteúdo** dos arquivos que ele próprio criou ou alterou dentro da lista de escrita autorizada do contrato do lote, reconstruindo o estado pré-lote a partir da evidência do próprio lote (baseline/inventário e comandos de leitura já registrados). Reverter é **reescrever conteúdo**, **não** executar comando Git: **`checkout`, `reset`, `restore`, `clean`, `stash` e `switch` são proibidos no rollback**, junto com qualquer outro comando Git de escrita; `HEAD`, índice, refs e todo arquivo fora da lista de escrita **não** são tocados. Artefatos do lote rejeitado são preservados para a revisão, nunca apagados | `git status` volta ao estado pré-lote **sem** nenhum comando Git de escrita executado; `HEAD` inalterado; `settings.py` igual ao byte anterior; `.github/` idêntico; import/`manage.py check` OK | Não, exceto a decisão de **atribuição/push** de refs e o **fechamento** de run — essas são decisões humanas, não rollback técnico |
| **F1 / WS-03** (acesso host) | Root inacessível após rotação; novo usuário não funciona; sessão ativa perdida; host key divergente rejeitada indevidamente (configuração errada de `known_hosts`) | Reabrir `PasswordAuthentication`/root **pela sessão ativa ou console do provedor**; restaurar `sshd_config` versionado; recriar chave; **remover apenas a linha de `known_hosts` comprovadamente errada e reinserir a chave obtida por canal confiável** (nunca desligar a verificação) | Root por senha **e** por chave testados; usuário non-root funcional; inventário final registrado; `known_hosts` correto e chave divergente continua rejeitada | Risco de **lockout** se console indisponível → exigir console do provedor **antes** de rotacionar (pré-condição) |
| **F1 / WS-04** (rede) | Após fechar portas, leitura pública cai; Nginx sem upstream | Reverter regra de firewall imediatamente (regras de allow mantidas antes do deny); restaurar `infra/nginx` versionado; subir o bind anterior | Leitura pública **e** internas restauradas; `ss` mostra o estado esperado; smoke passa | Não, se a sequência allow→deny for respeitada |
| **F1 / WS-05** (domínio/TLS/HSTS) | HTTPS quebra; redirect/HSTS quebra um hostname de ambiente; certificado não renova | Reverter DNS ao valor anterior; desativar HSTS/redirect; restaurar certificado anterior; corrigir vhost | `https://portal-noticias.com/` volta a servir; redirect conforme decisão; smoke por domínio passa; **HSTS é o ponto mais sensível: uma vez ativo, os navegadores passam a respeitar; janela aprovada obrigatória** | Parcial: **HSTS é difícil de reverter** (cache do navegador) — ativação só em janela aprovada |
| **F2 / WS-06** (isolamento) | Cross-read detectado; worker consome fila errada; migration quebra | Voltar ao release anterior; **não** desfazer banco por `migrate` às cegas; restaurar config por ambiente; se dados ficou inconsistente, restaurar do backup externo | Teste negativo de isolamento passa; workers/filas corretos; `manage.py check` OK; contagens conferidas | **Migrations**: se aplicadas em ambiente com dados reais, a reversão é via backup/restore (decisão humana antes de PROD) |
| **F2 / WS-07** (backup/restore) | Backup falha; cópia externa não chega; restore não valida | Corrigir script; reexecutar backup; **restore continua obrigatório** antes de qualquer promoção | Backup `exit 0` + cópia externa confirmada; restore isolado verde; RPO evidenciado | Não; mas **sem restore verde não há promoção** |
| **F3 / WS-08** (ingestão) | Itens errados publicados em massa; custo OpenAI dispara; fila trava | **Kill switch de ingestão** (sem deploy); reverter para release anterior; reexecutar reprocessamento idempotente; desligar OpenAI (fallback local) | Publicação parada; itens afetados identificados e removidos/reprocessados; telemetria coerente; custo dentro do teto | Remoção de itens já publicados é **editorial**: exige critério e registro (remeter a D-04) |
| **F4 / WS-09** (identidade) | Vazamento de token; OAuth em domínio errado; envio de email indevido | Reverter release; desabilitar Google login (flag); pausar envios Resend; rotacionar segredos se houver suspeita | Cadastro/reset/verificação controlam; token fora de log; OAuth correto; consentimento fail-closed | **Rotação de segredo** é irreversível no sentido de que o valor antigo morre — planejar antes |
| **F5 / WS-10** (Premium) | Webhook de assinatura inconsistente; duplicidade; usuário Premium indevido | **Fechar Premium** (flag de ativação off) — ação de produto, imediata; reverter release; **reconciliar** com o gateway; nunca "apertar" estado financeiro à mão sem registro | Premium fechado ⇒ fallback gratuito; **reconciliação registrada e datada**; idempotência reprocessada sem duplicar | **Reconciliação financeira** é sempre com o gateway; decisão humana se houver divergência de saldo |
| **F6 / WS-11** (ads/analytics) | Ads em Premium; script vazando sem consentimento; payload vazando token; build quebrado | **Desligar ads** (modo Free sem ads); desligar GA4; reverter release; corrigir redaction | Premium sem ads; sem consentimento ⇒ nada sai; payload sem token; build/typecheck verdes | Não |
| **F7 / WS-12** (módulos) | Publicação ocultada vazando; B2B vazando entre organizações; upload inseguro; kill switch quebrado | Reverter release; **fechar** o módulo afetado (desabilitar rota) em vez de deixar o módulo meio aberto; kill switch de ingestão como contenção | Ocultação garantida; isolamento B2B OK; upload allowlisted; kill switch funciona | Não; **vazamento de organização é incidente** → rotacionar/avaliar credenciais conforme runbook |
| **F8–F9 / WS-13, WS-14** (soak/go-live) | Incidente durante soak; suíte vermelha; security review aberta; restore não validado | **Não promover**; corrigir e **repetir o soak**; se já promovido, rollback para SHA anterior + restaurar config/dados do ambiente | Suíte verde; security review limpa; soak repetido com critérios atendidos; smoke verde | Promoção para PROD é o ponto de maior exposição: exigirá janela + backup + smoke + rollback pronto |
**Regras de rollback transversais:**

1. **Code rollback** = promover o SHA anterior **do mesmo ambiente**; nunca `git revert` às cegas em PROD sem versão testada.
2. **Config rollback** = restaurar a versão anterior do arquivo versionado; config de ambiente é sempre versionada.
3. **Data rollback** = migration reversível **ou** restore do backup externo; escolha decidida **antes** de aplicar, não depois. Em PROD com dados reais, restaurar é decisão humana.
4. **Product rollback** = fechar a feature (Premium off, ads off, kill switch de ingestão) antes de mexer em código, quando o problema é de produto.
5. **Rollback do lote `repo-only` (F0) é auto-reversão lógica**, não comando Git: reescrever o **conteúdo** dos arquivos que o lote autorizou a escrever, com `HEAD` intacto. `checkout`, `reset`, `restore`, `clean` e `stash` continuam **proibidos** mesmo em rollback; se a reversão exigir qualquer comando Git de escrita, isso vira **decisão humana** (G0–G5) e sai do escopo do lote.
6. Todo rollback executado é registrado em `implementation-history.md` com **motivo, comando/ação, verificação e evidência**.

---

## 15. Definition of Done e checklist go/no-go

### 15.1 Definition of Done do programa (DOD)

- [ ] **GP-0** Proveniência reconciliada com decisão humana para **G0, G2, G3, G4, G5** (G1 fora deste gate); nenhum arquivo protegido tocado; nenhum comando Git de escrita por agente.
- [ ] **GP-1** Lote P0-1 entregue, testado e revisado (AC-1..AC-10); gate de proveniência read-only, fail-closed, determinístico, sem vazamento; caso negativo demonstrado; `.github/` inalterado; `run-state.json` fora do diff do executor; R-1 registrado como **aceito e aberto**.
- [ ] **GP-1b** Resultado de **G1** lido: `settings.py` validado funcionalmente (ou encerrado por evidência, com decisão do orchestrator registrada).
- [ ] **GP-2a** Root por senha desabilitado e testado; usuário non-root; nenhum processo root; **host key validada e fixada em `known_hosts`, com teste negativo de chave divergente**; divergência do caminho de CI registrada (R-16).
- [ ] **GP-2b** Portas de aplicação fechadas; Nginx único proxy público; exceção declarada se o bind em loopback for adiado.
- [ ] **GP-3** `https://portal-noticias.com/` com TLS válido, redirect, HSTS aprovado, headers de segurança, cookies seguros; smoke por domínio.
- [ ] **GP-4a** Isolamento DEV/HOMOLOG/PROD comprovado por teste **negativo**; workers/beat/filas por ambiente; expurgo resolvido.
- [ ] **GP-4b** Backup externo diário criptografado; restore em ambiente isolado verde; RPO de 24h evidenciado; alerta e runbook de restore.
- [ ] **GP-5** Ingestão de todas as fontes sem erro de persistência; falha isolada por grupo; fallback local executado e distinguível; concorrência travada; kill switch testado; sem conteúdo fictício.
- [ ] **GP-6** E-mail real (verificação/reset/newsletter) via Resend; Google OAuth por ambiente; consentimento fail-closed; LGPD (exportação/exclusão) auditada; tokens fora de log.
- [ ] **GP-7** Premium: sandbox verde; webhook assinado e idempotente; cancelamento/renovação/inadimplência consistentes; plano na Central; ativação condicional.
- [ ] **GP-8** AdSense só em Free+consentimento; Premium sem ads; fallback Free sem ads; GA4 pós-consentimento; métricas com redaction; formulários reais; `next` sem advisory crítico; lint/typecheck/build verdes; checklist visual/browser completo.
- [ ] **GP-9** Community/cache corrigido; `oculto=True` invisível publicamente; credenciamento com upload allowlisted; B2B isolado e com papéis corretos; Central/Admin auditados; kill switch testado.
- [ ] **GP-10** Suíte completa verde no SHA de release; security review sem blocker/major; observabilidade pesquisável; **soak em HOMOLOG** concluído nos critérios, com evidência de restore arquivada; testes de carga (P2-05) documentados; smoke verde em todos os ambientes. **GP-7 e GP-9 precisam estar testados antes do go/no-go, mas não são pré-requisito de GP-10.**
- [ ] **GP-11** Go/no-go assinado pelo solicitante, **incluindo a linha de aceite assinado de R-1**; `report.md`, `HISTORY.md`, `documentation-update.md` e `run-state.json` fechados; desfecho da run 1020 **registrado como decidido** (**inclusive mantida aberta**), sem afirmação de que esta run a fechou.

### 15.2 Checklist go/no-go (binário, verificado por evidência; decisão do solicitante)

**Proveniência e release**
- [ ] Working tree limpo no release; SHA único e validado; `git status` de DEV/HOMOLOG/PROD mostra o mesmo SHA. (O SHA vem do release re-derivado; `645aca3` é **snapshot datado**, não SHA de release.)
- [ ] Gate de proveniência verde no SHA, caso negativo demonstrado, e prova de read-only arquivada.
- [ ] `.github/` sem alteração no lote P0-1/F0 e nesta fase do programa; **nenhum valor de domínio em workflow alterado**; desvio do critério de aceite 4 do contrato mestre declarado.
- [ ] Decisões de proveniência (**G0, G2, G3, G4, G5**) registradas **e re-verificadas frescas** imediatamente antes de GP-0 fechar (§4.2.1, com timestamp); **política de promoção** entre `develop`, `main` e HOMOLOG decidida (**D-08**, com o equivalente **HD-3** do contrato do lote). **No estado re-derivado de §4.1.1 (2026-09-25T18:32:47Z) não há push pendente:** `948a5b5`/`645aca3` já constam de `origin/develop` e `develop` está em paridade (`0/0`) — se a re-verificação final mostrar divergência, o push volta a ser item de G2.
- [ ] Resultado de **G1** (verificação de `settings.py`) lido e GP-1b encerrado — por validação ou por evidência.
- [ ] **`run-state.json` fora do diff de qualquer executor** (AC-10); estado da run atualizado pelo orchestrator.
- [ ] **WIP da run `20260925-1020-observabilidade` isolado**: não adotado, não reaproveitado, não fechado por esta run; custódia (G0) e atribuição (G5) registradas; desfecho **decidido** registrado (inclusive mantida aberta), sem alegação de fechamento.

**Riscos aceitos — linhas obrigatórias, com assinatura**

- [ ] **R-1 (supply chain PR → VPS): ACEITO, ABERTO, não mitigado, não coberto pelo gate e não bloqueante.** Registrado como **aceito** — **nunca** como resolvido. A linha traz: o que está sendo aceito (caminho PR → VPS ativo em HOMOLOG), o escopo, até quando, e quem assinou. **Sem esta linha assinada, o go/no-go não fecha.**
- [ ] **R-15 (divergência de domínio: canônico `.com` × `portal-noticias.com.br` dos workflows):** registrada, com o lote que a resolve e a decisão sobre nomes de ambiente.
- [ ] **R-16 (host key do caminho de CI por senha, sem impressão digital):** registrada, com a evidência do *pinning* feito em WS-03 para o acesso humano e o follow-up de CI/CD.

**Host, rede, domínio**
- [ ] Root por senha desabilitado (testado), chave only, usuário non-root, nenhum processo root.
- [ ] **Host key validada e fixada** em `known_hosts` para o acesso humano e o usuário de deploy, com **teste negativo** de chave divergente rejeitada (GP-2a, HD-7).
- [ ] `ss`/firewall: expostos apenas SSH gerenciado e Nginx; 3101–3103/5101–5103 inacessíveis externamente.
- [ ] `https://portal-noticias.com/` com certificado válido; HTTP→HTTPS; HSTS ativo após janela aprovada; CSP e headers presentes; `www` decidido (D-01).
- [ ] Cookies `Secure`/`HttpOnly` em PROD; `ALLOWED_HOSTS`/CORS por ambiente.

**Ambientes, backup, dados**
- [ ] Isolamento DEV/HOMOLOG/PROD com teste negativo verde; workers/beat/filas/mídias separados.
- [ ] Backup diário externo criptografado com `exit 0`; **restore em ambiente isolado verde**; RPO de 24h evidenciado; alerta de atraso ativo.
- [ ] Nenhuma migration sem teste, backup verificado, homologação e rollback documentado.
- [ ] Nenhum conteúdo fictício (MOCK) em qualquer ambiente que serve público.

**Produto e integrações**
- [ ] Ingestão automática de todas as fontes sem revisão humana, sem erro de persistência; falha registrada; kill switch testado.
- [ ] OpenAI com teto; fallback local executado e distinguível na telemetria.
- [ ] Resend entregando cadastro/verificação/reset/newsletter/descadastro; Google OAuth funcional no domínio de PROD.
- [ ] Consentimento fail-closed; GA4 e ads só após consentimento; Premium sem ads; fallback Free sem ads ativo.
- [ ] **GP-7** Premium: sandbox verde, webhook assinado/idempotente; **ativação apenas se** plano na Central + credenciais + sandbox; caso contrário Premium fechado com fallback — **registrar qual dos dois estados vai a produção**. GP-7 não é pré-requisito de GP-10, mas **é exigido neste go/no-go** (§2.2/§12.2).
- [ ] **GP-9** Community/ocultação/cache, credenciamento/upload, B2B/isolamento, Central/Admin: todos os gates GP-9 verdes. GP-9 não é pré-requisito de GP-10, mas **é exigido neste go/no-go** (§2.2/§12.2).

**Qualidade, operação, governança**
- [ ] Suíte backend/frontend/integração/browser/segurança verde no SHA de release; coverage gate, typecheck, lint, build verdes; `next` sem advisory crítico.
- [ ] Security review (WS-13) sem blocker/major; nenhum `str(exc)`/traceback exposto; anti-SSRF e allowlist de upload em teste.
- [ ] Observabilidade pesquisável (release, request ID, filas, workers, alertas) com responsável.
- [ ] Soak em **HOMOLOG** concluído nos critérios aprovados, sem incidente aberto, com evidência de restore arquivada; testes de carga documentados; smoke por domínio em DEV/HOMOLOG/PROD.
- [ ] Runbooks: deploy, operação, incidentes, restore, consentimento, rollback, DNS/TLS, credenciais — publicados.
- [ ] **Decisão de risco jurídico (D-04) registrada e assinada**; nenhuma declaração de conformidade LGPD em documento ou no produto.
- [ ] Matriz de dependências humanos (§13.1) com **nenhuma dependência bloqueante em aberto** — ou as não bloqueantes explicitamente listadas com dono e prazo de decisão.
- [ ] **Go/no-go assinado pelo solicitante.**

---

## 16. Fora do escopo (do lote P0-1/F0 e do programa)

### 16.1 Fora do escopo **do lote P0-1/F0** (Fase 0 — reconciliação, lote P0-1 e_settings.py)

Nada abaixo é entregue agora, **por definição**, e nenhum lote pode tocá-lo sem contrato próprio:

- **Nenhuma alteração na VPS**: sem rotação de root, sem usuário non-root, sem firewall, sem bind loopback, sem Nginx, sem systemd/PM2, sem processos, **sem validação/pinning de host key** (que é de **WS-03**, GP-2a).
- **Nenhuma mudança de DNS, domínio, TLS, HSTS ou cookies.** No lote P0-1/F0, o **único valor de domínio adotado** é o canônico `https://portal-noticias.com/`; o registro efetivo, DNS, **nomes de host de DEV/HOMOLOG/PROD** (ainda não decididos), certificado, renovação e o alinhamento dos valores existentes nos workflows (`portal-noticias.com.br`, **R-15**) são **lote posterior**, sem alterar estrutura nem gatilhos de workflow.
- **Nenhum backup, restore, alerta ou storage externo.**
- **Nenhum isolamento de ambiente** (bancos, Redis, filas, mídia, chaves, workers/beat).
- **Nenhuma ingestão, editorial, OpenAI, fallback local ou kill switch.**
- **Nenhuma identidade, Resend, Google, newsletter, consentimento ou LGPD.**
- **Nenhum Premium, Mercado Pago, plano na Central ou ativação de cobrança.**
- **Nenhum AdSense, GA4, Consent Mode, métrica, rota, formulário, build ou upgrade de dependência frontend.**
- **Nenhum módulo de produto**: Community, credenciamento, B2B, Central, Admin.
- **Nenhum teste de soak, nenhum smoke por domínio, nenhum go-live**, nenhuma promoção entre ambientes.
- **Nenhuma correção de `settings.py` de conteúdo** — o lote P0-1 apenas **verifica**; a correção (se necessária) é WS-02, lote próprio.
- **Nenhuma alteração em `.github/`** — nem em workflow existente, nem novo workflow, nem registro do gate como check, nem branch protection/rulesets/environments/secrets por API, nem **valor de domínio** em workflow. Decisão do solicitante (revisões 2 e 3 do lote P0-1).
- **Nenhum comando Git de escrita**: sem `add`, `commit`, `push`, `merge`, `rebase`, `reset`, `clean`, `checkout`, `switch`, `stash`, `restore`, `apply`, `prune`, `gc`. Sem normalização de `packed-refs`, sem podar o worktree `wt-merge`, sem push dos commits locais, sem criar branch/tag — **essas são decisões humanas (G2–G4), não ações do agente.** No estado re-derivado (§4.1.1) **não há push pendente**; se a re-verificação fresca mostrar divergência entre `develop` e `origin/develop`, o push é reaberto como decisão humana, **não** executado por agente.
- **Nenhuma edição de `.gitignore`**: o diretório de estado das runs — inclusive `agentic-framework/state/run-20260925-1433-go-live-producao/`, artefato de planejamento **não rastreado** desta run, **fora de release** e **re-derivado** a cada gate — é tratado por **inventário e ownership** (G5/D-08), nunca por regra de ignore.
- **Nenhuma escrita em `run-state.json` por executor**: o arquivo é do **orchestrator**, atualizado depois do lote (AC-10).
- **Nenhuma correção de conteúdo de `settings.py`**: o lote P0-1 apenas **verifica** (G1/AC-3); a correção, se necessária, é WS-02, em lote próprio.
- **Nenhuma migration, seed, escrita em banco, `manage.py migrate`, ou acesso a segredo.**
- **Nenhuma execução de suite completa ou build de produção** como parte do lote de proveniência; o lote valida sintaxe/parse e read-only, não a aplicação.
- **Nenhuma estratégia de promoção de branch, `workflow_dispatch` ou de deploy de HOMOLOG inventada.**
- **Nenhuma declaração de conformidade jurídica, LGPD ou de que R-1/supply chain foi resolvido.** R-1 é **aceito e aberto**.

### 16.2 Fora do escopo do **programa** (decidido no task-plan, permanece fora)

Kubernetes/service mesh/multi-node/multi-região/HA; cloud gerenciada (banco, Redis, app); apps móveis nativos; outros provedores de pagamento, e-mail ou login; cupons/moedas/períodos de teste/cobrança avançada; cobrança B2B; session replay/captura de tela/PII; warehouse de analytics; ML própria; moderação humana obrigatória; takedown automático por direitos autorais; declaração de conformidade sem advogado; redesenho geral de marca/design system fora dos ads e dos fluxos quebrados. **Também permanece fora:** alteração do CI/CD nesta fase do programa (D-03 como decisão futura, com R-1 **aceito e aberto**), HA de verdade, e qualquer coisa que pressuponha ambiente já pronto (nada aqui presume).

---

## 17. Decisões pendentes

Nenhuma destas pode ser respondida por agente. Cada uma tem dono, o que bloqueia e o gate em que precisa estar decidida. **Nenhuma tem data fixa aqui** — o solicitante define a janela.

| ID | Decisão pendente | Quem decide | Bloqueia | Gate |
|---|---|---|---|---|
| **D-01** | **`www` e hostnames de ambiente:** apex canônico com `www` redirecionando para apex (recomendado) ou o contrário; efeito em DNS, cookies, CORS, redirect URI do Google, HSTS, métricas; e **nomes de host de DEV/HOMOLOG/PROD** (hoje `portal-noticias.com.br` nos workflows, canônico do programa `https://portal-noticias.com/`). Não configurar `www` nem nome de ambiente por conta própria. | Solicitante (+ quem controla DNS) | Config final de DNS/TLS; OAuth; analytics; alinhamento de valores de domínio em workflow (**R-15**) | GP-3 |
| **D-02** | **Branch protection (HD-2):** configurar no GitHub com PR obrigatório; e, mais adiante, **registrar o gate como required status check** (o que exigiria um workflow — fora de escopo no lote P0-1/F0 e nesta fase do programa). Sem isso, o gate é manual. | Solicitante/admin do repositório | Eficácia do gate (não sua entrega); **não bloqueia o go-live** | GP-11 (registro da limitação) |
| **D-03** | **CI/CD futuro / R-1 (HD-1):** duas partes, com pesos diferentes. (a) **Aceite explícito e assinado** do risco do caminho PR → VPS ativo, no go/no-go — **é o que o go-live exige**, e o go-live **não** depende de a decisão abaixo. (b) **Decisão futura** sobre o gatilho, branch e `verify_ref` que substituem o deploy de PR — branch de promoção, `workflow_dispatch` com SHA explícito, ou desabilitar o deploy por PR — em lote próprio com revisão de CI/CD. No lote P0-1/F0 e nesta fase do programa o caminho **permanece ativo** e **R-1 permanece aceito e aberto**. | Solicitante | (a) assinatura da linha de R-1 no go/no-go; (b) encerramento de "supply chain resolvida" | GP-11 |
| **D-04** | **Legal:** registrar formalmente a decisão de publicar sem revisão jurídica formal; quem assina; manter canal de denúncia e atribuição; o que NÃO será declarado (conformidade LGPD). | Solicitante | Go-live | GP-11 |
| **D-05** | **AdSense:** status real da conta; se aguardando aprovação; o que fazer enquanto não aprova (default: Free sem ads); política de conteúdo republicado e risco de negação. | Solicitante | Fechamento de WS-11; o go-live **não** depende da aprovação | GP-8 (registro do estado) |
| **D-06** | **Credenciais:** quais já existem (Resend, Google, GA4, Mercado Pago, AdSense, OpenAI, storage externo); quem providencia; canal seguro; rotação. **Nunca valores no repositório** — só referência de existência. | Solicitante/equipe | WS-08/09/10/11; go-live dos que dependem | GP-3..GP-8 |
| **D-07** | **Plano Premium:** nome, valor, duração, benefícios, quem pode comprar; cadastro na Central. **Somente valores de plano são permitidos em lote posterior**; no lote P0-1/F0, **nenhum** valor é definido e **nenhum** valor é hardcoded. Premium só abre depois de plano + credencial + sandbox. | Solicitante | GP-7; decide se o go-live tem Premium ativo | GP-7 |
| **D-08** | **Proveniência (G2–G5, HD-3, HD-5):** (a) **política de promoção** entre `develop`, `main` e HOMOLOG — *divergência registrada com o planejamento: no estado re-derivado (§4.1.1) `948a5b5` e `645aca3` **já estão** em `origin/develop` e `develop` está **em paridade** (`0/0`); **não há push pendente** a decidir, apenas a política*; (b) normalizar a divergência **ref solta × `.git/packed-refs`** (`origin/develop` `7715dae8` × `b671a86`; `origin/main` `bb63cb3d` × `cbe161e`, no snapshot de §4.1.1 — valores a re-derivar); (c) destino de `4c57ff04` — ***dangling*, recuperável só pelo SHA, ausente do reflog***; (d) entrada de worktree `wt-merge` ainda registrada como `prunable` (`main`), com diretório já ausente em disco; (e) **atribuição dos arquivos de origem desconhecida**; (f) **inventário e ownership** do artefato não rastreado `agentic-framework/state/run-20260925-1433-go-live-producao/` (planejamento desta run, **fora de release**, re-derivado a cada gate) — resolvido **sem editar `.gitignore`**; (g) desfecho do WIP **isolado** da run `20260925-1020-observabilidade`; (h) quem escreve a linha do `HISTORY.md`. | Solicitante | GP-0; e, em especial, **qual SHA é o release** (re-derivado no lote, confirmado aqui) | GP-0 |
| **D-09** | **Topologia de execução (HD-4):** bind em loopback vs rede privada entre Nginx e aplicação; impacto em HOMOLOG. | Solicitante | WS-04 (GP-2b) | GP-2b |
| **D-10** | **Onde o gate roda (HD-6):** runner local, hook externo, job de outro projeto, ou não rodar recorrentemente. | Solicitante | Eficácia operacional do gate (não bloqueia o go-live) | GP-11 |
| **D-11** | **HSTS/CSP:** ativar HSTS (e preload) e CSP estrito vs `Report-Only`; janela de ativação. | Solicitante | WS-05 (GP-3) | GP-3 |
| **D-12** | **Backup externo:** provedor, retenção, quem guarda a chave de criptografia, como recuperar a chave, RPO além do diário. | Solicitante | WS-07 (GP-4b) | GP-4b |
| **D-13** | **Janela e responsáveis:** janela para HSTS/redirect; janela de promoção a PROD; duração e critérios do soak (executado em **HOMOLOG**); responsável por deploy; canal de incidentes; plantão. | Solicitante | WS-05, WS-14, GP-11 | GP-3, GP-11 |
| **D-14** | **HSTS é uma decisão irreversível curto-prazo** (cache do navegador): mesmo que revertido no servidor, navegadores já podem recusar HTTP. Ativar só em janela aprovada e com os hostnames de ambiente preparados. | Solicitante | WS-05 | GP-3 |
| **D-15** | **Host key (HD-7):** como a host key da VPS é obtida por canal confiável e fixada em `known_hosts`; evidência do teste negativo de chave divergente; e reconhecimento de que o caminho de **CI** segue por senha sem impressão digital, o que só um lote de CI/CD altera (**R-16**). | Solicitante | WS-03 (GP-2a) e a linha de R-16 no go/no-go | GP-2a, GP-11 |

---

## 18. Nota de encerramento deste documento

- Este **action-plan** é um documento de **execução sequenciada**. Ele **não** implementa nada, **não** executa nada, **não** acessa a VPS e **não** define datas.
- Todos os workstreams estão **planejados e não iniciados**. O único artefato de execução previsto no lote P0-1/F0 é o lote P0-1, cujo contrato já existe (revisão 3) e cuja aprovação é condição de delegação.
- **Regra de delegação repetida (§0.1):** nenhum código, infraestrutura, credencial ou comando de VPS é delegado sem **contrato de lote aprovado + gate de passagem aprovado**. Divergência entre plano e execução ⇒ devolução ao orchestrator, nunca improviso.
- **Veracidade:** o caminho PR → VPS (R-1) está **aceito e aberto** por decisão do solicitante — **não bloqueia o go-live**, mas **exige aceite assinado no go/no-go** — e nenhum artefato pode marcá-lo como resolvido. As divergências entre `task-plan.md`, `implementation-contract.md`, `backlog.md` e `lote-p0-1-proveniencia.md` estão registradas em §4.6.1 e não foram mascaradas.
- **Próximo passo do orchestrator:** fechar GP-0 (custódia + atribuição + decisões **G0, G2, G3, G4, G5** com o solicitante) **após a re-verificação fresca de G0–G5 exigida em §4.2.1** — o estado de §4.1.1 é snapshot e não substitui essa medição — e, em seguida, submeter o lote P0-1 (`lote-p0-1-proveniencia.md`, revisão 3) à aprovação e à execução delegada, onde **G1** é executado e alimenta GP-1/GP-1b. Nada além disso começa antes.

---

## 19. Addendum de remediação de planejamento — 2026-09-25

**Natureza:** addendum **datado**, aplicado sobre a versão anterior deste documento. **Nada foi apagado:** o histórico das decisões (incluindo a revisão 2 do contrato do lote, que continua válida) está preservado, e todas as correções são localizáveis por achado. **Nenhuma implementação foi feita:** este addendum é só de planejamento.

| Achado | Correção aplicada neste documento |
|---|---|
| **B1** — gate circular (GP-0 exigia G1, executado só depois de GP-0) | §2.2 (GP-0 = G0, G2, G3, G4, G5; G1 → WS-01), §3.3 (itens 9 e 10 + estado dos gates), §4.2 (sequência + mapa de G6/G7), §4.3 (G1 executado no lote, alimentando GP-1/GP-1b), §4.4, §4.7 (GP-0/GP-1/GP-1b), §13.1 (HD-L), §15.1 |
| **B2** — R-1 com tratamento divergente e **capaz de bloquear** o go-live | §0.1, §1.2, §1.3, §4.6 (situação padronizada), §4.6.1, §4.7, §12.3 (item 9), §13.1 (HD-M), §13.2 (R-1), §15.1, §15.2 (linha de aceite assinado, nunca "resolvido"), §17 (D-03), §18 |
| **M1** — conflito AC-9 × `run-state.json` | §3.2 (nota de custódia de `run-state.json`), §3.3 (item 7), §4.3, §4.5, §4.7, §15.2, §16.1, e contrato do lote rev. 3 (**AC-10**) |
| **M2** — validação/pinning de host key sem dono | §5.1 (passo 2, evidência mínima, limite honesto, GP-2a), §5.4, §13.1 (**HD-U**), §13.2 (**R-16**), §14 (rollback de `known_hosts`), §15.1, §15.2, §17 (**D-15**) |
| **M3** — caminho crítico com convergência mal desenhada | §2.2 (novo desenho + tabela de dependências), §3.1 (gate de saída de WS-10), §12.2, §15.1 |
| **m1** — mapa G6/G7 incorreto | §4.2: G6 = formalização do WIP da run 1020 como lote próprio (com o desfecho **já decidido**, registrado no F9); G7 = critérios de aceite de proveniência do contrato mestre — **AC-1** **coberto por GP-1**, **AC-2** (mesmo SHA nos três ambientes, `implementation-contract.md`) evidenciado em **GP-4a/GP-10** e no go/no-go; nenhum dos dois é gate de GP-0 |
| **m2** — IDs inexistentes | `D-HD3` → **D-08** (§15.2); `HD-3` referenciado apenas com o escopo correto (equivalente no contrato do lote); **D-15** criado para host key |
| **m3** — subdomínios tratados como decididos | §5.3, §12.2 (passo 6), §13.2 (**R-15**), §16.1, §17 (**D-01**), §14: nenhum hostname de ambiente é afirmado sem decisão |
| **m4** — ambiguidade "nesta fase" | §4.5, §4.6, §4.6.1, §5.1, §8 (mantido onde o escopo é realmente o programa), §12.1, §13.1, §15.2, §16.1/§16.2, §17, §18: "nesta fase" → "no lote P0-1/F0" ou "nesta fase do programa", conforme o escopo real |
| **m5** — soak sem ambiente definido | §12.2 (soak em **HOMOLOG**), §13.1 (**HD-T**), §15.1, §15.2, §17 (**D-13**) |
| **m6** — cobertura de P2-05/P2-06/P2-07 ausente | §3.1 (linha de cobertura de P2 + itens de backlog), §12.2 (passos 4 e 5), §15.1 |
| **m7** — snapshot `645aca3` tratado como atual | §4.2, §13.1 (HD-L/D-08), §15.2, §17 (D-08) e contrato do lote (HD-3): marcado como **snapshot datado**; SHA de release **re-derivado** no início do lote |
| **m8** — corrupções de texto | §1.2 (`acionável`), §4.1 (`usuário vê`), §5.3 (`ALLOWED_HOSTS`/CORS), §10.2 (`leitura; GA4`), §12.2 (`backup e restore testados`), §14 (`reconciliação registrada e datada`), §17 (`Janela e responsáveis`) |
| **m9** — placeholder de template aparente (chaves duplas) | §4.6: a expressão do workflow foi reescrita em prosa (`github.event.pull_request.head.sha`), preservando o fato e eliminando o token de placeholder |

**Concordância entre artefatos após este addendum (checada por leitura):** CI/CD intocado no lote P0-1/F0 e nesta fase do programa · **R-1 aceito, aberto, não bloqueante, com aceite assinado no go/no-go** · domínio canônico `https://portal-noticias.com/`, com a divergência dos workflows registrada como **R-15** · WIP da run de observabilidade **isolado** (R-17, HD-5) · `settings.py` apenas **verificado** no lote (G1 → GP-1/GP-1b) · gates com dependências explicadas em §2.2 e §3.1.

### 19.1 Acabamento documental pós-revisão independente — 2026-09-25

**Natureza:** aplicação **exclusivamente documental** das ressalvas **R1–R11** da revisão independente (veredito `passed`, 0 blocker, 0 major). **Nenhuma decisão do solicitante, nenhum gate, nenhuma dependência e nenhum escopo mudou**; nenhuma implementação foi feita, nenhum comando Git de escrita, nenhum acesso à VPS. As versões e os addenda anteriores permanecem válidos e preservados.

| Ressalva | Onde foi aplicada |
|---|---|
| **R1** — colchete/ASCII do caminho crítico | §2.2: desenho refeito — **GP-5/GP-6/GP-8 → GP-10**; **GP-9** depende de GP-5+GP-6 e é independente de GP-10; **GP-7** depende de GP-4b+GP-6 e é independente de GP-10 |
| **R2** — GP-11 sem listar GP-7/GP-9 | §2.2 (tabela de dependências + bullet), §15.2 (linhas de GP-7 e GP-9 marcadas como exigidas no go/no-go) |
| **R3** — G7 superestimado | §4.2 (critério 1 coberto por GP-1; critério 2 **parcialmente** coberto, evidência em GP-4a/GP-10 e go/no-go), §6.1 (GP-4a), §12.2 (GP-10), §19 (linha m1) |
| **R4** — rollback confuso com comando Git | §14 (linha F0: **auto-reversão lógica** só dos arquivos autorizados pelo lote; `checkout`/`reset`/`restore`/`clean`/`stash`/`switch` **proibidos** no rollback) + nova regra transversal 5 |
| **R5** — exit code sem `--expected-sha` | `lote-p0-1-proveniencia.md`: Interface 1, AC-4, comandos de validação e DoD — ausência da flag ⇒ **exit `1` (incompleto)**, mantendo `0/1/2` |
| **R6** — typos e frases quebradas | §4.3 (`eficácia condicional`), §4.2 (**G7: `exagerar` o alcance**), §4.6.1 (`**Não satisfeito**` — critério 4 do contrato), §4.7 (`G7 é **satisfeito** por GP-1`), §7.1 (`ingestão`), §9.1 (`— WS-12`, `estado de pagamento`), §19 (`capaz de bloquear`); contrato do lote (`Código não aprovado`, `decididos`, `afirmado`, `capaz de bloquear`) |
| **R7** — HD-5 fora da matriz | §13.1: linha **HD-5** criada, com o conteúdo de HD-5 preservado |
| **R8** — R-13 com subdomínios afirmados | §13.2 (R-13 alinhado a **D-01/D-11/D-14**; nenhum hostname assumido antes da decisão) |
| **R9** — ownership de `run-state.json` | §3.2 (tabela + nota: **orchestrator** durante o programa, **historian** só no **F9**, **executor nunca**); espelhado em `task-plan.md` §Restrições, `implementation-contract.md` AC 44 e `backlog.md` (addendum M1) |
| **R10** — F9 e desfecho da run 1020 | §4.2 (G6), §12.2 (passo 8), §13.2 (R-17), §15.1 (GP-11), §15.2: F9 **registra** o desfecho decidido, **inclusive a run 1020 mantida aberta**, sem afirmar fechamento |
| **R11** — texto de versão anterior em §4.6.1 | §4.6.1: todas as citações de versão anterior marcadas **(versão anterior)** + nota de leitura deixando explícito que a exigência antiga de remover PR → VPS **não está vigente** |

### 19.2 Segunda rodada de remediação de planejamento — 2026-09-25 (estado Git re-derivado)

**Natureza:** aplicação **exclusivamente documental** dos achados da revisão de planejamento (1 major, 5 minor, 5 nit). **Nenhuma decisão do solicitante mudou** — CI/CD permanece intocado, **R-1** continua **aceito, aberto, não mitigado, não coberto pelo gate e não bloqueante, com aceite assinado no go/no-go**, o **domínio canônico** continua sendo `https://portal-noticias.com/`, o WIP da run `20260925-1020-observabilidade` continua **isolado**, `settings.py` continua **apenas verificado**, a execução segue por **subagentes especializados** e **sem datas artificiais**. Nenhuma implementação foi feita; nenhum comando Git de escrita; nenhum acesso à VPS; nenhum `implementation-history.md` criado.

**Estado Git efetivamente observado (leitura apenas, carimbada em 2026-09-25T18:32:47Z / 15:32:47 -03:00):** registrado **integralmente** em **§4.1.1**, com o comando de leitura de cada linha. Resumo: `develop` e `origin/develop` **iguais** em `7715dae8`, paridade `0/0`; `948a5b5`/`645aca3` **já no remoto**; `4c57ff04` ***dangling*, ausente do reflog, recuperável só por SHA**; divergência **ref solta × `packed-refs` ainda aberta**; worktree `wt-merge` ainda registrado como `prunable` com diretório ausente; `stash` vazio; 8 rastreados modificados + 21 não rastreados; `.gitignore` sem regra para `agentic-framework/state/`. **Nenhum snapshot antigo foi reaproveitado.**

| Achado | Correção aplicada neste documento |
|---|---|
| **MAJOR 1** — o documento afirmava estado Git que **não** se sustenta: `develop` 2 commits à frente, `948a5b5`/`645aca3` precisando de push, `4c57ff04` "recuperável só por reflog" | **§4.1.1 (novo)**: estado re-derivado com timestamp, comando de reprodução por linha e lista explícita das três afirmações **não** sustentadas. **§4.1 item 3** reescrito como afirmação de planejamento não confirmada. **§4.2**: G2 (sem push pendente; decide-se a **política** de promoção; push reabre se a re-verificação mostrar divergência), G3 (SHAs de `packed-refs` atualizados; `4c57ff04` como ***dangling* por SHA**), G4 (entrada de worktree registrada, diretório ausente), G5. **§4.6.1**: nova linha citando a afirmação antiga como **(snapshot de planejamento anterior)**, com a nota de leitura ampliada. **§11.1**: `4c57ff04` qualificado. **§15.2**, **§16.1** e **§17 (D-08)** reescritos. `948a5b5`/`645aca3` e todos os SHAs de ref permanecem **snapshots datados**; nenhum é SHA de release |
| **MAJOR 1** (segunda parte) — GP-0 tinha de exigir artefato que só WS-01 produz | **§4.2.1 (novo)**: **re-verificação fresca obrigatória de G0–G5** (branch, `HEAD`, `origin/*`, paridade, refs, `status`, presença de `4c57ff04` por SHA, worktree, stash) com **timestamp**, registrada no inventário de **WS-00**; comandos de leitura fornecidos; reabertura da G correspondente em caso de divergência. **A re-derivação detalhada fica em WS-01/GP-1** (§4.3 passo 1). **§2.2** (linha GP-0), **§3.3** (novo item 11 + estado dos gates), **§4.7** (checklist GP-0), **§13.1** (HD-L). **Sem circularidade:** GP-0 depende só de decisões humanas + leitura; G1 continua fora de GP-0 |
| **MINOR 2** — WS-14 dependia de "todos os WS anteriores" | **§3.1**: dependência real — **GP-5, GP-6 e GP-8 `pass` + GP-4b vigente**; GP-7/GP-9 testados antes do go/no-go, não pré-requisito de GP-10; WS-13 é transversal e WS-02/WS-04 entram por GP-1b/GP-2b. **§12.2**: coerência explícita com §2.2/§3.1 |
| **MINOR 3** — P0-01 misturava baseline/reconciliação com re-derivação, e GP-0 exigia artefato de WS-01 | `backlog.md`: **P0-01** passou a ser reconciliação/inventário/ownership + decisões G0–G5 + **re-verificação fresca** (saída de WS-00/GP-0); **P0-01b (novo)** passou a ser a **re-derivação detalhada** do estado Git e a baseline de release, em **WS-01/GP-1**, dependente de P0-01. Aqui: §4.2.1 e §4.3 passo 1 |
| **MINOR 4** — prova de não-vazamento de segredo tautológica | `lote-p0-1-proveniencia.md`: comandos substituídos por prova com **literal sintético real** em **arquivo rastreado de repositório de fixture descartável, fora do repositório do portal**, com **controle positivo** (o literal está no arquivo), **prova de detecção** (o gate reporta o achado) e **prova de não-vazamento** em `stdout`, `stderr` e `--json`. Aqui: §4.3 passo 5 |
| **MINOR 5** — "critério 24" ambíguo entre contrato e backlog | **§2.2**: **AC-24 do `implementation-contract.md`** (plano inativo/sem credencial ⇒ assinatura bloqueada) + **`P1-08` do `backlog.md`**; **§4.2**: G7 citado como **AC-1/AC-2 do `implementation-contract.md`**; **§19** (linha m1) alinhado |
| **MINOR 6** — diretório de estado da run sem tratamento explícito | **§4.2 (G5)**, **§4.3 (passo 1)**, **§4.5**, **§4.7**, **§15.2**, **§16.1** e **§17 (D-08, item f)**: `agentic-framework/state/run-20260925-1433-go-live-producao/` é **artefato não rastreado de planejamento desta run, fora de release, re-derivado a cada gate**, resolvido por **inventário + ownership**, **sem editar `.gitignore`** (`.gitignore` declarado intocado) |
| **NIT 7** — `able a bloquear` | `task-plan.md` §19 (linha B2): `capaz de bloquear` |
| **NIT 8** — `exaggerar` | **§4.2** (G7): `exagerar` |
| **NIT 9** — mapa §19.1 R6 apontava `satisfeito` para §4.2 | **§19.1 (R6)**: localizações reais — **§4.2** (`exagerar`), **§4.6.1** (`Não satisfeito`), **§4.7** (`satisfeito por GP-1`) |
| **NIT 10** — linha de DoD do lote como citação histórica sem marcador | **§4.6.1**: linha do `lote-p0-1-proveniencia.md` DoD marcada **(versão anterior)**, coerente com R11 |
| **NIT 11** — `run-state.json` | **Não editado** (nenhuma escrita nesta rodada). Registrado aqui: o `orchestrator` o atualizará **após a revisão final**, com **timestamp posterior** ao desta remediação; `executor` nunca escreve; `historian` só no F9 (§3.2, §3.3 item 7, §4.7, §15.2) |

*Remediação restrita a `task-plan.md`, `implementation-contract.md`, `backlog.md`, `action-plan.md` e `lote-p0-1-proveniencia.md` da run `20260925-1433-go-live-producao`. `provenance-reconciliation.md` **não** foi editado: ele permanece como snapshot de planejamento e é lido junto de §4.1.1.*

---

*Documento produced na fase de planejamento da run `20260925-1433-go-live-producao`. Único arquivo criado por este subagente: `agentic-framework/state/run-20260925-1433-go-live-producao/action-plan.md`. Nenhum outro arquivo editado; nenhum comando Git de escrita; nenhum acesso à VPS.*

*Addendum de remediação de planejamento (2026-09-25, §19): o `action-plan.md` foi revisado, assim como `task-plan.md`, `implementation-contract.md`, `backlog.md` e `lote-p0-1-proveniencia.md` (revisão 3). Nenhum código, workflow, run anterior, VPS ou `run-state.json` foi alterado; nenhum comando Git de escrita foi executado; nenhuma data de calendário foi criada.*

*Acabamento documental pós-revisão independente (2026-09-25, §19.1): as ressalvas **R1–R11** do reviewer foram aplicadas **apenas** a `task-plan.md`, `implementation-contract.md`, `backlog.md`, `action-plan.md` e `lote-p0-1-proveniencia.md`. Nenhuma decisão, gate, dependência, escopo ou versão foi alterado; nenhum `implementation-history.md` foi criado; nenhum código, workflow, VPS, run 1020, run 2136, `settings.py` ou `run-state.json` foi tocado; nenhum comando Git de escrita foi executado.*

*Segunda rodada de remediação de planejamento (2026-09-25, §19.2): estado Git **re-derivado** por leitura em 2026-09-25T18:32:47Z e registrado em §4.1.1; achados major/minor/nit aplicados **apenas** nos cinco artefatos de planejamento desta run. Nenhuma decisão, gate, escopo ou versão mudou; **nenhum** `implementation-history.md` criado; `run-state.json` **não** foi editado — o **orchestrator** o atualizará **após a revisão final**, com timestamp **posterior** ao desta remediação; `provenance-reconciliation.md`, run 1020, run 2136, `settings.py`, `.github/`, `.gitignore`, código, workflows e VPS intocados; **nenhum comando Git de escrita**.*
