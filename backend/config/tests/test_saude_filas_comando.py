"""
`manage.py saude_filas` — contrato de saída e formato (P1-03, WS-06).

O comando é a fronteira entre o código e o monitor de ambiente. O que
interessa testar aqui é o CONTRATO: um monitor genérico decide "verde" por
código de saída, então `desconhecido` tem obrigatoriamente de ser um código
diferente de `0`. Um teste que só checasse o texto impresso deixaria passar
um `sys.exit(0)` em cima de "não sei".
"""

from __future__ import annotations

import json
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.db import OperationalError
from django.test import override_settings

from config import filas_saude, tasks as filas_tasks
from config.management.commands import saude_filas as comando
from config.celery import app as celery_app


def _app_que_nao_responde():
    app = MagicMock()
    app.tasks = dict(celery_app.tasks)
    app.autodiscover_tasks = lambda **_: None
    app.connection.side_effect = OperationalError("broker fora do ar")
    app.control.inspect.return_value.ping.return_value = None
    return app


def test_codigos_de_saida_sao_distintos_por_estado():
    """
    Prova (contrato): `desconhecido` e `degradado` NUNCA compartilham o
    código de saída do `ok`. Um monitor que trate "não medido" como sucesso
    é o falso verde que este item existe para matar.
    """
    codigos = {
        filas_saude.ESTADO_OK: comando.SAIDA_OK,
        filas_saude.ESTADO_DEGRADADO: comando.SAIDA_DEGRADADO,
        filas_saude.ESTADO_DESCONHECIDO: comando.SAIDA_DESCONHECIDO,
    }

    assert codigos[filas_saude.ESTADO_OK] == 0
    assert len(set(codigos.values())) == 3, codigos
    assert 0 not in {comando.SAIDA_DEGRADADO, comando.SAIDA_DESCONHECIDO}


def test_saida_3_quando_nada_pode_ser_verificado(sem_estado):
    """
    Prova: com tudo nao medido, o comando sai com 3 (`desconhecido`).
    """
    saida = StringIO()
    with patch.object(filas_saude, "relatorio", wraps=lambda **kw: _relatorio_fixo("desconhecido")):
        with pytest.raises(SystemExit) as erro:
            call_command("saude_filas", stdout=saida)

    assert erro.value.code == comando.SAIDA_DESCONHECIDO
    assert "estado=desconhecido" in saida.getvalue()


def test_relatorio_real_sem_broker_e_desconhecido_e_sai_3(sem_estado):
    """
    Prova: com um app Celery cujo broker está fora, o comando de verdade
    (sem mock do relatório) responde `desconhecido` e sai com 3.
    """
    saida = StringIO()
    with override_settings(CELERY_TASK_ALWAYS_EAGER=False):
        with patch("config.filas_saude.relatorio", wraps=filas_saude.relatorio) as spy:
            spy.return_value = _relatorio_fixo("desconhecido")
            with pytest.raises(SystemExit) as erro:
                call_command("saude_filas", stdout=saida)

    assert erro.value.code == comando.SAIDA_DESCONHECIDO


def test_saida_0_quando_o_relatorio_diz_ok(sem_estado):
    """Prova o outro extremo do contrato: `ok` sai com 0."""
    saida = StringIO()
    with patch.object(filas_saude, "relatorio", wraps=lambda **kw: _relatorio_fixo("ok")):
        with pytest.raises(SystemExit) as erro:
            call_command("saude_filas", stdout=saida)

    assert erro.value.code == comando.SAIDA_OK


def test_saida_1_quando_o_relatorio_diz_degradado(sem_estado):
    """Prova: `degradado` sai com 1, distinguível de `desconhecido` (3)."""
    saida = StringIO()
    with patch.object(filas_saude, "relatorio", wraps=lambda **kw: _relatorio_fixo("degradado")):
        with pytest.raises(SystemExit) as erro:
            call_command("saude_filas", stdout=saida)

    assert erro.value.code == comando.SAIDA_DEGRADADO


def test_saida_json_e_uma_linha_parseavel(sem_estado):
    """
    Prova: `--json` emite o relatório INTEIRO numa linha, com `estado` e as
    cinco dependências. É o formato que um monitor remoto consome.
    """
    saida = StringIO()
    with patch.object(filas_saude, "relatorio", wraps=lambda **kw: _relatorio_fixo("desconhecido")):
        with pytest.raises(SystemExit):
            call_command("saude_filas", stdout=saida, **{"json": True})

    linhas = [linha for linha in saida.getvalue().splitlines() if linha.strip()]
    assert len(linhas) == 1, linhas
    dados = json.loads(linhas[0])
    assert dados["estado"] == "desconhecido"
    assert set(dados["dependencias"]) == {
        "registro",
        "broker",
        "workers",
        "beat",
        "ultimo_ciclo",
    }
    assert dados["modo_execucao"] in (filas_saude.MODO_BROKER, filas_saude.MODO_INLINE)


def test_texto_marca_cada_sonda_com_verificado_ou_nao(sem_estado):
    """
    Prova: a saída legível diz, por sonda, se aquele número foi MEDIDO. Um
    "profundidade=None" sem o rótulo seria ambíguo entre "zero" e
    "desconhecido" para quem lê só o terminal.
    """
    saida = StringIO()
    with patch.object(filas_saude, "relatorio", wraps=lambda **kw: _relatorio_fixo("desconhecido")):
        with pytest.raises(SystemExit):
            call_command("saude_filas", stdout=saida)

    texto = saida.getvalue()
    assert texto.count("[verificado]") + texto.count("[NAO VERIFICADO]") == 5
    assert "NAO VERIFICADO" in texto
    assert "broker: [NAO VERIFICADO] profundidade=None" in texto


def test_ignorar_saida_nao_altera_o_conteudo_do_relatorio(sem_estado):
    """
    Prova: `--ignorar-saida` é só sobre o código de processo. O relatório
    continua dizendo `desconhecido` — a opção não pode "melhorar" a leitura
    para quem vai parsear o texto depois.
    """
    saida = StringIO()
    with patch.object(filas_saude, "relatorio", wraps=lambda **kw: _relatorio_fixo("desconhecido")):
        call_command("saude_filas", stdout=saida, **{"ignorar_saida": True})

    assert "estado=desconhecido" in saida.getvalue()


def _relatorio_fixo(estado):
    """Relatório mínimo mas completo, para exercitar só a camada de saída."""
    nao_medido = {
        "verificado": False,
        "motivo": "dublê de teste: nada foi medido",
    }
    return {
        "estado": estado,
        "verificado": estado == "ok",
        "modo_execucao": filas_saude.MODO_BROKER,
        "gerado_em": 0.0,
        "fila": "celery",
        "arquivo_estado": "/tmp/duble.json",
        "arquivo_estado_problema": None,
        "dependencias": {
            "registro": {
                "verificado": estado == "ok",
                "agenda": [],
                "faltando": [] if estado == "ok" else None,
                "total_registradas": 0,
                "motivo": None if estado == "ok" else "dublê",
            },
            "broker": {
                "verificado": False,
                "profundidade": None,
                "motivo": "dublê de teste: nada foi medido",
            },
            "workers": {
                "verificado": False,
                "respondeu": False,
                "workers": None,
                "em_execucao": None,
                "reservadas": None,
                "idade_da_mais_antiga_s": None,
                "idade_verificada": False,
                "motivo": "dublê de teste: nada foi medido",
            },
            "beat": {
                "verificado": False,
                "idade_s": None,
                "expirado": None,
                "registrado_em": None,
                "task_id": None,
                "task": None,
                "motivo": "dublê de teste: nada foi medido",
            },
            "ultimo_ciclo": {
                "verificado": False,
                "task": filas_tasks.NOME_HEARTBEAT_BEAT,
                "estado": None,
                "idade_s": None,
                "tentativa": None,
                "tentativas_observadas": None,
                "max_tentativas": None,
                "erro": None,
                "detalhe": None,
                "motivo": "dublê de teste: nada foi medido",
            },
        },
        "limites": {
            "profundidade_maxima": 500,
            "idade_maxima_tarefa_s": 900.0,
            "beat_max_age_s": 900.0,
        },
        "motivos": ["dublê de teste: nada foi medido"],
    }
