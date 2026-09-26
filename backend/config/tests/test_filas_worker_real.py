"""
Integração real do caminho broker -> worker -> disco (P1-03, WS-06).

`config/tests/test_filas.py` prova o consumo com um worker em thread
(`pool="solo"`), que é suficiente para provar que a fila é consumida. Este
arquivo vai um passo adiante e é o que sustenta a afirmação "um worker REAL
executa a task":

- o worker é um PROCESSO SEPARADO, iniciado com `celery -A config worker`;
- o broker é o transporte de filesystem do kombu (um broker de verdade,
  fora do processo, sem depender de Redis instalado na máquina);
- o estado gravado pelo worker filho é lido pelo PAI, num caminho de estado
  que só ele conhece.

Nenhuma asserção aqui depende de mock. É também o teste que mostra por que o
modo inline éDevelopment: aqui o pai não tem como "executar por conta própria"
— a prova depende de existir um processo consumindo a fila.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not Path(sys.executable).exists(),
    reason="o interpretador do venv e obrigatorio para subir o worker filho",
)


def _esperar_por(condicao, *, timeout=45.0, intervalo=0.2):
    """Espera activa por `condicao`, com limite — nunca um `sleep` fixo."""
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        if condicao():
            return True
        time.sleep(intervalo)
    return False


def _ambiente_do_worker(estado_dir: Path, transporte: Path):
    """
    Ambiente do processo filho.

    Reproduz o mínimo do que o systemd/PM2 precisa em DEV/HOMOLOG/PROD: um
    broker alcançável e um `PORTAL_FILAS_ESTADO_DIR` durável e FORA do
    repositorio. É a mesma configuração que `P0-07` terá de criar nos três
    ambientes — o codigo nao presume nenhum valor magico.
    """
    env = dict(os.environ)
    env.update(
        {
            # Modulo de settings DEDICADO a este teste: e a unica forma de
            # injetar `broker_transport_options` num processo filho (ver a
            # justificativa longa em `config/settings_teste_filas.py` — o
            # Celery nao faz json.loads dessa chave vinda do ambiente).
            "DJANGO_SETTINGS_MODULE": "config.settings_teste_filas",
            "DJANGO_DEBUG": "true",
            "DJANGO_DB_NAME": env.get("DJANGO_DB_NAME", "brd_portal_noticias"),
            "DJANGO_SECRET_KEY": env.get("DJANGO_SECRET_KEY", "") or "p103-integracao-chave-local",
            "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
            "PORTAL_FILAS_ESTADO_DIR": str(estado_dir),
            "P103_BROKER_TRANSPORT_DIR": str(transporte),
        }
    )
    return env


def test_worker_em_processo_separado_consome_a_fila_e_grava_o_estado(tmp_path):
    """
    PROVA: um `celery -A config worker` de verdade, num processo separado e
    com broker de filesystem, consome uma task publicada pelo pai e grava o
    estado duravel. O pai so descobre o resultado lendo o arquivo.

    E este o teste que responde a pergunta que o backlog faz ("um worker
    realmente a executa?") sem depender de mock nem de servico externo.
    """
    import os

    from config import tasks as filas_tasks
    from config.celery import app as celery_app

    estado_dir, transporte, log, worker = _subir_worker(tmp_path)
    leitor = threading.Thread(target=_consumir_log, args=(worker, log), daemon=True)
    leitor.start()
    try:
        # Espera o worker anunciar "ready" no proprio log em vez de dormir um
        # tempo fixo: publicar antes de o consumer subir seria uma corrida, e
        # um `sleep(2)` seria ao mesmo tempo lento e instavel em maquina
        # carregada.
        def _worker_pronto():
            return worker.poll() is None and any(" ready" in linha for linha in log)

        assert _esperar_por(_worker_pronto), _formatar_log(log)

        resultado = celery_app.send_task(
            filas_tasks.NOME_HEARTBEAT_BEAT,
            connection=_conexao_do_pai(transporte),
        )
        assert _esperar_por(
            lambda: _ler_beat(estado_dir) is not None, timeout=45.0
        ), _formatar_log(log)
        registro = _ler_beat(estado_dir)
        assert registro["task"] == filas_tasks.NOME_HEARTBEAT_BEAT
        # O `pid` e a prova dura de que quem gravou foi o PROCESSO FILHO: o
        # pai consegue ler o arquivo, mas nao consegue escreve-lo nesta task.
        assert registro["pid"] != os.getpid()
        assert resultado.id
    finally:
        _derrubar(worker)


def _conexao_do_pai(transporte: Path):
    """
    Conexao do PAI, com os dois papeis de pasta INVERTIDOS em relacao ao
    worker.

    O transporte de filesystem do kombu nao e um broker "de verdade": ele e
    um par de diretorios onde `_put()` escreve em `data_folder_out` e
    `_get()` le de `data_folder_in` (ver `kombu/transport/filesystem.py`).
    Para dois processos conversarem, o `out` de um tem de ser o `in` do
    outro. Por isso o pai usa in=`saida` e out=`entrada` -- o oposto do
    worker, que e quem define os papeis em `config/settings_teste_filas.py`.

    O pai passa `transport_options=` direto no `Connection` (ele nao passa
    pelo `app.conf`), entao nao sofre do problema de JSON do Celery.
    """
    from kombu import Connection

    return Connection(
        "filesystem://",
        transport_options={
            "data_folder_in": str(transporte / "saida"),
            "data_folder_out": str(transporte / "entrada"),
            "control_folder": str(transporte / "controle"),
            "store_processed": False,
            "polling_interval": 0.1,
        },
    )


def _consumir_log(processo, destino: list[str]) -> None:
    """Drena o stdout do worker num buffer, para poder esperar "pronto" sem deadlock."""
    if processo.stdout is None:  # pragma: no cover - defensivo
        return
    for linha in processo.stdout:
        destino.append(linha.rstrip())


def _formatar_log(log: list[str]) -> str:
    """Log do worker na mensagem de falha — sem ele, um timeout e opaco."""
    return "\n".join(log[-40:]) or "(o worker nao produziu nenhuma saida)"


def _ler_beat(estado_dir: Path):
    caminho = estado_dir / "estado-filas.json"
    if not caminho.exists():
        return None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # Escrita em andamento (o `os.replace` é atômico, mas a leitura pode
        # pegar o instante anterior): trata como "ainda nao".
        return None
    return (dados or {}).get("beat")


def test_relatorio_real_mede_o_broker_do_filho_e_recusa_dizer_ok(tmp_path, monkeypatch):
    """
    PROVA (o teste de "falso verde" com broker REAL, não mock): com um
    `celery -A config worker` de verdade consumindo a fila em processo
    separado, o relatório de saúde roda no PAI e:

    1. MEDE de verdade a profundidade da fila no broker do worker
       (0, porque o worker consumiu a mensagem);
    2. LÊ de verdade o heartbeat que o FILHO gravou em disco, e confirma
       que está dentro do limite de idade;
    3. NÃO diz `ok` — devolve `desconhecido`, porque a sonda de workers não
       pôde ser verificada.

    O ponto 3 é o que interessa, e ele NÃO é um defeito do código: o
    transporte de filesystem do kombu é "publica/consome" e não entrega
    mensagem de CONTROLE em broadcast — o `reply.celery.pidbox.exchange` fica
    gravado no `control_folder` e o `inspect().ping()` volta `None` mesmo com
    o worker ali, vivo e consumindo (verificado à mão nesta máquina). Em
    DEV/HOMOLOG/PROD o broker é Redis, onde `inspect().ping()` é um RPC de
    broadcast; o caminho de código é o mesmo dos dois lados.

    O que este teste portanto prova, com broker real em vez de dublê: uma
    dependência não verificável derruba o estado para `desconhecido`, mesmo
    com todo o resto medido e perfeito. Um relatório que devolvesse `ok`
    aqui estaria mentindo sobre um ambiente que ele não consegue ver por
    inteiro — que é a falha que o P1-03 precisa impedir.
    """
    from django.test import override_settings

    from config import filas_saude, tasks as filas_tasks
    from config.celery import app as celery_app

    from django.conf import settings as dj
    print("PROBE settings_module:", dj.SETTINGS_MODULE, "| env:", os.environ.get("DJANGO_SETTINGS_MODULE"))
    print("PROBE django CELERY_RESULT_BACKEND:", getattr(dj, "CELERY_RESULT_BACKEND", "AUSENTE"))
    print("PROBE result_backend:", celery_app.conf.result_backend)
    estado_dir, transporte, log, worker = _subir_worker(tmp_path)
    leitor = threading.Thread(target=_consumir_log, args=(worker, log), daemon=True)
    leitor.start()
    try:
        assert _esperar_por(
            lambda: worker.poll() is None and any(" ready" in linha for linha in log)
        ), _formatar_log(log)

        print("PROBE2 result_backend:", celery_app.conf.result_backend, "| changes:", dict(celery_app.conf.changes))
        celery_app.send_task(
            filas_tasks.NOME_HEARTBEAT_BEAT, connection=_conexao_do_pai(transporte)
        )
        assert _esperar_por(lambda: _ler_beat(estado_dir) is not None), _formatar_log(log)

        # O PAI tem de olhar para o MESMO diretorio de estado que o filho
        # gravou -- e o do teste, nao o default do ambiente.
        monkeypatch.setenv("PORTAL_FILAS_ESTADO_DIR", str(estado_dir))

        from config.celery import app as celery_app

        with override_settings(
            FILAS_TAREFA_MONITORADA=filas_tasks.NOME_HEARTBEAT_BEAT,
            FILAS_BEAT_MAX_AGE_SEGUNDOS=900,
        ):
            # A CONEXAO do pai e passada explicitamente: sem isso o
            # relatório abriria a propria, a partir de
            # `CELERY_BROKER_URL` do pytest (que e `memory://` — um broker
            # dentro do processo do pai, onde o worker nao existe), e
            # mediria uma fila que nao tem nada a ver com a do filho.
            relatorio = filas_saude.relatorio(
                app=celery_app, conexao=_conexao_do_pai(transporte)
            )

        partes = relatorio["dependencias"]

        # (1) leitura real do broker do worker filho
        assert partes["broker"]["verificado"] is True, relatorio["motivos"]
        assert partes["broker"]["profundidade"] == 0, "o worker deveria ter consumido a fila"

        # (2) heartbeat gravado pelo processo filho, dentro do limite
        assert partes["beat"]["verificado"] is True
        assert partes["beat"]["expirado"] is False
        assert partes["beat"]["task"] == filas_tasks.NOME_HEARTBEAT_BEAT

        # (3) e ainda assim: NAO verde.
        assert partes["workers"]["verificado"] is False
        assert relatorio["estado"] == filas_saude.ESTADO_DESCONHECIDO
        assert relatorio["verificado"] is False
        assert any("worker" in motivo for motivo in relatorio["motivos"])
    finally:
        _derrubar(worker)


def _subir_worker(tmp_path):
    """Sobe o worker real em processo separado e devolve os objetos de teste."""
    estado_dir = tmp_path / "estado"
    transporte = tmp_path / "broker"
    estado_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("entrada", "saida", "controle"):
        (transporte / sub).mkdir(parents=True, exist_ok=True)

    env = _ambiente_do_worker(estado_dir, transporte)
    worker = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "config",
            "worker",
            "--loglevel=info",
            "--pool=solo",
            "--concurrency=1",
        ],
        cwd=str(Path(__file__).resolve().parents[2]),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return estado_dir, transporte, [], worker


def _derrubar(worker) -> None:
    worker.terminate()
    try:
        worker.wait(timeout=20)
    except subprocess.TimeoutExpired:  # pragma: no cover - defensivo
        worker.kill()
        worker.wait(timeout=10)


def test_modulo_de_settings_de_teste_fala_quando_e_para_que(monkeypatch):
    """
    PROVA (cobertura do modulo de settings do worker): o modulo
    `config.settings_teste_filas` so tem efeito quando
    `P103_BROKER_TRANSPORT_DIR` aponta para um diretorio de transporte. Sem
    essa variavel ele nao troca broker nenhum — e um `import` dele num
    processo normal nao muda nada.

    Este teste existe por dois motivos:

    1. cobertura: o modulo e executado no PROCESSO FILHO (o
       `celery -A config worker`), e a coverage do pai nao enxerga o que
       acontece la. Sem este teste o arquivo apareceria com 0% e ninguem
       notaria que ele nem esta sendo testado.
    2. contrato: o default "nao mexe em nada" e o que garante que importar
       este modulo por engano, num processo normal, nao troque o broker de
       ninguem.
    """
    import importlib

    from django.test import override_settings

    with override_settings():
        monkeypatch.delenv("P103_BROKER_TRANSPORT_DIR", raising=False)
        sem_transporte = importlib.reload(importlib.import_module("config.settings_teste_filas"))
        assert sem_transporte.CELERY_BROKER_URL == "redis://localhost:6379/0"
        assert not getattr(sem_transporte, "CELERY_BROKER_TRANSPORT_OPTIONS", None)

        monkeypatch.setenv("P103_BROKER_TRANSPORT_DIR", "/tmp/p103-transporte-prova")
        com_transporte = importlib.reload(importlib.import_module("config.settings_teste_filas"))
        opcoes = com_transporte.CELERY_BROKER_TRANSPORT_OPTIONS
        assert com_transporte.CELERY_BROKER_URL == "filesystem://"
        assert opcoes["data_folder_in"] == "/tmp/p103-transporte-prova/entrada"
        assert opcoes["data_folder_out"] == "/tmp/p103-transporte-prova/saida"
        assert opcoes["control_folder"] == "/tmp/p103-transporte-prova/controle"
        assert com_transporte.CELERY_RESULT_BACKEND == "cache+memory://"

    # Restaura o estado do modulo para nao vazar broker de filesystem para
    # os testes seguintes (o reload deixa o objeto do modulo em memoria).
    monkeypatch.delenv("P103_BROKER_TRANSPORT_DIR", raising=False)
    importlib.reload(importlib.import_module("config.settings_teste_filas"))
