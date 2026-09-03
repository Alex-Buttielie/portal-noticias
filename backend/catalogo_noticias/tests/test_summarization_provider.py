"""
Testes diretos de `LLMHttpSummarizationProvider` (nenhum existia antes desta
correcao — o restante da suite so exercita a interface `SummarizationProvider`
via dubles injetados em `executar_ingestao`, nunca a implementacao HTTP real).

Cobre especificamente `resumir_e_classificar_em_lote` (reducao de
custo/numero de chamadas ao provedor real, pedido do usuario apos configurar
uma chave de LLM) — a garantia central e que cada item do lote so pode
receber o SEU PROPRIO resumo, mesmo quando a resposta do provedor vem fora
de ordem ou incompleta para algum item.

Nenhum teste faz chamada de rede real: `requests.post` e sempre mockado.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from catalogo_noticias.providers.news_source import ItemBruto
from catalogo_noticias.providers.summarization import (
    LLMHttpSummarizationProvider,
    SummarizationProviderError,
)


def _item(titulo, nome_fonte="G1", url=None, conteudo="Conteudo bruto de teste."):
    return ItemBruto(
        titulo=titulo,
        url_fonte_original=url or f"https://exemplo/{titulo}",
        nome_fonte=nome_fonte,
        conteudo_bruto=conteudo,
    )


def _resposta_chat_completions(conteudo_json: str, total_tokens: int | None = None) -> MagicMock:
    resposta = MagicMock()
    resposta.raise_for_status.side_effect = None
    corpo: dict = {"choices": [{"message": {"content": conteudo_json}}]}
    if total_tokens is not None:
        corpo["usage"] = {"total_tokens": total_tokens}
    resposta.json.return_value = corpo
    return resposta


class TestResumirEClassificarEmLote:
    def test_lote_bem_formado_devolve_um_resultado_por_item_na_ordem_correta(self):
        provider = LLMHttpSummarizationProvider(api_key="chave-de-teste")
        itens = [_item("Noticia A"), _item("Noticia B"), _item("Noticia C")]
        conteudo = json.dumps(
            [
                {"id": 1, "resumo": "Resumo autoral de A.", "categoria": "geral", "urgente": False},
                {"id": 2, "resumo": "Resumo autoral de B.", "categoria": "esportes", "urgente": True},
                {"id": 3, "resumo": "Resumo autoral de C.", "categoria": "economia", "urgente": False},
            ]
        )

        with patch(
            "catalogo_noticias.providers.summarization.requests.post",
            return_value=_resposta_chat_completions(conteudo, total_tokens=90),
        ) as mock_post:
            resultados = provider.resumir_e_classificar_em_lote(itens)

        # UMA UNICA chamada HTTP para os 3 itens (o ganho de custo/chamadas).
        assert mock_post.call_count == 1
        assert len(resultados) == 3
        assert resultados[0].resumo == "Resumo autoral de A."
        assert resultados[1].resumo == "Resumo autoral de B."
        assert resultados[1].urgente is True
        assert resultados[2].categoria == "economia"
        # tokens do lote inteiro divididos entre os itens (30 cada, de 90 totais)
        assert resultados[0].tokens_utilizados == 30

    def test_max_tokens_da_chamada_e_proporcional_ao_tamanho_do_lote(self):
        provider = LLMHttpSummarizationProvider(
            api_key="chave-de-teste", max_tokens_por_item=200
        )
        itens = [_item("Noticia A"), _item("Noticia B")]
        conteudo = json.dumps(
            [
                {"id": 1, "resumo": "Resumo A.", "categoria": "geral", "urgente": False},
                {"id": 2, "resumo": "Resumo B.", "categoria": "geral", "urgente": False},
            ]
        )

        with patch(
            "catalogo_noticias.providers.summarization.requests.post",
            return_value=_resposta_chat_completions(conteudo),
        ) as mock_post:
            provider.resumir_e_classificar_em_lote(itens)

        corpo_enviado = mock_post.call_args.kwargs["json"]
        assert corpo_enviado["max_tokens"] == 400  # 200 por item x 2 itens

    def test_item_ausente_na_resposta_recebe_fallback_isolado_sem_afetar_os_demais(self):
        """
        Garantia central anti-misattribution aplicada ao caso em lote: se o
        provedor "esquecer" de responder por um id, aquele item especifico
        vira resumo vazio (forca revisao humana em services/ingestao.py) —
        nunca herda o resumo de outro item do mesmo lote, e os OUTROS itens
        do lote continuam corretos.
        """
        provider = LLMHttpSummarizationProvider(api_key="chave-de-teste")
        itens = [_item("Noticia A"), _item("Noticia B"), _item("Noticia C")]
        # id=2 (Noticia B) ausente da resposta.
        conteudo = json.dumps(
            [
                {"id": 1, "resumo": "Resumo autoral de A.", "categoria": "geral", "urgente": False},
                {"id": 3, "resumo": "Resumo autoral de C.", "categoria": "geral", "urgente": False},
            ]
        )

        with patch(
            "catalogo_noticias.providers.summarization.requests.post",
            return_value=_resposta_chat_completions(conteudo),
        ):
            resultados = provider.resumir_e_classificar_em_lote(itens)

        assert len(resultados) == 3
        assert resultados[0].resumo == "Resumo autoral de A."
        assert resultados[1].resumo == ""  # id=2 ausente -> fallback isolado, nao o resumo de A ou C
        assert resultados[2].resumo == "Resumo autoral de C."

    def test_resposta_fora_de_ordem_e_mapeada_pelo_id_nao_pela_posicao(self):
        """O provedor pode devolver os objetos em qualquer ordem — o mapeamento e sempre por 'id'."""
        provider = LLMHttpSummarizationProvider(api_key="chave-de-teste")
        itens = [_item("Noticia A"), _item("Noticia B")]
        conteudo = json.dumps(
            [
                {"id": 2, "resumo": "Resumo autoral de B.", "categoria": "geral", "urgente": False},
                {"id": 1, "resumo": "Resumo autoral de A.", "categoria": "geral", "urgente": False},
            ]
        )

        with patch(
            "catalogo_noticias.providers.summarization.requests.post",
            return_value=_resposta_chat_completions(conteudo),
        ):
            resultados = provider.resumir_e_classificar_em_lote(itens)

        assert resultados[0].resumo == "Resumo autoral de A."  # item na posicao 0 = Noticia A = id 1
        assert resultados[1].resumo == "Resumo autoral de B."

    def test_resposta_nao_e_uma_lista_json_levanta_summarizationprovidererror(self):
        provider = LLMHttpSummarizationProvider(api_key="chave-de-teste")
        itens = [_item("Noticia A")]
        conteudo = json.dumps({"resumo": "formato de item unico, nao de lote"})

        with patch(
            "catalogo_noticias.providers.summarization.requests.post",
            return_value=_resposta_chat_completions(conteudo),
        ):
            with pytest.raises(SummarizationProviderError):
                provider.resumir_e_classificar_em_lote(itens)

    def test_lista_vazia_nao_faz_chamada_http(self):
        provider = LLMHttpSummarizationProvider(api_key="chave-de-teste")
        with patch("catalogo_noticias.providers.summarization.requests.post") as mock_post:
            resultados = provider.resumir_e_classificar_em_lote([])
        assert resultados == []
        mock_post.assert_not_called()


class TestResumirEClassificarItemUnicoContinuaFuncionando:
    """Regressao: o metodo de item unico (ja validado em producao) nao foi alterado."""

    def test_resumir_e_classificar_item_unico_sem_teto_de_tokens_por_padrao(self):
        provider = LLMHttpSummarizationProvider(api_key="chave-de-teste")
        conteudo = json.dumps({"resumo": "Resumo autoral.", "categoria": "geral", "urgente": False})

        with patch(
            "catalogo_noticias.providers.summarization.requests.post",
            return_value=_resposta_chat_completions(conteudo, total_tokens=42),
        ) as mock_post:
            resultado = provider.resumir_e_classificar([_item("Noticia unica")])

        assert resultado.resumo == "Resumo autoral."
        assert resultado.tokens_utilizados == 42
        # comportamento historico preservado: sem max_tokens no payload
        # quando chamado via `resumir_e_classificar` (nao em lote).
        assert "max_tokens" not in mock_post.call_args.kwargs["json"]


# ===========================================================================
# AC-5 (implementation-contract.md, run 20260903-1211-teto-gasto-diario-llm):
# `custo_estimado_usd = (tokens/1000) * preco_configurado`, nunca mais
# sempre `None`, quando `tokens_utilizados` e conhecido.
# ===========================================================================


class TestCustoEstimadoUsd:
    @override_settings(CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS=0.20)
    def test_resumir_e_classificar_calcula_custo_a_partir_de_tokens_e_preco_configurado(self):
        provider = LLMHttpSummarizationProvider(api_key="chave-de-teste")
        conteudo = json.dumps({"resumo": "Resumo autoral.", "categoria": "geral", "urgente": False})

        with patch(
            "catalogo_noticias.providers.summarization.requests.post",
            return_value=_resposta_chat_completions(conteudo, total_tokens=500),
        ):
            resultado = provider.resumir_e_classificar([_item("Noticia unica")])

        assert resultado.tokens_utilizados == 500
        assert resultado.custo_estimado_usd == pytest.approx((500 / 1000) * 0.20)

    def test_resumir_e_classificar_sem_tokens_conhecidos_devolve_custo_none(self):
        """Sem `usage.total_tokens` na resposta do provedor, nunca inventamos tokens/custo."""
        provider = LLMHttpSummarizationProvider(api_key="chave-de-teste")
        conteudo = json.dumps({"resumo": "Resumo autoral.", "categoria": "geral", "urgente": False})

        with patch(
            "catalogo_noticias.providers.summarization.requests.post",
            return_value=_resposta_chat_completions(conteudo),  # sem total_tokens
        ):
            resultado = provider.resumir_e_classificar([_item("Noticia unica")])

        assert resultado.tokens_utilizados is None
        assert resultado.custo_estimado_usd is None

    @override_settings(CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS=0.30)
    def test_resumir_e_classificar_em_lote_calcula_custo_por_item_a_partir_dos_tokens_ja_divididos(self):
        """
        `custo_estimado_usd` por item deriva do MESMO `tokens_por_item` ja
        dividido proporcionalmente (implementation-contract.md — nao deve
        alterar essa divisao existente), so convertido em custo pelo preco
        configurado.
        """
        provider = LLMHttpSummarizationProvider(api_key="chave-de-teste")
        itens = [_item("Noticia A"), _item("Noticia B"), _item("Noticia C")]
        conteudo = json.dumps(
            [
                {"id": 1, "resumo": "Resumo autoral de A.", "categoria": "geral", "urgente": False},
                {"id": 2, "resumo": "Resumo autoral de B.", "categoria": "geral", "urgente": False},
                {"id": 3, "resumo": "Resumo autoral de C.", "categoria": "geral", "urgente": False},
            ]
        )

        with patch(
            "catalogo_noticias.providers.summarization.requests.post",
            return_value=_resposta_chat_completions(conteudo, total_tokens=90),
        ):
            resultados = provider.resumir_e_classificar_em_lote(itens)

        # 90 tokens totais / 3 itens = 30 tokens por item (mesma divisao ja existente)
        assert all(r.tokens_utilizados == 30 for r in resultados)
        custo_esperado = pytest.approx((30 / 1000) * 0.30)
        assert all(r.custo_estimado_usd == custo_esperado for r in resultados)

    def test_resumir_e_classificar_em_lote_sem_tokens_conhecidos_devolve_custo_none_por_item(self):
        provider = LLMHttpSummarizationProvider(api_key="chave-de-teste")
        itens = [_item("Noticia A"), _item("Noticia B")]
        conteudo = json.dumps(
            [
                {"id": 1, "resumo": "Resumo A.", "categoria": "geral", "urgente": False},
                {"id": 2, "resumo": "Resumo B.", "categoria": "geral", "urgente": False},
            ]
        )

        with patch(
            "catalogo_noticias.providers.summarization.requests.post",
            return_value=_resposta_chat_completions(conteudo),  # sem total_tokens
        ):
            resultados = provider.resumir_e_classificar_em_lote(itens)

        assert all(r.tokens_utilizados is None for r in resultados)
        assert all(r.custo_estimado_usd is None for r in resultados)

    @override_settings(CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS=0.15)
    def test_preco_configuravel_via_env_var_muda_o_custo_calculado_sem_alterar_codigo(self):
        """Mesmo padrao de configurabilidade ja usado pelas demais settings CATALOGO_NOTICIAS_LLM_*."""
        provider_preco_padrao = LLMHttpSummarizationProvider(api_key="chave-de-teste")
        conteudo = json.dumps({"resumo": "Resumo autoral.", "categoria": "geral", "urgente": False})

        with patch(
            "catalogo_noticias.providers.summarization.requests.post",
            return_value=_resposta_chat_completions(conteudo, total_tokens=1000),
        ):
            resultado_preco_padrao = provider_preco_padrao.resumir_e_classificar([_item("Noticia unica")])

        assert resultado_preco_padrao.custo_estimado_usd == pytest.approx(0.15)

        with override_settings(CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS=1.0):
            provider_preco_alterado = LLMHttpSummarizationProvider(api_key="chave-de-teste")
            with patch(
                "catalogo_noticias.providers.summarization.requests.post",
                return_value=_resposta_chat_completions(conteudo, total_tokens=1000),
            ):
                resultado_preco_alterado = provider_preco_alterado.resumir_e_classificar([_item("Noticia unica")])

        assert resultado_preco_alterado.custo_estimado_usd == pytest.approx(1.0)
        assert resultado_preco_alterado.custo_estimado_usd != resultado_preco_padrao.custo_estimado_usd
