# Pingeres de heartbeat — os dois "quem_pinge" que o `checks.json` pedia

Este diretório (e `infra/backup/`) fecha a lacuna que o P2-01 registrou e que
impedia o cadastro de `cron_monitor_backup` e `cron_monitor_filas`:
**os dois cron monitors estavam definidos, e nenhum dos dois tinha pinger.**

Cadastrá-los sem pinger é pior do que não cadastrar: os dois pagariam o
plantão desde o primeiro dia sem nunca alarmar, e treinaríam o time a ignorar
o canal. Este diretório é a parte que faltava.

| cron monitor do `checks.json` | pinger | quem chama |
|---|---|---|
| `cron_monitor_backup` (linha 199) | `infra/backup/pingar-backup.sh` | cron diário, depois do backup |
| `cron_monitor_filas` (linha 217) | `infra/filas/pingar-filas.sh` | cron de 5 min |

---

## 1. O segredo: de onde vem o token, e por que ele não é um "token"

Não há token. A URL de heartbeat **é** a credencial.

> A URL de heartbeat é credencial — quem a tiver consegue anunciar um backup
> ou uma leitura de filas que não houve. (`checks.json:18`, `:214`, `:232`)

Ela vem de **variável de ambiente**, nunca de arquivo versionado:

| pinger | variável | documentada em |
|---|---|---|
| backup | `BACKUP_HEARTBEAT_URL` | `checks.json:207` (`heartbeat_url_env_var`) |
| filas | `FILAS_HEARTBEAT_URL` | `checks.json:225` (`heartbeat_url_env_var`) |

`pingar-backup.sh` e `pingar-filas.sh` **não imprimem a URL em nenhum
momento**: nem no stdout JSON, nem no stderr, nem no arquivo de estado, nem no
argv. As duas garantias, e as duas são testadas:

* **fora do argv** — o `curl` a recebe por stdin (`--config -`), e o `printf`
  que a monta é um *builtin* do bash. Com a URL direto no `argv` do `curl`,
  qualquer outro usuário da VPS a lê em `ps` durante os 20 s do `--max-time`.
  Um log bem fechado e um `ps` aberto continuam sendo um segredo aberto.
* **fora da saída** — a falha do `curl` é reportada pelo *código de saída*
  (6 = DNS, 7 = conexão, 22 = HTTP, 28 = timeout), que basta para a
  remediação sem que a credencial entre na linha.

Se `FILAS_HEARTBEAT_URL`/`BACKUP_HEARTBEAT_URL` não estiverem no ambiente, o
pinger **não falha calado**: ele calcula o veredito, imprime, e sai com **6**
(`sem-destino`) — um código que existe justamente para que "não tenho para
onde dizer" nunca seja lido como "está tudo bem".

---

## 2. O pinger 1 — backup: como "rodou" se distingue de "o script foi chamado"

`checks.json:213` pede o ping *"depois de `verify_s3_object` ter confirmado
os dois objetos, e só ali"*. O pinger é um script **separado**, e a decisão
foi deliberada:

* **o estado real medido em 2026-09-28**: os três cron de backup recebem
  `Permission denied` e o `pg_backup_pm2.sh` **nunca chega a ser executado**.
  Um ping dentro dele nunca dispararia, e o monitor ficaria em `desconhecido`
  para sempre;
* o `pg_backup_pm2.sh` está sendo corrigido por outro fluxo, e acoplar esta
  mudança a ele aumentaria o conflito sem ganhar garantia.

Um pinger que **verifica o estado por conta própria** cobre o caso que um ping
interno não cobre: o backup não rodou.

### A regra

O heartbeat só é enviado quando as três coisas abaixo são **medidas**:

1. `verificar_backup.sh` devolveu 0. A política de 26 h, de "nunca executou",
   de "sem destino" e de "marcador mentiroso" **não foi reimplementada** — ela
   é consumida (`verificar_backup.sh:75`, `:202` do `checks.json`, o mesmo 26
   h nos dois lugares). O exit 0 dele já implica cópia remota confirmada
   (`:280-301`).
2. O dump passa num **piso de conteúdo em bytes** — a camada que nenhum
   mecanismo existente tem.
3. O objeto da **mídia** também está no bucket. O watchdog confirma só o dump
   (`verificar_backup.sh:220`); o contrato do cron monitor fala nos **dois**
   objetos.

### O piso de conteúdo — medido, não estimado

Postgres 16.15 real, container isolado, 2026-09-28:

| cenário | bytes | `pg_restore --list` → TABLE DATA |
|---|---|---|
| banco sem tabelas de usuário | 809 | **0** |
| 2 tabelas, ZERO linhas | 4 144 | **2** |
| 40 tabelas, ZERO linhas | 79 150 | **40** |
| 1 tabela, 2 000 linhas × 200 bytes | 8 599 | 1 |

Duas conclusões que mudaram o desenho:

* **Contar linhas de `TABLE DATA` no TOC NÃO detecta dump vazio.** Um banco
  com 40 tabelas e zero linhas produz 40 dessas linhas. A discriminação que
  parecia óbvia está errada. O que sobra do TOC serve só como corrimão extra
  (separa os 809 bytes do resto), e o script diz isso no código.
* **`pg_restore --list` não traz tamanho de bloco de dados** — medido nos
  dumps reais, o formato é `dumpId; tableoid oid DESC`. Não existe leitura
  barata e exata de "este dump tem dados". O que resta é um **piso em bytes**,
  e é isso que o script aplica: padrão **1 MiB**, muito acima dos **48 KB** do
  dump que está em produção hoje.

O piso é um **piso, não uma prova**, e está escrito assim no código. Quem souber
o tamanho do dump real de produção deve subir
`BACKUP_PING_TAMANHO_MINIMO_BYTES` para perto dele, com folga, em vez de
deixar o padrão adivinhar. Desligá-lo (`BACKUP_PING_EXIGIR_CONTEUDO=0`) muda o
`status` para `ok-sem-piso` **e diz isso no `motivo`** — um painel que mostra
`ok` sem mostrar que o piso está desligado é o falso verde de volta, por outro
caminho.

### Exit codes

| exit | status | ping |
|---|---|---|
| 0 | `ok` | **enviado** |
| 1 | `backup-nao-verificado` / `midia-sem-confirmacao` | não |
| 2 | `conteudo-insuficiente` | não |
| 3 | `indisponivel` (configuração) | não |
| 4 | `ping-nao-entregue` (o backup está bom, o canal não) | tentado |
| 5 | o watchdog nem pôde rodar — "não sei", não "ruim" | não |
| 6 | `sem-destino` (não há `BACKUP_HEARTBEAT_URL`) | não |

São **distintos dos do watchdog** (`verificar_backup.sh:52-57`) de propósito:
quem watchdog `1` e quem pinger `1` dizem coisas diferentes.

---

## 3. O pinger 2 — filas: o JSONL e o rótulo

Cron de 5 minutos. Roda `manage.py saude_filas --json`, anexa ao JSONL que o
`loki.source.file "filas"` já lê (`config.alloy:293`) e avisa o Better Stack
**só no 0**.

* **Não usa `--ignorar-saida`.** O `PROVISIONAMENTO.md` §2.3 item 1 sugere
  esse flag, e ele é **diretamente contraditório** com a regra de reprovação do
  mesmo `checks.json:228`: com `--ignorar-saida` o exit é sempre 0 e um
  monitor que trata 0 como saúde nunca alarmaria. O pinger passa o exit do
  `saude_filas` direto para o cron, e os três códigos continuam significando
  o que `saude_filas.py:10-19` diz que significam. **0 e 3 nunca são
  achatados** — o teste tem um caso que falha se eles coincidirem.
* **O `desconhecido` (3) VAI para o JSONL.** Um JSONL onde só entram os `ok`
  mente por omissão, e é a omissão que ninguém vê no painel.
* **O `estado` é o único rótulo**, com os 3 valores do contrato
  (`filas_saude.py:51-53`). O wrapper **não sintetiza campo nenhum**: ele
  anexa a linha que o `saude_filas` imprimiu, sem acrescentar nada. Assim a
  cardinalidade do índice é a que o `config.alloy:308-333` já extrai, e não
  uma que o wrapper inventou.

### O JSONL não cresce sem limite — o que foi escolhido

Medido: uma linha tem ~2,3 KB. A 5 min são 288 linhas/dia ≈ 660 KB/dia ≈
240 MB/ano.

**Escolhido: rotação por contagem de linhas, com uma geração de sobreposição.**
Ao chegar em `PING_FILAS_MAX_LINHAS` (padrão **576** ≈ 48 h), o arquivo é
renomeado para `<arquivo>.1` — substituindo o `.1` anterior — e um novo é
criado. O total em disco fica em **~2× o teto** (2 × 576 linhas ≈ 2,6 MB).

* **Por que rotação e não truncamento.** O `loki.source.file` segue o arquivo
  por posição de byte. Truncar deixa a posição do leitor sem objeto e o Loki
  ou pula linhas ou relê do começo. Renomear e recriar dá um arquivo **novo**,
  com posição 0.
* **Por que o `.1` antigo é descartado, e não um `.2` que cresce.** O
  `ignore_older_than = "24h"` (`config.alloy:302`) já declara que nada com
  mais de um dia interessa ao coletor; e 576 linhas ≈ 48 h, então a rotação
  nunca descarta algo dentro da janela de leitura. Guardar `.2`, `.3`… seria
  guardar em disco o que ninguém vai ler.
* `flock` impede que duas execuções se intercalem: meia linha no meio do
  arquivo é um registro que o `stage.json` não extrai, justamente no
  incidente.

**Limite honesto:** o comportamento do tailer do Loki ao ver o inode mudar
(pode reler a janela retida) é o comportamento padrão de rotação de log, e
**não pôde ser provado aqui** — não há Alloy neste ambiente.

---

## 4. O sinal de "o pinger está morto"

Um pinger que depende de rede externa é um ponto único de falha, e o
`cron_monitor` externo **não distingue** as três causas de "não chegou
heartbeat":

| o que o Better Stack vê | o que aconteceu | o que se olha |
|---|---|---|
| sem heartbeat | o backup parou | o backup |
| sem heartbeat | o pinger parou | o cron do pinger |
| sem heartbeat | a rede/DNS/token quebrou | a saída da VPS |

As três paginam igual. A resposta é um **sinal local**, e ele tem duas partes:

1. **Arquivo de estado com mtime**, escrito em **toda** execução, inclusive
   nas que falham, e lido por `--saude-do-pinger` a partir de uma **entrada de
   cron SEPARADA**. A separação é o ponto: se a mesma entrada de cron fizesse
   as duas coisas, um pinger quebrado não teria como reportar que está
   quebrado.
   * exit 0 `pinger-vivo` · exit 1 `nunca-executou` / `pinger-parado` ·
     exit 3 configuração inválida.
2. **Para as filas, um sinal a mais e gratuito: a idade da última linha do
   JSONL.** É o mesmo dado que o painel exibe — visto do lado que o painel
   **não** mostra. O painel mostra a última leitura como se fosse de agora;
   o `--saude-do-pinger` diz que ela tem 2 h.

E o estado local é gravado **antes** de qualquer tentativa de rede, e de novo
depois: um pinger que não conseguiu falar com o destino ainda deixa rastro do
que mediu — que é a evidência que separa "a internet caiu" de "o pinger está
quebrado".

---

## 5. Instalação (o que o operador precisa fazer)

```bash
# 1. as URLs vêm do painel do Better Stack, para o env do serviço
BACKUP_HEARTBEAT_URL=<a URL do cron monitor 'backup-diario-pm2'>
FILAS_HEARTBEAT_URL=<a URL do cron monitor 'saude-filas-periodico'>
#    ^ valores NUNCA entram no repositório, no chat nem no log.

# 2. cron do pinger de backup — depois do backup diário
17 4 * * * /home/apps/portal-prod/infra/backup/pingar-backup.sh \
    >> /var/log/portal/backup-pinger.log 2>&1

# 3. cron do pinger de filas
3 * * * * /home/apps/portal-prod/infra/filas/pingar-filas.sh \
    >> /var/log/portal/filas-pinger.log 2>&1

# 4. as DUAS entradas que vigiam os pingers (cadências diferentes, de propósito)
7 * * * * /home/apps/portal-prod/infra/filas/pingar-filas.sh --saude-do-pinger \
    >> /var/log/portal/filas-pinger.log 2>&1
11 * * * * /home/apps/portal-prod/infra/backup/pingar-backup.sh --saude-do-pinger \
    >> /var/log/portal/backup-pinger.log 2>&1
```

O `--saude-do-pinger` precisa de **algum** consumidor para o exit != 0 não ser
um exit que ninguém lê. As opções são o e-mail do cron, ou o `verificar-env.sh`
do Alloy. Esta última é a natural e está **fora do escopo deste item** — é
provisão de quem opera a VPS.

### Variáveis de ambiente

| variável | padrão | o que faz |
|---|---|---|
| `BACKUP_HEARTBEAT_URL` | — | destino. Ausente ⇒ exit 6, nenhum ping |
| `BACKUP_PING_TAMANHO_MINIMO_BYTES` | `1048576` | piso de conteúdo do dump |
| `BACKUP_PING_EXIGIR_CONTEUDO` | `1` | `0` ⇒ `ok-sem-piso`, dito no motivo |
| `BACKUP_PING_EXIGIR_MEDIA_REMOTA` | `1` | exigir o objeto da mídia no bucket |
| `BACKUP_PING_PULAR_ESTRUTURA` | `0` | `1` ⇒ só o piso, sem `pg_restore` |
| `BACKUP_PING_SINAL_IDADE_HORAS` | `1` | idade máxima do sinal local |
| `FILAS_HEARTBEAT_URL` | — | destino. Ausente ⇒ exit 6, nenhum ping |
| `PING_FILAS_MAX_LINHAS` | `576` | teto do JSONL antes da rotação |
| `PING_FILAS_APP_DIR` / `PING_FILAS_PYTHON` | `<repo>/backend` / `.venv/bin/python` | onde roda o `manage.py` |
| `PING_FILAS_SINAL_IDADE_MINUTOS` | `20` | idade máxima do sinal local |

`BACKUP_MAX_AGE_HOURS` (26) e `ALLOY_FILAS_JSON_PATH` são as **mesmas** variáveis
do watchdog e do Alloy — é a reutilização que impede os dois lados divergirem.

---

## 6. Provas

```bash
bash infra/backup/testar-pingar-backup.sh     # 23/23
bash infra/filas/testar-pingar-filas.sh      # 20/20
```

Ambos contam os heartbeats num servidor HTTP local que faz as vezes de Better
Stack, e ambos têm uma seção que **reverte a garantia** numa cópia e mostra
que o veredito muda — inclusive as **mutações que NÃO desfazem a garantia**,
declaradas como tal (ver o relatório do run).

O teste de backup precisa de um `pg_restore` **real** e **aborta** se não
achar um: enfraquecer o pinger para o teste passar seria trocar uma garantia
por um verde.
