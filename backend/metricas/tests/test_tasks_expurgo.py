"""Expurgo de analytics: retenção, idempotência, lotes, agregados e auditoria.

Critério 24 (implementation-contract.md): eventos brutos E agregados
anteriores à janela de 12 meses são removidos de forma idempotente, em lotes,
e o job é auditável sem vazar dado pessoal.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from config.metrics import METRICS
from feed.models import EventoBusca, InteracaoNoticia
from metricas.models import EventoSite
from metricas.tasks import expurar_analytics

pytestmark = pytest.mark.django_db

EMAIL = "leitor.exemplo@dominio.invalid"


def _criar_eventos(idade_dias: int, quantidade: int = 3) -> None:
    """Eventos de analytics com a idade desejada (`auto_now_add` é ignorado)."""

    antigo = timezone.now() - timedelta(days=idade_dias)
    criados: dict[str, list[int]] = {"site": [], "busca": [], "interacao": []}
    for indice in range(quantidade):
        evento = EventoSite.objects.create(
            tipo=EventoSite.TIPO_PAGE_VIEW,
            path=f"/politica/{indice}",
            sessao=f"sessao-{indice}",
            extra={"contato": EMAIL},
        )
        criados["site"].append(evento.pk)
        busca = EventoBusca.objects.create(
            query=f"termo pessoal {indice}", query_normalizada=f"termo {indice}"
        )
        criados["busca"].append(busca.pk)
        interacao = InteracaoNoticia.objects.create(
            tipo=InteracaoNoticia.TIPO_VIEW, entry_tipo="item", categoria="politica"
        )
        criados["interacao"].append(interacao.pk)
    _forcar_idade(EventoSite, criados["site"], antigo)
    _forcar_idade(EventoBusca, criados["busca"], antigo)
    _forcar_idade(InteracaoNoticia, criados["interacao"], antigo)


def _forcar_idade(model, pks: list[int], momento) -> None:
    """Age apenas as linhas recém-criadas (nunca `update()` global, que mudaria
    também os eventos recentes que o teste precisa preservar)."""

    model.objects.filter(pk__in=pks).update(criado_em=momento)


# ---------------------------------------------------------------------------
# Retenção
# ---------------------------------------------------------------------------


def test_expurga_eventos_brutos_anteriores_a_janela():
    _criar_eventos(idade_dias=400, quantidade=5)
    _criar_eventos(idade_dias=10, quantidade=2)

    resultado = expurar_analytics.run()

    assert EventoSite.objects.count() == 2
    assert EventoBusca.objects.count() == 2
    assert InteracaoNoticia.objects.count() == 2
    assert resultado["removidos"] == {
        "metricas.EventoSite": 5,
        "feed.InteracaoNoticia": 5,
        "feed.EventoBusca": 5,
    }
    assert resultado["total_removido"] == 15


def test_retention_days_de_12_meses_padrao_e_configuravel():
    _criar_eventos(idade_dias=364, quantidade=1)
    _criar_eventos(idade_dias=366, quantidade=1)

    with override_settings(ANALYTICS_RETENTION_DAYS=365):
        expurar_analytics.run()

    # Só o que passou de 365 dias sai; o evento de 364 dias é preservado.
    assert EventoSite.objects.count() == 1

    with override_settings(ANALYTICS_RETENTION_DAYS=30):
        expurar_analytics.run()

    assert EventoSite.objects.count() == 0


def test_idempotente_segunda_execucao_nao_altera_nada():
    _criar_eventos(idade_dias=500, quantidade=4)
    expurar_analytics.run()

    segunda = expurar_analytics.run()

    assert segunda["total_removido"] == 0
    assert segunda["removidos"] == {
        "metricas.EventoSite": 0,
        "feed.InteracaoNoticia": 0,
        "feed.EventoBusca": 0,
    }


def test_processa_em_lotes_e_registra_a_quantidade(caplog):
    caplog.set_level(logging.INFO, logger="metricas.tasks")
    _criar_eventos(idade_dias=500, quantidade=7)

    resultado = expurar_analytics.run(lote=2)

    assert resultado["lote"] == 2
    # 7 linhas com lote 2 => 4 lotes (2+2+2+1) e o job parou ao esvaziar.
    assert resultado["lotes"]["metricas.EventoSite"] == 4
    assert resultado["removidos"]["metricas.EventoSite"] == 7
    assert "expurgo de analytics concluido" in caplog.text


def test_lote_invalido_e_ignorado_sem_quebrar():
    _criar_eventos(idade_dias=500, quantidade=2)

    resultado = expurar_analytics.run(lote=0)

    assert resultado["lote"] >= 1
    assert resultado["total_removido"] == 6


# ---------------------------------------------------------------------------
# Agregados
# ---------------------------------------------------------------------------


def test_invalida_o_agregado_cache_derivado_dos_eventos(monkeypatch):
    """Os agregados deste projeto são calculados na leitura, mas o snapshot
    em cache (`populares`) sobrevive ao expurgo: sem invalidação, a UI
    continuaria servindo um agregado feito sobre eventos já removidos."""

    _criar_eventos(idade_dias=500, quantidade=2)
    cache.set("feed:autocomplete:v2:populares", [{"query_normalizada": "termo", "total": 2}])
    chamadas = []
    monkeypatch.setattr(
        "feed.busca.invalidar_cache_autocomplete", lambda: chamadas.append(1)
    )

    expurar_analytics.run()

    assert chamadas == [1]
    assert cache.get("feed:autocomplete:v2:populares") is None


# ---------------------------------------------------------------------------
# Auditoria sem dado pessoal
# ---------------------------------------------------------------------------


def test_log_tecnico_e_auditavel_e_nao_carrega_dado_pessoal(caplog):
    caplog.set_level(logging.INFO, logger="metricas.tasks")
    _criar_eventos(idade_dias=500, quantidade=2)

    expurar_analytics.run()

    registro = next(r for r in caplog.records if "expurgo" in r.getMessage())
    mensagem = registro.getMessage()
    dados = json.dumps({"msg": mensagem, "args": [str(a) for a in registro.args]})
    # Auditável: contagem, janela, corte e duração.
    assert "total_removido=6" in mensagem
    assert "retencao_dias=365" in mensagem
    assert "corte=" in mensagem
    assert "duracao_s=" in mensagem
    # Sem dado pessoal: nem query buscada, nem path, nem sessão, nem e-mail.
    for pii in (EMAIL, "termo pessoal", "/politica/0", "sessao-0"):
        assert pii not in dados


def test_registra_metricas_tecnicas_do_expurgo():
    METRICS.clear()
    _criar_eventos(idade_dias=500, quantidade=3)

    expurar_analytics.run()

    exposicao = METRICS.render_prometheus()
    assert "portal_analytics_purge_deleted_total" in exposicao
    assert "portal_analytics_purge_duration_seconds_count" in exposicao


def test_contagem_de_linhas_e_valor_e_nao_rotulo():
    """Achado MINOR-5: com `rows=<contagem>` como rótulo, cada contagem distinta
    criava uma série nova e o alerta por `rows` não agregava nada. Aqui a
    contagem é o valor do contador e a série é só por modelo."""

    METRICS.clear()
    _criar_eventos(idade_dias=500, quantidade=3)
    expurar_analytics.run()
    primeira = METRICS.render_prometheus()
    METRICS.clear()

    # Segunda execução: 0 linhas (idempotente).
    expurar_analytics.run()
    segunda = METRICS.render_prometheus()

    assert 'rows=' not in primeira
    assert 'portal_analytics_purge_deleted_total{model="metricas.EventoSite"} 3' in primeira
    assert 'portal_analytics_purge_deleted_total{model="metricas.EventoSite"} 0' in segunda
    # Uma série por modelo, não uma por contagem.
    series = [linha for linha in primeira.splitlines() if linha.startswith("portal_analytics_purge_deleted_total{")]
    assert len(series) == 3


def test_contagem_acumula_entre_execucoes():
    METRICS.clear()
    _criar_eventos(idade_dias=500, quantidade=3)
    expurar_analytics.run()
    _criar_eventos(idade_dias=500, quantidade=2)
    expurar_analytics.run()

    # Contador cumulativo: 3 + 2 na MESMA série (com `rows=` seriam duas séries
    # de valor 1, e o alerta por `rows` não agregaria nada).
    assert 'portal_analytics_purge_deleted_total{model="metricas.EventoSite"} 5' in METRICS.render_prometheus()


def test_task_esta_registrada_no_app_celery():
    from config.celery import app

    app.loader.import_default_modules()

    assert expurar_analytics.name == "metricas.tasks.expurar_analytics"
    assert "metricas.tasks.expurar_analytics" in app.tasks
