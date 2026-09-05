"""
Interface `SummarizationProvider` (ARCHITECTURE.md secao 6) + implementacao
concreta via API HTTP de um provedor de LLM de terceiros.

Decisao de provedor concreto (documentada com o racional completo em
implementation-history.md): cliente HTTP generico compativel com o formato
"Chat Completions" popularizado pela OpenAI (tambem usado por Azure OpenAI,
Groq, OpenRouter, modelos locais via Ollama/vLLM em modo compativel, etc.) —
nao amarra o pipeline a um SDK de um unico fornecedor especifico. Nao ha
credenciais reais de nenhum provedor de LLM neste ambiente; a chamada de
rede real fica isolada em `_chamar_api()`, mockavel em testes sem exigir
rede real (ver `tests/`).
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import requests
from django.conf import settings

from .news_source import ItemBruto

logger = logging.getLogger(__name__)


@dataclass
class ResultadoResumo:
    """Saida de `SummarizationProvider.resumir_e_classificar()`."""

    resumo: str
    categoria: str = ""
    urgente: bool = False
    tokens_utilizados: Optional[int] = None
    custo_estimado_usd: Optional[float] = None


class SummarizationProviderError(Exception):
    """Levantada quando o provedor de LLM falha (rede, resposta invalida, etc.)."""


class SummarizationProvider(ABC):
    """
    Contrato que qualquer provedor de LLM (OpenAI, Azure OpenAI, Anthropic,
    modelo self-hosted, etc.) deve implementar (ARCHITECTURE.md secao 6).
    """

    @abstractmethod
    def resumir_e_classificar(self, itens_brutos: list[ItemBruto]) -> ResultadoResumo:
        """
        Recebe um ou mais `ItemBruto` que cobrem o MESMO acontecimento (um
        unico item para cobertura de fonte unica; multiplos itens quando o
        pipeline de deduplicacao ja identificou que se trata do mesmo
        acontecimento coberto por fontes diferentes) e devolve um resumo
        PROPRIO (nunca copia do texto bruto) + classificacao de
        categoria/urgencia. Implementacoes devem levantar
        `SummarizationProviderError` (nao uma excecao generica) em caso de
        falha, para que o chamador trate isso de forma previsivel.
        """
        raise NotImplementedError

    def resumir_e_classificar_em_lote(self, itens_brutos: list[ItemBruto]) -> list[ResultadoResumo]:
        """
        Versao em LOTE: resume/classifica VARIOS itens INDEPENDENTES numa
        unica chamada ao provedor, para reduzir o numero de chamadas/custo
        (pedido do usuario apos configurar uma chave real de LLM — o
        pipeline antes chamava o provider uma vez por item, sempre). Cada
        posicao do retorno corresponde EXCLUSIVAMENTE ao item na MESMA
        posicao de `itens_brutos` (retorno sempre com o MESMO tamanho da
        entrada) — implementacoes nunca podem combinar/misturar conteudo
        entre itens desta lista, mesmo estando na mesma chamada. Essa e a
        MESMA garantia estrutural anti-misattribution de
        `resumir_e_classificar` (BRD secao 18), so que agora amortizada
        sobre N itens por chamada em vez de 1 — NAO deve ser confundida com
        o caso de uso de `resumir_e_classificar` com varios itens (que
        significa "varias FONTES do MESMO acontecimento -> UM resumo
        combinado"): aqui e o oposto, "N acontecimentos possivelmente
        diferentes -> N resumos independentes".

        Implementacao PADRAO (usada por qualquer `SummarizationProvider` que
        nao sobrescreva este metodo — inclui todos os dubles/mocks de teste
        ja existentes neste projeto): chama `resumir_e_classificar` uma vez
        por item, preservando exatamente o comportamento/numero de chamadas
        de antes. Only `LLMHttpSummarizationProvider` (o provedor HTTP real)
        sobrescreve isto com uma chamada HTTP unica de fato por lote.
        """
        return [self.resumir_e_classificar([item]) for item in itens_brutos]


class LLMHttpSummarizationProvider(SummarizationProvider):
    """
    Implementacao concreta via API HTTP de LLM, no formato "Chat
    Completions". Endpoint, modelo e API key vem de `settings` (nunca
    hardcoded), permitindo trocar de provedor sem alterar codigo de negocio
    — mitiga o risco de "Custo de IA/infraestrutura" (BRD secao 30) mantendo
    o pipeline desacoplado do SDK/formato de um fornecedor especifico.
    """

    def __init__(
        self,
        api_base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        modelo: Optional[str] = None,
        timeout_segundos: Optional[int] = None,
        tamanho_lote: Optional[int] = None,
        max_tokens_por_item: Optional[int] = None,
    ):
        try:
            from catalogo_noticias.services.config_robo import cfg_valor as _cv
            _db_base = _cv("CATALOGO_NOTICIAS_LLM_API_BASE_URL", "llm_api_base_url")
            _db_model = _cv("CATALOGO_NOTICIAS_LLM_MODEL", "llm_model")
            _db_timeout = int(_cv("CATALOGO_NOTICIAS_LLM_TIMEOUT_SEGUNDOS", "llm_timeout_segundos", int))
        except Exception:
            _db_base = settings.CATALOGO_NOTICIAS_LLM_API_BASE_URL
            _db_model = settings.CATALOGO_NOTICIAS_LLM_MODEL
            _db_timeout = settings.CATALOGO_NOTICIAS_LLM_TIMEOUT_SEGUNDOS
        self.api_base_url = api_base_url or _db_base
        self.api_key = api_key if api_key is not None else settings.CATALOGO_NOTICIAS_LLM_API_KEY
        self.modelo = modelo or _db_model
        self.timeout_segundos = timeout_segundos or _db_timeout
        # Reducao de custo/numero de chamadas (pedido do usuario): quantos
        # itens INDEPENDENTES entram em uma unica chamada HTTP de
        # `resumir_e_classificar_em_lote`, e um teto de tokens de resposta
        # proporcional ao tamanho do lote — sem isso, uma resposta prolixa
        # custa mais tokens de SAIDA (cobrados a taxa mais alta que os de
        # entrada, na maioria dos provedores) do que o necessario para um
        # resumo curto.
        try:
            from catalogo_noticias.services.config_robo import cfg_valor as _cv2
            _db_lote = int(_cv2("CATALOGO_NOTICIAS_LLM_TAMANHO_LOTE", "llm_tamanho_lote", int))
            _db_max = int(_cv2("CATALOGO_NOTICIAS_LLM_MAX_TOKENS_POR_ITEM", "llm_max_tokens_por_item", int))
            _db_preco = float(_cv2("CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS", "llm_preco_por_1k_tokens", float))
        except Exception:
            _db_lote = settings.CATALOGO_NOTICIAS_LLM_TAMANHO_LOTE
            _db_max = settings.CATALOGO_NOTICIAS_LLM_MAX_TOKENS_POR_ITEM
            _db_preco = settings.CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS
        self.tamanho_lote = tamanho_lote or _db_lote
        self.max_tokens_por_item = max_tokens_por_item or _db_max
        # Preco estimado (USD por 1k tokens) usado por `_interpretar_resposta`/
        # `_interpretar_resposta_lote` para calcular `custo_estimado_usd`
        # (implementation-contract.md, run 20260903-1211-teto-gasto-diario-llm)
        # — lido de `settings` no __init__ (nao a cada chamada) para permitir
        # override via `settings.py`/env var sem exigir um parametro novo no
        # construtor, mesmo padrao dos demais atributos acima.
        self.preco_usd_por_1k_tokens = _db_preco

        if not self.api_key:
            logger.warning(
                "CATALOGO_NOTICIAS_LLM_API_KEY nao configurada — usando resumo local "
                "derivado do titulo/fonte (sem LLM) ate a API key ser definida; "
                "itens nao-sensiveis serao publicaveis sem revisao humana.",
            )

    def _resumo_local_para_item(self, item: ItemBruto) -> ResultadoResumo:
        titulo = (item.titulo or "").strip()
        nome_fonte = (item.nome_fonte or "").strip()
        if titulo and nome_fonte:
            resumo = f"{titulo} — publicada por {nome_fonte}. Confira a integra na fonte original."
        elif titulo:
            resumo = f"{titulo} — confira a integra na fonte original."
        else:
            resumo = "Confira a integra desta materia na fonte original."
        return ResultadoResumo(resumo=resumo, categoria=(item.categoria or "").strip().lower(), urgente=False)

    def resumir_e_classificar(self, itens_brutos: list[ItemBruto]) -> ResultadoResumo:
        if not itens_brutos:
            raise ValueError("resumir_e_classificar requer ao menos um ItemBruto")
        if not (self.api_key or "").strip():
            return self._resumo_local_para_item(itens_brutos[0])

        prompt = self._montar_prompt(itens_brutos)
        resposta_bruta = self._chamar_api(prompt)
        return self._interpretar_resposta(resposta_bruta)

    def _montar_prompt(self, itens_brutos: list[ItemBruto]) -> str:
        fontes_texto = "\n\n".join(
            f"Fonte: {item.nome_fonte}\nTitulo: {item.titulo}\nConteudo: {item.conteudo_bruto}"
            for item in itens_brutos
        )
        return (
            "Voce e um assistente de curadoria jornalistica. Escreva um "
            "resumo PROPRIO (nunca copie frases literais do texto original) "
            "do acontecimento coberto pelas fontes abaixo, e classifique "
            "categoria (uma palavra, ex.: politica, economia, esportes, "
            "seguranca publica, tecnologia) e se e urgente (true/false). "
            'Responda em JSON: {"resumo": ..., "categoria": ..., '
            '"urgente": ...}.\n\n' + fontes_texto
        )

    def _chamar_api(self, prompt: str, max_tokens: Optional[int] = None) -> dict:
        """
        Isolada em metodo proprio para ser mockavel em testes sem exigir
        rede real nem credenciais (nao ha credenciais reais de nenhum
        provedor de LLM neste ambiente — ver implementation-history.md).

        `max_tokens`: teto de tokens de RESPOSTA (nunca aplicado ao prompt de
        entrada). Opcional/None preserva o comportamento historico (sem
        teto, campo omitido do payload) — usado por `resumir_e_classificar`
        (chamada unica, ja validada em producao); `resumir_e_classificar_em_lote`
        sempre passa um valor explicito (ver `_max_tokens_para_lote`).
        """
        corpo: dict = {
            "model": self.modelo,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        }
        if max_tokens is not None:
            corpo["max_tokens"] = max_tokens

        try:
            resposta = requests.post(
                f"{self.api_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=corpo,
                timeout=self.timeout_segundos,
            )
            resposta.raise_for_status()
            return resposta.json()
        except requests.RequestException as exc:
            logger.exception("Falha ao chamar o provedor de LLM (%s)", self.api_base_url)
            raise SummarizationProviderError(str(exc)) from exc

    def _interpretar_resposta(self, resposta_bruta: dict) -> ResultadoResumo:
        try:
            conteudo = resposta_bruta["choices"][0]["message"]["content"]
            dados = json.loads(conteudo)
            uso = resposta_bruta.get("usage", {}) or {}
            tokens_utilizados = uso.get("total_tokens")
            return ResultadoResumo(
                resumo=dados["resumo"],
                categoria=(dados.get("categoria") or "").strip().lower(),
                urgente=bool(dados.get("urgente", False)),
                tokens_utilizados=tokens_utilizados,
                # Custo ESTIMADO (implementation-contract.md, run
                # 20260903-1211-teto-gasto-diario-llm) — tokens x preco
                # configuravel (`CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS`),
                # nao a tabela de precos real de um provedor especifico
                # (decisao de provedor concreto continua em aberto,
                # ARCHITECTURE.md secao 8). `None` quando o provedor nao
                # devolve `usage.total_tokens` (nunca inventamos tokens).
                custo_estimado_usd=(
                    (tokens_utilizados / 1000) * self.preco_usd_por_1k_tokens
                    if tokens_utilizados
                    else None
                ),
            )
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            logger.exception("Resposta do provedor de LLM em formato inesperado")
            raise SummarizationProviderError(
                f"Resposta do provedor de LLM em formato inesperado: {exc}"
            ) from exc

    # -----------------------------------------------------------------------
    # Reducao de custo/numero de chamadas (pedido do usuario apos configurar
    # uma chave real de LLM): resume/classifica VARIOS itens INDEPENDENTES
    # numa UNICA chamada HTTP, em vez de uma chamada por item. A garantia
    # anti-misattribution (BRD secao 18) e preservada por construcao: cada
    # item e identificado por um "id" numerico no prompt e na resposta
    # esperada, e a interpretacao da resposta (`_interpretar_resposta_lote`)
    # NUNCA aplica o resumo de um id a outro — um id ausente/invalido na
    # resposta vira apenas ResultadoResumo(resumo="") para AQUELE item
    # (forca revisao humana, mesmo tratamento ja dado a qualquer resumo
    # nao confiavel em `services/ingestao.py`), sem afetar os demais itens
    # do mesmo lote.
    # -----------------------------------------------------------------------

    def resumir_e_classificar_em_lote(self, itens_brutos: list[ItemBruto]) -> list[ResultadoResumo]:
        if not itens_brutos:
            return []
        if not (self.api_key or "").strip():
            return [self._resumo_local_para_item(item) for item in itens_brutos]

        prompt = self._montar_prompt_lote(itens_brutos)
        max_tokens = self._max_tokens_para_lote(len(itens_brutos))
        resposta_bruta = self._chamar_api(prompt, max_tokens=max_tokens)
        return self._interpretar_resposta_lote(resposta_bruta, quantidade_esperada=len(itens_brutos))

    def _max_tokens_para_lote(self, quantidade_itens: int) -> int:
        return self.max_tokens_por_item * quantidade_itens

    def _montar_prompt_lote(self, itens_brutos: list[ItemBruto]) -> str:
        itens_texto = "\n\n".join(
            f"Noticia {indice}:\nFonte: {item.nome_fonte}\nTitulo: {item.titulo}\nConteudo: {item.conteudo_bruto}"
            for indice, item in enumerate(itens_brutos, start=1)
        )
        return (
            "Voce e um assistente de curadoria jornalistica. Abaixo ha "
            f"{len(itens_brutos)} noticias NUMERADAS e INDEPENDENTES entre si "
            "(podem ou nao ser sobre o mesmo assunto — trate cada uma "
            "separadamente). Para CADA noticia, escreva um resumo PROPRIO "
            "(nunca copie frases literais do texto original, e nunca "
            "misture informacao de uma noticia com outra, mesmo que "
            "pareçam relacionadas) e classifique categoria (uma palavra, "
            "ex.: politica, economia, esportes, seguranca publica, "
            "tecnologia) e se e urgente (true/false).\n\n"
            f"{itens_texto}\n\n"
            f"Responda em JSON: uma lista com exatamente {len(itens_brutos)} "
            "objetos, um por noticia, na mesma ordem, cada um no formato "
            '{"id": <numero da noticia>, "resumo": ..., "categoria": ..., '
            '"urgente": ...}. Responda SOMENTE a lista JSON, sem texto '
            "adicional antes ou depois."
        )

    def _interpretar_resposta_lote(
        self, resposta_bruta: dict, quantidade_esperada: int
    ) -> list[ResultadoResumo]:
        try:
            conteudo = resposta_bruta["choices"][0]["message"]["content"]
            dados = json.loads(conteudo)
            if not isinstance(dados, list):
                raise ValueError("resposta em lote esperada como uma lista JSON")
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.exception("Resposta em lote do provedor de LLM em formato inesperado")
            raise SummarizationProviderError(
                f"Resposta em lote do provedor de LLM em formato inesperado: {exc}"
            ) from exc

        uso = resposta_bruta.get("usage", {}) or {}
        # Tokens/custo desta chamada sao do LOTE inteiro, nao de um item so —
        # dividimos proporcionalmente entre os itens para que a soma total
        # (feita item a item por `services/ingestao.py`, sem mudar essa
        # logica) continue refletindo o total real da chamada.
        tokens_totais_lote = uso.get("total_tokens")
        tokens_por_item = (
            tokens_totais_lote // quantidade_esperada if tokens_totais_lote else None
        )

        por_id: dict[int, dict] = {}
        for entrada in dados:
            if isinstance(entrada, dict) and isinstance(entrada.get("id"), int):
                por_id[entrada["id"]] = entrada

        resultados: list[ResultadoResumo] = []
        for indice in range(1, quantidade_esperada + 1):
            entrada = por_id.get(indice)
            if not entrada or not (entrada.get("resumo") or "").strip():
                # id ausente, fora de posicao ou sem resumo utilizavel: NUNCA
                # adivinhamos/reaproveitamos o resumo de outro id — este item
                # especifico cai no mesmo fallback de "sem resumo confiavel"
                # (forca revisao humana em services/ingestao.py), os demais
                # itens do lote nao sao afetados.
                logger.warning(
                    "Item %d/%d sem entrada valida na resposta em lote do provedor de LLM — "
                    "forcando resumo vazio (revisao humana) so para este item.",
                    indice,
                    quantidade_esperada,
                )
                resultados.append(ResultadoResumo(resumo=""))
                continue

            resultados.append(
                ResultadoResumo(
                    resumo=entrada["resumo"],
                    categoria=(entrada.get("categoria") or "").strip().lower(),
                    urgente=bool(entrada.get("urgente", False)),
                    tokens_utilizados=tokens_por_item,
                    # Mesmo calculo de `_interpretar_resposta` (run
                    # 20260903-1211-teto-gasto-diario-llm), aplicado ao
                    # `tokens_por_item` ja dividido proporcionalmente acima —
                    # NAO recalcula/redivide tokens aqui, so converte o mesmo
                    # numero em custo.
                    custo_estimado_usd=(
                        (tokens_por_item / 1000) * self.preco_usd_por_1k_tokens
                        if tokens_por_item
                        else None
                    ),
                )
            )
        return resultados
