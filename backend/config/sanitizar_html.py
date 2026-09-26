"""
Sanitizador de HTML editorial — fronteira primária de XSS no backend.

POR QUE EXISTE
--------------
`moderacao.PaginaEditorial.conteudo` é HTML editável pelo admin e é
consumido por `frontend/app/paginas/[slug]/page.tsx` via
`dangerouslySetInnerHTML`. Enquanto o texto não for sanitizado, qualquer
HTML com `<script>`, `onerror=` ou `javascript:` neste campo viraria XSS
armazenado servido na origem do portal.

Este é o ponto PRIMÁRIO de sanitização (roda no servidor, antes de
persistir e antes de servir pela API). O sanitizador do frontend
(`frontend/lib/sanitizar-html.ts`) é a segunda camada, útil para HTML já
gravado antes desta validação existir ou que venha de cache.

POR QUE `html.parser` E NÃO REGEX
---------------------------------
`html.parser.HTMLParser` é um tokenizador de streaming que implementa as
regras da spec HTML (raw text, atributos com/sem aspas, comentários,
CDATA,<TEntity). Regex sobre HTML é a origem clássica de bypass
(`<scr"+"ipt>`, `<img src=x onerror =alert(1)>`, comentários
condicionais). Aqui a decisão é tomada token a token, o que torna a
classe inteira de bypass de parsing estruturalmente inexistente.

POLÍTICA: ALLOWLIST
-------------------
Tags e atributos são reconstruídos a partir de uma allowlist. Tudo que
não está na allowlist é DESCARTADO. O default é "não renderizar", nunca
"não bloquear" — uma blacklist de tags perigosas é sempre incompleta
(`<svg><animate onbegin=…>`, `<math><mtext>`, `<details ontoggle>`, …).

`conteudo` de tag proibida é descartado junto (comportamento de DOMPurify
para `script`/`style`/`iframe`): manter o código-fonte de um script como
texto visível não é neutralização, é ruído.

A allowlist é deliberadamente estreita: uma página editorial (Termos,
Política de Privacidade, Sobre) é texto institucional com formatação
simples. Não há caso legítimo para `<form>`, `<iframe>`, `<object>`,
`<style>`, atributos `on*` ou `style=` inline.
"""

from __future__ import annotations

from html import escape
from html.parser import HTMLParser
from typing import Iterable

# --------------------------------------------------------------------------
# Allowlist
# --------------------------------------------------------------------------

# tag -> "fechar" (mantém o elemento) | "descartar-conteudo" (remove o miolo)
TAGS_PERMITIDAS: dict[str, str] = {
    # Estrutura e texto
    "p": "fechar",
    "br": "fechar",
    "hr": "fechar",
    "strong": "fechar",
    "b": "fechar",
    "em": "fechar",
    "i": "fechar",
    "u": "fechar",
    "s": "fechar",
    "sub": "fechar",
    "sup": "fechar",
    "small": "fechar",
    "mark": "fechar",
    "abbr": "fechar",
    "time": "fechar",
    # Títulos
    "h1": "fechar",
    "h2": "fechar",
    "h3": "fechar",
    "h4": "fechar",
    "h5": "fechar",
    "h6": "fechar",
    # Listas
    "ul": "fechar",
    "ol": "fechar",
    "li": "fechar",
    "dl": "fechar",
    "dt": "fechar",
    "dd": "fechar",
    # Citação e código
    "blockquote": "fechar",
    "pre": "fechar",
    "code": "fechar",
    "kbd": "fechar",
    "samp": "fechar",
    "var": "fechar",
    # Tabelas (usadas em tabela de preços / prazos dos Termos)
    "table": "fechar",
    "thead": "fechar",
    "tbody": "fechar",
    "tfoot": "fechar",
    "tr": "fechar",
    "th": "fechar",
    "td": "fechar",
    "caption": "fechar",
    "col": "fechar",
    "colgroup": "fechar",
    # Link
    "a": "fechar",
    # Elementos cujo CONTEÚDO é inseguro no contexto do elemento.
    "script": "descartar-conteudo",
    "style": "descartar-conteudo",
    "iframe": "descartar-conteudo",
    "frame": "descartar-conteudo",
    "frameset": "descartar-conteudo",
    "object": "descartar-conteudo",
    "embed": "descartar-conteudo",
    "applet": "descartar-conteudo",
    "template": "descartar-conteudo",
    "noscript": "descartar-conteudo",
    "svg": "descartar-conteudo",
    "math": "descartar-conteudo",
    "canvas": "descartar-conteudo",
    "audio": "descartar-conteudo",
    "video": "descartar-conteudo",
    "form": "descartar-conteudo",
    "button": "descartar-conteudo",
    "select": "descartar-conteudo",
    "textarea": "descartar-conteudo",
    "link": "descartar-conteudo",
    "meta": "descartar-conteudo",
    "base": "descartar-conteudo",
}

# Atributos aceitos por tag. `"*"` vale para todas.
ATRIBUTOS_GLOBAIS: frozenset[str] = frozenset({"title", "lang", "dir"})
ATRIBUTOS_POR_TAG: dict[str, frozenset[str]] = {
    "a": frozenset({"href", "rel", "target"}),
    "ol": frozenset({"start", "type", "reversed"}),
    "li": frozenset({"value"}),
    "td": frozenset({"colspan", "rowspan", "headers"}),
    "th": frozenset({"colspan", "rowspan", "scope", "abbr"}),
    "col": frozenset({"span"}),
    "colgroup": frozenset({"span"}),
    "time": frozenset({"datetime"}),
    "abbr": frozenset({"title"}),
}

# Atributos booleanos legítimos (presentes sem valor).
ATRIBUTOS_BOOLEANOS: frozenset[str] = frozenset({"reversed"})

# Esquemas tolerados em `href`.
ESQUEMAS_HREF: frozenset[str] = frozenset({"http", "https", "mailto"})

# `target` aceito. Qualquer outro valor (inclusive `_top`, que sobe
# para o frame superior) é descartado — não ampliamos o pedido do autor.
TARGETS_ACEITOS: frozenset[str] = frozenset({"_blank"})


def _href_seguro(valor: str) -> str | None:
    """
    Valida e canonicaliza um `href`. Devolve `None` se não for permitido.

    Não usa comparação por substring nem `startswith("https://")`: o
    esquema é extraído com `urllib.parse.urlsplit`, que faz a análise
    completa (e é o mesmo parser que o browser usa para o início da URL).
    """
    from urllib.parse import urlsplit

    bruto = (valor or "").strip()
    if not bruto:
        return None

    # Remove controles C0/DEL. Neutraliza `java\tscript:alert(1)` — o
    # browser ignora tab/CR/LF dentro de uma URL. ESPAÇO não é removido:
    # `java script:` vira esquema inválido e é recusado logo abaixo.
    bruto = "".join(c for c in bruto if ord(c) > 0x1F and ord(c) != 0x7F)
    if not bruto:
        return None

    try:
        partes = urlsplit(bruto)
    except ValueError:
        return None

    esquema = (partes.scheme or "").lower()
    if not esquema:
        # Relativa: só aceita caminho absoluto interno (`/politica`).
        # `//evil.tld` é scheme-relative e resolve para QUALQUER host.
        if bruto.startswith("/") and not bruto.startswith("//"):
            return bruto
        return None

    if esquema not in ESQUEMAS_HREF:
        return None

    # Credenciais embutidas (phishing com URL "confiável").
    if esquema != "mailto" and partes.username:
        return None
    # `mailto:` não tem host; as demais exigem.
    if esquema != "mailto" and not partes.netloc:
        return None

    return bruto


def _atributos_permitidos(tag: str) -> frozenset[str]:
    return ATRIBUTOS_GLOBAIS | ATRIBUTOS_POR_TAG.get(tag, frozenset())


class _Sanitizador(HTMLParser):
    """
    Reconstrói o documento a partir de uma allowlist.

    `HTMLParser` já trata raw text (`<script>`), comentários, CDATA e
    aspas em atributos — que é exatamente a superfície onde sanitizadores
    baseados em regex costumam ser furados.
    """

    def __init__(self) -> None:
        # `convert_charrefs=False` para não reaplicar escape em texto que
        # já passamos por `escape()`.
        super().__init__(convert_charrefs=False)
        self._saida: list[str] = []
        self._pular_ate: str | None = None
        self._pular_profundidade = 0

    # -- texto -------------------------------------------------------------
    def handle_data(self, data: str) -> None:
        if self._pular_ate is not None:
            return
        # `quote=True` escapa também `"` e `'`. Inofensivo em text node e
        # necessário se a saída um dia for embutida num atributo — mesma
        # decisão do sanitizador do frontend, pelo mesmo motivo.
        self._saida.append(escape(data, quote=True))

    def handle_entityref(self, name: str) -> None:  # ex.: `&amp;`
        if self._pular_ate is not None:
            return
        self._saida.append(f"&{name};")

    def handle_charref(self, name: str) -> None:  # ex.: `&#38;`
        if self._pular_ate is not None:
            return
        self._saida.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        # Comentários HTML são clássico vetor de conditional comment e de
        # smuggling em parsers lenient. Descartados.
        return

    def handle_decl(self, decl: str) -> None:
        return

    def handle_pi(self, data: str) -> None:
        return

    def unknown_decl(self, data: str) -> None:
        # CDATA, por exemplo.
        return

    # -- elementos ---------------------------------------------------------
    def handle_starttag(self, tag: str, attrs: Iterable[tuple[str, str | None]]) -> None:
        nome = tag.lower()
        if self._pular_ate is not None:
            # Dentro de um elemento "descartar-conteudo": só importa
            #rementar profundidade para aninhamento da MESMA tag.
            if nome == self._pular_ate:
                self._pular_profundidade += 1
            return

        modo = TAGS_PERMITIDAS.get(nome)
        if modo is None:
            # Tag fora da allowlist: descarta a TAG e preserva o texto
            # interno (que o browser renderizaria como texto puro).
            return
        if modo == "descartar-conteudo":
            self._pular_ate = nome
            self._pular_profundidade = 1
            return

        self._saida.append(self._tag_abertura(nome, attrs))

    def handle_startendtag(self, tag: str, attrs: Iterable[tuple[str, str | None]]) -> None:
        nome = tag.lower()
        if self._pular_ate is not None:
            return
        if nome not in TAGS_PERMITIDAS or TAGS_PERMITIDAS[nome] == "descartar-conteudo":
            return
        # `convert_charrefs=False` não afeta self-closing; emite `<br/>`
        # para tags que a spec define como vazias.
        self._saida.append(self._tag_abertura(nome, attrs) + (" />" if nome in _VAZIAS else ">"))

    def handle_endtag(self, tag: str) -> None:
        nome = tag.lower()
        if self._pular_ate is not None:
            if nome == self._pular_ate:
                self._pular_profundidade -= 1
                if self._pular_profundidade <= 0:
                    self._pular_ate = None
                    self._pular_profundidade = 0
            return
        if nome in TAGS_PERMITIDAS and TAGS_PERMITIDAS[nome] == "fechar":
            self._saida.append(f"</{nome}>")

    # -- serialização ------------------------------------------------------
    def _tag_abertura(self, nome: str, attrs: Iterable[tuple[str, str | None]]) -> str:
        permitidos = _atributos_permitidos(nome)
        vistos: set[str] = set()
        pares: list[tuple[str, str | None]] = []
        for bruto_nome, valor in attrs:
            chave = (bruto_nome or "").lower()
            if chave in vistos:
                continue  # duplicata: vence a primeira (o browser também usa a 1ª)
            vistos.add(chave)
            if chave.startswith("on"):
                continue  # handler: nunca passa
            if chave in {"style", "src", "srcset", "data", "formaction", "action", "background"}:
                continue
            if chave not in permitidos:
                continue
            if chave == "href":
                seguro = _href_seguro(valor or "")
                if seguro is None:
                    continue
                pares.append((chave, seguro))
                continue
            if chave == "target":
                if (valor or "").lower() not in TARGETS_ACEITOS:
                    continue
                pares.append((chave, (valor or "").lower()))
                continue
            if valor is None:
                if chave in ATRIBUTOS_BOOLEANOS:
                    pares.append((chave, None))
                continue
            pares.append((chave, valor))

        # `target="_blank"` sem `rel=noopener` é reverse tabnabbing. Injeta.
        tem_target = any(nome_atrib == "target" for nome_atrib, _ in pares)
        tem_noopener = any(
            nome_atrib == "rel" and "noopener" in (valor or "").lower()
            for nome_atrib, valor in pares
        )
        if tem_target and not tem_noopener:
            pares.append(("rel", "noopener noreferrer nofollow"))

        if not pares:
            return f"<{nome}>"
        serializados = "".join(
            f" {chave}" if valor is None else f' {chave}="{escape(valor, quote=True)}"'
            for chave, valor in pares
        )
        return f"<{nome}{serializados}>"

    def resultado(self) -> str:
        return "".join(self._saida)


# Tags vazias na spec HTML (não devem receber tag de fechamento).
_VAZIAS: frozenset[str] = frozenset(
    {"br", "hr", "col", "wbr", "area", "base", "img", "input", "link", "meta", "source", "track"}
)


def sanitizar_html(entrada: object) -> str:
    """
    Devolve `entrada` com apenas marcação da allowlist.

    - Nunca lança. Entrada não-string (ou `None`) vira `""`.
    - Preserva o TEXTO (escapado) e remove a marcação não permitida.
    - `html.parser` tolera HTML malformado; nunca propaga exceção para o
      render da página.
    """
    if not isinstance(entrada, str) or not entrada:
        return ""
    try:
        analisador = _Sanitizador()
        analisador.feed(entrada)
        analisador.close()
        return analisador.resultado()
    except Exception:  # noqa: BLE001 — sanitização é fail-closed, nunca fail-open
        # Se o tokenizer explodir (bug do parser, entrada bizarra), o
        # fallback seguro é NÃO renderizar HTML. Texto puro seria ainda
        # melhor, mas exigiria um segundo parser; vazio é fail-closed e
        # nunca expõe marcação não sanitizada.
        return ""


def contem_html_perigoso(entrada: object) -> bool:
    """
    `True` se a sanitização REMOVEU algo — usado para emitir log de
    auditoria quando conteúdo editorial chega sujo, sem fazer a
    requisição falhar.
    """
    if not isinstance(entrada, str):
        return False
    return sanitizar_html(entrada) != entrada
