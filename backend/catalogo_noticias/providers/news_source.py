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
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional

import feedparser
import requests
from django.conf import settings
from django.utils import timezone as django_timezone

# P1-01: os utilitarios de texto (limpeza de HTML + truncagem segura) vivem em
# `catalogo_noticias/limites_texto.py`, sem dependencia de models, para que o
# provider e o servico de ingestao compartilhem a MESMA implementacao — duas
# copias divergentes fariam um dos caminhos aceitar o que o outro recusa.
from ..limites_texto import (
    FOLGA_ANTES_DE_LIMPAR_HTML,
    limpar_html_para_texto,
    truncar,
)
# P0-10 (eixo 2, SSRF): todo egresso HTTP deste provider passa por
# `config.egress.SessaoEgress`, que valida o destino antes de abrir a conexão.
# Independente dos limites de texto acima: uma constrain o QUE entra no
# registro, o outro para ONDE o provider pode buscar.
from config.egress import EgressBloqueado, SessaoEgress

logger = logging.getLogger(__name__)


class FonteIndisponivelError(Exception):
    """
    Levantada quando uma fonte nao pode ser acessada/parseada (erro de rede,
    HTTP nao-2xx, feed corrompido, etc.). `services/ingestao.py` captura essa
    excecao por fonte para que a falha de uma fonte nao derrube as demais
    (implementation-contract.md, criterio de aceite 1).
    """


def parece_pagina_html(corpo: bytes) -> bool:
    """Detecta homepage/página HTML cadastrada por engano no lugar do feed.

    Contexto real (2026-09-18): fontes cadastradas em Central > Robôs com a
    URL da homepage do portal (ex.: `https://www.bbc.com/portuguese`) em vez
    do endpoint RSS — o fetch retorna HTML 200, o feedparser acusa
    "malformado" e a ingestão zera para todas elas. O sniff é pelo corpo
    (não pelo Content-Type: há feeds legítimos servidos como `text/html`,
    ex.: Correio Braziliense), após BOM/whitespace.
    """
    try:
        inicio = (corpo or b"").lstrip(b"\xef\xbb\xbf \t\r\n").lower()[:20]
    except Exception:
        return False
    return inicio.startswith(b"<html") or inicio.startswith(b"<!doctype html")


def extrair_imagem_url(entrada) -> str:
    for key in ("enclosures", "media_content", "media_thumbnail"):
        vals = getattr(entrada, key, None)
        if vals:
            for v in vals:
                href = (v.get("url") if isinstance(v, dict) else getattr(v, "url", "")) or (v.get("href") if isinstance(v, dict) else getattr(v, "href", ""))
                if href and href.startswith("http"):
                    return href.strip()
    for key in ("image",):
        val = getattr(entrada, key, None)
        if val:
            href = val.get("href") if isinstance(val, dict) else getattr(val, "href", "")
            if href and href.startswith("http"):
                return href.strip()
            if isinstance(val, str) and val.startswith("http"):
                return val.strip()
    links = getattr(entrada, "links", None)
    if links:
        for lk in links:
            rel = lk.get("rel") if isinstance(lk, dict) else getattr(lk, "rel", "")
            href = lk.get("href") if isinstance(lk, dict) else getattr(lk, "href", "")
            tipo = lk.get("type") if isinstance(lk, dict) else getattr(lk, "type", "")
            if href and href.startswith("http") and (rel == "enclosure" or (tipo or "").startswith("image/")):
                return href.strip()
    summary = getattr(entrada, "summary", "") or ""
    if summary and "og:image" in summary:
        import re
        m = re.search(r'og:image["\']?\s*content=["\']([^"\']+)["\']', summary)
        if m and m.group(1).startswith("http"):
            return m.group(1).strip()
        m2 = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary)
        if m2 and m2.group(1).startswith("http"):
            return m2.group(1).strip()
    return ""


TETO_CONTEUDO_COMPLETO_CHARS = 8000

# ---------------------------------------------------------------------------
# Tetos do provider (P1-01) — o FRONT de memoria do pipeline.
#
# estes numeros reproduzem os `max_length` REAIS do modelo `NewsItem`. Sao
# declarados aqui, e nao lidos de `_meta`, porque este modulo e a camada de
# FONTE e nao deve depender de `django.db.models`; a garantia de que eles nao
# divergem do DDL esta em
# `tests/test_p1_01_ingestao_limites.py::test_tetos_do_provider_batem_com_o_modelo`.
#
# O provider nao e o lugar onde o limite e GARANTIDO: um feed pode vir de
# qualquer fonte, e `services/limites.py` reaplica tudo no servico antes de
# qualquer escrita. Aqui o objetivo e outro e mais fraco: nao segurar um feed
# gigante em memoria ate o fim da rodada, e nao alimentar o `SequenceMatcher`
# do agrupamento com titulos enormes.
# ---------------------------------------------------------------------------
_LIMITE_TITULO = 300
_LIMITE_URL = 1000
_LIMITE_NOME_FONTE = 150
_LIMITE_CATEGORIA = 100
_LIMITE_ESTADO = 100
_LIMITE_PAIS = 100
_LIMITE_IMAGEM_URL = 1000
_TETO_CONTEUDO_BRUTO = 20_000


def _limitar_url(url: str, nome_fonte: str) -> str:
    """URL acima do `max_length` e um item INUTILIZAVEL, nao um item para
    truncar: truncar produziria outra URL, que nao e a materia da fonte.

    O item e descartado aqui (vazio), e o servico nunca chega a tentar
    persistir uma URL invalida. O motivo fica registrado no log de WARNING
    porque o operador precisa saber que o feed trouxe algo descartavel —
    e no placar de falhas da rodada, no servico.
    """
    if len(url) <= _LIMITE_URL:
        return url
    logger.warning(
        "Item do feed '%s' descartado: url_fonte_original tem %d caracteres e o "
        "limite e %d (truncar fabricaria outra URL).",
        nome_fonte,
        len(url),
        _LIMITE_URL,
    )
    return ""


def _limitar_imagem(url: str) -> str:
    """URL de imagem acima do `max_length` e descartada (vira ""): uma URL
    cortada aponta para um recurso inexistente, que e pior que nao ter
    imagem — o item entra sem imagem em vez de nao entrar."""
    if len(url) <= _LIMITE_IMAGEM_URL:
        return url
    logger.warning(
        "imagem_url com %d caracteres (limite %d) descartada; o item segue sem imagem.",
        len(url),
        _LIMITE_IMAGEM_URL,
    )
    return ""


def _cortar_html_bruto(html: str) -> str:
    """Corta o HTML bruto ANTES da limpeza, para nao materializar o feed
    inteiro so para descartar quase tudo logo em seguida.

    Antes o corte vinha depois: um `content:encoded` de 3 MB virava 3 MB de
    texto e so entao era truncado para 8.000 chars — o pico de memoria da
    ingestao crescia com o tamanho do feed, nao com o teto do campo. A folga
    de `FOLGA_ANTES_DE_LIMPAR_HTML` cobre o caso em que a limpeza INFLА o
    texto por expansao de entidades, e nunca resulta em menos texto util do
    que antes, porque o corte final em `TETO_CONTEUDO_COMPLETO_CHARS` segue
    valendo.
    """
    teto = TETO_CONTEUDO_COMPLETO_CHARS * FOLGA_ANTES_DE_LIMPAR_HTML
    if len(html) <= teto:
        return html
    # O corte e no ultimo `>` para nao deixar markup pela metade, que a
    # limpeza depois transformaria em texto solto sem sentido.
    cortado = html[:teto]
    ultimo_fim_de_tag = cortado.rfind(">")
    if ultimo_fim_de_tag > teto // 2:
        return cortado[: ultimo_fim_de_tag + 1]
    return cortado


def extrair_conteudo_completo(entrada) -> str:
    """Texto integral da matéria direto do RSS (`content:encoded` quando o
    feed traz; senão o summary/description), limpo de HTML e limitado a
    `TETO_CONTEUDO_COMPLETO_CHARS` chars. Best-effort: retorna "" se o feed
    só trouxer título/link. Exibido de forma TRUNCADA no frontend, sempre
    com crédito + link para a fonte original (BRD seção 18)."""
    html_completo = ""
    conteudos = getattr(entrada, "content", None)
    if conteudos:
        for bloco in conteudos:
            valor = (bloco.get("value") if isinstance(bloco, dict) else getattr(bloco, "value", "")) or ""
            if valor and len(valor) > len(html_completo):
                html_completo = valor
    if not html_completo.strip():
        html_completo = getattr(entrada, "summary", "") or getattr(entrada, "description", "") or ""
    texto = limpar_html_para_texto(_cortar_html_bruto(html_completo))
    return texto[:TETO_CONTEUDO_COMPLETO_CHARS].strip()


@dataclass
class ItemBruto:
    titulo: str
    url_fonte_original: str
    nome_fonte: str
    conteudo_bruto: str = ""
    conteudo_completo: str = ""
    categoria: str = ""
    imagem_url: str = ""
    timestamp_publicacao_fonte: Optional[datetime] = None
    # Recorte regional da fonte (ex.: "GO" para o G1 Goiás): herdado pelo
    # NewsItem quando o RSS não informa localidade própria. Vazio = nacional.
    estado_fonte: str = ""
    pais_fonte: str = ""


class NewsSourceProvider(ABC):
    """
    Contrato que qualquer fonte de noticias (RSS hoje; API licenciada,
    integracao futura, etc.) deve implementar (ARCHITECTURE.md secao 6).
    """

    def __getattr__(self, name: str):  # type: ignore[no-redef]
        """Alias de compatibilidade: providers podem usar ``nome`` ou
        ``nome_fonte`` — aceita ambos sem quebrar (``FakeProvider`` do
        report usava ``nome`` e quebrava com ``has no attribute 'nome'``).

        Deixa ``getattr(obj, 'nome_fonte', default)`` funcionar com fallback
        para ``default`` quando NENHUM dos dois existe (re-levanta
        AttributeError para o ``getattr`` capturar).
        """
        if name == "nome":
            try:
                return object.__getattribute__(self, "nome_fonte")
            except AttributeError:
                raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'") from None
        if name == "nome_fonte":
            try:
                return object.__getattribute__(self, "nome")
            except AttributeError:
                raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'") from None
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

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

    def __init__(
        self,
        nome_fonte: str,
        url_feed: str,
        timeout_segundos: int = 15,
        estado_fonte: str = "",
        pais_fonte: str = "",
        etag: str = "",
        last_modified: str = "",
        fonte_robo=None,
        ultima_revalidacao_completa=None,
    ):
        self.nome_fonte = nome_fonte
        self.url_feed = url_feed
        self.timeout_segundos = timeout_segundos
        self.estado_fonte = (estado_fonte or "").strip().upper()
        self.pais_fonte = (pais_fonte or "").strip()
        self.etag = str(etag or "").strip()
        self.last_modified = str(last_modified or "").strip()
        self.fonte_robo = fonte_robo
        self.ultima_revalidacao_completa = (
            getattr(fonte_robo, "ultima_revalidacao_completa", None)
            if ultima_revalidacao_completa is None
            else ultima_revalidacao_completa
        )
        self.not_modified = False
        self._validators_pendentes: tuple[str, str] | None = None
        self._validacao_completa_pendente = False

    @staticmethod
    def _header(resposta, nome: str) -> str:
        headers = getattr(resposta, "headers", None) or {}
        try:
            valor = headers.get(nome, "")
            if not valor:
                # `requests` entrega CaseInsensitiveDict, mas dublês e
                # fontes de teste às vezes usam um dict simples.
                for chave, candidato in headers.items():
                    if str(chave).lower() == nome.lower():
                        valor = candidato
                        break
        except (AttributeError, TypeError):
            return ""
        return str(valor).strip() if valor else ""

    def _revalidacao_forcada(self) -> bool:
        """Indica que os validators não devem ser enviados nesta rodada.

        Um 304 é apenas uma resposta do upstream, não uma prova de que o
        acervo local está completo.  Forçamos uma leitura sem headers após
        o TTL de segurança; o marcador ``NULL`` das linhas migradas também
        provoca essa reconciliação na primeira execução.
        """
        ultima = self.ultima_revalidacao_completa
        if not ultima:
            return True
        try:
            horas = float(
                getattr(settings, "CATALOGO_NOTICIAS_REVALIDACAO_COMPLETA_HORAS", 6)
            )
        except (TypeError, ValueError):
            horas = 6.0
        if horas <= 0:
            return True
        if django_timezone.is_naive(ultima):
            ultima = django_timezone.make_aware(ultima)
        return django_timezone.now() - ultima >= timedelta(hours=horas)

    def _capturar_validadores(self, resposta) -> None:
        """Captura headers para confirmar somente após persistir os itens.

        Salvar o validator no fetch criaria uma janela perigosa: o worker
        poderia cair depois do INSERT do validator e antes dos NewsItems;
        na próxima rodada um 304 faria o pipeline perder os itens baixados.
        """
        self.etag = self._header(resposta, "ETag")
        self.last_modified = self._header(resposta, "Last-Modified")
        self._validators_pendentes = (self.etag, self.last_modified)
        self._validacao_completa_pendente = True

    def confirmar_validadores(self) -> None:
        """Persiste validators/marcador de uma execução concluída com sucesso.

        O ``UPDATE`` condicional por ``pk + url`` é a barreira contra a
        corrida em que um administrador troca a URL enquanto o pipeline ainda
        está resumindo/persistindo o feed antigo.  Não usamos ``save()`` da
        instância carregada no início: ela poderia estar obsoleta (TOCTOU).
        """
        pendentes = self._validators_pendentes
        if pendentes is None and not self._validacao_completa_pendente:
            return
        fonte = self.fonte_robo
        try:
            if fonte is not None and getattr(fonte, "pk", None):
                from ..models import FonteRobo

                updates = {
                    "ultima_revalidacao_completa": django_timezone.now(),
                }
                if pendentes is not None:
                    updates["etag"], updates["last_modified"] = pendentes
                atualizados = FonteRobo.objects.filter(
                    pk=fonte.pk,
                    url=self.url_feed,
                ).update(**updates)
                if not atualizados:
                    logger.info(
                        "Validator HTTP descartado para '%s': a URL mudou "
                        "durante a execução (pk=%s).",
                        self.nome_fonte,
                        fonte.pk,
                    )
                else:
                    # Mantém a instância do provider coerente para uma
                    # eventual reentrega no mesmo objeto, sem salvar a linha.
                    if pendentes is not None:
                        fonte.etag, fonte.last_modified = pendentes
                    fonte.ultima_revalidacao_completa = updates[
                        "ultima_revalidacao_completa"
                    ]
                    self.ultima_revalidacao_completa = fonte.ultima_revalidacao_completa
        except Exception:
            # O fetch e os itens já foram processados; uma falha ao salvar o
            # validator apenas fará um download completo na próxima rodada.
            logger.warning(
                "Não foi possível persistir validator HTTP da fonte '%s'",
                self.nome_fonte,
                exc_info=True,
            )
        finally:
            self._validators_pendentes = None
            self._validacao_completa_pendente = False

    def invalidar_validadores_apos_erro(self) -> None:
        """Limpa validators antigos quando a última tentativa falhou.

        A comparação com os valores vistos no início evita que uma execução
        concorrente que já confirmou um fetch novo seja apagada por um erro
        atrasado da execução anterior.  A próxima rodada então faz download
        completo em vez de aceitar um 304 possivelmente enganoso.
        """
        fonte = self.fonte_robo
        if fonte is None or not getattr(fonte, "pk", None):
            return
        try:
            from ..models import FonteRobo

            FonteRobo.objects.filter(
                pk=fonte.pk,
                url=self.url_feed,
                etag=self.etag,
                last_modified=self.last_modified,
                ultima_revalidacao_completa=self.ultima_revalidacao_completa,
            ).update(
                etag="",
                last_modified="",
                ultima_revalidacao_completa=None,
            )
        except Exception:
            logger.warning(
                "Não foi possível invalidar validator HTTP da fonte '%s'",
                self.nome_fonte,
                exc_info=True,
            )

    def buscar_itens(self) -> list[ItemBruto]:
        self.not_modified = False
        self._validators_pendentes = None
        self._validacao_completa_pendente = False
        headers = {"User-Agent": "BRDPortalNoticias/1.0 (+ingestao-catalogo-noticias)"}
        forcar_revalidacao = self._revalidacao_forcada()
        if not forcar_revalidacao:
            if self.etag:
                headers["If-None-Match"] = self.etag
            if self.last_modified:
                headers["If-Modified-Since"] = self.last_modified
        try:
            # `SessaoEgress` e não `requests.get`: `url_feed` vem do
            # cadastro de fontes, preenchido a partir de dados de
            # TERCEIROS (o `descobrir_feeds` extrai endpoints de
            # homepages externas) ou de um admin. Sem isto, um feed
            # apontando para `http://169.254.169.254/latest/meta-data/`
            # (ou para um `302` que aponte para lá) fazia o servidor
            # ler a rede interna e devolver o corpo como "itens do feed".
            with SessaoEgress() as sessao:
                resposta = sessao.get(
                    self.url_feed,
                    timeout=self.timeout_segundos,
                    headers=headers,
                )
            # 304 é uma resposta válida de download condicional: não há corpo
            # para parsear e os validators anteriores devem ser preservados.
            if getattr(resposta, "status_code", None) == 304:
                self.not_modified = True
                # Mesmo um 304 sem validators (reconciliação periódica) é
                # uma tentativa concluída; o marcador só é confirmado pelo
                # pipeline depois de toda a persistência.
                self._validacao_completa_pendente = True
                return []
            resposta.raise_for_status()
        except EgressBloqueado as exc:
            # Destino forbidden por política de saída. Não é "fonte fora do
            # ar": é uma fonte CADASTRADA COM URL PROIBIDA. A distinção
            # importa para o operador (é um erro de configuração/cadastro,
            # não uma indisponibilidade temporária) e para o log, que não
            # deve repetir a URL com a query (pode conter segredo).
            logger.error(
                "Saída bloqueada para a fonte '%s' (host=%s ip=%s): %s",
                self.nome_fonte,
                exc.host or "?",
                exc.ip or "?",
                exc,
            )
            raise FonteIndisponivelError(
                f"A fonte '{self.nome_fonte}' tem um endereço de destino não permitido "
                f"pela política de segurança de saída do portal. Corrija o cadastro."
            ) from exc
        except requests.RequestException as exc:
            raise FonteIndisponivelError(
                f"Falha ao buscar o feed RSS de '{self.nome_fonte}' ({self.url_feed}): {exc}"
            ) from exc

        corpo = resposta.content or b""
        if parece_pagina_html(corpo):
            raise FonteIndisponivelError(
                f"URL cadastrada para '{self.nome_fonte}' ({self.url_feed}) não é um feed RSS/Atom "
                f"(retornou página HTML). Cadastre o endpoint do feed RSS em Central > Robôs > Fontes "
                f"— não a homepage do portal."
            )
        feed = feedparser.parse(corpo)
        if feed.bozo and not feed.entries:
            # `bozo=1` sinaliza XML malformado; se ainda assim vieram
            # entries, seguimos em frente (feedparser costuma extrair o que
            # da mesmo em feeds levemente invalidos) — so tratamos como
            # indisponivel quando NADA pode ser extraido.
            raise FonteIndisponivelError(
                f"Feed RSS de '{self.nome_fonte}' ({self.url_feed}) malformado: {feed.bozo_exception} "
                f"(se a URL for a homepage do portal, cadastre o endpoint do feed RSS em Central > Robôs > Fontes)"
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

            # P1-01: a URL e tratada ANTES de montar o `ItemBruto`, porque um
            # item sem URL utilizavel nao e publicavel (criterio de aceite 3) e
            # nao adianta limitador nenhum: ele acabaria recusado la no
            # `NewsItem.clean()`. Descartar aqui mantem o item malformado
            # longe do lote, no mesmo caminho (e com o mesmo log) do item sem
            # titulo/URL acima.
            url_limitada = _limitar_url(url_item.strip(), self.nome_fonte)
            if not url_limitada:
                continue

            # P1-01: teto no proprio provider, para que um feed enorme nao
            # seja segurado em memoria ate o fim da rodada. A garantia
            # DEFINITIVA de que nada grande chega ao banco e a aplicacao em
            # `services/limites.py` (o servico), que cobre qualquer fonte —
            # aqui o ponto e so reduzir o pico de memoria e o custo de CPU do
            # agrupamento (que compara titulos com `SequenceMatcher`).
            itens.append(
                ItemBruto(
                    titulo=truncar(
                        limpar_html_para_texto(titulo_item.strip()),
                        _LIMITE_TITULO,
                    ),
                    url_fonte_original=url_limitada,
                    nome_fonte=truncar(
                        limpar_html_para_texto(self.nome_fonte), _LIMITE_NOME_FONTE
                    ),
                    conteudo_bruto=truncar(
                        conteudo.strip(), _TETO_CONTEUDO_BRUTO
                    ),
                    conteudo_completo=extrair_conteudo_completo(entrada),
                    categoria=truncar(
                        limpar_html_para_texto(categoria.strip().lower()),
                        _LIMITE_CATEGORIA,
                    ),
                    imagem_url=_limitar_imagem(extrair_imagem_url(entrada)),
                    timestamp_publicacao_fonte=timestamp_publicacao,
                    estado_fonte=truncar(
                        limpar_html_para_texto(self.estado_fonte), _LIMITE_ESTADO
                    ),
                    pais_fonte=truncar(
                        limpar_html_para_texto(self.pais_fonte), _LIMITE_PAIS
                    ),
                )
            )
        # Só capturamos validators depois de um parse válido. A gravação no
        # FonteRobo é adiada para `confirmar_validadores`, após a persistência
        # dos NewsItems, para não perder uma rodada em queda de worker.
        self._capturar_validadores(resposta)
        return itens
