# Termo de Aceite — R-1 · Portal de Notícias

**Versão:** 1 · **Data de redactação:** 2026-09-28
**Redigido por:** o agente de orquestração, a pedido do solicitante
**A assinar:** o solicitante

> Este termo existe porque **publicar não é o mesmo que entregar**. Ele registra
> o que está provado, o que **não** está, e o que permanece bloqueado. Assinar
> significa aceitar os dois lados do que está escrito, não apenas o lado bom.

---

## 1. O que está sendo aceito

**Base:** `origin/develop` = `1dec732` (publicada, CI verde)
**Alvo da aceitação:** o portal em `main`, com a lista da seção 3 fechada.

### 1.1. Estado publicado e medido

| Item | O que entrega | Número medido |
|---|---|---|
| P0-1 | Gate de proveniência de release | 10/10 checagens · sha256 `32ed34b3…` congelado |
| P0-02b/02c | Integridade e hardening de settings | `check --deploy` sem warning novo |
| P0-08 | Conteúdo fictício barrado | guarda exit 0 |
| P0-10 | Hardening: XSS, SSRF, uploads, health | — |
| P1-01/01b | Limites de ingestão + política dos 29 admins | 20/20 |
| P1-02 | Fallback de OpenAI | dublê de egress, sem rede |
| P1-03 | Workers, beat e estado de filas | 6 testes anti-falso-verde |
| P1-13 | B2B | — |
| P1-15/15b | Rotas de formulário + endpoint de contato | 71 testes |
| P1-16/16b | Tooling e guardas de frontend | `npm audit` **0 vulnerabilidades** |
| O1 | Formulário de contato ligado ao endpoint real | 200/400/503/429 por HTTP real |
| P1-11 | Cutover do cache `feed:v1` → `feed:v2` | Redis real; reverter faz **exatamente 1** teste falhar na suíte inteira |
| P1-07 | Caminho de dinheiro | 74 testes (era 30) · 6 mutações detectadas |
| P1-06 | Newsletter e descadastro | 127 testes · 4 estados comparados byte a byte |
| P1-04 | Entrega de e-mail | gate de 2 etapas · 24 testes reprovam ao reverter |
| P1-08 | Vazamento de Premium | matriz de 15 linhas, **0 divergências** |
| P1-09/10 | Anúncios e analytics | poder discriminante medido **em navegador** |

**Suíte combinada, medida com os 8 itens rodando juntos:**
`1349 passed · 0 falhas · 93,09%` · `check` limpo · `check --deploy` idêntico ao
baseline · gate 10/10.

A contagem **subiu** e **nenhum teste deixou de coletar** — verificado comparando
os conjuntos de identificadores de teste, não confiando no número.

### 1.2. Quatro blockers que estavam em produção e foram fechados

1. **Webhook de pagamento sem autenticação de origem.** `AllowAny` com
   `authentication_classes` vazias, zero verificação de assinatura, identificador
   de pré-pagamento **sequencial**.
2. **Sequestro de conta no login social por e-mail não verificado**, e ausência
   total de proteção CSRF — o vínculo ficava persistido no banco.
3. **Descadastro de newsletter como oráculo de cadastro.** Direito de
   cancelamento (art. 8º, V) permitia consultar se alguém está inscrito (art. 19).
4. **Cadastro, redefinição e newsletter anunciavam entrega de e-mail que não
   acontecia.**

Cada um foi medido antes da correção, com o defeito reproduzido.

---

## 2. O que NÃO está provado

Assinar este termo significa aceitar estas lacunas como lacunas.

| # | Não provado | Por quê |
|---|---|---|
| 1 | **Entrega real de e-mail** | `RESEND_API_KEY` não fornecida. O gate recusa, fail-closed. **O cadastro responde 503** |
| 2 | **HMAC do webhook contra o provedor real** | `ASSINATURA_MP_WEBHOOK_SECRET` não fornecida. O esquema é testado contra si mesmo |
| 3 | **Renovar, cancelar e reconciliar de verdade** | Sem credencial de sandbox |
| 4 | **Caminho feliz do login social** | `GOOGLE_OAUTH_CLIENT_ID` não fornecida. O *contrato* está provado; a assinatura real do provedor, não |
| 5 | **Anúncio e GA4 reais** | Sem conta. `ADSENSE_CLIENT_ID` é vazio; GA4 não implementado |
| 6 | **Importação dos painéis e disparo de alertas** | Sem Grafana Cloud. `promtool` valida a decisão da expressão, não a entrega ao canal |
| 7 | **`alloy run` ponta a ponta, `head-object` real** | Sem credencial |
| 8 | **Restore de backup executado** | Dependência do P0-06 |
| 9 | **Aparência visual** | Toda prova de interface foi `jsdom`, `tsc`, build e Chrome headless. **CSS e pintura nunca foram vistos por olho humano** |
| 10 | **Revisão jurídica e base legal da newsletter** | Pendência jurídica. O consentimento não tem data própria de concessão nem de revogação |

---

## 3. O que precisa estar fechado para publicar em `main`

| # | Item | Estado |
|---|---|---|
| 1 | MAJOR-1 — limite de requisição anulado por cabeçalho forjável | em execução |
| 2 | Vazamento do corpo do provedor no log, e o teste que promete o que não verifica | em execução |
| 3 | `X-Forwarded-For` e os 2 pingeres de observabilidade | em execução |
| 4 | As 5 mudanças autorizadas em `.github/` | **pronto e verificado** |
| 5 | Suíte completa + gate verdes no estado combinado | a rodar |
| 6 | **Revisor independente** da branch integrada | pendente — nenhum dos que escreveu revisou o conjunto |
| 7 | Verificação visual com a pessoa navigando | pendente |

---

## 4. O que NÃO bloqueia `main` e por quê

- **6 P0 de infraestrutura** (rotação de SSH, portas, DNS/TLS, backup externo,
  isolamento de ambientes, host key). São de **produção**, não de código. Não
  impedem `main`; impedem declarar que o ambiente está seguro.
- **Consolidação do WIP de observabilidade** (20 commits). Julgado
  **NÃO ADOTÁVEL** com 6 blockers. Só a parte de infraestrutura entrou, e só
  depois de consertada. Não será adotado.

---

## 5. Riscos residuais que permanecem depois de `main`

1. **O cadastro está 503 em DEV.** Não é defeito: é o gate recusando
   honestamente a falta de canal. Destrava com a credencial.
2. **Alertas de taxa só são confiáveis depois do MAJOR-1.** Até lá, um cliente
   pode influenciar a métrica que o alerta observa.
3. **Termo de aceite visual ausente.** A interface pode ter defeito de
   aparência ou de leitura em celular que nenhum teste acima enxerga.
4. **Contas possivelmente vulneráveis.** O defeito do login social allows
   vinculação por e-mail não verificado. O endpoint era anônimo e sem CSRF, mas
   **a interface do portal nunca o chamou** — a exposição era requisição direta.
   Ainda assim, audite as contas vinculadas contra o estado de verificação de
   e-mail antes de anunciar o serviço.
5. **Revisão jurídica não feita.** A política vigente é rascunho.

---

## 6. Decisões já tomadas pelo solicitante

| Decisão | Efeito |
|---|---|
| Cancelar **não** corta o período pago | Comportamento mantido e fixado em teste. Mais protetivo do pagante |
| Retenção de métricas: **90 dias** | Afeta custo e o documentado nos painéis |
| Publicar até `main`; PROD **só** com este termo assinado | Caminho de publicação definido |
| Provisionar os 2 pingeres **antes** de cadastrar os monitores | Monitor sem pinger paga sem avisar e treina o time a ignorar o canal |
| Nenhuma credencial nesta rodada | As 7 validações com credencial seguem marcadas como pendentes |

---

## 7. Declaração

Eu, solicitante, declaro que:

- [ ] **Li** a seção 2 e estou ciente de que **10 itens não estão provados**,
      incluindo a entrega de e-mail e o caminho feliz do login social.
- [ ] **Estou ciente** de que o cadastro responde **503** até a credencial de
      e-mail existir, e que isso é intencional.
- [ ] **Aceito** publicar em `main` com esses pontos abertos, desde que
      documentados e visíveis.
- [ ] **Não** autorizo criação de tag de produção enquanto os itens da seção 3
      estiverem abertos, em especial o **revisor independente**.
- [ ] **Entendo** que a assinatura deste termo **não** substitui a revisão
      jurídica da política de privacidade.

**Assinatura:** _______________________________________  **Data:** ____________

---

## 8. Registro de honestidade

Este termo foi escrito para que a assinatura não possa ser dada em cima de uma
impressão favorable. Três fatos que **não** estão a favor da entrega, e que
constam aqui porque omiti-los tornaria o termo falso:

1. **Eu quebrei o cadastro em DEV.** Integrei o item que valida a entrega de
   e-mail sem ter a credencial. O estado mudou de "201 e nenhum e-mail sai" para
   "503 e nenhuma conta é criada" — mais honesto, e ainda quebrado. O empurrão
   foi meu.
2. **Parte das medições da Onda 1 foram feitas sob pressão de memória.** Criei 28
   worktrees que encheram a área temporária de memória, levando a máquina a 7,6 GB
   de troca em 8 GB. Testes sob troca são mais lentos e menos confiáveis. Não sei
   quais foram afetados nem em que grau.
3. **Não houve revisor independente até este ponto.** Só o primeiro item teve
   revisão por outro agente. O restante foi validado por quem escreveu.

O que mitigate a (1) e a (2) é que a suíte final roda de novo, com a máquina
saudável, no estado combinado — e é esse resultado, não os anteriores, que este
termo aceita.
