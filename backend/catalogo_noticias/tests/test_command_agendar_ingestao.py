"""
Comando `manage.py agendar_ingestao` — critérios de aceite 1-5 do
implementation-contract.md (run 20260924-2136-ingestao-noticias, versão 2)
e teste de equivalência da otimização da deduplicação (critério 9).

Os testes do agendador NÃO chamam o pipeline real (`executar_ingestao` é
mockado — faria HTTP nos feeds RSS); exercitam o loop de verdade: primeira
rodada imediata, isolamento de falha de rodada, intervalo configurado e
default via settings, encerramento gracioso via SINAL REAL (SIGINT/SIGTERM
entregues ao próprio processo com o handler instalado pelo command) e
`close_old_connections()` por rodada.

O teste de equivalência replica a implementação ANTIGA de
`agrupar_itens_brutos` (copiada VERBATIM de
`git show HEAD:backend/catalogo_noticias/services/deduplicacao.py`, com
prefixo `_antiga_` para não colidir com o módulo novo) e compara os grupos
de saída com a implementação nova (pre-filtro por upper bound + cache LRU)
em lotes variados (150 e 300 itens + lotes aleatórios com seed fixa) —
os grupos devem ser IDÊNTICOS (critério de aceite 9).

Lacunas de cobertura fechadas pelo tester (iteração 7) — os testes acima
exercitam o command IN-PROCESS (via `call_command`), o que prova a lógica do
loop mas NÃO prova o que o critério fala literalmente ("o processo sai com
código 0", "sai sem traceback não tratado"). Por isso há também testes em
PROCESSO REAL (subprocesso): o `manage.py agendar_ingestao` é executado de
verdade, com `executar_ingestao` substituído no próprio processo filho, e o
código de saída / stderr / latência de encerramento são observados de fora.
"""

from __future__ import annotations

import logging
import os
import random
import re
import signal
import subprocess
import sys
import time
from difflib import SequenceMatcher
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from catalogo_noticias.providers.news_source import ItemBruto
from catalogo_noticias.services import deduplicacao as dedup_nova

_PATCH_TARGET = "catalogo_noticias.management.commands.agendar_ingestao.executar_ingestao"
_LOGGER = "catalogo_noticias.management.commands.agendar_ingestao"
_BACKEND = Path(__file__).resolve().parents[2]


def _registro(**sobrescritas):
    base = {
        "id": 99,
        "total_itens_ingeridos": 3,
        "total_grupos_formados": 1,
        "total_duplicatas_agrupadas": 0,
        "chamadas_summarization_provider": 1,
        "itens_por_fonte": {"G1": 3},
        "erros_por_fonte": {},
    }
    base.update(sobrescritas)
    return SimpleNamespace(**base)


def _logs_do_agendador(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == _LOGGER]


# ==============================================================================
# Critério 1: primeira rodada imediata, executar_ingestao 1x, log início/fim,
# saída sem erro (equivalente in-process de código 0: handle() completa sem
# CommandError/exceção).
#
# django_db OBRIGATÓRIO nestes testes: o command chama close_old_connections()
# de verdade (comportamento inerente ao command de longa vida), que toca a
# conexão de banco — o pytest-django bloqueia sem a marca. Rodando o arquivo
# sozinho o bloqueio nem chega a ser instalado (nenhum teste pediu o banco
# antes), mas na suíte completa sim — por isso a marca é explícita.
# ==============================================================================


@pytest.mark.django_db
def test_primeira_rodada_imediata_chama_executar_ingestao_uma_vez(caplog):
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        with patch(_PATCH_TARGET, return_value=_registro()) as executar:
            saida = StringIO()
            call_command("agendar_ingestao", "--rodadas", "1", stdout=saida)

    assert executar.call_count == 1
    mensagens = _logs_do_agendador(caplog)
    assert any("Rodada 1/1: iniciando ingestão" in m for m in mensagens)
    assert any("Rodada 1/1 concluída (registro_id=99, 3 itens" in m for m in mensagens)
    assert any("primeira rodada imediata" in m for m in mensagens)
    assert "Agendador finalizado (1 rodada(s))." in saida.getvalue()


# ==============================================================================
# Critério 2: exceção na primeira rodada é logada com traceback e o loop segue
# para a segunda rodada.
# ==============================================================================


@pytest.mark.django_db
def test_falha_na_primeira_rodada_nao_mata_o_loop(caplog):
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        with patch(
            _PATCH_TARGET,
            side_effect=[RuntimeError("fonte caiu"), _registro(id=100)],
        ) as executar:
            # --intervalo-segundos 1: sem isso a espera REAL entre as rodadas
            # seria o default de 900s (o teste não pode dormir 15 min)
            call_command("agendar_ingestao", "--intervalo-segundos", "1", "--rodadas", "2")

    assert executar.call_count == 2
    mensagens = _logs_do_agendador(caplog)
    assert any("Rodada 1/2: iniciando ingestão" in m for m in mensagens)
    assert any("Rodada 1/2: falhou — seguindo para a próxima rodada" in m for m in mensagens)
    assert any("Rodada 2/2: iniciando ingestão" in m for m in mensagens)
    assert any("Rodada 2/2 concluída (registro_id=100" in m for m in mensagens)
    # traceback da exceção logado (logger.exception → exc_info no record)
    registros_com_traceback = [r for r in caplog.records if r.name == _LOGGER and r.exc_info]
    assert len(registros_com_traceback) == 1


# ==============================================================================
# Critério 3: `--intervalo-segundos 1` é respeitado — a segunda rodada acontece
# após ~1s (não 15 min). Teste de tempo REAL (~1s) + teste do mecanismo de
# espera (fatias de 1s) com sleep mockado.
# ==============================================================================


@pytest.mark.django_db
def test_intervalo_configurado_respeitado_segunda_rodada_apos_o_intervalo(caplog):
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        with patch(_PATCH_TARGET, return_value=_registro()) as executar:
            inicio = time.monotonic()
            call_command("agendar_ingestao", "--intervalo-segundos", "1", "--rodadas", "2")
            decorrido = time.monotonic() - inicio

    assert executar.call_count == 2
    # ~1s de espera real (fatia única de 1s); folga para máquinas lentas, e
    # ordem de grandeza muito menor que os 900s do default
    assert 0.9 <= decorrido < 30


@pytest.mark.django_db
def test_intervalo_configurado_chega_ao_mecanismo_de_espera(caplog):
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        with patch(_PATCH_TARGET, return_value=_registro()):
            with patch(
                "catalogo_noticias.management.commands.agendar_ingestao.time.sleep"
            ) as dormir:
                call_command(
                    "agendar_ingestao", "--intervalo-segundos", "3", "--rodadas", "2"
                )

    # _dormir(3) dorme em 3 fatias de 1s (resposta de encerramento em ~1s,
    # sem busy-wait) — total de 3s entre as rodadas
    assert dormir.call_args_list == [call(1), call(1), call(1)]


# ==============================================================================
# Critério 4: sem flags, o intervalo vem de
# CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS * 60 — provado com um valor
# DISTINTO da setting (7 → 420s): um default hardcoded de 15*60 falharia aqui.
# ==============================================================================


@pytest.mark.django_db
def test_intervalo_default_vem_da_setting_de_minutos(caplog):
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        with patch(_PATCH_TARGET, return_value=_registro()):
            with patch(
                "catalogo_noticias.management.commands.agendar_ingestao.time.sleep"
            ) as dormir:
                with override_settings(CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS=7):
                    call_command("agendar_ingestao", "--rodadas", "2")

    total_dormido = sum(c.args[0] for c in dormir.call_args_list)
    assert total_dormido == 7 * 60
    mensagens = _logs_do_agendador(caplog)
    assert any("intervalo=420s" in m for m in mensagens)


# ==============================================================================
# Critério 5: SIGINT/SIGTERM durante o loop → para de agendar e sai sem
# traceback não tratado. Sinal REAL entregue ao próprio processo enquanto o
# handler do command está instalado (rede de segurança: se o handler não foi
# instalado, o teste falha LIMPA em vez de matar o pytest).
# ==============================================================================


def _dispara_sinal_e_devolve(nome_sinal, chamadas, registro):
    # mock chama side_effect com os MESMOS argumentos da chamada real (nenhum);
    # o registro devolvido vem da closure (construída antes do loop)
    def _lado():
        chamadas.append(1)
        handler_atual = signal.getsignal(nome_sinal)
        if handler_atual in (signal.SIG_DFL, None):
            raise AssertionError(
                f"command não instalou handler de {nome_sinal} antes do loop"
            )
        os.kill(os.getpid(), nome_sinal)
        return registro

    return _lado


@pytest.mark.django_db
def test_sigterm_durante_o_loop_para_de_agendar_graciosamente(caplog):
    chamadas: list[int] = []
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        with patch(
            _PATCH_TARGET,
            side_effect=_dispara_sinal_e_devolve(
                signal.SIGTERM, chamadas, _registro(id=101)
            ),
        ) as executar:
            # --intervalo-segundos 1: com a implementação correta o sinal
            # interrompe a espera antes de dormir; em modo de falha evita o
            # sleep REAL de 900s travar a suíte
            call_command("agendar_ingestao", "--intervalo-segundos", "1", "--rodadas", "2")

    assert executar.call_count == 1  # nenhuma nova rodada agendada
    mensagens = _logs_do_agendador(caplog)
    assert any("Sinal SIGTERM recebido — encerrando após a rodada atual" in m for m in mensagens)
    assert any("Agendador encerrado por SIGTERM (rodadas executadas=1)" in m for m in mensagens)


@pytest.mark.django_db
def test_sigint_durante_o_loop_para_de_agendar_graciosamente(caplog):
    chamadas: list[int] = []
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        with patch(
            _PATCH_TARGET,
            side_effect=_dispara_sinal_e_devolve(
                signal.SIGINT, chamadas, _registro(id=102)
            ),
        ) as executar:
            call_command("agendar_ingestao", "--intervalo-segundos", "1", "--rodadas", "2")

    assert executar.call_count == 1
    mensagens = _logs_do_agendador(caplog)
    assert any("Sinal SIGINT recebido — encerrando após a rodada atual" in m for m in mensagens)
    assert any("Agendador encerrado por SIGINT (rodadas executadas=1)" in m for m in mensagens)


# ==============================================================================
# Restrição do contrato: close_old_connections() no início E fim de cada rodada
# (mesmo padrão de _executar_ingestao_em_background em robos_views.py).
# ==============================================================================


# ==============================================================================
# Critérios 1, 4 e 5 em PROCESSO REAL (subprocesso).
#
# Os testes in-process acima provam a LÓGICA do loop, mas o contrato fala em
# "o processo sai com código 0" (critério 1) e "sai sem traceback não tratado"
# (critério 5) — propriedades do PROCESSO, não de `handle()`. Aqui o
# `manage.py agendar_ingestao` roda de verdade; o `executar_ingestao` é
# substituído DENTRO do processo filho (o command faz
# `from ... import executar_ingestao`, então o patch é no módulo do command),
# e código de saída / stderr / latência são observados de fora.
# ==============================================================================

# Roda em processo separado; imprime marcadores estruturados em stdout.
# MODO=normal      : --rodadas 1, imprime "RODADA=<n>" a cada ingestão
# MODO=conta_sleep : registra cada time.sleep em SLEEP=<s> e retorna na hora
#                    (permite observar o intervalo default sem esperar 900s)
_FILHO = r'''
import os, sys, time
sys.path.insert(0, %(backend)r)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_test")
os.environ.setdefault(
    "DJANGO_SECRET_KEY", "test-only-secret-key-nao-usar-fora-da-suite-0123456789"
)
import django
django.setup()

from types import SimpleNamespace
import catalogo_noticias.management.commands.agendar_ingestao as cmd

MODO = os.environ["MODO_FILHO"]
PRONTO = os.environ["ARQUIVO_PRONTO"]
contador = [0]


def _registro():
    return SimpleNamespace(
        id=777,
        total_itens_ingeridos=3,
        total_grupos_formados=1,
        total_duplicatas_agrupadas=0,
        chamadas_summarization_provider=1,
        itens_por_fonte={"G1": 3},
        erros_por_fonte={},
    )


def _ingestao_fake(*_a, **_k):
    contador[0] += 1
    print("RODADA=%%d" %% contador[0], flush=True)
    return _registro()


cmd.executar_ingestao = _ingestao_fake

if MODO == "conta_sleep":
    class _Shim:
        """Substitui o modulo `time` do command (NAO o global) para nao dormir."""
        def __init__(self):
            self.total = 0.0
        def sleep(self, segundos):
            self.total += segundos
            print("SLEEP=%%s" %% segundos, flush=True)
    _shim = _Shim()
    cmd.time = _shim
    _orig_handle = cmd.Command.handle
    def handle(self, *a, **opcoes):
        _orig_handle(self, *a, **opcoes)
        print("TOTAL_SLEEP=%%s" %% _shim.total, flush=True)
    cmd.Command.handle = handle

# avisa o pai que o pipeline fake está pronto (o pai então manda o SIGTERM)
with open(PRONTO, "w") as fh:
    fh.write(str(os.getpid()))

cmd.Command().run_from_argv(sys.argv)
'''


def _filho(tmp_path, modo):
    """Escreve o script filho e devolve o comando pronto para executar."""
    script = tmp_path / f"filho_{modo}.py"
    script.write_text(_FILHO % {"backend": str(_BACKEND)}, encoding="utf-8")
    pronto = tmp_path / f"pronto_{modo}.txt"
    env = dict(os.environ, MODO_FILHO=modo, ARQUIVO_PRONTO=str(pronto))
    env["PYTHONPATH"] = str(_BACKEND)
    argv = [
        sys.executable,
        str(script),
        "agendar_ingestao",
        "--intervalo-segundos",
        "1",
        "--rodadas",
        "1",
    ]
    return argv, env, pronto


def test_rodada_unica_em_processo_real_sai_com_codigo_zero(tmp_path):
    """Critério 1 no processo real: 1 rodada, código de saída 0."""
    argv, env, _ = _filho(tmp_path, "normal")

    proc = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=120)

    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    assert "Traceback" not in proc.stderr
    assert proc.stdout.count("RODADA=1") == 1
    assert proc.stdout.count("RODADA=2") == 0
    assert "Agendador finalizado (1 rodada(s))." in proc.stdout


def test_sigterm_em_processo_real_encerra_sem_traceback_e_rapido(tmp_path):
    """Critério 5 no processo real: SIGTERM de fora -> sai 0, sem traceback.

    Roda com --rodadas 5 e intervalo alto (30s): sem o handler, o SIGTERM
    mataria o processo no meio (sem "finalizado") ou o SIGINT levantaria
    KeyboardInterrupt com traceback. Com o handler, o command para de agendar
    e sai — e a resposta é ~1s (sleep em fatias), não 30s.
    """
    script = tmp_path / "filho_sigterm.py"
    script.write_text(_FILHO % {"backend": str(_BACKEND)}, encoding="utf-8")
    pronto = tmp_path / "pronto_sigterm.txt"
    env = dict(os.environ, MODO_FILHO="normal", ARQUIVO_PRONTO=str(pronto))
    env["PYTHONPATH"] = str(_BACKEND)

    argv = [
        sys.executable,
        str(script),
        "agendar_ingestao",
        "--intervalo-segundos",
        "30",
        "--rodadas",
        "5",
    ]
    proc = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # espera o pipeline fake rodar 1x (o command entra no sleep de 30s)
    limite = time.monotonic() + 60
    while time.monotonic() < limite and not pronto.exists():
        if proc.poll() is not None:
            break
        time.sleep(0.05)
    assert pronto.exists(), f"filho nao sinalizou pronto (returncode={proc.poll()})"
    time.sleep(0.3)  # deixa o command entrar no sleep

    inicio = time.monotonic()
    proc.send_signal(signal.SIGTERM)
    stdout, stderr = proc.communicate(timeout=60)
    decorrido = time.monotonic() - inicio

    assert proc.returncode == 0, f"stdout={stdout!r} stderr={stderr!r}"
    assert "Traceback" not in stderr, stderr
    assert "KeyboardInterrupt" not in stderr
    # o command escreve as mensagens de ENCERRAMENTO via logging (stderr) e a
    # linha final via self.stdout.write (stdout) -> olhar o fluxo combinado
    saida = stdout + stderr
    assert "Agendador encerrado por SIGTERM (rodadas executadas=1)" in saida
    assert "Agendador finalizado (1 rodada(s))." in saida
    assert stdout.count("RODADA=") == 1  # nenhuma nova rodada agendada
    # resposta em ~1s (sleep em fatias de 1s), muito menos que os 30s do intervalo
    assert decorrido < 10, f"encerramento levou {decorrido:.1f}s (esperado <10s)"


def test_intervalo_default_em_processo_real_vem_da_setting(tmp_path):
    """Critério 4 no processo real: sem flags, dorme 15*60 = 900s.

    Usa MODO=conta_sleep para não esperar 900s: registra o que o command
    pediu para dormir. O valor esperado vem da SETTING REAL (não de um
    override) — se o default fosse hardcoded 900passaria por acaso, então
    o teste compara com settings.CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS.
    """
    script = tmp_path / "filho_conta.py"
    script.write_text(_FILHO % {"backend": str(_BACKEND)}, encoding="utf-8")
    pronto = tmp_path / "pronto_conta.txt"
    env = dict(os.environ, MODO_FILHO="conta_sleep", ARQUIVO_PRONTO=str(pronto))
    env["PYTHONPATH"] = str(_BACKEND)

    argv = [sys.executable, str(script), "agendar_ingestao", "--rodadas", "2"]
    proc = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=120)

    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    esperado = settings.CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS * 60
    # o command dorme o intervalo padrao entre as 2 rodadas
    assert f"TOTAL_SLEEP={float(esperado)}" in proc.stdout
    # e o banner registra o intervalo em segundos (logging -> stderr)
    assert f"intervalo={esperado}s" in (proc.stdout + proc.stderr)


# ==============================================================================
# Critério 9 (complemento): a Otimização NÃO pode alterar os VALORES de
# similaridade dos pares que sobrevivem ao pre-filtro — os grupos saem
# idênticos, mas isso por si só não prova que `_similaridade_ponderada` (e a
# API pública `calcular_similaridade_titulos`) continuam bit-idênticos. Estes
# testes comparam os floats diretamente contra a cópia ANTIGA.
# ==============================================================================


@pytest.mark.parametrize("seed", [11, 22, 33])
def test_similaridade_ponderada_e_identica_antiga_vs_nova(seed):
    """`_similaridade_ponderada` nova == antiga, bit a bit (float exato)."""
    itens = _itens_sinteticos(80, seed=seed)
    tokens_por_item = [
        {p for p in re.sub(r"[^\w\s]", " ", it.titulo.lower()).split() if p not in _ANTIGA_STOPWORDS_PT}
        for it in itens
    ]
    pesos = _antiga_pesos_por_frequencia_no_lote(tokens_por_item)

    comparados = 0
    for i, a in enumerate(tokens_por_item):
        for b in tokens_por_item[i + 1 :]:
            antigo = _antiga_similaridade_ponderada(a, b, pesos)
            novo = dedup_nova._similaridade_ponderada(a, b, pesos)
            # igualdade EXATA de float (bit a bit), não só approximate
            assert novo == antigo, f"divergiu no par ({i}) peso={novo!r} vs {antigo!r}"
            comparados += 1
    assert comparados > 100  # sanidade: o lote realmente exercitou a comparacao


def test_calcular_similaridade_titulos_publico_inalterado():
    """A API pública de similaridade devolve exatamente o valor de antes."""
    titulos = [
        "Prefeitura de Sao Paulo anuncia novo plano de seguranca publica",
        "Prefeitura de Sao Paulo anuncia novo plano de mobilidade urbana",
        "Presidente sanciona pacote fiscal",
        "Pacote fiscal e sancionado pelo presidente",
        "governo federal",
        "Grande incendio em cidade",
    ]
    for a in titulos:
        for b in titulos:
            pesos = {t: 0.15 for t in re.findall(r"\w+", (a + " " + b).lower())}
            antigo = _antiga_similaridade_ponderada(
                _antiga_tokens_titulo(a), _antiga_tokens_titulo(b), pesos
            )
            novo = dedup_nova.calcular_similaridade_titulos(a, b, pesos)
            assert novo == antigo, f"divergiu em ({a!r},{b!r}): {novo!r} vs {antigo!r}"


def test_agrupar_respeita_limiar_customizado_igual_antigo():
    """`_similaridade_ponderada`/`agrupar_itens_brutos` com limiar != 0.55
    também produzem grupos idênticos (o pre-filtro usa o limiar efetivo)."""
    itens = _itens_sinteticos(120, seed=99)
    for limiar in (0.4, 0.55, 0.7):
        ga = _antiga_agrupar_itens_brutos(list(itens), limiar_similaridade=limiar)
        gb = dedup_nova.agrupar_itens_brutos(list(itens), limiar_similaridade=limiar)
        assert _grupos_por_url(gb) == _grupos_por_url(ga), f"limiar={limiar}"


def test_close_old_connections_no_inicio_e_fim_de_cada_rodada(caplog):
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        with patch(_PATCH_TARGET, return_value=_registro()):
            with patch(
                "catalogo_noticias.management.commands.agendar_ingestao.close_old_connections"
            ) as fechar:
                call_command(
                    "agendar_ingestao", "--intervalo-segundos", "1", "--rodadas", "2"
                )

    # 2 chamadas por rodada (início + finally) × 2 rodadas
    assert fechar.call_count == 4


def test_intervalo_nao_positivo_rejeita_com_command_error():
    with pytest.raises(CommandError, match="deve ser positivo"):
        call_command("agendar_ingestao", "--intervalo-segundos", "0", "--rodadas", "1")
    with pytest.raises(CommandError, match="deve ser positivo"):
        call_command("agendar_ingestao", "--intervalo-segundos", "-5", "--rodadas", "1")


# ==============================================================================
# Remediação pós-review (Iteração 8) — Findings 1, 2, 3 e 8 do
# code-review-contract.md do run 20260924-2136-ingestao-noticias.
# ==============================================================================


def test_rodadas_negativo_rejeita_com_command_error():
    """Finding 8: simetria com `--intervalo-segundos` — negativo é erro de uso."""
    with pytest.raises(CommandError, match="não pode ser negativo"):
        call_command("agendar_ingestao", "--rodadas", "-1")
    with pytest.raises(CommandError, match="não pode ser negativo"):
        call_command("agendar_ingestao", "--intervalo-segundos", "1", "--rodadas", "-10")


def test_rodadas_zero_avisa_e_nao_executa_nada(caplog):
    """Finding 8: `--rodadas 0` não pode mais sair em silêncio.

    Antes: rodava zero rodadas e imprimia "Agendador finalizado (0 rodada(s))"
    como se o agendador tivesse rodado. Agora há um WARNING explícito no log.
    """
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        with patch(_PATCH_TARGET, return_value=_registro()) as executar:
            saida = StringIO()
            call_command("agendar_ingestao", "--rodadas", "0", stdout=saida)

    assert executar.call_count == 0
    mensagens = _logs_do_agendador(caplog)
    assert any("--rodadas 0: nenhuma rodada será executada" in m for m in mensagens)
    # o "0 rodada(s)" continua (é verdade), mas accompanied do aviso explícito
    assert "Agendador finalizado (0 rodada(s))." in saida.getvalue()


@pytest.mark.django_db
def test_falhas_consecutivas_geram_alerta_em_error(caplog):
    """Finding 2: a partir de N falhas SEGUIDAS o log sobe para ERROR.

    É o que transforma "ingestão parada e ninguém sabe" em falha visível. O
    isolamento de falha NÃO muda: as 4 rodadas rodam.
    """
    from catalogo_noticias.management.commands.agendar_ingestao import (
        FALHAS_CONSECUTIVAS_PARA_ALERTAR,
    )

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        with patch(
            _PATCH_TARGET,
            side_effect=[RuntimeError("banco travado")] * 3 + [_registro(id=555)],
        ) as executar:
            call_command("agendar_ingestao", "--intervalo-segundos", "1", "--rodadas", "4")

    # isolamento de falha preservado: as 4 rodadas executaram
    assert executar.call_count == 4

    alertas = [
        r
        for r in caplog.records
        if r.name == _LOGGER
        and r.levelno == logging.ERROR
        and "rodadas consecutivas falharam" in r.getMessage()
    ]
    # alerta na 3ª falha (limiar) e só nela — a 4ª rodada teve sucesso
    assert len(alertas) == 1
    texto = alertas[0].getMessage()
    assert f"{FALHAS_CONSECUTIVAS_PARA_ALERTAR} rodadas consecutivas falharam" in texto
    assert "INGESTÃO ESTÁ PARADA" in texto
    # o alerta tem nível ERROR (a falha isolada já é ERROR; o que não existia
    # era a mensagem dizendo que a ingestão parou de fato, não foi um episode)
    assert alertas[0].levelno == logging.ERROR


@pytest.mark.django_db
def test_contador_de_falhas_reseta_apos_rodada_com_sucesso(caplog):
    """Finding 2: 2 falhas -> 1 sucesso -> 2 falhas = NUNCA chega ao alerta.

    Sem o reset, uma ingestão que se recupera voltaria a gritar "ingestão
    parada" — o alerta deixaria de ser um sinal confiável.
    """
    from catalogo_noticias.management.commands.agendar_ingestao import (
        FALHAS_CONSECUTIVAS_PARA_ALERTAR,
    )

    # F F S F F: com o reset, o pior trecho é de 2 falhas seguidas (< limiar)
    assert FALHAS_CONSECUTIVAS_PARA_ALERTAR == 3  # o cenário acima depende disso
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        with patch(
            _PATCH_TARGET,
            side_effect=[RuntimeError("x"), RuntimeError("x"), _registro(id=556),
                         RuntimeError("x"), RuntimeError("x")],
        ) as executar:
            call_command("agendar_ingestao", "--intervalo-segundos", "1", "--rodadas", "5")

    assert executar.call_count == 5
    alertas = [
        r
        for r in caplog.records
        if r.name == _LOGGER
        and r.levelno == logging.ERROR
        and "rodadas consecutivas falharam" in r.getMessage()
    ]
    assert alertas == [], "o contador de falhas não foi zerado após a rodada com sucesso"
    assert any("contador de falhas consecutivas zerado" in m for m in _logs_do_agendador(caplog))


@pytest.mark.django_db
def test_falha_no_log_de_sucesso_nao_mata_o_loop(caplog):
    """Finding 3: a garantia 'nunca mata o processo' cobre a RODADA INTEIRA.

    Antes o log de sucesso vivia no bloco `else` (fora do `except`), então um
    erro ao ler `registro.id` escapava do `while` e matava o processo — o
    agendador, iniciado por nohup sem supervisor, parava em silêncio.
    Aqui `executar_ingestao` devolve um objeto SEM os campos esperados.
    """
    registro_sem_campos = SimpleNamespace()  # sem .id / .total_itens_ingeridos

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        with patch(
            _PATCH_TARGET, side_effect=[registro_sem_campos, _registro(id=557)]
        ) as executar:
            call_command("agendar_ingestao", "--intervalo-segundos", "1", "--rodadas", "2")

    assert executar.call_count == 2  # a 2ª rodada rodou -> o processo NÃO morreu
    mensagens = _logs_do_agendador(caplog)
    assert any("Rodada 1/2: falhou" in m for m in mensagens)
    assert any("Rodada 2/2 concluída (registro_id=557" in m for m in mensagens)
    # a exceção do log de sucesso aparece com traceback, no mesmo isolamento
    # de falha das demais (uma por rodada, e só uma)
    registros_com_traceback = [r for r in caplog.records if r.name == _LOGGER and r.exc_info]
    assert len(registros_com_traceback) == 1


# Finding 1(b): o 2º sinal escala. Precisa de PROCESSO REAL — a escalonamento usa
# os._exit(), que mataria o pytest se fosse testado in-process. O filho tem uma
# rodada ETERNA (modela o backlog que levou 7h54m na Iteração 3), então o 1º
# SIGTERM só pode marcar a parada: o processo tem de continuar vivo.
_FILHO_RODADA_ETORNA = r'''
import os, sys, time
sys.path.insert(0, %(backend)r)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_test")
os.environ.setdefault(
    "DJANGO_SECRET_KEY", "test-only-secret-key-nao-usar-fora-da-suite-0123456789"
)
import django
django.setup()

import catalogo_noticias.management.commands.agendar_ingestao as cmd

PRONTO = os.environ["ARQUIVO_PRONTO"]
DERROTA = os.environ["ARQUIVO_DERROTA"]


def _rodada_eterna(*_a, **_k):
    # avisa o pai só de dentro da rodada: o handler de sinal já está instalado
    # quando este arquivo aparece (o pai espera por ele antes de mandar sinal)
    if not os.path.exists(PRONTO):
        with open(PRONTO, "w") as fh:
            fh.write(str(os.getpid()))
    while not os.path.exists(DERROTA):
        time.sleep(0.05)
    raise RuntimeError("rodada abandonada (nao deveria chegar aqui)")


cmd.executar_ingestao = _rodada_eterna

cmd.Command().run_from_argv(sys.argv)
'''


def test_segundo_sinal_escala_e_encerra_na_hora(tmp_path):
    """Finding 1(b): 1º sinal = gracioso, 2º sinal = saída imediata e previsível.

    Antes o segundo sinal era engolido e só `kill -9` encerrava — o `--stop`
    ficava sem desfecho definido (e era justamente esse limbo que mantinha a
    janela de dupla instância).
    """
    script = tmp_path / "filho_escalona.py"
    script.write_text(_FILHO_RODADA_ETORNA % {"backend": str(_BACKEND)}, encoding="utf-8")
    pronto = tmp_path / "pronto_escalona.txt"
    derrota = tmp_path / "DERROTA"  # nunca é criado: a rodada é eterna
    env = dict(os.environ, ARQUIVO_PRONTO=str(pronto), ARQUIVO_DERROTA=str(derrota))
    env["PYTHONPATH"] = str(_BACKEND)
    argv = [sys.executable, str(script), "agendar_ingestao", "--intervalo-segundos", "30"]

    proc = subprocess.Popen(
        argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        limite = time.monotonic() + 60
        while time.monotonic() < limite and not pronto.exists():
            assert proc.poll() is None, f"filho morreu (returncode={proc.poll()})"
            time.sleep(0.05)
        assert pronto.exists(), "filho não entrou na rodada"

        # 1º SIGTERM: só marca a parada — a rodada em curso TERMINA (não morre)
        proc.send_signal(signal.SIGTERM)
        time.sleep(2.0)
        assert proc.poll() is None, "1º sinal não pode matar o processo no meio da rodada"

        # 2º SIGTERM: escalonamento, sai na hora
        inicio = time.monotonic()
        proc.send_signal(signal.SIGTERM)
        stdout, stderr = proc.communicate(timeout=30)
        decorrido = time.monotonic() - inicio
    finally:
        if proc.poll() is None:  # pragma: no cover - só em falha do teste
            proc.kill()
            proc.communicate(timeout=30)

    assert "Sinal SIGTERM recebido — encerrando após a rodada atual" in stderr
    assert "Segundo sinal SIGTERM — encerrando IMEDIATAMENTE" in stderr
    assert "Traceback" not in stderr, stderr
    # código de saída = 128 + sinal (convenção de shell para "morto por sinal")
    assert proc.returncode == 128 + int(signal.SIGTERM), (
        f"returncode={proc.returncode} stdout={stdout!r} stderr={stderr!r}"
    )
    assert decorrido < 10, f"escalonamento levou {decorrido:.1f}s (esperado <10s)"


# ==============================================================================
# Critério 9: equivalência da otimização da deduplicação — implementação ANTIGA
# (copiada verbatim do HEAD) vs NOVA (pre-filtro por upper bound + cache LRU).
# Os grupos de saída devem ser IDÊNTICOS (mesma composição E mesma ordem).
# ==============================================================================

_ANTIGA_STOPWORDS_PT = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "um",
    "uma", "para", "com", "por", "que", "no", "na", "nos", "nas", "ao",
    "aos", "se", "sobre",
}
_ANTIGA_LIMIAR_FUZZY_TOKEN = 0.82
_ANTIGA_PESO_TOKEN_GENERICO_DO_LOTE = 0.15
_ANTIGA_DF_MINIMO_GENERICO = 4
_ANTIGA_TAMANHO_MINIMO_LOTE_PARA_PESO = 6
_ANTIGA_PESO_TOKEN_CONECTOR_CURADO = 0.15
_ANTIGA_CONECTORES_JORNALISTICOS_COMUNS_PT = {
    "anuncia", "anuncio", "anuncios", "anunciam", "anunciou", "anunciando",
    "anunciado", "anunciada", "anunciados", "anunciadas",
    "lanca", "lança", "lancam", "lançam", "lancou", "lançou", "lancamento",
    "lançamento",
    "divulga", "divulgam", "divulgou", "divulgacao", "divulgação",
    "apresenta", "apresentam", "apresentou", "apresentacao", "apresentação",
    "plano", "planos", "pacote", "pacotes", "medida", "medidas",
    "programa", "programas", "projeto", "projetos", "proposta", "propostas",
    "governo", "governamental", "prefeitura",
    "policia", "polícia", "policial", "policiais",
    "investiga", "investigam", "investigou", "investigacao", "investigação",
    "novo", "nova", "novos", "novas",
}


def _antiga_tokens_titulo(titulo: str) -> set[str]:
    titulo = titulo.lower()
    titulo = re.sub(r"[^\w\s]", " ", titulo)
    return {p for p in titulo.split() if p not in _ANTIGA_STOPWORDS_PT}


def _antiga_pesos_por_frequencia_no_lote(lista_de_tokens: list[set[str]]) -> dict[str, float]:
    pesos: dict[str, float] = {}

    n = len(lista_de_tokens)
    if n > 0:
        frequencia_no_lote: dict[str, int] = {}
        for tokens in lista_de_tokens:
            for token in tokens:
                frequencia_no_lote[token] = frequencia_no_lote.get(token, 0) + 1

        limiar_generico = _ANTIGA_DF_MINIMO_GENERICO if n >= _ANTIGA_TAMANHO_MINIMO_LOTE_PARA_PESO else n + 1
        pesos = {
            token: (_ANTIGA_PESO_TOKEN_GENERICO_DO_LOTE if freq >= limiar_generico else 1.0)
            for token, freq in frequencia_no_lote.items()
        }

    for tokens in lista_de_tokens:
        for token in tokens:
            if token in _ANTIGA_CONECTORES_JORNALISTICOS_COMUNS_PT:
                pesos[token] = min(pesos.get(token, 1.0), _ANTIGA_PESO_TOKEN_CONECTOR_CURADO)

    return pesos


_ANTIGA_CACHE_FUZZY_RATIO: dict[tuple[str, str], float] = {}


def _antiga_ratio_cached(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if abs(len(a) - len(b)) > 4 and min(len(a), len(b)) <= 4:
        return 0.0
    key = (a, b) if a < b else (b, a)
    v = _ANTIGA_CACHE_FUZZY_RATIO.get(key)
    if v is not None:
        return v
    v = SequenceMatcher(None, a, b).ratio()
    if len(_ANTIGA_CACHE_FUZZY_RATIO) > 8000:
        _ANTIGA_CACHE_FUZZY_RATIO.clear()
    _ANTIGA_CACHE_FUZZY_RATIO[key] = v
    return v


def _antiga_tokens_fuzzy_pareados(tokens_a: set[str], tokens_b: set[str]) -> list[tuple[str, str]]:
    comuns = tokens_a & tokens_b
    pares = [(token, token) for token in comuns]

    restantes_a = tokens_a - comuns
    restantes_b = set(tokens_b - comuns)
    for token_a in restantes_a:
        melhor_par = None
        melhor_score = 0.0
        for token_b in restantes_b:
            score = _antiga_ratio_cached(token_a, token_b)
            if score > melhor_score:
                melhor_score = score
                melhor_par = token_b
                if score >= 0.99:
                    break
        if melhor_par is not None and melhor_score >= _ANTIGA_LIMIAR_FUZZY_TOKEN:
            pares.append((token_a, melhor_par))
            restantes_b.discard(melhor_par)

    return pares


def _antiga_similaridade_ponderada(
    tokens_a: set[str], tokens_b: set[str], pesos_tokens: dict[str, float]
) -> float:
    if not tokens_a or not tokens_b:
        return 0.0

    pares = _antiga_tokens_fuzzy_pareados(tokens_a, tokens_b)
    peso_intersecao = sum(
        max(pesos_tokens.get(token_a, 1.0), pesos_tokens.get(token_b, 1.0)) for token_a, token_b in pares
    )
    peso_uniao = sum(pesos_tokens.get(token, 1.0) for token in (tokens_a | tokens_b))
    if peso_uniao <= 0:
        return 0.0
    return peso_intersecao / peso_uniao


def _antiga_agrupar_itens_brutos(
    itens: list[ItemBruto], limiar_similaridade: float = 0.55
) -> list[list[ItemBruto]]:
    tokens_por_item = [_antiga_tokens_titulo(item.titulo) for item in itens]
    pesos_tokens = _antiga_pesos_por_frequencia_no_lote(tokens_por_item)

    grupos_indices: list[list[int]] = []

    for indice_item, tokens_item in enumerate(tokens_por_item):
        melhor_grupo_indice = None
        melhor_score = 0.0
        for grupo_indice, indices_do_grupo in enumerate(grupos_indices):
            score = max(
                _antiga_similaridade_ponderada(tokens_item, tokens_por_item[outro_indice], pesos_tokens)
                for outro_indice in indices_do_grupo
            )
            if score > melhor_score:
                melhor_score = score
                melhor_grupo_indice = grupo_indice

        if melhor_grupo_indice is not None and melhor_score >= limiar_similaridade:
            grupos_indices[melhor_grupo_indice].append(indice_item)
        else:
            grupos_indices.append([indice_item])

    return [[itens[indice] for indice in indices_do_grupo] for indices_do_grupo in grupos_indices]


def _grupos_por_url(grupos: list[list[ItemBruto]]) -> list[list[str]]:
    return [[item.url_fonte_original for item in grupo] for grupo in grupos]


def _itens_sinteticos(total: int, seed: int) -> list[ItemBruto]:
    """
    Lote sintético jornalístico variado: duplicatas exatas (outra fonte),
    near-duplicatas (pequena variação de redação), mesmo padrão sintático com
    fatos DIFERENTES (falso-positivo em potencial) e itens únicos — os quatro
    tipos exercitam exatamente os caminhos do pre-filtro por upper bound
    (pares na faixa perto do limiar 0.55 não podem ser podados indevidamente).
    """
    rng = random.Random(seed)
    orgaos = [
        "Prefeitura de Sao Paulo",
        "Governo Federal",
        "Ministerio da Saude",
        "Tribunal de Contas",
        "Camara dos Deputados",
        "Prefeitura do Rio",
        "Governo de Minas",
    ]
    verbos = ["anuncia", "investiga", "lanca", "aprova", "amplia", "corta", "divulga"]
    assuntos = [
        "seguranca publica",
        "mobilidade urbana",
        "educacao basica",
        "saude publica",
        "reforma administrativa",
        "transporte publico",
        "habitação popular",
        "obra viaria",
    ]
    qualificadores = ["novo", "emergencial", "historico", "inedito", "ampliado"]

    itens: list[ItemBruto] = []

    def _append(titulo: str, indice: int) -> None:
        itens.append(
            ItemBruto(
                titulo=titulo,
                url_fonte_original=f"https://equivalencia.test/item/{seed}/{indice}",
                nome_fonte=f"Fonte {indice % 7}",
                conteudo_bruto=f"Texto bruto original do item {indice}.",
            )
        )

    indice = 0
    palavras_especificas = [
        "orçamento", "emenda", "licitação", "convênio", "delegacia", "hospital",
        "escola", "rodovia", "ponte", "terminal", "estádio", "parque", "porto",
        "aeroporto", "metrô", "ônibus", "ciclovia", "creche", "abrigo", "defesa",
        "guarda", "fiscal", "tribunal", "câmara", "senado", "ministério",
        "secretaria", "autarquia", "fundação", "instituto", "universidade",
        "pesquisa", "tecnologia", "energia", "saneamento", "drenagem", "pavimentação",
        "iluminação", "vigilância", "epidemia", "vacina", "moradia", "reassentamento",
        "regularização", "incentivo", "subsídio", "crédito", "financiamento",
    ]
    while len(itens) < total:
        indice += 1
        orgao = rng.choice(orgaos)
        verbo = rng.choice(verbos)
        assunto = rng.choice(assuntos)
        qualificador = rng.choice(qualificadores)
        valor = rng.randint(100, 9999)
        # palavras específicas quase únicas por manchete (típico de manchetes
        # reais): pares não relacionados ficam com bound MUITO abaixo do
        # limiar — exercita a poda do pre-filtro em massa (critério 9)
        especificas = rng.sample(palavras_especificas, 3)
        tipo = rng.random()

        if itens and tipo < 0.20:
            # duplicata exata em outra fonte
            original = itens[rng.randrange(len(itens))]
            _append(original.titulo, indice)
        elif itens and tipo < 0.40:
            # near-duplicata: mesma manchete com pequena variação de redação
            original = itens[rng.randrange(len(itens))]
            variacao = original.titulo.replace("anuncia", "anunciou").replace(" novo ", " novos ")
            if variacao == original.titulo:
                variacao = original.titulo + " nesta quinta"
            _append(variacao, indice)
        elif tipo < 0.55:
            # mesmo padrão sintático, fato DIFERENTE (o clássico falso-positivo
            # do Finding 2: NÃO deve agrupar)
            outro_assunto = rng.choice([a for a in assuntos if a != assunto])
            _append(
                f"{orgao} {verbo} {qualificador} pacote de {outro_assunto} no valor de {valor} sobre {especificas[0]} e {especificas[1]}",
                indice,
            )
        else:
            _append(
                f"{orgao} {verbo} {qualificador} pacote de {assunto} no valor de {valor} sobre {especificas[0]} e {especificas[1]} e {especificas[2]}",
                indice,
            )

    return itens


def _assert_lote_exercita_agrupamento(grupos: list[list[ItemBruto]]) -> None:
    # sanidade: o lote tem duplicatas de verdade (não é tudo singleton)
    assert len(grupos) > 1
    assert any(len(grupo) >= 2 for grupo in grupos)


def test_equivalencia_antiga_vs_nova_lote_150_itens():
    itens = _itens_sinteticos(150, seed=20260924)

    grupos_antigos = _antiga_agrupar_itens_brutos(list(itens))
    grupos_novos = dedup_nova.agrupar_itens_brutos(list(itens))

    _assert_lote_exercita_agrupamento(grupos_novos)
    assert _grupos_por_url(grupos_novos) == _grupos_por_url(grupos_antigos)


def test_equivalencia_antiga_vs_nova_lote_300_itens():
    itens = _itens_sinteticos(300, seed=20260925)

    grupos_antigos = _antiga_agrupar_itens_brutos(list(itens))
    grupos_novos = dedup_nova.agrupar_itens_brutos(list(itens))

    _assert_lote_exercita_agrupamento(grupos_novos)
    assert _grupos_por_url(grupos_novos) == _grupos_por_url(grupos_antigos)


@pytest.mark.parametrize("seed,tamanho", [(1, 40), (2, 80), (3, 120), (42, 60)])
def test_equivalencia_antiga_vs_nova_lotes_aleatorios_seed_fixa(seed, tamanho):
    itens = _itens_sinteticos(tamanho, seed=seed)

    grupos_antigos = _antiga_agrupar_itens_brutos(list(itens))
    grupos_novos = dedup_nova.agrupar_itens_brutos(list(itens))

    _assert_lote_exercita_agrupamento(grupos_novos)
    assert _grupos_por_url(grupos_novos) == _grupos_por_url(grupos_antigos)


def test_equivalencia_antiga_vs_nova_lote_sem_itens_e_um_item():
    for itens in ([], [_itens_sinteticos(1, seed=7)[0]]):
        grupos_antigos = _antiga_agrupar_itens_brutos(list(itens))
        grupos_novos = dedup_nova.agrupar_itens_brutos(list(itens))
        assert _grupos_por_url(grupos_novos) == _grupos_por_url(grupos_antigos)
