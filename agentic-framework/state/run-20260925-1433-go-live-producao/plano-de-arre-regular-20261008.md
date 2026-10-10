# PLANO DE ARREGAR TUDO — 2026-10-08

Derivado da síntese de 2026-10-08. Cada fase valida antes de integrar; **nada
junta tudo e só depois mede**. `develop` é alvo móvel — houve 6 dias em que a
outra sessão não publicou nada, o que muda o custo de re-merge para perto de
zero neste momento.

## Decisões do solicitante (2026-10-08)

| # | Decisão |
|---|---|
| 1 | Migration `0004` do double opt-in **AUTORIZADA** para aplicação |
| 2 | DNS: apontar **só** `portal-noticias.com` e `www` para `108.174.147.50`. DEV e HOMOLOG por **IP + Host header** |
| 3 | **Fechar `8080` e `8443`** (Caddy do `plataforma-educacao`) |
| 4 | **Rotacionar a senha do root** e desligar `passwordauthentication`/`permitrootlogin` **depois** que um deploy por chave passar no CI |
| 5 | Alcance: o que bloqueia PROD · publicar `develop`→`main` · levantar DEV para navegação · **os 7 itens de P2/observabilidade (P2-01..P2-07 do backlog recuperado)**. **Revisão jurídica da LGPD fora** (registrada como pendência) |
| 6 | **Não possui conta no Grafana Cloud nem no Better Stack** (perguntado e respondido em 2026-10-08). Consequência registrada: **P2-01 não é observabilidade** — é configuração em arquivo que não roda em nenhum ambiente. Ver "BLOQUEIO — telemetria sem conta" abaixo |

---

## BLOQUEIO — telemetria sem conta (2026-10-08)

Perguntado ao solicitante se havia conta no **Grafana Cloud** e no **Better
Stack**. Resposta: **não, por enquanto**.

Isso não é "falta instalar". É dependência externa com MFA. O que está no
repositório, e o que de fato **não** está rodando em lugar nenhum:

| No repositório | Estado real |
|---|---|
| 4 painéis Grafana em JSON | **arquivo**; nenhum Grafana apontando para eles |
| 14 regras de alerta Prometheus | **arquivo**; sem Prometheus, `absent()` e `for:` não são avaliados |
| coletor Alloy | **configuração**; nenhuma instância instalada |
| `verify-env.sh` do observability | roda, e **avisa** que falta — é a única parte que fiscaliza a verdade |

**O que isso significa na prática, sem eufemismo:**

- **Não existe detecção de incidente.** Nenhum alerta dispara em DEV, HOMOLOG ou
  PROD. Se PROD cair, o descobrimento é o visitante, não o sistema.
- **Não há painel nenhum.** Os 4 JSON não têm onde aparecer.
- **14 regras de alerta não avaliam nada.** Um arquivo de regras que ninguém
  executa é documentação, não proteção — e é o que a seção 8 do
  `infra/observability/README.md` já registra como a rejeição do WIP.
- **O `/metrics` da aplicação não tem consumidor.** A aplicação expõe
  métricas em formato Prometheus, e não há quem as colha.

**O que NÃO fazer com essa informação:** escrever "observabilidade pronta" ou
"resolvido". Qualquer relatório deste programa que diga isso está errado, e o
motivo está nesta seção.

**Alternativa que existe e não foi escolhida — custo explícito.** Dá para rodar
Grafana + Prometheus + Loki **na própria VPS**, sem conta externa. Medido hoje:
a máquina tem **3915 MB de RAM, com 1936 MB em uso** — sobram ~2 GB. Prometheus e
Loki sozinho cabem; o Grafana também, mas é apertado. O custo é Maintenance e
superfície de falha numa máquina que está **estável e é o único ambiente de
produção**. Decisão do solicitante, não minha, e **não recomendada enquanto DNS,
TLS e a reconciliação de PROD estiverem abertos** — porque o objetivo declarado
agora é estabilidade, e adicionar três serviços a um servidor de 4 GB é o
contrário disso.

---

## FASE 1 — Destravar o repositório (risco datado)

**1.1 Fix do backup.** O script corrigido está **não commitado na VPS** (`M` em
PROD e HOMOLOG) e ausente de `develop`. O `deploy.yml` faz `git reset --hard`
(linhas 289, 291, 294, 304, 307), então **qualquer deploy reverte o backup para
a versão quebrada**. O fix entra por arquivo, não por merge do branch: o branch
`backup-pm2-6-quebras` diverge em 10 arquivos que são só a base antiga dele.

Critério: sha de `infra/backup/pg_backup_pm2.sh` em `develop` = `93edff7e…`,
igual ao que roda na VPS. Depois disso, `git reset --hard` na VPS traz a
versão **certa** de volta.

**1.2 Defeito do revisor.** `settings.py:671` tem 3 backends,
`email_entrega.py:82` tem 5 — faltam `filebased` e `""`, e não existe o teste
que prende as duas listas. O par pior possível: `verificar_canal_email()`
recusa e o boot cala.

**Não** é merge do branch `revisor-final`: ele branchou antes do picsum, então
mergear faria o `develop` perder `frontend/lib/placeholder.ts` e
`frontend/testes/placeholder.test.mjs`. Reaplicar por cima do `develop` atual.

---

## FASE 2 — Migration `0004` (autorizada)

Dump antes em DEV e HOMOLOG → aplicar → verificar colunas e job → publicar o
double opt-in em `develop` → suíte + gate.

Medido: **0 inscrições nos três ambientes**, então a consequência de desligar o
envio de quem já estava inscrito não atinge ninguém. PROD aplica `0003` + `0004`
juntas, dentro do deploy.

Ordem obrigatória: **aplicar a migration ANTES de publicar o código**, porque
o código novo morre com `column token_confirmacao does not exist`.

---

## FASE 3 — `develop` → `main`

`main` recebe `develop` com suíte e gate verdes. `main` **não** dispara deploy
de PROD: `deploy-prod.yml` só dispara em tags `v*`.

---

## FASE 4 — Fechar `8080`/`8443` na VPS — **FEITA 2026-10-08**

### O que elas eram

Não eram portas soltas: `8080` e `8443` são o **ingress público de produção** do
`plataforma-educacao` (`plataforma-educacao-prod-caddy-1`, `Up 2 weeks (healthy)`,
`0.0.0.0:8080→80` e `0.0.0.0:8443→443`). O solicitante foi avisado e autorizou
mesmo assim.

### Medição que corrigiu a minha leitura

Eu disse que o sistema "não servia nada" — 0 conexões, nenhum certificado TLS
emitido, log do Caddy vazio. **A leitura estava errada.** Os contadores de DNAT
mostram tráfego real:

```
table ip nat, PREROUTING:
  tcp dport 8080  counter packets 24552  dnat to 172.22.0.6:80
  tcp dport 8443  counter packets 33983  dnat to 172.22.0.6:443
```

**Ausência de log não é ausência de tráfego.** O log do Caddy estava vazio, e eu
usei isso como prova de que ninguém usava. O contador do DNAT é a fonte certa.
O solicitante foi recommunicado e confirmou o fechamento.

### Por que `DOCKER-USER` não funciona para portas publicadas

O Docker faz DNAT na cadeia `nat`/`PREROUTING` (`dport 8080 → 172.22.0.6:80`).
Quando o pacote chega em `filter`/`forward`, a porta de destino **já é 80/443**.
Uma regra em `DOCKER-USER` casando `dport 8080` **nunca casa**. Medido: regra
inserida, contador em 0 pacotes, e a porta continuava servindo de fora
(`HTTP 308`, `Server: Caddy`).

### Por que `ufw deny` também não funciona

O tráfego de porta publicada do Docker **não percorre a cadeia `INPUT** — é
DNAT em `prerouting` e segue por `forward`. O `deny` do UFW vive em
`ufw-user-input`, que é `INPUT`, então nunca é consultado para esse tráfego.

Correção de um erro meu: cheguei a dizer que `ufw-user-input` tinha um
`ACCEPT all` na regra 1. **Não tem** — é `ACCEPT tcp dpt:22022`. O motivo real
é o caminho, não a ordem.

### O que funciona

`nft insert rule ip nat PREROUTING iifname "ens3" tcp dport { 8080, 8443 } counter drop`
— antes do salto para `DOCKER`.

**Prova, não leitura:** de fora `000` nas duas portas; o contador do DROP
registrou as tentativas; o DNAT parou de crescer; portal `200` nos três vhosts;
containers do outro sistema `healthy`; SSH intacta.

### Persistência — e o achado de que nada persistia

**Não havia hook de boot.** As 5 regras antigas do `DOCKER-USER`
(`4300, 4200, 4100, 3306, 3000`) estavam vivas só enquanto o Docker não
reiniciasse — um reboot ou `docker compose down/up` abria tudo, sem ninguém ver.

Criado `/usr/local/bin/aplicar-regras-firewall.sh` +
`aplicar-regras-firewall.service` (`After=docker.service`, três passadas com
30 s de intervalo porque o Docker sobe aos poucos e pode reescrever as chains
depois). **Idempotente, verificado:** três execuções seguidas, zero duplicata.

Os `deny` do UFW que eu tinha criado foram removidos: não faziam nada, e um
controle que parece fechar uma porta e não fecha é o tipo de falso verde que
este programa existe para eliminar.

---

## FASE 5 — DEV para o solicitante navegar

DEV já roda `develop`. Levantar e entregar acesso. Funciona por IP + Host
header (`dev.portal-noticias.com.br`), sem depender de DNS.

---

## FASE 6 — SSH

6.1 Rotacionar a senha do root (a atual está no histórico do chat).
6.2 Provador um deploy por chave no CI. Enquanto isso, **senha fica ligada**.
6.3 Só então desligar `passwordauthentication` e `permitrootlogin`, com
**rollback automático em 10 min**: se o CI não conseguir conectar, o servidor
volta sozinho ao estado anterior e oCoordinate avisa.

Sequência invertida quebra o pipeline. Ordem correta: chave primeiro, senha
depois.

---

## FASE 7 — P2 / observabilidade (7 itens)

**`observability-20260925-1020` NÃO É MERGEÁVEL.** Ele tentaria apagar
`scripts/release/verificar-proveniencia.sh` (851 linhas, sha256 congelado em
`32ed34b3…b57b59`) e `scripts/verificar-gate-usuarios-teste.sh` (673 linhas):
400 arquivos, +42.204/−66.999. Branchou de uma base muito antiga.

Método: cherry-pick de commits soltos, nunca merge. Cada item P2 entra medido
e sozinho.

---

## BLOQUEIO INVESTIGADO — `Deploy DEV` sem jobs (2026-10-08)

### O sintoma

`Deploy DEV` termina em **0s**, `conclusion=failure`, com **zero jobs**. Não é o
CI: `verify` nunca chega a rodar. `develop` está verde no CI
(`✓ frontend-build`, `✓ backend-tests`) e o deploy continua sem nascer.

**Não é a credencial ausente.** Em 2026-10-08 eu apostei que faltava o secret
`VPS_SSH_KEY` nos chamadores, corrigi os quatro (deploy-dev, deploy-homolog,
deploy-prod e **rollback**, que eu tinha esquecido) e o run continuou com zero
jobs. A hipótese era plausível e **falsa**.

### O isolamento, por sonda em branch separado

`develop` não foi tocado durante a investigação. O branch `probe/deploy-bisect`
foi apagado depois — as variantes do `deploy.yml` que ele carrega quebram o
deploy se alguém mesclar.

| variante | linhas | bytes | chars de script | jobs |
|---|---|---|---|---|
| `deploy.yml` de 2026-09-29 | 644 | 33.190 | 21.576 | **4** |
| atual menos 16 linhas | 737 | 39.172 | 24.407 | **4** |
| atual menos 8 linhas | 754 | 40.387 | 25.408 | **0** |
| atual | 762 | 40.966 | 25.883 | **0** |

O que **não** é a causa, medido: as declarações de `secrets` no
`on.workflow_call`; o bloco `with:` do `ssh-action` (`key:`, `env:`, `envs:`); a
validação de `ALLOWED_HOSTS` isolada; as mudanças de dependência.

### O que ficou em aberto, e deliberadamente

**Não identifiquei o limite.** O limiar está entre 24.407 e 25.408 caracteres de
script. **Não existe número redondo conhecido de limite do GitHub Actions que
caiba aí**, e uma virada em 8 linhas não é base para declarar "é limite de
tamanho". Registrado como correlação medida, não como causa. Declarar o número
seria inventar.

### A causa raiz é de manutenção, e ela é anterior ao sintoma

Um shell de **25.883 caracteres dentro de YAML** é a razão pela qual a sessão
anterior passou **35 execuções** de uma sonda (`zz-sonda.yml`, runs intitulados
"27 de 30 comentários", "tamanho: 250 linhas de comentário") sem fechar. O que a
sonda provou, quando alguém foi buscar os jobs de um run dela: **o `deploy.yml`
era válido**, os 4 jobs existiam, e a falha era de verdade nos testes — porque a
própria sonda passava `verify_ref` com 40 zeros. Ela mediu a coisa errada.

Corção autorizada pelo solicitante: **extrair os dois scripts para
`infra/deploy/`**, trocando cada `${{ inputs.X }}` por variável de ambiente. O
YAML cai para ~200 linhas, a pergunta do limite desaparece sem depender de
adivinhá-lo, e o script passa a ser executável **fora do GitHub** — que é o que
o harness do gate `usuarios_teste` já faz hoje com o script embutido.

### Erro de método meu, duas vezes

Imprimi a conclusão **invertida** — "a causa é X" quando `jobs=4` significa que X
*funcionava* — porque confiei no `if` sem reler o dado. Duas vezes. Quase
anunciei a causa errada. O `if` é o que se corrige primeiro, antes de falar.

- **DNS**: `portal-noticias.com` e `www` → `108.174.147.50`. Sem isso não há
  TLS, e sem TLS PROD não é PROD.
- **`RESEND_API_KEY`**: cadastro em **503 medido** nos três ambientes.
- **`VPS_SSH_KEY`**: `cat /root/.ssh/deploy_ci` na VPS → secret do GitHub.
  Pré-requisito da Fase 6.3.
- **Credencial do R2**: hoje o backup só existe nesta VPS, e o próprio script
  avisa isso no log a cada execução.
- **Assinatura do R-1** → libera a tag `v*` → PROD.

## Registrado sem solução, por decisão

- Revisão jurídica da LGPD (política de privacidade é rascunho).
- PROD em `v1.0.29` (`290a7b7`), 8 dias, sem nenhum dos 11 itens da Onda 1:
  o oráculo de enumeração e a mentira de entrega continuam no ar até a tag.