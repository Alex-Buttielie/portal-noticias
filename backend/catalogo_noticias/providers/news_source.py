"""
Interface `NewsSourceProvider` (ARCHITECTURE.md secao 6) + implementacao
concreta via RSS (`RSSNewsSourceProvider`).

Qualquer fonte futura (API licenciada, outro RSS, etc.) deve implementar
`NewsSourceProvider.buscar_itens()` e devolver uma lista de `ItemBruto` — o
restante do pipeline (`services/ingestao.py`) nao conhece detalhes de
RSS/HTTP, apenas este contrato.
"""

from __future__ import annotations

import calendar
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from typing import Optional

import feedparser
import requests

logger = logging.getLogger(__name__)


class FonteIndisponivelError(Exception):
    """
    Levantada quando uma fonte nao pode ser acessada/parseada (erro de rede,
    HTTP nao-2xx, feed corrompido, etc.). `services/ingestao.py` captura essa
    excecao por fonte para que a falha de uma fonte nao derrube as demais
    (implementation-contract.md, criterio de aceite 1).
    """


@dataclass
class ItemBruto:
    """Item de noticia ainda nao processado por dedup/resumo/classificacao."""

    titulo: str
    url_fonte_original: str
    nome_fonte: str
    conteudo_bruto: str = ""
    categoria: str = ""
    timestamp_publicacao_fonte: Optional[datetime] = None


class NewsSourceProvider(ABC):
    """
    Contrato que qualquer fonte de noticias (RSS hoje; API licenciada,
    integracao futura, etc.) deve implementar (ARCHITECTURE.md secao 6).
    """

    @abstractmethod
    def buscar_itens(self) -> list[ItemBruto]:
        """
        Retorna os itens brutos disponiveis nesta fonte no momento da
        chamada. Deve levantar `FonteIndisponivelError` (nao uma excecao
        generica) em caso de falha de rede/parsing, para que o chamador
        possa tratar essa falha de forma previsivel e isolada por fonte.
        """
        raise NotImplementedError


class RSSNewsSourceProvider(NewsSourceProvider):
    """
    Implementacao de `NewsSourceProvider` via feed RSS/Atom (biblioteca
    `feedparser`). Cada instancia representa uma unica fonte configurada
    (nome + URL do feed) — a lista de fontes-semente vive em
    `settings.CATALOGO_NOTICIAS_FONTES_RSS`, nunca hardcoded aqui.
    """

    def __init__(self, nome_fonte: str, url_feed: str, timeout_segundos: int = 15):
        self.nome_fonte = nome_fonte
        self.url_feed = url_feed
        self.timeout_segundos = timeout_segundos

    def buscar_itens(self) -> list[ItemBruto]:
        try:
            resposta = requests.get(
                self.url_feed,
                timeout=self.timeout_segundos,
                headers={"User-Agent": "BRDPortalNoticias/1.0 (+ingestao-catalogo-noticias)"},
            )
            resposta.raise_for_status()
        except requests.RequestException as exc:
            raise FonteIndisponivelError(
                f"Falha ao buscar o feed RSS de '{self.nome_fonte}' ({self.url_feed}): {exc}"
            ) from exc

        feed = feedparser.parse(resposta.content)
        if feed.bozo and not feed.entries:
            # `bozo=1` sinaliza XML malformado; se ainda assim vieram
            # entries, seguimos em frente (feedparser costuma extrair o que
            # da mesmo em feeds levemente invalidos) — so tratamos como
            # indisponivel quando NADA pode ser extraido.
            raise FonteIndisponivelError(
                f"Feed RSS de '{self.nome_fonte}' ({self.url_feed}) malformado: {feed.bozo_exception}"
            )

        itens: list[ItemBruto] = []
        for entrada in feed.entries:
            url_item = getattr(entrada, "link", "") or ""
            titulo_item = getattr(entrada, "title", "") or ""
            if not url_item or not titulo_item:
                # Item individual sem URL/titulo nao e publicavel (criterio
                # de aceite 3) — descartado aqui (nao e erro de fonte, so um
                # item malformado dentro de um feed bom no geral).
                logger.debug(
                    "Item descartado do feed '%s' por falta de titulo/URL.", self.nome_fonte
                )
                continue

            conteudo = getattr(entrada, "summary", "") or getattr(entrada, "description", "") or ""
            categoria = ""
            tags = getattr(entrada, "tags", None)
            if tags:
                categoria = getattr(tags[0], "term", "") or ""

            timestamp_publicacao = None
            published_parsed = getattr(entrada, "published_parsed", None)
            if published_parsed:
                timestamp_publicacao = datetime.fromtimestamp(
                    calendar.timegm(published_parsed), tz=dt_timezone.utc
                )

            itens.append(
                ItemBruto(
                    titulo=titulo_item.strip(),
                    url_fonte_original=url_item.strip(),
                    nome_fonte=self.nome_fonte,
                    conteudo_bruto=conteudo.strip(),
                    categoria=categoria.strip().lower(),
                    timestamp_publicacao_fonte=timestamp_publicacao,
                )
            )
        return itens
