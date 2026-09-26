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

# P0-10 (eixo 2, SSRF): TODO o egresso deste provider passa por
# `config.egress.SessaoEgress`, que valida o destino antes de abrir a conexão.
# Nao e oposto a classificacao de motivo do P1-02 abaixo: uma constrain ONDE
# podemos chamar, a outra diz POR QUE a chamada falhou. As duas sao necessarias.
from config.egress import ALVO_CONFIANCAVEL, EgressBloqueado, SessaoEgress

# P1-02: rotulos fechados de motivo para a metrica e o marcador de origem.
from .fallback_local import (
    MOTIVO_ERRO_DO_PROVIDER,
    MOTIVO_ERRO_HTTP,
    MOTIVO_RATE_LIMIT,
    MOTIVO_RESPOSTA_INVALIDA,
    MOTIVO_SEM_CREDENCIAL,
    MOTIVO_TIMEOUT,
    normalizar_motivo,
)
from .news_source import ItemBruto

logger = logging.getLogger(__name__)

# P1-02 (WS-08/GP-5): menor timeout aceito na chamada externa. `requests`
# levanta `ValueError` (NAO uma `RequestException`) para `timeout <= 0` e
# trata `timeout=None` como "espere para sempre" — nos dois casos a excecao
# escaparia do `except requests.RequestException` de `_chamar_api` e derrubaria
# a ingestao inteira. Um timeout sempre positivo e sempre explicito e a
# unica garantia de que a chamada externa nunca fica pendurada.
TIMEOUT_MINIMO_SEGUNDOS = 1

# Status HTTP de rate limit, classificado como motivo PROPRIO de fallback
# (o provedor esta recusando por cota, nao por falha da chamada).
_HTTP_TOO_MANY_REQUESTS = 429


@dataclass
class ResultadoResumo:
    """Saida de `SummarizationProvider.resumir_e_classificar()`."""

    resumo: str
    categoria: str = ""
    urgente: bool = False
    tokens_utilizados: Optional[int] = None
    custo_estimado_usd: Optional[float] = None
    # P1-02 (WS-08/GP-5): `fallback=True` marca este resultado como gerado
    # pelo caminho LOCAL deterministico (`providers/fallback_local.py`) e nao
    # pelo provedor externo, com `motivo_fallback` dizendo POR QUE. Sem isso o
    # objeto persistido seria indistinguivel de um resumo do provedor — o
    # "sistema degradado que parece saudavel". `motivo_fallback` e sempre um
    # rotulo fechado de `fallback_local.MOTIVOS_CONHECIDOS`, nunca texto livre.
    fallback: bool = False
    motivo_fallback: str = ""


class SummarizationProviderError(Exception):
    """
    Levantada quando o provedor de LLM falha (rede, resposta invalida, etc.).

    P1-02: carrega `motivo` — um rotulo fechado de
    `fallback_local.MOTIVOS_CONHECIDOS` (timeout, rate_limit, erro_http,
    resposta_invalida, sem_credencial) — para que o chamador register metrica,
    log e marcador de origem com o CAUSA, e nao apenas com "deu erro".
    """

    def __init__(self, mensagem: str = "", *, motivo: str = ""):
        super().__init__(mensagem)
        self.motivo = normalizar_motivo(motivo) if motivo else ""


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
        # P1-02: o timeout NUNCA e "sem limite" — `requests` trata
        # `timeout=None` como "espere para sempre" e levanta `ValueError`
        # (que NAO e `RequestException`) para `timeout <= 0`; nos dois casos a
        # excecao escaparia do tratamento de erro de `_chamar_api` e
        # derrubaria a ingestao inteira.
        self.timeout_segundos = self._normalizar_timeout(timeout_segundos or _db_timeout)
        # P0-10: sinal de auditoria de `api_base_url` fora do catalogo de
        # hosts. Independente da normalizacao acima (uma define o QUANTO
        # esperar, a outra PARA ONDE) — as duas sao aplicadas.
        self._avisar_host_de_llm_nao_esperado()
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
                "CATALOGO_NOTICIAS_LLM_API_KEY nao configurada — o provedor externo "
                "nao sera chamado; o pipeline usara o fallback local deterministico "
                "(motivo=%s) ate a API key ser definida.",
                MOTIVO_SEM_CREDENCIAL,
            )

    @staticmethod
    def _normalizar_timeout(valor) -> int:
        """
        Garante um timeout EXPLICITO e POSITIVO na chamada externa.

        Configuracao invalida (0, negativo, `None`, string nao numerica) e
        normalizada para `TIMEOUT_MINIMO_SEGUNDOS` com aviso — em vez de
        deixar `requests` receber `timeout=None` (espera indefinida) ou
        levantar `ValueError` (que nao e `RequestException` e escaparia do
        tratamento de erro, derrubando a ingestao).
        """
        try:
            segundos = int(float(valor))
        except (TypeError, ValueError):
            segundos = 0
        if segundos < TIMEOUT_MINIMO_SEGUNDOS:
            logger.warning(
                "Timeout do SummarizationProvider invalido (%r) — usando o minimo "
                "de %d s para nunca deixar a chamada externa sem limite de espera.",
                valor,
                TIMEOUT_MINIMO_SEGUNDOS,
            )
            return TIMEOUT_MINIMO_SEGUNDOS
        return segundos

    def resumir_e_classificar(self, itens_brutos: list[ItemBruto]) -> ResultadoResumo:
        if not itens_brutos:
            raise ValueError("resumir_e_classificar requer ao menos um ItemBruto")
        if not (self.api_key or "").strip():
            # P1-02: antes isto devolvia silenciosamente um resumo local, com
            # zero rastro de que o provedor nunca fora chamado. Agora levanta
            # com motivo explicito e deixa a producao do fallback (metrica +
            # log + marcador de origem) a cargo de `services/ingestao.py`, que
            # e o unico ponto que conhece o resto do fluxo.
            raise SummarizationProviderError(
                "SummarizationProvider sem credencial configurada "
                "(CATALOGO_NOTICIAS_LLM_API_KEY vazia) — provedor externo nao chamado.",
                motivo=MOTIVO_SEM_CREDENCIAL,
            )

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

    def _avisar_host_de_llm_nao_esperado(self) -> None:
        """
        Sinal de AUDITORIA para `api_base_url` fora do catálogo.

        O campo é administrável e é a base de um POST que leva
        `Authorization: Bearer <api_key>`. O controle de saída já garante
        que o destino não é rede privada; o que sobra é o destino ser um
        host PÚBLICO inesperado — para onde a credencial do provedor seria
        enviada.

        Não bloqueamos: LLM self-hosted é uso legítimo, e quem configura é
        admin. O ponto é que a decisão fique registrada em log, e não
        espalhada pelo código. O catálogo é `config.egress.ALVO_CONFIANCAVEL`.
        """
        from urllib.parse import urlsplit

        try:
            host = (urlsplit(self.api_base_url).hostname or "").lower()
        except ValueError:
            return
        if not host:
            return
        de_confianca = any(
            host == alvo or host.endswith("." + alvo) for alvo in ALVO_CONFIANCAVEL
        )
        if not de_confianca:
            logger.warning(
                "api_base_url do provedor de LLM aponta para '%s', fora do "
                "catálogo de hosts esperados (%s). Se isto não for um provedor "
                "self-hosted autorizado, a credencial do provedor está sendo "
                "enviada para um host inesperado.",
                host,
                ", ".join(sorted(ALVO_CONFIANCAVEL)),
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

        # `api_base_url` é ADMINISTRÁVEL pela API
        # (`robos_serializers.ConfigRoboSerializer.llm_api_base_url`) e é a
        # base de um POST que leva `Authorization: Bearer <api_key>`. Sem
        # controle de saída, apontar isso para `http://169.254.169.254/` (ou
        # para um serviço interno) transforma a integração de LLM em cURL
        # para dentro, com a credencial do provedor na requisição.
        #
        # P0-10 + P1-02 (disputa real de comportamento, resolvida a favor dos
        # DOIS): este bloco originalmente tinha duas versoes conflitantes —
        # o lado P0-10 postava por `SessaoEgress` e o lado P1-02 postava por
        # `requests.post` direto, com a clasificacao de motivo. Nao se pode
        # escolher um: o `requests.post` direto permitiria `api_base_url`
        # apontando para rede interna COM a credencial do provedor no
        # cabecalho (eixo SSRF do P0-10), e `SessaoEgress` sozinho perderia o
        # `motivo` na metrica do P1-02. A resolucao mantem a sessao valida e
        # classifica a falha DEPOIS dela.
        #
        # E `EgressBloqueado` e o PRIMEIRO `except` de proposito: nao e
        # subclasse de `requests.RequestException` (essa e a raza de existir,
        # ver `config/egress.py`), mas ser o primeiro torna a garantia
        # estrutural e explicita — nenhum handler de rede, por mais largo que
        # fique, pode reclassificar "destino proibido por politica" como
        # "provedor fora do ar".
        url = f"{self.api_base_url.rstrip('/')}/chat/completions"
        try:
            with SessaoEgress() as sessao:
                resposta = sessao.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=corpo,
                    timeout=self.timeout_segundos,
                )
            # 429 e classificado ANTES de `raise_for_status()`: rate limit e
            # um motivo de fallback distinto de "erro http generico" (o
            # provedor esta recusando por cota, nao por falha da chamada), e
            # o operador precisa ver a diferenca na metrica.
            if getattr(resposta, "status_code", None) == _HTTP_TOO_MANY_REQUESTS:
                logger.warning(
                    "Provedor de LLM respondeu 429 (rate limit) em %s — "
                    "motivo de fallback=%s.",
                    self.api_base_url,
                    MOTIVO_RATE_LIMIT,
                )
                raise SummarizationProviderError(
                    "Provedor de LLM respondeu 429 (rate limit).",
                    motivo=MOTIVO_RATE_LIMIT,
                )
            resposta.raise_for_status()
            return resposta.json()
        except EgressBloqueado as exc:
            # Não é "provedor fora do ar": é destino proibido. A distinção
            # fica no log e no tipo da exceção. O `motivo` rotulado entra na
            # metrica do P1-02 para que o operador saiba que a queda nao foi
            # do provedor, e sim de configuracao — `erro_do_provider` e o
            # umbrella honesto: o provedor nao respondeu porque a chamada nem
            # saiu. (Nao inventamos rotulo novo: o conjunto e fechado em
            # `fallback_local.MOTIVOS_CONHECIDOS`.)
            logger.error("LLM: destino bloqueado pela política de saída: %s", exc)
            raise SummarizationProviderError(
                "O endereço configurado para o provedor de LLM não é permitido "
                "pela política de segurança de saída do portal.",
                motivo=MOTIVO_ERRO_DO_PROVIDER,
            ) from exc
        except SummarizationProviderError:
            # Relança o 429 acima (e qualquer outro) sem reclassificar: o
            # `motivo` já foi decidido no ponto em que a causa é conhecida.
            raise
        except requests.Timeout as exc:
            # `requests.Timeout` (Read/Connect) e subclasse de
            # `RequestException` — precisa ser checado ANTES do `except`
            # generico para nao ser rotulado como "erro http".
            logger.warning(
                "Timeout de %ss ao chamar o provedor de LLM (%s) — motivo de fallback=%s.",
                self.timeout_segundos,
                self.api_base_url,
                MOTIVO_TIMEOUT,
            )
            raise SummarizationProviderError(
                f"Timeout de {self.timeout_segundos}s ao chamar o provedor de LLM.",
                motivo=MOTIVO_TIMEOUT,
            ) from exc
        except requests.HTTPError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning(
                "Provedor de LLM respondeu HTTP %s (%s) — motivo de fallback=%s.",
                status,
                self.api_base_url,
                MOTIVO_ERRO_HTTP,
            )
            raise SummarizationProviderError(
                f"Provedor de LLM respondeu HTTP {status}.",
                motivo=MOTIVO_ERRO_HTTP,
            ) from exc
        except requests.RequestException as exc:
            # Conexao recusada/DNS/TLS: `str(exc)` carrega a URL do host, nunca
            # o cabecalho de autorizacao, mas mesmo assim nao logamos a
            # excecao completa aqui — so o tipo, que e o que diagnostica.
            logger.warning(
                "Falha de rede ao chamar o provedor de LLM (%s, %s) — motivo de fallback=%s.",
                self.api_base_url,
                type(exc).__name__,
                MOTIVO_ERRO_HTTP,
            )
            raise SummarizationProviderError(
                f"Falha de rede ao chamar o provedor de LLM: {type(exc).__name__}.",
                motivo=MOTIVO_ERRO_HTTP,
            ) from exc

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
            # Log com o TIPO da falha, nunca com o corpo da resposta do
            # provedor (pode ecoar conteudo da fonte ou trecho da materia).
            logger.warning(
                "Resposta do provedor de LLM em formato inesperado (%s) — "
                "motivo de fallback=%s.",
                type(exc).__name__,
                MOTIVO_RESPOSTA_INVALIDA,
            )
            raise SummarizationProviderError(
                f"Resposta do provedor de LLM em formato inesperado: {exc}",
                motivo=MOTIVO_RESPOSTA_INVALIDA,
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
            # Mesmo contrato de `resumir_e_classificar`: sem credencial o
            # provedor externo nao e chamado e o motivo do fallback fica
            # explicito, para `services/ingestao.py` registrar metrica, log e
            # marcador de origem. Ver `resumir_e_classificar`.
            raise SummarizationProviderError(
                "SummarizationProvider sem credencial configurada "
                "(CATALOGO_NOTICIAS_LLM_API_KEY vazia) — provedor externo nao chamado.",
                motivo=MOTIVO_SEM_CREDENCIAL,
            )

        prompt = self._montar_prompt_lote(itens_brutos)
        max_tokens = self._max_tokens_para_lote(len(itens_brutos))
        resposta_bruta = self._chamar_api(prompt, max_tokens=max_tokens)
        return self._interpretar_resposta_lote(resposta_bruta, quantidade_esperada=len(itens_brutos))

    def _max_tokens_para_lote(self, quantidade_itens: int) -> int:
        return self.max_tokens_por_item * quantidade_itens

    def estimar_custo_em_lote(self, quantidade_itens: int) -> float:
        """Reserva conservadora antes da chamada HTTP.

        O valor usa o teto configurado de tokens de resposta e o preço por
        1k tokens. É deliberadamente uma reserva, não Usage do provider:
        se a chamada cair, o gasto continua visível no teto. O fallback local
        (sem API key) não tem custo externo e reserva zero.
        """
        if not (self.api_key or "").strip() or quantidade_itens <= 0:
            return 0.0
        return (
            self._max_tokens_para_lote(quantidade_itens) / 1000
        ) * self.preco_usd_por_1k_tokens

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
            logger.warning(
                "Resposta em lote do provedor de LLM em formato inesperado (%s) — "
                "motivo de fallback=%s.",
                type(exc).__name__,
                MOTIVO_RESPOSTA_INVALIDA,
            )
            raise SummarizationProviderError(
                f"Resposta em lote do provedor de LLM em formato inesperado: {exc}",
                motivo=MOTIVO_RESPOSTA_INVALIDA,
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
