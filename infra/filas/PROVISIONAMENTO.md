# Provisionamento das filas (P1-03) — dependência humana, item P0-07

Este arquivo **não** é um tutorial. É a lista exata do que falta para a
terceira parte do critério de saída do P1-03 — *"task registrada, consumida
e **monitorada por ambiente**"* — virar verdade em DEV, HOMOLOG e PROD.

Nenhuma linha aqui foi executada. O P1-03 entrega o **código** que mede e o
**formato consultável** (`manage.py saude_filas`); o provisionamento é
alguém com acesso às máquinas. Até essa pessoa agir, o estado honesto dos
três ambientes é `desconhecido` — e o código diz isso, em vez de dizer `ok`.

---

## 1. O que o código já faz (não precisa ser feito de novo)

| # | O que | Onde |
|---|---|---|
| 1 | Task do heartbeat registrada com nome estável | `backend/config/tasks.py` → `config.tasks.heartbeat_beat` |
| 2 | Heartbeat agendado no beat, a cada 5 min | `backend/config/settings.py` → `CELERY_BEAT_SCHEDULE["portal-heartbeat-beat"]` |
| 3 | Relatório de saúde com 3 estados e 3 códigos de saída | `backend/manage.py saude_filas` (`backend/config/management/commands/saude_filas.py`) |
| 4 | Leitura durável de fila/worker/heartbeat/último ciclo | `backend/config/filas_saude.py`, `backend/config/filas_estado.py` |
| 5 | Retry com backoff e tentativas observáveis na ingestão | `backend/catalogo_noticias/tasks.py` |
| 6 | Idempotência do reprocessamento | `NewsItem.url_fonte_original` `UNIQUE` + filtro em lote de `services/ingestao.py` |

O que **não** é código e depende de alguém: os itens 2 a 6 da tabela
abaixo.

---

## 2. O que falta, por ambiente

### 2.1 Os três processos, por ambiente

Para cada um de `dev`, `homolog`, `prod`:

```bash
# 1. broker + cache (o compose já descreve isto em docker-compose.yml)
#    DEV/HOMOLOG/PROD rodam com systemd+PM2, nao com compose — o compose e
#    a referencia de CONFIGURACAO, nao o supervisor real.
systemctl enable --now redis-server      # ou a imagem/equivalente do ambiente

# 2. worker
celery -A config worker --loglevel=info --concurrency=2 --max-tasks-per-child=100
#    precisa sobreviver a restart e ser reiniciado na queda:
#    -> unit systemd com Restart=always, ou entrada no ecosystem do PM2

# 3. beat
celery -A config beat --loglevel=info
#    ATENCAO: exatamente UM beat por ambiente. Dois beats = cada entrada do
#    CELERY_BEAT_SCHEDULE disparada em dobro.
```

**Decisão de supervisor ainda não tomada neste repositório:** `infra/systemd/`
não existe no meu escopo e as units **não foram criadas** por este item —
criá-las sem poder testá-las seria declarar provisionamento que não existe.
Quem provisionar escolhe entre:

- **(a) systemd** — `celery-worker@<env>.service` e `celery-beat@<env>.service`
  com `User=` resolvido do mesmo lugar nos dois, `Restart=always`,
  `EnvironmentFile=` apontando para o env do ambiente; ou
- **(b) PM2** — o backend já é gerido por PM2 (ver `infra/DEPLOY.md`);
  adicionar `celery worker` e `celery beat` ao `ecosystem.config.js`.
  Atenção: o PM2 cuida de *reiniciar*, mas **não** de *não duplicar*: é
  preciso `instances: 1` no beat, e `max_restarts` sem `crontab`.

As units não devem usar `touch` para "provar" que o beat vive: isso prova
que o *timer* vive, não que a agenda disparou — o falso verde que o P1-03
existe para eliminar. O produtor do heartbeat é a **task**, despachada pelo
beat e executada por um worker.

### 2.2 Diretório de estado durável — obrigatório

O relatório lê `PORTAL_FILAS_ESTADO_DIR`. Sem ele, o padrão cai no
`$XDG_STATE_HOME`/tempdir do usuário do serviço, que **some a cada reboot** —
e aí o relatório volta (corretamente) para `desconhecido` até o primeiro
tick pós-boot. Crie por ambiente:

```bash
install -d -o apps -g apps -m 0755 /var/lib/portal-noticias
# e no env do serviço:
PORTAL_FILAS_ESTADO_DIR=/var/lib/portal-noticias
```

O usuário tem que ser o mesmo do `celery-beat` **e** do `celery-worker`
(não só do beat: quem grava o `ciclo` da ingestão é o worker). Divergência de
`User=` entre as duas units produz `gravou_estado=False` no log e um
heartbeat que nunca aparece.

### 2.3 Fechar o laço no monitor (a parte "monitorada por ambiente")

O comando já sai com código de saída estável (`0`/`1`/`3`). Falta plugá-lo:

1. **Check no monitor externo** (o que já existe para `/healthz`, em
   `infra/observability/` — padrão de check HTTP já iniciado lá):
   ```bash
   cd /home/apps/portal-<env> && \
     .venv/bin/python manage.py saude_filas --json --ignorar-saida
   ```
   com regra: **crítico se o processo sai ≠ 0**. Isso cobre `degradado` (1)
   e `desconhecido` (3) no mesmo alerta, sem parsing de texto. Se o check
   aceitar corpo, use `.estado` do JSON.
2. **Distinguir 1 de 3 no alerta.** Não é detalhe: 1 é "medido e ruim"
   (página), 3 é "não medi" (também página — porque `ok` é o único estado
   que não página). Um alerta que trata os dois como "aviso" volta a ser
   verde para quem não lê.
3. **Painel**: `portal_filas` precisa de `profundidade`, `idade da tarefa
   mais antiga` e `resultado do último ciclo`. Os campos já vêm nomeados no
   JSON (`dependencias.broker.profundidade`,
   `dependencias.workers.idade_da_mais_antiga_s`,
   `dependencias.ultimo_ciclo.estado`). A transformação JSON → métrica
   Prometeus é do provisionamento, não deste item.

### 2.4 Cutover de produção (ordem importa)

1. provisionar Redis, diretório de estado e **os dois** processos;
2. `manage.py saude_filas` → esperar `ok` (saída 0);
3. só então plugar o alerta.

Inverter 2 e 3 produz um alerta de `desconhecido` no primeiro minuto de um
ambiente que está perfeitamente bem — que é o modo mais rápido de ensinar
todo mundo a ignorar o alerta.

---

## 3. O que este item **não** pode declarar

- **Não** pode dizer que algum ambiente está saudável: nenhum foi
  provisionado nem medido aqui. O que existe é código testado contra broker
  e worker reais em processo separado
  (`backend/config/tests/test_filas_worker_real.py`), o que prova o
  *mecanismo*, não o *ambiente*.
- **Não** pode dizer que o consume de fila está rodando em DEV/HOMOLOG/PROD.
  Localmente não há Redis nem supervisor; a prova de consumo é o worker real
  do teste de integração, com transporte de filesystem.
- **Não** pode dizer que existe alerta de fila. Nenhum foi criado: `.github/`
  está fora do escopo deste item por decisão explícita, e os YAMLs de alerta
  de `infra/observability/` pertencem a outro workstream.

O primeiro `ok` verdadeiro só existe depois de 2.1 + 2.2 + 2.3. Até lá,
`desconhecido` é a resposta correta, e é o que o código devolve.
