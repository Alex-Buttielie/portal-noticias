"""Canal durável de telemetria de job: worker -> processo que serve `/metrics`.

Achado MAJOR-4 (critério 14): `METRICS` é por processo, o `/metrics` é servido
pelo processo **web** e o `record_celery` roda no **worker** — então
`portal_celery_tasks_total`, `portal_celery_task_duration_seconds` e as métricas
do expurgo não apareciam em nenhum scrape, e não existia métrica de **atraso**.
Estes testes fixam o canal (`config/job_state.py`), o sinal de atraso e a
visibilidade no scrape.
"""

from __future__ import annotations

import json
import time

import pytest
from django.test import Client, override_settings

from config import health, job_state
from config.metrics import METRICS

pytestmark = pytest.mark.django_db

IP_EXTERNO = "203.0.113.10"


@pytest.fixture
def arquivo_de_estado(tmp_path):
    """Arquivo de estado isolado por teste (o canal é por caminho)."""

    caminho = tmp_path / "jobs.json"
    with override_settings(OBSERVABILITY_JOB_STATE_FILE=str(caminho)):
        yield caminho


# ---------------------------------------------------------------------------
# Escrita (lado worker) e leitura (lado web)
# ---------------------------------------------------------------------------


def test_task_terminada_e_publicada_para_o_processo_que_expoe_metrics(arquivo_de_estado):
    job_state.registrar_task("feed.tasks.registrar_evento_busca", "SUCCESS", 0.5)
    job_state.registrar_task("feed.tasks.registrar_evento_busca", "FAILURE", 0.25)
    job_state.registrar_retry("feed.tasks.registrar_evento_busca")

    METRICS.clear()
    resumo = job_state.publicar_metricas()

    texto = METRICS.render_prometheus()
    task = 'task="feed.tasks.registrar_evento_busca"'
    assert f'portal_job_tasks_recorded{{result="SUCCESS",{task}}} 1' in texto
    assert f'portal_job_tasks_recorded{{result="FAILURE",{task}}} 1' in texto
    assert f"portal_job_task_retries_recorded{{{task}}} 1" in texto
    assert f"portal_job_task_duration_seconds_count{{{task}}} 2" in texto
    assert f"portal_job_task_duration_seconds_sum{{{task}}} 0.75" in texto
    assert f"portal_job_task_idle_seconds{{{task}}} 0" in texto
    assert resumo["tasks"] == 1
    # Nada de dado pessoal: o estado é nome de task (código), estado e contagem.
    assert "email" not in json.dumps(json.loads(arquivo_de_estado.read_text()))


def test_atraso_de_job_e_a_idade_do_ultimo_sucesso(arquivo_de_estado):
    """O que o critério 14 pedia e não existia: um sinal de ATRASO. `idle` é o
    tempo desde o último término BEM-SUCEDIDO; uma task que só falha tem
    último sucesso em zero e fica marcada como sinal ausente (-1), em vez de
    parecer saudosa."""

    METRICS.clear()
    job_state.registrar_task("catalogo_noticias.tasks.ingerir", "FAILURE", 1.0)
    METRICS.clear()
    job_state.publicar_metricas()
    assert 'portal_job_task_idle_seconds{task="catalogo_noticias.tasks.ingerir"} -1' in (
        METRICS.render_prometheus()
    )

    job_state.registrar_task("catalogo_noticias.tasks.ingerir", "SUCCESS", 1.0)
    METRICS.clear()
    job_state.publicar_metricas()
    assert 'portal_job_task_idle_seconds{task="catalogo_noticias.tasks.ingerir"} 0' in (
        METRICS.render_prometheus()
    )


def test_escrita_e_atomica_e_acumula_por_task(arquivo_de_estado):
    for indice in range(3):
        job_state.registrar_task("a.tasks.x", "SUCCESS", indice)

    estado = json.loads(arquivo_de_estado.read_text())

    assert estado["tasks"]["a.tasks.x"]["resultados"]["SUCCESS"] == 3
    assert estado["tasks"]["a.tasks.x"]["duracao_contagem"] == 3
    assert estado["versao"] == 1
    # Nenhum arquivo temporário sobrou (a escrita é `write` + `os.replace`).
    assert list(arquivo_de_estado.parent.glob("*.tmp-*")) == []


def test_sem_canal_configurado_nao_inventa_sinal():
    with override_settings(OBSERVABILITY_JOB_STATE_FILE=""):
        assert job_state.caminho() is None
        assert job_state.ler() is None
        assert job_state.publicar_metricas() is None
        # E a escrita é no-op: o worker não cria arquivo fantasma.
        job_state.registrar_task("a.tasks.x", "SUCCESS", 0.1)
        job_state.registrar_retry("a.tasks.x")


def test_check_de_job_reporta_cada_estado_do_canal(tmp_path):
    with override_settings(OBSERVABILITY_JOB_STATE_FILE=""):
        assert health.check_celery_jobs().status == "not_configured"

    ausente = tmp_path / "nao-existe.json"
    with override_settings(OBSERVABILITY_JOB_STATE_FILE=str(ausente)):
        assert health.check_celery_jobs().status == "error"

    valido = tmp_path / "jobs.json"
    valido.write_text(json.dumps({"versao": 1, "atualizado_em": time.time(), "tasks": {}}))
    with override_settings(OBSERVABILITY_JOB_STATE_FILE=str(valido)):
        assert health.check_celery_jobs().status == "ok"

    velho = tmp_path / "velho.json"
    velho.write_text(
        json.dumps({"versao": 1, "atualizado_em": time.time() - 7200, "tasks": {}})
    )
    with override_settings(
        OBSERVABILITY_JOB_STATE_FILE=str(velho), OBSERVABILITY_JOB_STATE_MAX_AGE_SECONDS=900
    ):
        resultado = health.check_celery_jobs()

    assert resultado.status == "degraded"
    assert "stale" in resultado.detail
    assert resultado.meta["age_seconds"] > 7000


def test_arquivo_corrompido_e_erro_e_nao_explode(arquivo_de_estado):
    arquivo_de_estado.write_text("{isto nao e json")

    with override_settings(OBSERVABILITY_JOB_STATE_FILE=str(arquivo_de_estado)):
        assert job_state.ler() is None
        assert health.check_celery_jobs().status == "error"


def test_metrica_de_job_aparece_no_scrape_do_processo_web(arquivo_de_estado):
    """O ponto do MAJOR-4: o que o worker escreveu tem que aparecer no
    `/metrics` do processo web — sem tráfego e sem probe de degradação (que
    publicaria por outro caminho). A view é chamada direto, sem middleware."""

    from django.test import RequestFactory

    from config.observability_views import metrics_view

    job_state.registrar_task("catalogo_noticias.tasks.ingerir", "SUCCESS", 2.0)
    METRICS.clear()
    request = RequestFactory().get("/metrics", REMOTE_ADDR="127.0.0.1")

    corpo = metrics_view(request).content.decode("utf-8")

    assert 'portal_job_task_idle_seconds{task="catalogo_noticias.tasks.ingerir"}' in corpo
    assert "portal_job_state_age_seconds" in corpo
    assert 'portal_job_task_duration_seconds_sum{task="catalogo_noticias.tasks.ingerir"} 2' in corpo


def test_metrica_de_job_aparece_no_scrape_ponta_a_ponta(arquivo_de_estado):
    job_state.registrar_task("catalogo_noticias.tasks.ingerir", "SUCCESS", 2.0)
    METRICS.clear()

    corpo = Client().get("/metrics", REMOTE_ADDR="127.0.0.1").content.decode("utf-8")

    assert 'portal_job_task_idle_seconds{task="catalogo_noticias.tasks.ingerir"}' in corpo
    # A negação do gating continua valendo (o canal não abre nada).
    assert Client().get("/metrics", REMOTE_ADDR=IP_EXTERNO).status_code == 404


def test_worker_registra_o_fim_de_task_no_canal(tmp_path):
    """Ponta a ponta do sinal: o `task_postrun` do Celery grava no arquivo."""

    caminho = tmp_path / "jobs.json"
    with override_settings(OBSERVABILITY_JOB_STATE_FILE=str(caminho)):
        from celery import signals

        class _Task:
            name = "feed.tasks.registrar_evento_busca"

        signals.task_prerun.send(
            sender=None, task_id="t1", task=_Task, args=(), kwargs={}
        )
        signals.task_postrun.send(sender=None, task_id="t1", state="SUCCESS")
        signals.task_retry.send(sender=None, request=type("R", (), {"task": _Task})(), kwargs={})

    estado = json.loads(caminho.read_text())

    assert estado["tasks"]["feed.tasks.registrar_evento_busca"]["resultados"] == {"SUCCESS": 1}
    assert estado["tasks"]["feed.tasks.registrar_evento_busca"]["retries"] == 1


def test_nome_de_task_dinamico_nao_cresce_o_arquivo_sem_teto(arquivo_de_estado):
    for indice in range(job_state.MAX_TASKS + 20):
        job_state.registrar_task(f"dyn.tasks.{indice}", "SUCCESS", 0.1)

    estado = json.loads(arquivo_de_estado.read_text())

    assert len(estado["tasks"]) == job_state.MAX_TASKS
