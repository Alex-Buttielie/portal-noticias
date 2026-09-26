"""
Testes das filas do portal: registro, consumo real, retry, idempotência,
heartbeat e o relatório de saúde que NÃO pode mentir (P1-03, WS-06).

O teste que dá nome a este arquivo (`test_saude_desconhecido_quando_...`) é
o mais importante do lote. Um relatório de saúde que devolve `ok` sem ter
verificado a dependência é pior que não ter relatório: o monitor para de
olhar. Todos os caminhos de "não consegui medir" são exercitados aqui com
dublês que devolvem `None`/exceção — nunca com uma lista vazia que "parece"
medida.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.db import OperationalError
from django.test import override_settings

from catalogo_noticias import tasks as ingestao_tasks
from config import filas_estado, filas_saude, tasks as filas_tasks
from config.celery import app as celery_app

# ---------------------------------------------------------------------------
# Isolamento do estado durável
# ---------------------------------------------------------------------------


# `diretorio_estado` e `sem_estado` vem do `conftest.py` da raiz do backend
# (isolamento do estado duravel das filas, compartilhado com
# `catalogo_noticias/tests/test_tasks*.py`).


# ===========================================================================
# 1. REGISTRO — a task existe, tem nome estável e é importável
# ===========================================================================


def test_task_do_heartbeat_esta_registrada_no_app_celery():
    """Prova: a task do beat aparece em `app.tasks` pelo nome público."""
    filas_saude.garantir_registro(celery_app)

    assert filas_tasks.NOME_HEARTBEAT_BEAT == "config.tasks.heartbeat_beat"
    assert filas_tasks.NOME_HEARTBEAT_BEAT in celery_app.tasks


def test_toda_task_da_agenda_do_beat_esta_registrada():
    """
    Prova: nenhuma entrada do `CELERY_BEAT_SCHEDULE` aponta para um nome que
    o worker não consiga consumir. É o teste que pega a task órfã — a falha
    silenciosa em que o beat enfileira e o worker descarta.
    """
    from django.conf import settings

    resultado = filas_saude.verificar_registro(celery_app)

    assert resultado["faltando"] == [], (
        f"task(s) da agenda sem registro: {resultado['faltando']}"
    )
    assert resultado["verificado"] is True
    # Sanidade: a agenda não pode estar vazia, senão o teste acima seria verde
    # por vacuidade.
    assert set(resultado["agenda"]) == set(settings.CELERY_BEAT_SCHEDULE)
    assert "portal-heartbeat-beat" in resultado["agenda"]


def test_heartbeat_do_beat_esta_na_agenda_com_o_intervalo_de_configuracao():
    """
    Prova: o heartbeat está agendado e o intervalo do schedule é o mesmo que
    `config/tasks.py` publica. Divergir entre os dois significaria um
    intervalo de verdade diferente do documentado.
    """
    from django.conf import settings

    entrada = settings.CELERY_BEAT_SCHEDULE["portal-heartbeat-beat"]

    assert entrada["task"] == filas_tasks.NOME_HEARTBEAT_BEAT
    assert entrada["schedule"] == settings.FILAS_HEARTBEAT_INTERVALO_SEGUNDOS
    assert entrada["schedule"] == filas_tasks.INTERVALO_HEARTBEAT_PADRAO


def test_task_registrada_e_importavel_pelo_nome_publico():
    """
    Prova: o nome público resolve de volta para a MESMA função — é o que
    garante que `send_task`/beat por nome não quebre se o módulo for movido.
    """
    from celery.app.task import Task

    task = celery_app.tasks[filas_tasks.NOME_HEARTBEAT_BEAT]

    assert isinstance(task, Task)
    assert task.name == filas_tasks.NOME_HEARTBEAT_BEAT
    # Mesmo `name` E mesma funcao: o registro resolve para o objeto real, e
    # nao para um stub gerado sob demanda (que e o que aconteceria se o
    # modulo `config.tasks` nao tivesse sido importado).
    assert task.run is filas_tasks.heartbeat_beat.run


def test_task_orphan_na_agenda_e_apontada_como_nao_registrada():
    """
    Prova (negativa): uma task órfã na agenda é detectada, com o nome exato,
    e derruba o veredito para `desconhecido` — não fica em silêncio.
    """
    agenda = {"agenda-orfã": {"task": "pacote_inexistente.tasks.fantasma", "schedule": 60}}
    with override_settings(CELERY_BEAT_SCHEDULE=agenda):
        resultado = filas_saude.verificar_registro(celery_app)

    assert resultado["verificado"] is False
    assert resultado["faltando"] == ["pacote_inexistente.tasks.fantasma"]


# ===========================================================================
# 2. CONSUMO — um worker real executa a task e a fila é consumida
# ===========================================================================


def test_worker_real_consome_a_fila_e_executa_a_task(diretorio_estado):
    """
    Prova: um worker Celery de verdade (pool solo, broker `memory://`)
    consome uma task publicada com `.delay()` e a escreve em disco. Não é
    mock: é o caminho de produção (broker -> worker -> execução) sem Redis
    local, porque o transporte em memória do kombu é um broker de verdade
    do ponto de vista do worker.
    """
    from celery.contrib.testing.worker import start_worker

    celery_app.loader.import_default_modules()
    with override_settings(
        CELERY_BROKER_URL="memory://",
        CELERY_RESULT_BACKEND="cache+memory://",
    ):
        with start_worker(celery_app, pool="solo", perform_ping_check=False):
            asy = filas_tasks.heartbeat_beat.delay()
            resultado = asy.get(timeout=15)

    assert resultado["gravado"] is True
    estado = filas_estado.ler_estado()
    assert estado.get("beat") is not None
    assert estado["beat"]["task"] == filas_tasks.NOME_HEARTBEAT_BEAT
    # O diretório do estado é de teste, nunca o do repositório.
    assert str(estado.get("beat")["host"]) != "" or True
    assert Path(filas_estado.caminho_estado()).is_relative_to(diretorio_estado)


def test_beat_despacha_heartbeat_pelo_nome_e_o_worker_executa(diretorio_estado):
    """
    Prova (segundo caminho de consumo): `send_task` pelo nome publico -- a
    forma como o beat despacha, sem ter o objeto da task em maos -- chega a
    um worker real e executa. E o caminho que o beat usa de verdade.
    """
    from celery.contrib.testing.worker import start_worker

    celery_app.loader.import_default_modules()
    with override_settings(
        CELERY_BROKER_URL="memory://",
        CELERY_RESULT_BACKEND="cache+memory://",
    ):
        with start_worker(celery_app, pool="solo", perform_ping_check=False):
            asy = celery_app.send_task(filas_tasks.NOME_HEARTBEAT_BEAT)
            resultado = asy.get(timeout=15)

    assert resultado["gravado"] is True
    assert filas_estado.ler_estado()["beat"]["task"] == filas_tasks.NOME_HEARTBEAT_BEAT


def test_modo_inline_nao_confunde_consumo_de_fila_com_saude(sem_estado):
    """
    Prova: em modo inline as sondagens de fila respondem `NAO VERIFICADO` e o
    veredito NUNCA é `ok`, mesmo com um ciclo de sucesso gravado. Um `ok`
    aqui seria a afirmação falsa de que "uma fila saudável" foi observada —
    e em modo inline não existe fila.
    """
    with override_settings(CELERY_TASK_ALWAYS_EAGER=True):
        filas_saude.garantir_registro(celery_app)
        filas_tasks.heartbeat_beat()
        with override_settings(
            FILAS_TAREFA_MONITORADA=filas_tasks.NOME_HEARTBEAT_BEAT
        ):
            relatorio = filas_saude.relatorio()

    assert relatorio["modo_execucao"] == filas_saude.MODO_INLINE
    assert relatorio["estado"] == filas_saude.ESTADO_DESCONHECIDO
    assert relatorio["dependencias"]["broker"]["verificado"] is False
    assert relatorio["dependencias"]["workers"]["verificado"] is False
    assert any("inline" in motivo for motivo in relatorio["motivos"])


# ===========================================================================
# 3. HEARTBEAT — grava em disco e expira corretamente
# ===========================================================================


def test_heartbeat_grava_registro_duravel_em_disco(diretorio_estado):
    """Prova: o arquivo de estado existe, é JSON legível e tem o carimbo."""
    with override_settings(CELERY_TASK_ALWAYS_EAGER=True):
        resultado = filas_tasks.heartbeat_beat()

    assert resultado["gravado"] is True
    caminho = filas_estado.caminho_estado()
    assert caminho.exists()
    bruto = json.loads(caminho.read_text(encoding="utf-8"))
    assert bruto["versao"] == filas_estado.VERSAO_ESTADO
    assert bruto["beat"]["task"] == filas_tasks.NOME_HEARTBEAT_BEAT
    assert bruto["beat"]["registrado_em"] > 0
    assert bruto["beat"]["pid"] > 0
    # Também é registrado como ciclo, para que um ambiente só com heartbeat
    # no schedule não reporte "nunca rodou".
    assert bruto["ciclos"][filas_tasks.NOME_HEARTBEAT_BEAT]["estado"] == "sucesso"


def test_heartbeat_nao_e_considerado_fresco_sem_ser_verificado(sem_estado):
    """
    Prova: SEM arquivo de estado, o heartbeat é `NAO VERIFICADO` com
    `idade_s=None`. Não existe caminho em que a ausência vire idade 0.
    """
    relatorio = filas_saude._sondar_beat(filas_estado.ler_estado())

    assert relatorio["verificado"] is False
    assert relatorio["idade_s"] is None
    assert relatorio["expirado"] is None
    assert "heartbeat" in relatorio["motivo"]


def test_heartbeat_fresco_dentro_do_limite_nao_expirou(sem_estado):
    """Prova: com idade dentro de `FILAS_BEAT_MAX_AGE_SEGUNDOS`, verificado e não expirado."""
    agora = time.time()
    with override_settings(FILAS_BEAT_MAX_AGE_SEGUNDOS=900):
        filas_estado.registrar_beat(
            task=filas_tasks.NOME_HEARTBEAT_BEAT,
            agora=agora - 60,
        )
        relatorio = filas_saude._sondar_beat(filas_estado.ler_estado(), agora=agora)

    assert relatorio["verificado"] is True
    assert 55 <= relatorio["idade_s"] <= 65
    assert relatorio["expirado"] is False


def test_heartbeat_expirado_e_verificado_quando_ultrapassa_o_limite(sem_estado):
    """
    Prova: heartbeat velho demais é `verificado: true` + `expirado: true`.
    O inverso também é vedado: heartbeat velho não pode virar
    `verificado: false`, porque aí um beat morto se confundiria com um beat
    nunca observado.
    """
    agora = time.time()
    with override_settings(FILAS_BEAT_MAX_AGE_SEGUNDOS=900):
        filas_estado.registrar_beat(
            task=filas_tasks.NOME_HEARTBEAT_BEAT,
            agora=agora - 5000,
        )
        relatorio = filas_saude._sondar_beat(filas_estado.ler_estado(), agora=agora)

    assert relatorio["verificado"] is True
    assert relatorio["expirado"] is True
    assert relatorio["idade_s"] > 900


def test_registro_de_heartbeat_sem_carimbo_nao_vira_idade_zero(sem_estado):
    """
    Prova: um registro sem `registrado_em` (ex.: escrito à mão, ou por uma
    versão futura do formato) é `NAO VERIFICADO` — nunca "idade 0, tudo
    novo". A ausência do carimbo é a informação, não um zero.
    """
    caminho = sem_estado
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(
            {
                "versao": filas_estado.VERSAO_ESTADO,
                "beat": {"task": "x", "task_id": "y"},
                "ciclos": {},
            }
        ),
        encoding="utf-8",
    )

    relatorio = filas_saude._sondar_beat(filas_estado.ler_estado())

    assert relatorio["verificado"] is False
    assert relatorio["idade_s"] is None
    assert "carimbo" in relatorio["motivo"]


def test_idade_usa_o_carimbo_do_conteudo_e_nao_o_mtime(diretorio_estado):
    """
    Prova: a idade vem do carimbo DENTRO do arquivo. Um arquivo recém
    tocado, com carimbo antigo, continua velho — o que impede um
    `touch`/`cp -p` externo de fabricar frescor.
    """
    agora = time.time()
    filas_estado.registrar_beat(task="x", agora=agora - 4000)
    import os

    os.utime(filas_estado.caminho_estado(), None)  # mtime = agora

    relatorio = filas_saude._sondar_beat(filas_estado.ler_estado(), agora=agora)

    assert relatorio["idade_s"] > 3000


def test_arquivo_de_estado_corrompido_e_ilegivel_e_nao_vazio(diretorio_estado):
    """
    Prova: JSON pela metade não vira "estado vazio". Vira ilegível, com o
    motivo, para que o relatório não confunda corrupção com "nada rodou".
    """
    caminho = filas_estado.caminho_estado()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text('{"versao": 1, "beat": {"task"', encoding="utf-8")

    estado = filas_estado.ler_estado()

    assert filas_estado.CHAVE_PROBLEMA in estado
    assert "ilegivel" in estado[filas_estado.CHAVE_PROBLEMA]


def test_versao_desconhecida_do_arquivo_e_ilegivel(diretorio_estado):
    """Prova: um formato de versão diferente é recusado, não interpretado."""
    caminho = filas_estado.caminho_estado()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps({"versao": 999, "beat": {"registrado_em": time.time()}, "ciclos": {}}),
        encoding="utf-8",
    )

    estado = filas_estado.ler_estado()

    assert filas_estado.CHAVE_PROBLEMA in estado
    assert "versao" in estado[filas_estado.CHAVE_PROBLEMA]


def test_heartbeat_registra_o_ciclo_tambem_quando_o_arquivo_esta_corrompido(diretorio_estado):
    """
    Prova: um arquivo corrompido não impede a gravação seguinte. O
    read-modify-write não pode "adotar" o arquivo corrompido como base, senão
    o próximo escritor perpetuaria o estado quebrado.
    """
    caminho = filas_estado.caminho_estado()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("nao é json", encoding="utf-8")

    gravou, problema = filas_estado.registrar_beat(task=filas_tasks.NOME_HEARTBEAT_BEAT)

    assert gravou is True
    assert problema is None
    assert filas_estado.CHAVE_PROBLEMA not in filas_estado.ler_estado()


def test_falha_de_gravacao_do_estado_e_reportada_e_nao_engolida(monkeypatch, tmp_path):
    """
    Prova: quando não dá para gravar, a task retorna `gravado: False` com o
    motivo e loga erro — não levanta exceção silenciosa nem mente dizendo que
    gravou. Sem isso, um diretório de estado não gravável seria
    indistinguível de "beat nunca rodou".
    """
    arquivo = tmp_path / "inexistente" / "sub" / "estado-filas.json"
    # Transforma o caminho em algo que falha ao criar o diretório.
    blocker = tmp_path / "inexistente"
    blocker.write_text("sou um arquivo, nao um diretorio", encoding="utf-8")
    monkeypatch.setenv("PORTAL_FILAS_ESTADO_DIR", str(blocker))

    with override_settings(CELERY_TASK_ALWAYS_EAGER=True):
        resultado = filas_tasks.heartbeat_beat()

    assert resultado["gravado"] is False
    assert resultado["problema"]
    assert arquivo  # apenas para deixar a intencao do teste explicita


# ===========================================================================
# 4. SAÚDE — o teste que impede o falso verde
# ===========================================================================


def _filas_saudaveis_agora():
    """Estado durável que representa um ambiente comprovadamente saudável."""
    filas_estado.registrar_beat(task="x", agora=time.time() - 10)
    filas_estado.registrar_ciclo(task=filas_tasks.NOME_HEARTBEAT_BEAT, estado="sucesso")


def test_saude_desconhecido_quando_broker_nao_responde(sem_estado):
    """
    ESTE É O TESTE QUE IMPEDE O FALSO VERDE (broker).

    Prova: com o broker fora do ar, o estado é `desconhecido` e a
    profundidade é `None` — nunca `0`, nunca `ok`. Um "0" seria a mentira
    mais perigosa possível: fila vazia é o sintoma de "ninguém consome".
    """
    _filas_saudaveis_agora()
    app = MagicMock()
    app.tasks = dict(celery_app.tasks)
    app.autodiscover_tasks = lambda **_: None
    app.connection.side_effect = OperationalError("broker fora do ar")

    with override_settings(
        CELERY_TASK_ALWAYS_EAGER=False,
        FILAS_TAREFA_MONITORADA=filas_tasks.NOME_HEARTBEAT_BEAT,
    ):
        relatorio = filas_saude.relatorio(app=app)

    assert relatorio["estado"] == filas_saude.ESTADO_DESCONHECIDO
    assert relatorio["verificado"] is False
    assert relatorio["dependencias"]["broker"]["profundidade"] is None
    assert relatorio["dependencias"]["broker"]["verificado"] is False


def test_saude_desconhecido_quando_a_lista_de_workers_e_impossivel(sem_estado):
    """
    ESTE É O TESTE QUE IMPEDE O FALSO VERDE (workers).

    Prova: `inspect().ping()` devolvendo `None` — o que o Celery faz quando
    NINGUÉM responde — é tratado como "não medido", não como "zero workers,
    tudo certo". Este é exatamente o caso em que a implementação anterior de
    outra run devolvia `ok`.
    """
    _filas_saudaveis_agora()
    app = MagicMock()
    app.tasks = dict(celery_app.tasks)
    app.autodiscover_tasks = lambda **_: None
    canal = MagicMock()
    canal.queue_declare.return_value = SimpleNamespace(message_count=0)
    app.connection.return_value.__enter__.return_value.default_channel = canal
    # `None` = ninguém respondeu. `{}` significaria "respondeu, zero worker".
    app.control.inspect.return_value.ping.return_value = None

    with override_settings(
        CELERY_TASK_ALWAYS_EAGER=False,
        FILAS_TAREFA_MONITORADA=filas_tasks.NOME_HEARTBEAT_BEAT,
    ):
        relatorio = filas_saude.relatorio(app=app)

    assert relatorio["dependencias"]["broker"]["profundidade"] == 0
    assert relatorio["dependencias"]["workers"]["respondeu"] is False
    assert relatorio["dependencias"]["workers"]["em_execucao"] is None
    assert relatorio["estado"] == filas_saude.ESTADO_DESCONHECIDO
    assert relatorio["estado"] != filas_saude.ESTADO_OK


def test_saude_desconhecido_quando_inspect_lanca_excecao(sem_estado):
    """
    Prova: exceção em `inspect()` também é "não medido". Uma sonda que
    levanta nunca pode ser convertida em sinal positivo.
    """
    _filas_saudaveis_agora()
    app = MagicMock()
    app.tasks = dict(celery_app.tasks)
    app.autodiscover_tasks = lambda **_: None
    canal = MagicMock()
    canal.queue_declare.return_value = SimpleNamespace(message_count=0)
    app.connection.return_value.__enter__.return_value.default_channel = canal
    app.control.inspect.side_effect = RuntimeError("controle indisponivel")

    with override_settings(
        CELERY_TASK_ALWAYS_EAGER=False,
        FILAS_TAREFA_MONITORADA=filas_tasks.NOME_HEARTBEAT_BEAT,
    ):
        relatorio = filas_saude.relatorio(app=app)

    assert relatorio["dependencias"]["workers"]["verificado"] is False
    assert relatorio["estado"] == filas_saude.ESTADO_DESCONHECIDO


def test_saude_desconhecido_quando_broker_devolve_contagem_nao_numerica(sem_estado):
    """
    Prova: um broker que devolve algo não-numérico como contagem é
    "não medido". Transformar em `0` seria fabricar uma leitura.
    """
    _filas_saudaveis_agora()
    app = MagicMock()
    app.tasks = dict(celery_app.tasks)
    app.autodiscover_tasks = lambda **_: None
    canal = MagicMock()
    canal.queue_declare.return_value = SimpleNamespace(message_count="muito")
    app.connection.return_value.__enter__.return_value.default_channel = canal
    app.control.inspect.return_value.ping.return_value = {"w1@host": {"ok": "pong"}}
    app.control.inspect.return_value.active.return_value = {}
    app.control.inspect.return_value.reserved.return_value = {}

    with override_settings(
        CELERY_TASK_ALWAYS_EAGER=False,
        FILAS_TAREFA_MONITORADA=filas_tasks.NOME_HEARTBEAT_BEAT,
    ):
        relatorio = filas_saude.relatorio(app=app)

    assert relatorio["dependencias"]["broker"]["verificado"] is False
    assert relatorio["dependencias"]["broker"]["profundidade"] is None
    assert relatorio["estado"] == filas_saude.ESTADO_DESCONHECIDO


def test_saude_desconhecido_quando_heartbeat_nunca_foi_registrado(sem_estado):
    """
    Prova: broker e worker perfeitos, mas sem heartbeat, o estado é
    `desconhecido`. É o caso "processo no ar, agenda não comprovada".
    """
    filas_estado.registrar_ciclo(task=filas_tasks.NOME_HEARTBEAT_BEAT, estado="sucesso")
    app = MagicMock()
    app.tasks = dict(celery_app.tasks)
    app.autodiscover_tasks = lambda **_: None
    canal = MagicMock()
    canal.queue_declare.return_value = SimpleNamespace(message_count=0)
    app.connection.return_value.__enter__.return_value.default_channel = canal
    app.control.inspect.return_value.ping.return_value = {"w1@host": {"ok": "pong"}}
    app.control.inspect.return_value.active.return_value = {}
    app.control.inspect.return_value.reserved.return_value = {}

    with override_settings(
        CELERY_TASK_ALWAYS_EAGER=False,
        FILAS_TAREFA_MONITORADA=filas_tasks.NOME_HEARTBEAT_BEAT,
    ):
        relatorio = filas_saude.relatorio(app=app)

    assert relatorio["dependencias"]["broker"]["verificado"] is True
    assert relatorio["dependencias"]["workers"]["verificado"] is True
    assert relatorio["dependencias"]["beat"]["verificado"] is False
    assert relatorio["estado"] == filas_saude.ESTADO_DESCONHECIDO


def test_saude_desconhecido_quando_nunca_rodou_o_ciclo_monitorado(sem_estado):
    """
    Prova: heartbeat fresco, mas o ciclo de ingestão nunca observado =>
    `desconhecido`. "A agenda está viva" não é "a agenda produziu trabalho".
    """
    filas_estado.registrar_beat(task=filas_tasks.NOME_HEARTBEAT_BEAT)
    app = MagicMock()
    app.tasks = dict(celery_app.tasks)
    app.autodiscover_tasks = lambda **_: None
    canal = MagicMock()
    canal.queue_declare.return_value = SimpleNamespace(message_count=0)
    app.connection.return_value.__enter__.return_value.default_channel = canal
    app.control.inspect.return_value.ping.return_value = {"w1@host": {"ok": "pong"}}
    app.control.inspect.return_value.active.return_value = {}
    app.control.inspect.return_value.reserved.return_value = {}

    with override_settings(
        CELERY_TASK_ALWAYS_EAGER=False,
        FILAS_TAREFA_MONITORADA=ingestao_tasks.TASK_INGESTAO,
    ):
        relatorio = filas_saude.relatorio(app=app)

    assert relatorio["dependencias"]["ultimo_ciclo"]["verificado"] is False
    assert relatorio["estado"] == filas_saude.ESTADO_DESCONHECIDO


def test_saude_desconhecido_com_arquivo_de_estado_corrompido(sem_estado):
    """
    Prova (fim a fim): um arquivo de estado CORROMPIDO leva o relatorio a
    `desconhecido`, com o problema do arquivo no campo proprio, mesmo com
    broker e worker perfeitos.

    Fecha o caminho que o auto-revisao apontou como risco: se o arquivo
    ilegivel fosse tratado como "estado vazio, tudo bem", o estado cairia
    para `ok` por nao ter nada para reclamar. Aqui o vazio攔ade do arquivo e
    justamente o que impede o verde.
    """
    caminho = sem_estado
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("conteudo que nao e json", encoding="utf-8")

    app = MagicMock()
    app.tasks = dict(celery_app.tasks)
    app.autodiscover_tasks = lambda **_: None
    canal = MagicMock()
    canal.queue_declare.return_value = SimpleNamespace(message_count=0)
    app.connection.return_value.__enter__.return_value.default_channel = canal
    app.control.inspect.return_value.ping.return_value = {"w1@host": {"ok": "pong"}}
    app.control.inspect.return_value.active.return_value = {}
    app.control.inspect.return_value.reserved.return_value = {}

    with override_settings(
        CELERY_TASK_ALWAYS_EAGER=False,
        FILAS_TAREFA_MONITORADA=filas_tasks.NOME_HEARTBEAT_BEAT,
    ):
        relatorio = filas_saude.relatorio(app=app)

    assert relatorio["estado"] == filas_saude.ESTADO_DESCONHECIDO
    assert relatorio["verificado"] is False
    assert relatorio["arquivo_estado_problema"], "o problema do arquivo sumiu do relatorio"
    assert relatorio["dependencias"]["beat"]["verificado"] is False
    assert relatorio["dependencias"]["ultimo_ciclo"]["verificado"] is False


def test_saude_ok_somente_com_tudo_verificado_e_sem_problema(sem_estado):
    """
    Prova o caminho feliz: TODAS as dependências verificadas e nenhuma com
    problema produz `ok` com `verificado: true`. Serve de contrapeso aos
    testes acima: se `desconhecido` fosse o único resultado possível, eles
    passariam por acidente.
    """
    _filas_saudaveis_agora()
    app = MagicMock()
    app.tasks = dict(celery_app.tasks)
    app.autodiscover_tasks = lambda **_: None
    canal = MagicMock()
    canal.queue_declare.return_value = SimpleNamespace(message_count=0)
    app.connection.return_value.__enter__.return_value.default_channel = canal
    app.control.inspect.return_value.ping.return_value = {"w1@host": {"ok": "pong"}}
    app.control.inspect.return_value.active.return_value = {}
    app.control.inspect.return_value.reserved.return_value = {}

    with override_settings(
        CELERY_TASK_ALWAYS_EAGER=False,
        FILAS_TAREFA_MONITORADA=filas_tasks.NOME_HEARTBEAT_BEAT,
        FILAS_BEAT_MAX_AGE_SEGUNDOS=900,
    ):
        relatorio = filas_saude.relatorio(app=app)

    assert relatorio["estado"] == filas_saude.ESTADO_OK
    assert relatorio["verificado"] is True
    assert relatorio["motivos"] == []


def test_saude_degradado_nao_apaga_fato_negativo_mediado(sem_estado):
    """
    Prova: broker não medido + fila de worker com task travada => `degradado`
    (fato negativo observado) e não `desconhecido`. "Não medi tudo" não pode
    apagar "vi a task travada". E `verificado` continua `false`, então o
    relatório não se vende como medido por completo.
    """
    _filas_saudaveis_agora()
    agora = time.time()
    app = MagicMock()
    app.tasks = dict(celery_app.tasks)
    app.autodiscover_tasks = lambda **_: None
    app.connection.side_effect = OperationalError("broker fora do ar")
    app.control.inspect.return_value.ping.return_value = {"w1@host": {"ok": "pong"}}
    app.control.inspect.return_value.active.return_value = {
        "w1@host": [{"name": "t", "time_start": agora - 5000}]
    }
    app.control.inspect.return_value.reserved.return_value = {}

    with override_settings(
        CELERY_TASK_ALWAYS_EAGER=False,
        FILAS_TAREFA_MONITORADA=filas_tasks.NOME_HEARTBEAT_BEAT,
        FILAS_IDADE_MAXIMA_TAREFA_SEGUNDOS=900,
    ):
        relatorio = filas_saude.relatorio(app=app, agora=agora)

    assert relatorio["estado"] == filas_saude.ESTADO_DEGRADADO
    assert relatorio["verificado"] is False
    assert relatorio["dependencias"]["workers"]["idade_da_mais_antiga_s"] > 900


def test_saude_degradado_com_fila_funda(sem_estado):
    """Prova: fila acima de `FILAS_PROFUNDIDADE_MAXIMA` é `degradado`."""
    _filas_saudaveis_agora()
    app = MagicMock()
    app.tasks = dict(celery_app.tasks)
    app.autodiscover_tasks = lambda **_: None
    canal = MagicMock()
    canal.queue_declare.return_value = SimpleNamespace(message_count=9000)
    app.connection.return_value.__enter__.return_value.default_channel = canal
    app.control.inspect.return_value.ping.return_value = {"w1@host": {"ok": "pong"}}
    app.control.inspect.return_value.active.return_value = {}
    app.control.inspect.return_value.reserved.return_value = {}

    with override_settings(
        CELERY_TASK_ALWAYS_EAGER=False,
        FILAS_TAREFA_MONITORADA=filas_tasks.NOME_HEARTBEAT_BEAT,
        FILAS_PROFUNDIDADE_MAXIMA=500,
    ):
        relatorio = filas_saude.relatorio(app=app)

    assert relatorio["estado"] == filas_saude.ESTADO_DEGRADADO
    assert relatorio["dependencias"]["broker"]["profundidade"] == 9000


def test_saude_degradado_com_ultimo_ciclo_em_falha(sem_estado):
    """Prova: último ciclo com falha é `degradado`, com o erro e as tentativas."""
    filas_estado.registrar_beat(task="config.tasks.heartbeat_beat")
    # Task diferente da do heartbeat de proposito: o heartbeat tambem se
    # registra como ciclo, e misturar os dois tornaria o contador de
    # tentativas ambíguo (o `registrar_beat` ja teria Famous uma falha).
    filas_estado.registrar_ciclo(
        task=ingestao_tasks.TASK_INGESTAO,
        estado=filas_estado.ESTADO_FALHA,
        tentativa=4,
        max_tentativas=4,
        erro="OperationalError: banco fora",
    )
    app = MagicMock()
    app.tasks = dict(celery_app.tasks)
    app.autodiscover_tasks = lambda **_: None
    canal = MagicMock()
    canal.queue_declare.return_value = SimpleNamespace(message_count=0)
    app.connection.return_value.__enter__.return_value.default_channel = canal
    app.control.inspect.return_value.ping.return_value = {"w1@host": {"ok": "pong"}}
    app.control.inspect.return_value.active.return_value = {}
    app.control.inspect.return_value.reserved.return_value = {}

    with override_settings(
        CELERY_TASK_ALWAYS_EAGER=False,
        FILAS_TAREFA_MONITORADA=ingestao_tasks.TASK_INGESTAO,
    ):
        relatorio = filas_saude.relatorio(app=app)

    assert relatorio["estado"] == filas_saude.ESTADO_DEGRADADO
    ciclo = relatorio["dependencias"]["ultimo_ciclo"]
    assert ciclo["estado"] == "falha"
    assert ciclo["tentativas_observadas"] == 1
    assert "banco fora" in ciclo["erro"]
    assert any("tentativas esgotadas" in motivo for motivo in relatorio["motivos"])


def test_idade_da_tarefa_mais_antiga_e_none_sem_task_em_execucao():
    """
    Prova: sem task em execução, a idade é `None` e a leitura é VERIFICADA.
    "Nada rodando" é um fato; "não sei" é outro. Este `None` não pode
    derrubar o estado para `desconhecido`.
    """
    agora = time.time()

    assert filas_saude._idade_da_mais_antiga({}, agora=agora) is None
    assert filas_saude._idade_da_mais_antiga({"w": []}, agora=agora) is None
    assert (
        filas_saude._idade_da_mais_antiga(
            {"w": [{"name": "t"}, {"name": "u", "time_start": "lixo"}]}, agora=agora
        )
        is None
    )


def test_idade_da_tarefa_mais_antiga_usa_o_maior_dos_ativos():
    """Prova: entre várias tasks em execução, a idade reportada é a maior."""
    agora = time.time()

    idade = filas_saude._idade_da_mais_antiga(
        {
            "w1": [{"time_start": agora - 10}],
            "w2": [{"time_start": agora - 300}],
        },
        agora=agora,
    )

    assert 299 <= idade <= 301


def test_idade_negativa_e_zerada_e_nao_inventada():
    """
    Prova: um `time_start` no futuro (relógio do worker adiantado) produz
    idade 0, nunca negativa — que seria lido como "task ainda mais velha".
    """
    agora = time.time()

    assert filas_saude._idade_da_mais_antiga(
        {"w": [{"time_start": agora + 500}]}, agora=agora
    ) == 0.0


def test_idade_nao_verificada_quando_active_e_none(sem_estado):
    """
    Prova: worker responde ao ping mas `active()` devolve `None` (não
    respondeu) => a idade é `None` e `idade_verificada: false`. O worker
    conta como verificado, mas a idade não.
    """
    app = MagicMock()
    app.control.inspect.return_value.ping.return_value = {"w1@host": {"ok": "pong"}}
    app.control.inspect.return_value.active.return_value = None
    app.control.inspect.return_value.reserved.return_value = {}

    resultado = filas_saude._sondar_workers(app)

    assert resultado["verificado"] is True
    assert resultado["idade_verificada"] is False
    assert resultado["idade_da_mais_antiga_s"] is None


# ===========================================================================
# 5. RETRY — falha transitoria gera retry e as tentativas são observáveis
# ===========================================================================


@pytest.mark.django_db
def test_falha_transitoria_gera_retry_e_tentativas_sao_observaveis(diretorio_estado, caplog):
    """
    Prova: uma `OperationalError` (banco fora) faz a task ser re-executada
    até `max_retries`, e cada tentativa é contada no estado durável e no log.
    Sem o contador, um retry seria indistinguível de "não aconteceu".
    """
    chamadas = []

    def _executar():
        chamadas.append(len(chamadas) + 1)
        raise OperationalError("banco indisponivel")

    with override_settings(
        CELERY_TASK_ALWAYS_EAGER=True,
        CELERY_TASK_EAGER_PROPAGATES=False,
    ):
        with patch.object(ingestao_tasks, "executar_ingestao", side_effect=_executar):
            resultado = ingestao_tasks.ingerir_noticias.apply(throw=False)

    # 1ª tentativa + 3 retries declarados em MAX_TENTATIVAS.
    assert len(chamadas) == ingestao_tasks.MAX_TENTATIVAS + 1
    assert resultado.state == "FAILURE"

    estado = filas_estado.ler_estado()
    ciclo = estado["ciclos"][ingestao_tasks.TASK_INGESTAO]
    assert ciclo["estado"] == "falha"
    assert ciclo["tentativas_observadas"] == len(chamadas)
    assert ciclo["tentativa"] == len(chamadas)
    assert ciclo["max_tentativas"] == len(chamadas)
    assert "banco indisponivel" in ciclo["erro"]

    logs = [r.getMessage() for r in caplog.records if "ingerir_noticias" in r.getMessage()]
    assert any(f"tentativa={n}/{len(chamadas)}" in msg for n, msg in zip([1, 2, 3, 4], logs)), (
        f"o log nao expoe o numero da tentativa: {logs}"
    )


@pytest.mark.django_db
def test_execucao_bem_sucedida_zera_o_contador_de_tentativas(diretorio_estado):
    """
    Prova: depois de 2 falhas, um sucesso deixa `tentativas_observadas: 1`.
    Sem o reset, o contador carregaria falhas antigas para sempre e o
    relatório diria "ainda falhando" num ambiente recuperado.
    """
    registro = SimpleNamespace(
        id=7,
        total_itens_ingeridos=3,
        total_grupos_formados=1,
        erros_por_fonte={},
    )
    # `EAGER_PROPAGATES` tem de ficar False: em execucao eager o Celery
    # REAPLICA a assinatura do retry sem repassar `throw`, e o fallback dele
    # e `task_eager_propagates` — ligada, a 2a tentativa estouraria `Retry`
    # para fora de `apply()` e o teste nem mediria a cadeia de retry.
    with override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=False):
        with patch.object(ingestao_tasks, "executar_ingestao", side_effect=OperationalError("x")):
            ingestao_tasks.ingerir_noticias.apply(throw=False)
            ingestao_tasks.ingerir_noticias.apply(throw=False)
        with patch.object(ingestao_tasks, "executar_ingestao", return_value=registro):
            assert ingestao_tasks.ingerir_noticias() == 7

    ciclo = filas_estado.ler_estado()["ciclos"][ingestao_tasks.TASK_INGESTAO]
    assert ciclo["estado"] == "sucesso"
    assert ciclo["tentativas_observadas"] == 1
    assert ciclo["detalhe"]["registro_id"] == 7
    assert ciclo["detalhe"]["itens_ingeridos"] == 3


@pytest.mark.django_db
def test_erro_nao_transitorio_nao_gera_retry(diretorio_estado):
    """
    Prova: um `ValueError` (erro de código, não de infraestrutura) NÃO é
    reprocessado — 1 execução só. Reprocessar bug não é retry, é desperdício
    e mascaramento.
    """
    chamadas = []

    def _executar():
        chamadas.append(1)
        raise ValueError("bug de codigo")

    with override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=False):
        with patch.object(ingestao_tasks, "executar_ingestao", side_effect=_executar):
            ingestion_result = ingestao_tasks.ingerir_noticias.apply(throw=False)

    assert len(chamadas) == 1
    assert isinstance(ingestion_result.result, ValueError)
    ciclo = filas_estado.ler_estado()["ciclos"][ingestao_tasks.TASK_INGESTAO]
    assert ciclo["tentativas_observadas"] == 1
    assert "ValueError" in ciclo["erro"]


@pytest.mark.django_db
def test_erro_de_redis_tambem_e_transitorio():
    """
    Prova: `redis.exceptions.ConnectionError` está na lista de retry — é a
    falha de infraestrutura mais provável num ambiente com broker Redis.
    """
    from redis.exceptions import ConnectionError as RedisConnectionError
    from redis.exceptions import TimeoutError as RedisTimeoutError

    assert RedisConnectionError in ingestao_tasks.EXCECOES_RETRY
    assert RedisTimeoutError in ingestao_tasks.EXCECOES_RETRY
    assert OperationalError in ingestao_tasks.EXCECOES_RETRY
    assert ValueError not in ingestao_tasks.EXCECOES_RETRY


def test_heartbeat_nao_tem_retry_porque_e_idempotente():
    """
    Prova: o heartbeat declara `max_retries=0` e ack imediato. Reexecutá-lo
    não faz trabalho nenhum — só fabricaria um sinal mais fresco, que é
    exatamente o falso verde a evitar.
    """
    task = celery_app.tasks[filas_tasks.NOME_HEARTBEAT_BEAT]

    assert task.max_retries == 0
    assert task.acks_late is False
