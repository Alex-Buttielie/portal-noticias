"""
Suite formal do `tester` (escrita pelo executor durante a implementação,
como autovalidação) para `implementation-contract.md`, run
20260903-1211-teto-gasto-diario-llm — cobre os 7 critérios de aceite
técnicos relacionados ao teto de gasto diário do `SummarizationProvider`:

- AC-1/AC-2/AC-3: enforcement do teto em `services/ingestao.py::executar_ingestao`
  (classe `TestEnforcementDoTetoEmExecutarIngestao` abaixo).
- AC-4: configurabilidade via `override_settings`
  (`TestAC4TetoConfiguravelSemAlterarCodigo`).
- AC-6: fail-open de `orcamento.gasto_llm_hoje_usd()`
  (`TestGastoLlmHojeUsd::test_falha_ao_consultar_banco_e_fail_open...`,
  `TestFailOpenPropagaParaExecutarIngestao`).

`test_summarization_provider.py` cobre AC-5 (cálculo de `custo_estimado_usd`);
`metricas/tests/` cobre AC-7 (exposição via `painel()`).

Nenhum teste faz chamada de rede real: `SummarizationProvider` é sempre um
dublê controlável (`ProviderControlavel` abaixo).
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest
from django.test import override_settings

from catalogo_noticias.models import NewsItem, RegistroExecucaoIngestao
from catalogo_noticias.providers.news_source import ItemBruto, NewsSourceProvider
from catalogo_noticias.providers.summarization import ResultadoResumo, SummarizationProvider
from catalogo_noticias.services import orcamento
from catalogo_noticias.services.ingestao import executar_ingestao

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Dublês
# ---------------------------------------------------------------------------


class FonteDeTeste(NewsSourceProvider):
    def __init__(self, nome_fonte, itens=None):
        self.nome_fonte = nome_fonte
        self._itens = itens or []

    def buscar_itens(self):
        return self._itens


def _item(indice: int, nome_fonte: str = "G1") -> ItemBruto:
    return ItemBruto(
        titulo=f"Acontecimento completamente distinto numero {indice}",
        url_fonte_original=f"https://exemplo/{nome_fonte}/{indice}",
        nome_fonte=nome_fonte,
        conteudo_bruto=f"Conteudo bruto original numero {indice}.",
    )


class ProviderControlavel(SummarizationProvider):
    """
    Dublê que sobrescreve `resumir_e_classificar_em_lote` diretamente
    (nunca a implementação padrão item-a-item) para permitir controlar
    exatamente o custo/tokens devolvidos por CHAMADA EM LOTE e contar
    quantas vezes o provedor foi de fato chamado — o sinal central que os
    testes de enforcement do teto (AC-1/2/3) precisam observar.
    """

    def __init__(self, custo_por_chamada: float = 0.001, tokens_por_item: int = 10):
        self.custo_por_chamada = custo_por_chamada
        self.tokens_por_item = tokens_por_item
        self.chamadas_em_lote = 0
        self.tamanhos_dos_lotes: list[int] = []

    def resumir_e_classificar(self, itens_brutos):  # pragma: no cover - nao usado (lote sempre sobrescrito)
        raise NotImplementedError("ProviderControlavel so implementa resumir_e_classificar_em_lote")

    def resumir_e_classificar_em_lote(self, itens_brutos):
        self.chamadas_em_lote += 1
        self.tamanhos_dos_lotes.append(len(itens_brutos))
        custo_por_item = self.custo_por_chamada / len(itens_brutos)
        return [
            ResultadoResumo(
                resumo=f"Sintese autoral do item {item.url_fonte_original}",
                categoria="geral",
                urgente=False,
                tokens_utilizados=self.tokens_por_item,
                custo_estimado_usd=custo_por_item,
            )
            for item in itens_brutos
        ]


# ===========================================================================
# Módulo `orcamento.py` isolado (sem passar por `executar_ingestao`)
# ===========================================================================


class TestGastoLlmHojeUsd:
    def test_sem_nenhum_registro_devolve_zero(self):
        assert orcamento.gasto_llm_hoje_usd() == 0.0

    def test_soma_apenas_registros_com_custo_conhecido_ignorando_none(self):
        RegistroExecucaoIngestao.objects.create(custo_estimado_summarization_usd=1.5)
        RegistroExecucaoIngestao.objects.create(custo_estimado_summarization_usd=None)
        RegistroExecucaoIngestao.objects.create(custo_estimado_summarization_usd=0.75)

        assert orcamento.gasto_llm_hoje_usd() == pytest.approx(2.25)

    def test_ignora_registros_de_dias_anteriores(self):
        from datetime import timedelta

        from django.utils import timezone

        registro_ontem = RegistroExecucaoIngestao.objects.create(custo_estimado_summarization_usd=4.0)
        RegistroExecucaoIngestao.objects.filter(pk=registro_ontem.pk).update(
            executado_em=timezone.now() - timedelta(days=1)
        )
        RegistroExecucaoIngestao.objects.create(custo_estimado_summarization_usd=1.0)

        assert orcamento.gasto_llm_hoje_usd() == pytest.approx(1.0)

    def test_considera_fuso_local_e_nao_meia_noite_utc_ao_calcular_o_dia_corrente(self):
        """
        Regressao para o Finding 1 do code-review-contract.md (run
        20260903-1211-teto-gasto-diario-llm): `gasto_llm_hoje_usd()` deve
        usar meia-noite no fuso LOCAL do projeto (America/Sao_Paulo,
        UTC-3), nao meia-noite UTC, para delimitar o "dia corrente".

        Congelamos "agora" em 2026-09-03 23:00:00 UTC — que em horario de
        Sao Paulo e 2026-09-03 20:00:00, ainda "hoje" (03/09) pelo
        calendario local.

        Com o bug original (`agora.replace(hour=0...)` aplicado direto
        sobre `timezone.now()`, que e UTC), a janela valida seria
        [2026-09-03 00:00 UTC, 2026-09-04 00:00 UTC), que corresponde a
        [2026-09-02 21:00, 2026-09-03 21:00) em horario local — um
        registro de 22h de ONTEM (02/09) em Sao Paulo cairia DENTRO dessa
        janela UTC bugada (vira 2026-09-03 01:00 UTC) e seria contabilizado
        erroneamente como gasto de "hoje", junto com o registro real de
        hoje (00:30 de 03/09 em Sao Paulo) — total incorreto de 5.0.

        Com a correcao (janela em meia-noite local), o registro de ontem
        (22h de 02/09 em Sao Paulo) fica de fora da janela local
        [2026-09-03 00:00-03:00, 2026-09-04 00:00-03:00), e apenas o
        registro de hoje (00:30 de 03/09 em Sao Paulo) e somado — total
        correto de 1.0.
        """
        from datetime import datetime, timedelta, timezone as dt_timezone

        from django.utils import timezone

        fuso_sp = dt_timezone(timedelta(hours=-3))
        agora_utc = datetime(2026, 9, 3, 23, 0, 0, tzinfo=dt_timezone.utc)  # == 20:00 em SP, ainda "hoje" (03/09) localmente

        registro_ontem_a_noite_em_sp = RegistroExecucaoIngestao.objects.create(
            custo_estimado_summarization_usd=4.0
        )
        RegistroExecucaoIngestao.objects.filter(pk=registro_ontem_a_noite_em_sp.pk).update(
            executado_em=datetime(2026, 9, 2, 22, 0, 0, tzinfo=fuso_sp)  # 22h de ONTEM em SP
        )

        registro_hoje_de_madrugada_em_sp = RegistroExecucaoIngestao.objects.create(
            custo_estimado_summarization_usd=1.0
        )
        RegistroExecucaoIngestao.objects.filter(pk=registro_hoje_de_madrugada_em_sp.pk).update(
            executado_em=datetime(2026, 9, 3, 0, 30, 0, tzinfo=fuso_sp)  # 00:30 de HOJE em SP
        )

        with patch.object(timezone, "now", return_value=agora_utc):
            resultado = orcamento.gasto_llm_hoje_usd()

        # Com o bug (janela em meia-noite UTC), o resultado seria 5.0
        # (os dois registros cairiam na mesma janela UTC bugada).
        # Com a correcao (janela em meia-noite local), so o registro de
        # hoje (00:30 em SP) conta.
        assert resultado == pytest.approx(1.0)

    def test_falha_ao_consultar_banco_e_fail_open_devolve_zero_e_loga_warning(self, caplog):
        """AC-6: qualquer exceção dentro de `gasto_llm_hoje_usd()` é capturada, logada e vira `0.0`."""
        with patch.object(
            orcamento.RegistroExecucaoIngestao.objects,
            "filter",
            side_effect=RuntimeError("banco indisponivel (simulado)"),
        ):
            with caplog.at_level(logging.WARNING):
                resultado = orcamento.gasto_llm_hoje_usd()

        assert resultado == 0.0
        assert "gasto_llm_hoje_usd" in caplog.text


class TestTetoDiarioUsd:
    def test_le_da_setting_default(self):
        assert orcamento.teto_diario_usd() == 5.0

    @override_settings(CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD=12.5)
    def test_configuravel_via_override_settings(self):
        assert orcamento.teto_diario_usd() == 12.5


class TestTetoExcedido:
    @override_settings(CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD=5.0)
    def test_abaixo_do_teto_nao_excedido(self):
        assert orcamento.teto_excedido(4.99) is False

    @override_settings(CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD=5.0)
    def test_exatamente_no_teto_ja_conta_como_excedido(self):
        assert orcamento.teto_excedido(5.0) is True

    @override_settings(CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD=5.0)
    def test_acima_do_teto_excedido(self):
        assert orcamento.teto_excedido(5.01) is True


# ===========================================================================
# Enforcement em `executar_ingestao` (AC-1, AC-2, AC-3 do implementation-contract.md)
# ===========================================================================


class TestEnforcementDoTetoEmExecutarIngestao:
    def test_ac1_gasto_abaixo_do_teto_todos_os_lotes_chamam_o_provedor_normalmente(self):
        """
        AC-1: dado um dia sem RegistroExecucaoIngestao anterior e teto de
        $5.00 (default), itens cujo custo total estimado fica abaixo do
        teto -> todos os lotes chamam o provedor normalmente, nenhum item
        cai em fallback por causa do teto.
        """
        itens = [_item(i) for i in range(4)]
        fontes = [FonteDeTeste("G1", itens=itens)]
        provider = ProviderControlavel(custo_por_chamada=0.01)  # bem abaixo do teto default de 5.0

        executar_ingestao(fontes=fontes, summarization_provider=provider)

        assert provider.chamadas_em_lote == 1
        itens_persistidos = list(NewsItem.objects.all())
        assert len(itens_persistidos) == 4
        assert all(item.resumo_proprio != "" for item in itens_persistidos)
        registro = RegistroExecucaoIngestao.objects.get()
        assert registro.chamadas_summarization_provider == 1

    def test_ac2_gasto_ja_acumulado_igual_ao_teto_nenhuma_chamada_ao_provedor_e_feita(self):
        """
        AC-2: gasto já acumulado hoje (via RegistroExecucaoIngestao
        existente) igual ao teto configurado -> NENHUMA chamada ao provedor
        é feita, todos os itens novos entram como pendente (fallback).
        """
        RegistroExecucaoIngestao.objects.create(custo_estimado_summarization_usd=5.0)  # == teto default

        itens = [_item(i) for i in range(3)]
        fontes = [FonteDeTeste("UOL", itens=itens)]
        provider = ProviderControlavel()

        executar_ingestao(fontes=fontes, summarization_provider=provider)

        assert provider.chamadas_em_lote == 0
        itens_persistidos = list(NewsItem.objects.all())
        assert len(itens_persistidos) == 3
        assert all(item.status_revisao == NewsItem.STATUS_PENDENTE for item in itens_persistidos)
        assert all(item.resumo_proprio == "" for item in itens_persistidos)
        registro_novo = RegistroExecucaoIngestao.objects.exclude(custo_estimado_summarization_usd=5.0).get()
        assert registro_novo.chamadas_summarization_provider == 0

    @override_settings(CATALOGO_NOTICIAS_LLM_TAMANHO_LOTE=2, CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD=2.5)
    def test_ac3_teto_ultrapassado_no_meio_da_execucao_so_o_primeiro_lote_chama_o_provedor(self):
        """
        AC-3: 3 lotes necessários (tamanho de lote=2, 6 itens standalone);
        o 1º lote (custo 3.0) já cruza o teto (2.5) sozinho -> o 1º lote
        chama o provedor normalmente, o 2º e o 3º NÃO chamam (fallback).
        """
        itens = [_item(i) for i in range(6)]
        fontes = [FonteDeTeste("G1", itens=itens)]
        provider = ProviderControlavel(custo_por_chamada=3.0)

        executar_ingestao(fontes=fontes, summarization_provider=provider)

        assert provider.chamadas_em_lote == 1
        assert provider.tamanhos_dos_lotes == [2]

        registro = RegistroExecucaoIngestao.objects.get()
        assert registro.chamadas_summarization_provider == 1

        itens_persistidos = list(NewsItem.objects.all())
        assert len(itens_persistidos) == 6
        com_resumo = [item for item in itens_persistidos if item.resumo_proprio != ""]
        sem_resumo = [item for item in itens_persistidos if item.resumo_proprio == ""]
        assert len(com_resumo) == 2  # os 2 itens do 1º lote, que de fato chamou o provedor
        assert len(sem_resumo) == 4  # os itens do 2º e 3º lotes, pulados por teto
        assert all(item.status_revisao == NewsItem.STATUS_PENDENTE for item in sem_resumo)

    def test_lotes_anteriores_ao_teto_ser_ultrapassado_nao_tem_comportamento_alterado(self):
        """
        Reforço explícito do implementation-contract.md ("Não alterar o
        comportamento para lotes que ocorrem ANTES do teto ser
        ultrapassado"): o(s) item(ns) do(s) lote(s) que chamaram o provedor
        com sucesso têm resumo/categoria/urgente vindos DE FATO do
        provedor, não do fallback.
        """

        @override_settings(CATALOGO_NOTICIAS_LLM_TAMANHO_LOTE=2, CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD=2.5)
        def _corpo():
            itens = [_item(i) for i in range(4)]
            fontes = [FonteDeTeste("G1", itens=itens)]
            provider = ProviderControlavel(custo_por_chamada=3.0)

            executar_ingestao(fontes=fontes, summarization_provider=provider)

            primeiro_lote_urls = {item.url_fonte_original for item in itens[:2]}
            itens_do_primeiro_lote = NewsItem.objects.filter(url_fonte_original__in=primeiro_lote_urls)
            assert itens_do_primeiro_lote.count() == 2
            for item in itens_do_primeiro_lote:
                assert item.resumo_proprio.startswith("Sintese autoral do item")
                assert item.categoria == "geral"

        _corpo()


class TestAC4TetoConfiguravelSemAlterarCodigo:
    @override_settings(CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD=10.0)
    def test_teto_mais_alto_via_override_settings_faz_o_mesmo_cenario_do_ac2_nao_pular_o_provedor(self):
        """
        AC-4: o mesmo cenário do critério 2 (gasto acumulado hoje = $5.00),
        mas com o teto sobrescrito para $10.00 -> o comportamento muda:
        o provedor volta a ser chamado normalmente (comprova
        configurabilidade sem alteração de código).
        """
        RegistroExecucaoIngestao.objects.create(custo_estimado_summarization_usd=5.0)

        itens = [_item(i) for i in range(2)]
        fontes = [FonteDeTeste("G1", itens=itens)]
        provider = ProviderControlavel(custo_por_chamada=0.01)

        executar_ingestao(fontes=fontes, summarization_provider=provider)

        assert provider.chamadas_em_lote == 1
        itens_persistidos = list(NewsItem.objects.filter(nome_fonte="G1"))
        assert len(itens_persistidos) == 2
        assert all(item.resumo_proprio != "" for item in itens_persistidos)
        assert all(item.status_revisao != NewsItem.STATUS_PENDENTE for item in itens_persistidos)


class TestFailOpenPropagaParaExecutarIngestao:
    def test_falha_em_gasto_llm_hoje_usd_nao_derruba_a_ingestao_e_se_comporta_como_gasto_zero(self):
        """
        AC-6 de ponta a ponta: uma falha simulada DENTRO de
        `gasto_llm_hoje_usd()` (mock lançando exceção na consulta ao banco)
        não pode propagar como exceção de `executar_ingestao` — a execução
        se comporta como se o gasto acumulado do dia fosse `0.0`
        (fail-open), então o provedor continua sendo chamado normalmente
        (teto default de $5.00 não é considerado excedido com gasto 0.0).
        """
        itens = [_item(i) for i in range(2)]
        fontes = [FonteDeTeste("G1", itens=itens)]
        provider = ProviderControlavel(custo_por_chamada=0.01)

        with patch.object(
            orcamento.RegistroExecucaoIngestao.objects,
            "filter",
            side_effect=RuntimeError("banco indisponivel (simulado)"),
        ):
            registro = executar_ingestao(fontes=fontes, summarization_provider=provider)

        assert provider.chamadas_em_lote == 1
        assert registro.chamadas_summarization_provider == 1
        itens_persistidos = list(NewsItem.objects.all())
        assert all(item.resumo_proprio != "" for item in itens_persistidos)
