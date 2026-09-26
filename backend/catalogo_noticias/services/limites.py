"""
Limites de campo e normalizacao do conteudo vindo de fonte externa
(P1-01 — workstream WS-08, gate GP-5).

Criterio de saida do backlog que este modulo atende:

    "Valores grandes nao causam ``DataError``; erro nao aborta todos os grupos"

Dois defeitos distintos, um por vez:

1. **Robustez de campo.** RSS e LLM sao fontes EXTERNAS e nao respeitam
   nenhum limite. No PostgreSQL cada ``CharField`` vira ``varchar(N)`` e um
   valor maior estoura o INSERT com
   ``psycopg2.errors.StringDataRightTruncation``, traduzido para
   ``django.db.DataError``. Antes deste modulo, o ``DataError`` subia de
   ``_persistir_news_items_em_lote`` (``services/ingestao.py``) e derrubava a
   rodada INTEIRA — proveniencia: ``docs/evidencias/p1-01-defeito-antes.txt``.

2. **HTML residual.** O titulo e o resumo do RSS iam CRU para o banco. Um
   ``<script>`` num ``<title>`` de feed e markup valido de RSS e chegava
   intacto a ``NewsItem.titulo``, que o frontend injeta em
   ``<script type="application/ld+json">`` via ``JSON.stringify`` (que nao
   escapa ``<`` nem ``/``) — XSS armazenado. Aqui todo texto passa por
   limpeza de HTML + decodificacao de entidades ANTES de ter tamanho medido.

**Os limites nao sao numeros chutados.** sao lidos de
``Model._meta.get_field(campo).max_length`` — a mesma metadada que gera o
DDL — entao um ``max_length`` novo ou alterado no modelo passa a valer aqui
sem ninguem editar este arquivo. Os tetos de ``TextField`` (que no banco
sao ``text``, sem limite, ~1 GB) sao os unicos numeros que este modulo
define proprio, e cada um vem com a justificativa do volume real que
representa.

Politica por campo, porque "truncar tudo" seria errado:

* ``TRUNCAR`` — texto de exibicao: limpa o HTML e corta com elipse
  preservando o texto util (``titulo``, ``resumo_proprio``,
  ``conteudo_completo``, ``categoria``, ``nome_fonte``, ``pais``/``estado``/
  ``cidade``, ``titulo_acontecimento``, ``categoria_dominante``). Perder a
  cauda de uma legenda e melhor do que perder a materia inteira.
* ``DESCARTAR_CAMPO`` — campo acessorio cujo valor truncado seria PIOR que a
  ausencia dele: uma URL de imagem cortada aponta para um recurso
  inexistente (``imagem_url``). Vira string vazia; a materia entra sem imagem.
* ``RECUSAR_ITEM`` — campo IDENTIFICADOR cujo valor truncado seria um valor
  DIFERENTE e errado: ``url_fonte_original`` e a chave de rastreabilidade
  (BRD secao 18, obrigatoria e unica no banco). Cortar
  ``https://a.test/noticia-de-rio`` nao produziria a mesma materia, produziria
  outra. O item e recusado com motivo explicito e vira entrada no placar de
  falhas — nunca um registro silenciosamente errado.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Optional

from django.core.exceptions import FieldDoesNotExist

# Utilitarios de TEXTO puros, sem dependencia de models: compartilhados com
# `providers/news_source.py` para que os dois caminhos apliquem a mesma
# limpeza/truncagem (duas copias divergentes fariam um aceitar o que o outro
# recusa). Ver `catalogo_noticias/limites_texto.py`.
from ..limites_texto import (
    FOLGA_ANTES_DE_LIMPAR_HTML,
    SUFIXO_ELLIPSIS,
    cortar_em_limite_seguro,
    limpar_html_para_texto,
    truncar,
)
from ..models import NewsCluster, NewsItem
from ..providers.news_source import (
    TETO_CONTEUDO_COMPLETO_CHARS as _TETO_CONTEUDO_COMPLETO_DO_PROVIDER,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tetos de aplicacao para os TextField (no banco sao `text`, sem limite)
# ---------------------------------------------------------------------------

# `resumo_proprio`: saida do SummarizationProvider.
# `ConfiguracaoRobo.llm_max_tokens_por_item` = 220 por padrao (~1.000
# caracteres em portugues) e o frontend ja exibe o resumo truncado. 4.000
# chars sao ~4x de folga para um provider verboso, ainda em tamanho de tela.
TETO_RESUMO_PROPRIO_CHARS = 4000

# `conteudo_bruto`: copia de auditoria/depuracao do snippet do RSS (BRD secao
# 18: NUNCA exibida). O original continua acessivel pela `url_fonte_original`,
# que e a rastreabilidade exigida. 20.000 chars sao ~20 KB por item; com a
# janela de deduplicacao de 300 itens (`dedup_max_itens`) o pior caso de
# `_itens_recentes_persistidos` fica na casa das dezenas de MB, nao de GB.
TETO_CONTEUDO_BRUTO_CHARS = 20_000

# `conteudo_completo`: o teto de 8.000 chars ja existia no provider
# (`news_source.TETO_CONTEUDO_COMPLETO_CHARS`); aqui e o MESMO numero lido
# daquela constante, para nao haver dois tetos divergentes para o mesmo campo.
TETO_CONTEUDO_COMPLETO_CHARS = _TETO_CONTEUDO_COMPLETO_DO_PROVIDER


def _teto_settings(nome: str, padrao: int) -> int:
    """Le um teto de `settings` com fallback no padrao do modulo.

    Segue o padrao ja estabelecido no projeto (criterio de aceite 7: mudar
    comportamento sem mudar codigo). O fallback nunca e 0 nem negativo: um
    teto nao pode ser desligado por erro de configuracao, porque o efeito
    seria voltar a estourar o banco.
    """
    from django.conf import settings

    bruto = getattr(settings, nome, padrao)
    try:
        valor = int(bruto)
    except (TypeError, ValueError):
        logger.warning("Teto %s invalido (%r); usando o padrao %d.", nome, bruto, padrao)
        return padrao
    return valor if valor > 0 else padrao


# ---------------------------------------------------------------------------
# Politica por campo
# ---------------------------------------------------------------------------

TRUNCAR = "truncar"
DESCARTAR_CAMPO = "descartar_campo"
RECUSAR_ITEM = "recusar_item"

#: Campos de TEXTO: o valor e limpo de HTML e truncado com elipse.
CAMPOS_TRUNCAVEIS = (
    "titulo",
    "resumo_proprio",
    "conteudo_bruto",
    "conteudo_completo",
    "nome_fonte",
    "categoria",
    "autor",
    "pais",
    "estado",
    "cidade",
    "status_revisao",
    # NewsCluster
    "titulo_acontecimento",
    "categoria_dominante",
)

#: Campo acessorio: valor truncado seria pior que a ausencia dele.
CAMPOS_DESCARTAVEIS = ("imagem_url",)

#: Identificador cujo truncamento fabricaria um valor errado -> item recusado.
CAMPOS_RECURSAVEIS = ("url_fonte_original",)


class CampoForaDoLimiteError(ValueError):
    """Valor obrigatorio acima do `max_length` do banco: o item nao pode ser
    persistido sem fabricar um valor diferente do que a fonte publicou.

    `registro_erro()` devolve uma frase com fonte, item e motivo — o motivo e
    obrigatorio porque este erro vira entrada do placar de falhas e nao pode
    virar um generico "algo deu errado".
    """

    def __init__(self, campo: str, valor: Any, limite: int, *, nome_fonte: str = "", identificador: str = ""):
        self.campo = campo
        self.limite = limite
        self.nome_fonte = nome_fonte
        self.identificador = identificador
        tamanho = len(valor) if hasattr(valor, "__len__") else "?"
        super().__init__(
            f"{campo} tem {tamanho} caracteres e o limite do modelo e {limite}; "
            f"valor descartado em vez de truncado (truncar fabricaria outro valor)"
        )

    def registro_erro(self) -> str:
        return (
            f"Item da fonte '{self.nome_fonte or 'desconhecida'}' "
            f"({self.identificador or 'sem identificador'}) descartado: {self}"
        )


# ---------------------------------------------------------------------------
# Truncagem e limpeza de HTML
# ---------------------------------------------------------------------------
#
# A implementacao esta em `catalogo_noticias/limites_texto.py` e e importada
# no topo deste modulo. Ela e compartilhada com `providers/news_source.py` de
# proposito: duas copias de `truncar`/`limpar_html_para_texto` divergem com o
# tempo, e a divergencia aparece exatamente no caminho o exercitado — um item
# grande aceito pelo provider e recusado pelo servico (ou vice-versa).
#
# `limpar_para_texto` fica aqui como a nomeacao do servico, deixando explicito
# que a partir deste ponto o valor e TEXTO, nunca markup.


def limpar_para_texto(valor: Any) -> str:
    """Converte o que veio da fonte externa em TEXTO PURO: remove
    ``<script>``/``<style>`` e todas as outras tags, decodifica entidades
    (``&amp;``, ``&nbsp;``, ``&mdash;``) e colapsa espacos.

    Idempotente: texto puro nao contem tags, entao a segunda passagem nao
    muda nada — importante porque a limpeza e aplicada em mais de uma camada
    (provider e servico). Nunca levanta excecao: um feed corrompido precisa
    virar texto, nao derrubar a ingestao.
    """
    return limpar_html_para_texto("" if valor is None else str(valor))


# ---------------------------------------------------------------------------
# Limites por campo, lidos do modelo
# ---------------------------------------------------------------------------


def _teto_de_aplicacao(campo: str) -> Optional[int]:
    """Teto de aplicacao de um campo cujo field do modelo e ``TextField`` (sem
    ``max_length`` no banco). Para ``CharField`` o teto e o ``max_length`` real
    e o teto de aplicacao nao existe — quem manda e o banco."""
    if campo == "resumo_proprio":
        return _teto_settings("CATALOGO_NOTICIAS_TETO_RESUMO_PROPRIO_CHARS", TETO_RESUMO_PROPRIO_CHARS)
    if campo == "conteudo_bruto":
        return _teto_settings("CATALOGO_NOTICIAS_TETO_CONTEUDO_BRUTO_CHARS", TETO_CONTEUDO_BRUTO_CHARS)
    if campo == "conteudo_completo":
        return _teto_settings(
            "CATALOGO_NOTICIAS_TETO_CONTEUDO_COMPLETO_CHARS", TETO_CONTEUDO_COMPLETO_CHARS
        )
    return None


class _LimitesModelo:
    """Limites por (modelo, campo), lidos da metadada do proprio modelo.

    Montado uma vez, no import deste modulo (nao uma vez por item), para
    manter o custo zero no caminho quente e, principalmente, para garantir
    que o dicionario derive do DDL: um ``max_length`` alterado no modelo
    entra em vigor aqui sozinho.
    """

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], Optional[int]] = {}

    def max_length(self, modelo, campo: str) -> Optional[int]:
        chave = (modelo.__name__, campo)
        if chave not in self._cache:
            self._cache[chave] = modelo._meta.get_field(campo).max_length
        return self._cache[chave]

    def teto(self, modelo, campo: str) -> int:
        """Teto EFETIVO do campo: o ``max_length`` real do modelo quando ele
        existe (manda o banco), o teto de aplicacao quando o campo e
        ``TextField`` (o banco nao manda)."""
        limite = self.max_length(modelo, campo)
        if limite is not None:
            return limite
        aplicacao = _teto_de_aplicacao(campo)
        if aplicacao is None:
            raise KeyError(
                f"{modelo.__name__}.{campo} nao tem max_length nem teto de aplicacao em "
                f"services/limites.py — declare o teto antes de usar este campo."
            )
        return aplicacao


LIMITES = _LimitesModelo()


def limite_de(modelo, campo: str) -> int:
    """Teto efetivo de um campo de texto, em caracteres. API publica: os
    testes medem contra a MESMA fonte de verdade do codigo de producao."""
    return LIMITES.teto(modelo, campo)


# ---------------------------------------------------------------------------
# Aplicacao
# ---------------------------------------------------------------------------


def _tem_campo(instancia, campo: str) -> bool:
    """True se o modelo da instancia tem o campo (o mesmo campo pode existir
    em `NewsItem` e nao em `NewsCluster`)."""
    try:
        instancia._meta.get_field(campo)
    except FieldDoesNotExist:
        return False
    return True


def _truncar_campo(instancia, campo: str) -> None:
    """Aplica limpeza de HTML + truncagem num campo de TEXTO."""
    teto = limite_de(type(instancia), campo)
    atual = getattr(instancia, campo, "") or ""
    # Limpar ANTES de medir: e o texto limpo que vai para o banco, entao e o
    # texto limpo que precisa caber. Medir antes deixaria o banco receber, as
    # vezes, um valor maior que o `varchar(N)`.
    limpo = limpar_para_texto(atual)
    setattr(instancia, campo, truncar(limpo, teto))


def _descartar_campo(instancia, campo: str) -> None:
    """Zera um campo acessorio cujo valor truncado seria pior que a ausencia
    dele (URL de imagem cortada aponta para recurso inexistente)."""
    if getattr(instancia, campo, "") or "":
        setattr(instancia, campo, "")


def _recusar_item(instancia, campo: str) -> None:
    """Levanta ``CampoForaDoLimiteError`` quando um campo IDENTIFICADOR passou
    do limite. Truncar um identificador fabricaria um valor diferente do que a
    fonte publicou, e a rastreabilidade (BRD secao 18) exige o valor real."""
    teto = limite_de(type(instancia), campo)
    valor = getattr(instancia, campo, "") or ""
    if len(str(valor)) > teto:
        raise CampoForaDoLimiteError(
            campo,
            valor,
            teto,
            nome_fonte=str(getattr(instancia, "nome_fonte", "") or ""),
            identificador=str(valor)[:120],
        )


def limitar_textos(instancia) -> None:
    """Aplica a politica de limites de `instancia`` (um ``NewsItem`` ou um
    ``NewsCluster``) IN PLACE, campo a campo.

    Idempotente e sem excecao para os campos truncaveis/descartaveis: rodar
    duas vezes devolve o mesmo resultado. A unica coisa que levanta excecao e
    ``url_fonte_original`` acima do limite — e ai a excecao e a resposta
    CORRETA (o item nao pode ser persistido), nao um defeito.
    """
    for campo in CAMPOS_TRUNCAVEIS:
        if _tem_campo(instancia, campo):
            _truncar_campo(instancia, campo)

    for campo in CAMPOS_DESCARTAVEIS:
        if _tem_campo(instancia, campo):
            _descartar_campo(instancia, campo)

    for campo in CAMPOS_RECURSAVEIS:
        if _tem_campo(instancia, campo):
            _recusar_item(instancia, campo)


def aplicar_limites_news_item(news_item) -> None:
    """Ponto de entrada nominal para ``NewsItem``."""
    limitar_textos(news_item)


def aplicar_limites_news_cluster(cluster) -> None:
    """Ponto de entrada nominal para ``NewsCluster``."""
    limitar_textos(cluster)


def checar_campos_recusaveis(instancia) -> None:
    """So a metade da politica que **nao se pode corrigir em silencio**, sem
    mutar nada: levanta ``CampoForaDoLimiteError`` se algum campo de
    ``CAMPOS_RECURSAVEIS`` passou do limite.

    Existe para os caminhos que precisam **recusar com mensagem** em vez de
    truncar — hoje, o ``ModelForm`` do Admin (P1-01b,
    ``catalogo_noticias/limites_admin.py``). Um ``ModelAdmin.save_model`` que
    levantasse a excecao devolveria HTTP 500 ao operador; um formulario que a
    converte em erro de campo mostra a mensagem no lugar certo. O que o
    formulario exibe ao operador e o que a ingestao faz com o item e a mesma
    decisao, so que dita um passo antes: aqui quem recusa e o formulario,
    la quem recusa e a ingestao.

    Deliberadamente NAO duplica a regra: reusa ``_recusar_item`` e
    ``limite_de``, entao o teto vem da mesma metadada que gera o DDL. Um
    ``max_length`` alterado no modelo vale aqui e na ingestao sem ninguem
    editar dois arquivos.
    """
    for campo in CAMPOS_RECURSAVEIS:
        if _tem_campo(instancia, campo):
            _recusar_item(instancia, campo)


def mensagem_para_erro(exc: BaseException, *, nome_fonte: str = "", identificador: str = "") -> str:
    """Mensagem de log estruturada de uma falha de limite, com o contexto
    minimo para diagnosticar sem reabrir o feed: fonte, identificador do item,
    campo e motivo."""
    if isinstance(exc, CampoForaDoLimiteError):
        return exc.registro_erro()
    return (
        f"Item da fonte '{nome_fonte or 'desconhecida'}' "
        f"({identificador or 'sem identificador'}) falhou: "
        f"{exc.__class__.__name__}: {exc}"
    )


def registrar_falha(
    mensagem: str,
    *,
    nome_fonte: str,
    identificador: str,
    escopo: str,
    exc: Optional[BaseException] = None,
) -> None:
    """Log de ERRO de uma falha isolada de ingestao, sempre com o contexto
    (fonte, item, escopo) e, quando ha excecao, com o traceback.

    Existe para que "isolar a falha" nunca vire "engolir a falha": todo
    ``except`` do pipeline de ingestao que isola passa por aqui.

    Alem do log, a falha e acrescentada ao placar de falhas da execucao em
    curso (`coletar_falhas`), para que o placar de sucesso/falha do fim da
    rodada possa contar tambem as falhas de item — detectadas em camadas
    profundas (`_persistir_grupo`) e que nao chegariam ao chamador sem mudar
    a assinatura dessas funcoes.
    """
    logger.error(
        "Ingestao: falha isolada em %s | fonte=%s | item=%s | %s",
        escopo,
        nome_fonte or "desconhecida",
        identificador or "sem identificador",
        mensagem,
        exc_info=exc,
    )
    # `isinstance(..., list)` e nao `is not None`: fora de `coletar_falhas` o
    # ContextVar devolve o SENTINELA `_SEM_COLETOR`, que nao e None e nao aceita
    # `append` — um `is not None` deixaria qualquer `registrar_falha` fora de
    # uma execucao (ex.: um `except` em codigo de request) estourar
    # `AttributeError` no lugar de so registrar o log.
    falhas = _falhas_execucao.get()
    if isinstance(falhas, list):
        falhas.append(
            {
                "escopo": escopo,
                "fonte": nome_fonte or "desconhecida",
                "item": identificador or "sem identificador",
                "motivo": mensagem,
            }
        )


# ---------------------------------------------------------------------------
# Placar de falhas por execucao
# ---------------------------------------------------------------------------

# Mesmo padrao de `config_robo.cache_por_execucao`: um `ContextVar` isola
# execucoes concorrentes e o token e restaurado no `finally`.
_SEM_COLETOR: object = object()
_falhas_execucao: ContextVar[object] = ContextVar(
    "ingestao_falhas_execucao", default=_SEM_COLETOR
)


@contextmanager
def coletar_falhas():
    """Coleta as falhas isoladas desta execucao para o placar de sucesso/falha.

    Sem este contexto, `registrar_falha` so escreve no log — o que e
    suficiente para diagnostico, mas nao para responder "quantos itens
    entraram e quantos foram recusados" ao operador que olha o registro da
    execucao.
    """
    falhas: list[dict] = []
    token = _falhas_execucao.set(falhas)
    try:
        yield falhas
    finally:
        _falhas_execucao.reset(token)


def falhas_da_execucao() -> list[dict]:
    """Placar de falhas da execucao em curso (vazio fora de `coletar_falhas`)."""
    falhas = _falhas_execucao.get()
    return list(falhas) if isinstance(falhas, list) else []


__all__ = [
    "CAMPOS_DESCARTAVEIS",
    "CAMPOS_RECURSAVEIS",
    "CAMPOS_TRUNCAVEIS",
    "CampoForaDoLimiteError",
    "DESCARTAR_CAMPO",
    "FOLGA_ANTES_DE_LIMPAR_HTML",
    "NewsCluster",
    "NewsItem",
    "RECUSAR_ITEM",
    "SUFIXO_ELLIPSIS",
    "TETO_CONTEUDO_BRUTO_CHARS",
    "TETO_CONTEUDO_COMPLETO_CHARS",
    "TETO_RESUMO_PROPRIO_CHARS",
    "TRUNCAR",
    "aplicar_limites_news_cluster",
    "aplicar_limites_news_item",
    "checar_campos_recusaveis",
    "cortar_em_limite_seguro",
    "limite_de",
    "limitar_textos",
    "limpar_para_texto",
    "mensagem_para_erro",
    "registrar_falha",
    "truncar",
]
