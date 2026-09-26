"""
Relatório de saúde das filas do portal (P1-03, WS-06).

A REGRA QUE ESTE MÓDULO EXISTE PARA IMPEDIR
-------------------------------------------
`estado` só pode ser `ok` quando TODAS as dependências declaradas foram de
fato sondadas e nenhuma delas mostrou problema. A tabela é curta e
deliberada:

| medição            | verificada | sem problema | com problema |
|--------------------|-----------|--------------|--------------|
| broker + profundidade | sim    | fila vazia   | fila funda  |
| worker vivo (ping)  | sim       | >= 1 pong    | -            |
| heartbeat do beat   | sim       | idade <= max | idade > max |
| ultimo ciclo        | sim       | sucesso      | falha        |

Qualquer dependência **não verificada** (broker inacessível, `inspect()`
sem resposta, arquivo de estado ausente/ilegível, modo inline sem fila)
leva a `desconhecido` — nunca a `ok`. Um "0" que não foi medido vira
`None` com `verificado: false`, e é isso que impede o falso verde: o
caminho de "não consegui medir" não converge com o caminho de "medei e está
tudo bem".

Uma nuance deliberada: se uma dependência não verificada e outra mostrar
problema MEDIDO, o veredito é `degradado`, não `desconhecido`. Não medir
tudo não pode apagar um fato negativo já observado — e `verificado: false`
continua no relatório, com os motivos, para que ninguém leia `degradado`
como "medido por completo".

O QUE ISTO NÃO MEDE (e por isso não é desculpa para chamar de verde)
--------------------------------------------------------------------
- Não mede se o beat está *agendando certo*: prova que uma mensagem do
  beat_schedule chegou a um worker. Um beat com as outras entradas quebradas
  continuaria tocando o heartbeat. O sinal que fecha esse buraco é
  `ultimo_ciclo` da task monitorada (`FILAS_TAREFA_MONITORADA`).
- Não mede saúde de P0-07 (provisionamento DEV/HOMOLOG/PROD). Este módulo
  dá o *formato consultável*; quem pergunta é o monitor do ambiente. Sem
  provisionamento, o honesto é este relatório dizer `desconhecido` — e é o
  que ele diz.
"""

from __future__ import annotations

import time
from typing import Any

from django.conf import settings

from . import filas_estado

ESTADO_OK = "ok"
ESTADO_DEGRADADO = "degradado"
ESTADO_DESCONHECIDO = "desconhecido"

MODO_BROKER = "broker"
MODO_INLINE = "inline"

#: Tempo de espera das sondagens de controle do Celery. Curto de propósito:
#: este relatório é chamado por monitor/HTTP; segurar a thread por dezenas
#: de segundos seria pior que devolver `desconhecido`.
TIMEOUT_INSPECAO_SEGUNDOS = 3.0


def _numero(valor: Any) -> float | None:
    """Converte para float ou devolve None — nunca 0 por Laden fails."""
    if valor is None or isinstance(valor, bool):
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def modo_execucao() -> str:
    """
    `broker` (padrão) ou `inline`.

    `inline` = `CELERY_TASK_ALWAYS_EAGER`: nada é enfileirado, `.delay()`
    roda no próprio processo. É atalho explícito de desenvolvimento/teste e
    NÃO mede consumo de fila — o relatório marca as sondagens de fila como
    não aplicáveis e não chega a `ok`.
    """
    return MODO_INLINE if bool(getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)) else MODO_BROKER


# ---------------------------------------------------------------------------
# Sondas
# ---------------------------------------------------------------------------


def _sondar_broker(app: Any, fila: str, conexao: Any | None = None) -> dict[str, Any]:
    """
    Conecta no broker e mede a profundidade da fila.

    A contagem vem de `queue_declare(fila).message_count`, que em redis é o
    próprio `LLEN` da lista (`kombu/transport/redis.py::_size`) e nos
    transportes virtuais do kombu (memory, filesystem) é a contagem real dos
    arquivos/mensagens da fila naquele diretório. Qualquer exceção — broker
    fora, fila ausente, transporte sem contagem — vira `profundidade: None` +
    `verificado: false` + o motivo. Nunca `0`.

    POR QUE `passive=False` (e não `passive=True`)
    ---------------------------------------------
    `passive=True` parece mais correto ("só pergunta, não cria"), e é uma
    armadilha. No Celery/kombu, `Channel.queue_declare(passive=True)` primeiro
    consulta `self._has_queue(queue)`, e esse método é específico do
    transporte:

    - redis: faz `EXISTS` na chave no servidor — correto;
    - transportes virtuais (memory, filesystem): `virtual.Channel._has_queue`
      devolve `True` **para qualquer fila**, mas o `filesystem` sobrescreve o
      `queue_declare` e responde 404 quando a fila não existe no *seu próprio*
      estado local — que, num processo que não é o worker, é sempre.

    Ou seja: `passive=True` transformaria "sistema novo, nada enfileirado
    ainda" em "não medido" — o oposto do falso verde, mas igualmente
    enganoso, e o estado nunca chegaria a `ok` num ambiente novo. Sem
    `passive`, `message_count` devolve 0 (que é a leitura CORRETA: não há
    nada na fila) e o declare é idempotente, exatamente igual ao que o worker
    faz ao consumir.

    `conexao`, quando informada, é usada em vez de `app.connection()` — e
    NÃO é fechada (é do chamador). Em produção ninguém passa nada: o app
    monta a própria conexão a partir de `CELERY_BROKER_URL`. A existência do
    parâmetro é para quem já tem uma conexão pronta e não quer que o relatório
    abra outra (o teste de integração com worker em processo separado).
    """
    try:
        if conexao is not None:
            contagem = _contar_na_conexao(conexao, fila)
        else:
            with app.connection() as propria:
                contagem = _contar_na_conexao(propria, fila)
    except Exception as exc:  # noqa: BLE001 - qualquer falha de broker é "não medido"
        return {
            "verificado": False,
            "profundidade": None,
            "motivo": f"nao foi possivel medir a fila {fila!r}: {type(exc).__name__}: {exc}",
        }
    medida = _numero(contagem)
    if medida is None:
        return {
            "verificado": False,
            "profundidade": None,
            "motivo": (
                f"o broker nao devolveu uma contagem numerica para a fila "
                f"{fila!r} (veio {contagem!r}); tratado como nao medido"
            ),
        }
    return {"verificado": True, "profundidade": int(medida), "motivo": None}


def _contar_na_conexao(conexao: Any, fila: str):
    """Declara a fila e devolve a contagem crua (sem interpretar)."""
    canal = conexao.default_channel
    return canal.queue_declare(fila).message_count


def _sondar_workers(app: Any, conexao: Any | None = None) -> dict[str, Any]:
    """
    Pergunta ao(s) worker(s) se estão vivos e o que estão fazendo.

    `inspect()` devolve `None` (e não `{}`) quando NINGUÉM respondeu. Tratar
    esse `None` como "zero workers, tudo bem" é exatamente o falso verde que
    este item existe para matar: `None` significa "não medido".
    """
    try:
        inspecao = app.control.inspect(timeout=TIMEOUT_INSPECAO_SEGUNDOS)
    except Exception as exc:  # noqa: BLE001
        return {
            "verificado": False,
            "respondeu": False,
            "workers": None,
            "em_execucao": None,
            "reservadas": None,
            "idade_da_mais_antiga_s": None,
            "idade_verificada": False,
            "motivo": f"nao foi possivel abrir a inspecao de controle: {type(exc).__name__}: {exc}",
        }

    try:
        pings = inspecao.ping()
    except Exception as exc:  # noqa: BLE001
        pings = None
        motivo_ping = f"inspect().ping() falhou: {type(exc).__name__}: {exc}"
    else:
        motivo_ping = None

    if not pings:
        return {
            "verificado": False,
            "respondeu": False,
            "workers": None,
            "em_execucao": None,
            "reservadas": None,
            "idade_da_mais_antiga_s": None,
            "idade_verificada": False,
            "motivo": (
                motivo_ping
                or "nenhum worker respondeu ao ping de controle (fila sem consumidor "
                "ou worker fora do ar — nao medido, nao 'saudavel')"
            ),
        }

    ativos = inspecao.active()
    reservados = inspecao.reserved()

    # `None` aqui também é "não respondeu", e vale para as duas coleções:
    # um worker que responde ao ping mas não ao `active` é um caso em que a
    # idade da tarefa mais antiga é desconhecida.
    if ativos is None or reservados is None:
        return {
            "verificado": True,
            "respondeu": True,
            "workers": sorted(pings),
            "em_execucao": None,
            "reservadas": None,
            "idade_da_mais_antiga_s": None,
            "idade_verificada": False,
            "motivo": (
                "algum worker respondeu ao ping mas nao devolveu a lista de "
                "tarefas em execucao; a idade da tarefa mais antiga ficou "
                "desconhecida"
            ),
        }

    mais_antigo = _idade_da_mais_antiga(ativos, agora=time.time())
    return {
        "verificado": True,
        "respondeu": True,
        "workers": sorted(pings),
        "em_execucao": len(ativos),
        "reservadas": len(reservados),
        "idade_da_mais_antiga_s": mais_antigo,
        "idade_verificada": True,
        "motivo": None,
    }


def _idade_da_mais_antiga(ativos: dict[str, Any], *, agora: float) -> float | None:
    """
    Idade, em segundos, da task em execução mais antiga (`inspect().active()`).

    `None` significa "não há nada em execução" — que é um fato verificado e
    diferente de "não sei". `time_start` é epoch em segundos (float) no
    payload do Celery; um valor ausente/ilegível é simplesmente ignorado, e
    se NENHUM dos ativos trouxer `time_start` o resultado é `None` com a
    leitura contada como não verificada lá em cima.
    """
    idades: list[float] = []
    for tarefas in ativos.values():
        if not isinstance(tarefas, list):
            continue
        for tarefa in tarefas:
            if not isinstance(tarefa, dict):
                continue
            inicio = _numero(tarefa.get("time_start"))
            if inicio is not None:
                idades.append(max(0.0, agora - inicio))
    if not idades:
        return None
    return max(idades)


def _sondar_beat(
    estado: dict[str, Any], *, agora: float | None = None
) -> dict[str, Any]:
    """
    Lê o registro durável do heartbeat e compara com a idade máxima.

    Ausência de registro não é "beat ok": é "nunca observado", e vira
    `verificado: false`. Um registro com `registrado_em` ilegível também — o
    carimbo é o que dá a idade, sem ele não há o que comparar com o limite.
    """
    momento = time.time() if agora is None else float(agora)
    registro = estado.get("beat")
    if registro is None:
        return {
            "verificado": False,
            "idade_s": None,
            "expirado": None,
            "registrado_em": None,
            "task_id": None,
            "task": None,
            "motivo": (
                "nenhum heartbeat do beat registrado: ou o beat nao esta "
                "agendando, ou ainda nao rodou neste ambiente"
            ),
        }

    idade = filas_estado.idade_de(registro, agora=momento)
    if idade is None:
        return {
            "verificado": False,
            "idade_s": None,
            "expirado": None,
            "registrado_em": None,
            "task_id": registro.get("task_id"),
            "task": registro.get("task"),
            "motivo": "registro de heartbeat sem carimbo de tempo utilizavel",
        }

    maximo = float(getattr(settings, "FILAS_BEAT_MAX_AGE_SEGUNDOS", 900))
    return {
        "verificado": True,
        "idade_s": round(idade, 3),
        "expirado": idade > maximo,
        "registrado_em": _numero(registro.get("registrado_em")),
        "task_id": registro.get("task_id"),
        "task": registro.get("task"),
        "max_age_s": maximo,
        "motivo": None,
    }


def _sondar_ultimo_ciclo(
    estado: dict[str, Any], *, agora: float | None = None
) -> dict[str, Any]:
    """
    Último ciclo registrado da task monitorada (`FILAS_TAREFA_MONITORADA`).

    Ausência = `nunca_observado` com `verificado: false`. É o sinal que
    distingue "a agenda do beat está configurada" de "a agenda do beat
    produziu resultado", e por isso não pode ser assumido em nenhum caso.
    """
    momento = time.time() if agora is None else float(agora)
    task = str(getattr(settings, "FILAS_TAREFA_MONITORADA", "") or "")
    if not task:
        return {
            "verificado": False,
            "task": None,
            "estado": None,
            "idade_s": None,
            "tentativa": None,
            "tentativas_observadas": None,
            "max_tentativas": None,
            "erro": None,
            "detalhe": None,
            "motivo": "FILAS_TAREFA_MONITORADA nao configurada: nao ha ciclo a monitorar",
        }

    registro = (estado.get("ciclos") or {}).get(task)
    if registro is None:
        return {
            "verificado": False,
            "task": task,
            "estado": None,
            "idade_s": None,
            "tentativa": None,
            "tentativas_observadas": None,
            "max_tentativas": None,
            "erro": None,
            "detalhe": None,
            "motivo": f"nenhum ciclo registrado para {task}",
        }

    return {
        "verificado": True,
        "task": task,
        "estado": registro.get("estado"),
        "idade_s": _arredondado(filas_estado.idade_de(registro, agora=momento)),
        "tentativa": registro.get("tentativa"),
        "tentativas_observadas": registro.get("tentativas_observadas"),
        "max_tentativas": registro.get("max_tentativas"),
        "erro": registro.get("erro"),
        "detalhe": registro.get("detalhe"),
        "motivo": None,
    }


def _arredondado(valor: float | None) -> float | None:
    return None if valor is None else round(valor, 3)


# ---------------------------------------------------------------------------
# Veredito
# ---------------------------------------------------------------------------


def _avaliar(
    *,
    registro: dict[str, Any],
    broker: dict[str, Any],
    workers: dict[str, Any],
    beat: dict[str, Any],
    ciclo: dict[str, Any],
    fila: str,
) -> tuple[str, bool, list[str]]:
    """
    Aplica a tabela do cabeçalho. Devolve `(estado, tudo_verificado, motivos)`.

    Três caminhos, nesta ordem:
    1. problema medido  -> `degradado` (um fato negativo não é apagado por
       "não consegui medir o resto");
    2. algo não verificado -> `desconhecido` (impede `ok`);
    3. tudo verificado e sem problema -> `ok`.
    """
    motivos: list[str] = []
    problemas: list[str] = []

    # --- registro das tasks da agenda
    if registro.get("verificado"):
        pass
    else:
        motivos.append(registro.get("motivo") or "registro de tasks nao verificado")

    # --- profundidade da fila
    if broker.get("verificado"):
        limite = int(getattr(settings, "FILAS_PROFUNDIDADE_MAXIMA", 500))
        if (broker.get("profundidade") or 0) > limite:
            problemas.append(
                f"fila {fila!r} com {broker['profundidade']} item(ns), acima do "
                f"limite de {limite}"
            )
    else:
        motivos.append(broker.get("motivo") or "profundidade da fila nao verificada")

    # --- worker vivo
    if workers.get("verificado"):
        if not workers.get("respondeu"):
            problemas.append("nenhum worker respondeu ao ping de controle")
        elif workers.get("idade_verificada"):
            idade = workers.get("idade_da_mais_antiga_s")
            if idade is not None:
                limite_idade = float(
                    getattr(settings, "FILAS_IDADE_MAXIMA_TAREFA_SEGUNDOS", 900)
                )
                if idade > limite_idade:
                    problemas.append(
                        f"task em execucao ha {idade}s, acima do limite de "
                        f"{limite_idade}s (possivel task travada)"
                    )
    else:
        motivos.append(workers.get("motivo") or "workers nao verificados")

    # --- heartbeat do beat
    if beat.get("verificado"):
        if beat.get("expirado"):
            problemas.append(
                f"heartbeat do beat com {beat.get('idade_s')}s de idade, acima do "
                f"limite de {beat.get('max_age_s')}s"
            )
    else:
        motivos.append(beat.get("motivo") or "heartbeat do beat nao verificado")

    # --- ultimo ciclo
    if ciclo.get("verificado"):
        if ciclo.get("estado") == filas_estado.ESTADO_FALHA:
            tentativas = ciclo.get("tentativas_observadas")
            esgotou = _tentativas_esgotadas(ciclo)
            problemas.append(
                f"ultimo ciclo de {ciclo.get('task')} falhou "
                f"({tentativas} tentativa(s) observada(s))"
                + (" — tentativas esgotadas, falha definitiva" if esgotou else " — ha novas tentativas a caminho")
                + (f": {ciclo.get('erro')}" if ciclo.get("erro") else "")
            )
    else:
        motivos.append(ciclo.get("motivo") or "ultimo ciclo nao verificado")

    tudo_verificado = all(
        parte.get("verificado")
        for parte in (registro, broker, workers, beat, ciclo)
    )
    if problemas:
        return ESTADO_DEGRADADO, tudo_verificado, problemas + motivos
    if not tudo_verificado:
        return ESTADO_DESCONHECIDO, False, motivos
    return ESTADO_OK, True, []


def garantir_registro(app: Any) -> tuple[bool, str | None]:
    """
    Dispara a descoberta de tasks do app Celery se ela ainda não rodou.

    Precisa porque `app.autodiscover_tasks()` (em `config/celery.py`) é
    PREGUIÇOSO: ele só registra um handler no sinal `import_modules`, que é
    emitido por `app.loader.import_default_modules()` — chamada pelo binário
    `celery`, nunca pelo `manage.py`. Sem forçar aqui, este comando rodando
    dentro do Django veria um registro vazio e acusaria toda task da agenda
    como "não registrada" — uma conclusão ERRADA (o worker tem todas), ou
    seja, o oposto do falso verde, mas igualmente enganoso.

    Importar módulo já importado é cacheado, então isto é barato e seguro
    fora do worker também.
    """
    try:
        app.autodiscover_tasks(force=True)
    except Exception as exc:  # noqa: BLE001
        return False, f"falha ao disparar a descoberta de tasks: {type(exc).__name__}: {exc}"
    return True, None


def verificar_registro(app: Any) -> dict[str, Any]:
    """
    Confere que toda task referenciada pelo `CELERY_BEAT_SCHEDULE` está de
    fato registrada no app Celery.

    Isso não é vaidade: uma task órfã no beat_schedule é o modo mais comum
    de "a agenda parou" sem ninguém perceber — o beat enfileira o nome, o
    worker não tem o que consumir, e o resultado é um descarte silencioso a
    cada 15 minutos. A checagem é feita contra `app.tasks` (o registro real),
    não contra o código-fonte: o que interessa é o que o WORKER consegue
    consumir, não o que existe em disco.
    """
    forcado, problema_forcado = garantir_registro(app)
    registradas = set(getattr(app, "tasks", {}) or {})
    try:
        agenda = dict(getattr(settings, "CELERY_BEAT_SCHEDULE", {}) or {})
    except Exception as exc:  # noqa: BLE001 - settings ausente não pode virar "tudo certo"
        return {
            "verificado": False,
            "agenda": None,
            "faltando": None,
            "total_registradas": len(registradas),
            "motivo": f"nao foi possivel ler o CELERY_BEAT_SCHEDULE: {type(exc).__name__}: {exc}",
        }

    faltando = sorted(
        {str(entrada.get("task")) for entrada in agenda.values() if isinstance(entrada, dict)}
        - registradas
        - {"None"}
    )
    if not forcado:
        # A descoberta não rodou: a lista de "faltando" pode estar cheia de
        # falsos positivos. Melhor `desconhecido` do que acusar task inocente.
        return {
            "verificado": False,
            "agenda": sorted(agenda),
            "faltando": None,
            "total_registradas": len(registradas),
            "motivo": (
                f"{problema_forcado}; o registro de tasks pode estar incompleto, "
                f"entao a lista de ausentes nao foi avaliada"
            ),
        }
    return {
        "verificado": not faltando,
        "agenda": sorted(agenda),
        "faltando": faltando,
        "total_registradas": len(registradas),
        "motivo": (
            None
            if not faltando
            else "task(s) do CELERY_BEAT_SCHEDULE sem registro no app Celery: "
            + ", ".join(faltando)
        ),
    }


def _tentativas_esgotadas(ciclo: dict[str, Any]) -> bool:
    """
    A tentativa que falhou era a última disponível?

    Dois sinais, e basta um: `tentativa >= max_tentativas` (a tentativa que
    falhou era a última) ou `tentativas_observadas >= max_tentativas` (o
    ciclo já consumiu toda a janela). Com nenhum dos dois números não se
    pode afirmar esgotamento — e afirmar uma "falha definitiva" que ninguém
    mediu seria exatamente o tipo de certeza inventada que este módulo
    recusa. Nesse caso devolvemos False e o motivo diz "ha novas tentativas
    a caminho", que é a leitura conservadora correta.
    """
    observadas = _numero(ciclo.get("tentativas_observadas"))
    maximas = _numero(ciclo.get("max_tentativas"))
    if maximas is None:
        return False
    tentativa = _numero(ciclo.get("tentativa"))
    if tentativa is not None and tentativa >= maximas:
        return True
    return observadas is not None and observadas >= maximas


def relatorio(
    *,
    app: Any | None = None,
    fila: str | None = None,
    agora: float | None = None,
    conexao: Any | None = None,
) -> dict[str, Any]:
    """
    Relatório completo e serializável da saúde das filas.

    Nunca levanta: uma falha de infraestrutura vira `desconhecido` com o
    motivo, porque um relatório que estoura exceção não é monitorável — e um
    monitor que engole a exceção e chama de "ok" é pior.
    """
    if app is None:
        from config.celery import app as celery_app

        app = celery_app
    if fila is None:
        fila = str(getattr(settings, "FILAS_NOME_FILA", "celery"))
    momento = time.time() if agora is None else float(agora)
    modo = modo_execucao()

    registro = verificar_registro(app)
    estado = filas_estado.ler_estado()
    problema_arquivo = estado.get(filas_estado.CHAVE_PROBLEMA)

    if modo == MODO_INLINE:
        # Em inline NAO existe fila nem worker. Dizer `ok` aqui seria afirmar
        # que uma fila está saudável sem existir fila. O relatório é
        # honesto: as sondagens de fila não se aplicam, o ciclo monitorado
        # continua sendo medido, e o veredito é `desconhecido`.
        broker = {
            "verificado": False,
            "profundidade": None,
            "motivo": (
                "modo inline (CELERY_TASK_ALWAYS_EAGER): nao ha broker nem fila "
                "para medir — este relatorio nao avalia consumo de fila"
            ),
        }
        workers = {
            "verificado": False,
            "respondeu": False,
            "workers": None,
            "em_execucao": None,
            "reservadas": None,
            "idade_da_mais_antiga_s": None,
            "idade_verificada": False,
            "motivo": (
                "modo inline (CELERY_TASK_ALWAYS_EAGER): nao ha worker consumindo "
                "fila para inspecionar"
            ),
        }
    else:
        broker = _sondar_broker(app, fila, conexao)
        workers = _sondar_workers(app, conexao)

    beat = _sondar_beat(estado, agora=momento)
    ciclo = _sondar_ultimo_ciclo(estado, agora=momento)

    # NÃO há (nem precisa haver) um ramo que traduza `problema_arquivo` em
    # `verificado: false` aqui. Todo caminho que preenche `CHAVE_PROBLEMA` em
    # `filas_estado.ler_estado()` devolve também o estado VAZIO (beat=None,
    # ciclos={}), então `_sondar_beat` e `_sondar_ultimo_ciclo` já respondem
    # `verificado: false` com motivo próprio. Um ramo de segurança para esse
    # caso seria código morto — e pior, daria a impressão de que um arquivo
    # corrompido poderia chegar a `ok` se os registros ainda fossem bons.
    # O problema do arquivo segue exposto em `arquivo_estado_problema`, que
    # é um campo de primeira classe do relatório.

    veredito, tudo_verificado, motivos = _avaliar(
        registro=registro,
        broker=broker,
        workers=workers,
        beat=beat,
        ciclo=ciclo,
        fila=fila,
    )

    return {
        "estado": veredito,
        "verificado": tudo_verificado,
        "modo_execucao": modo,
        "gerado_em": momento,
        "fila": fila,
        "arquivo_estado": str(filas_estado.caminho_estado()),
        "arquivo_estado_problema": problema_arquivo,
        "dependencias": {
            "registro": registro,
            "broker": broker,
            "workers": workers,
            "beat": beat,
            "ultimo_ciclo": ciclo,
        },
        "limites": {
            "profundidade_maxima": int(getattr(settings, "FILAS_PROFUNDIDADE_MAXIMA", 500)),
            "idade_maxima_tarefa_s": float(
                getattr(settings, "FILAS_IDADE_MAXIMA_TAREFA_SEGUNDOS", 900)
            ),
            "beat_max_age_s": float(getattr(settings, "FILAS_BEAT_MAX_AGE_SEGUNDOS", 900)),
        },
        "motivos": motivos,
    }
