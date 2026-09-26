"""
Fallback LOCAL e DETERMINISTICO do `SummarizationProvider` — P1-02
(workstream WS-08, gate GP-5).

Por que este modulo existe
--------------------------
Antes desta intervencao, a falha do provedor externo (OpenAI/Chat
Completions) levava `services/ingestao.py::_resultado_fallback_erro` a
devolver `ResultadoResumo(resumo="")`, o que em `_persistir_grupo` vira
`status_revisao=pendente` (implementacao-contract.md, criterio de aceite 4) e,
como `feed/services.py::STATUS_PUBLICAVEIS` so expoe `nao_aplicavel`/`aprovado`,
o item **nao chegava ao leitor**. Ou seja: a degradacao produzia um
"rascunho fantasma" — objeto persistido, sumido do feed, sem resumo e sem
nenhum marcador de que houve fallback. Um teste do WIP de outra run pegou
exatamente essa classe de falso verde: o sistema parecia saudavel enquanto
nao publicava nada.

Este modulo produz conteudo por caminho local, **sem rede e sem LLM**.

Regra inegociavel: NAO FABRICAR MATERIA
---------------------------------------
O fallback nao pode inventar fato, numero, cifra ou nome de fonte que nao
esteja no material de origem. Isso e garantido por CONSTRUCAO e verificado
em tempo de execucao por `verificar_sem_fabricacao()`:

1. O texto e montado apenas por CONCATENACAO de (a) trechos VERBATIM do
   material de origem (`titulo`, `nome_fonte`, `categoria`, `pais_fonte`,
   `estado_fonte`) e (b) frases de SCAFFOLDING fixas, definidas nas
   constantes `_*` abaixo — que nao contem nenhum dado e nunca mudam.
2. `verificar_sem_fabricacao()` reconstrói essa separacao em tempo de execucao:
   toda palavra do resumo que NAO pertence ao scaffolding tem de existir no
   material de origem; e nenhum digito pode aparecer no resumo sem existir
   no material. Se a verificacao falhar, o gerador NAO preenche: devolve
   "material insuficiente" e deixa a decisao para a revisao humana
   (motivo `conteudo_insuficiente`).

MARKER DE ORIGEM (sem migration)
-------------------------------
O item persistido carrega o marcador em `NewsItem.tags` (JSONField de lista
de strings, ja existente e best-effort) com o prefixo reservado
`p1-02:`. Escolha e implicacoes:

* REAPROVEITAR `tags` em vez de criar coluna: nenhum `migrations/` novo e
  criado nesta intervencao (as migracoes existentes sao intocadas por
  decisao de escopo), e o marcador fica consultavel por ORM
  (`NewsItem.objects.filter(tags__contains=[TAG_ORIGEM_FALLBACK])`),
  duravel entre reinicios, e ja viaja para a UI que expoe `tags`.
* O prefixo `p1-02:` marca o marcador como TECNICO. `feed/busca.py`
  ignora tags com esse prefixo no calculo de relevancia (um marcador de
  provenance nunca deve influenciar a busca do leitor) e
  `painel_admin/serializers.py` expoe o marcador de forma explicita na
  fila editorial.
* SEGUIMENTO REPORTADO (nao feito aqui, por exigir migration): um campo
  dedicado `NewsItem.origem_resumo` (choices) + `NewsItem.motivo_fallback`
  daria uma coluna de primeira classe, indexada e sem os efeitos colaterais
  de reaproveitar `tags`. Ver o relatorio do executor.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

from .news_source import ItemBruto

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rotulos de motivo (metrica + marcador persistido + log).
#
# `sem_credencial`, `timeout`, `erro_http`, `rate_limit` e
# `conteudo_insuficiente` sao os rotulos exigidos pelo backlog P1-02.
# `resposta_invalida`, `erro_do_provider` e `teto_de_gasto` sao extensoes
# honestas: umbrella-generica demais ("erro de qualquer tipo") seria exatamente
# o tipo de rotulo que impede o diagnostico, e `teto_de_gasto` e um
# fail-safe de CUSTO (nao de falha do provedor) que hoje passa pelo mesmo
# caminho de fallback e precisa ser distinguivel dele.
# ---------------------------------------------------------------------------
MOTIVO_SEM_CREDENCIAL = "sem_credencial"
MOTIVO_TIMEOUT = "timeout"
MOTIVO_ERRO_HTTP = "erro_http"
MOTIVO_RATE_LIMIT = "rate_limit"
MOTIVO_CONTEUDO_INSUFICIENTE = "conteudo_insuficiente"
MOTIVO_RESPOSTA_INVALIDA = "resposta_invalida"
MOTIVO_ERRO_DO_PROVIDER = "erro_do_provider"
MOTIVO_TETO_DE_GASTO = "teto_de_gasto"
MOTIVO_APLICADO = "aplicado"

MOTIVOS_CONHECIDOS = frozenset(
    {
        MOTIVO_SEM_CREDENCIAL,
        MOTIVO_TIMEOUT,
        MOTIVO_ERRO_HTTP,
        MOTIVO_RATE_LIMIT,
        MOTIVO_CONTEUDO_INSUFICIENTE,
        MOTIVO_RESPOSTA_INVALIDA,
        MOTIVO_ERRO_DO_PROVIDER,
        MOTIVO_TETO_DE_GASTO,
        MOTIVO_APLICADO,
    }
)

# Rotulo usado quando o motivo informado nao e reconhecido: cardinalidade
# limitada de proposito (um rotulo livre permitiria cardinalidade ilimitada
# e, no pior caso, vazar texto sensivel para dentro do nome da metrica).
MOTIVO_DESCONHECIDO = "erro_interno"


# ---------------------------------------------------------------------------
# Marcador de origem persistido em `NewsItem.tags`.
# ---------------------------------------------------------------------------
PREFIXO_TAG_TECNICA = "p1-02:"
TAG_ORIGEM_FALLBACK = f"{PREFIXO_TAG_TECNICA}origem_resumo_fallback_local"
PREFIXO_TAG_MOTIVO = f"{PREFIXO_TAG_TECNICA}motivo_fallback_"


def marcadores_tags(motivo: str) -> list[str]:
    """Tags de provenance a gravar em `NewsItem.tags` para um fallback local."""
    motivo_normalizado = normalizar_motivo(motivo)
    return [TAG_ORIGEM_FALLBACK, f"{PREFIXO_TAG_MOTIVO}{motivo_normalizado}"]


def eh_tag_tecnica(tag: object) -> bool:
    return str(tag or "").startswith(PREFIXO_TAG_TECNICA)


def origem_fallback_local(tags) -> bool:
    """`True` quando as tags do item carregam o marcador de fallback local."""
    return TAG_ORIGEM_FALLBACK in [str(t) for t in (tags or [])]


def motivo_fallback_local(tags) -> str:
    """Motivo do fallback local gravado nas tags ("" quando nao houver)."""
    for tag in tags or []:
        texto = str(tag or "")
        if texto.startswith(PREFIXO_TAG_MOTIVO):
            return texto[len(PREFIXO_TAG_MOTIVO) :]
    return ""


def normalizar_motivo(motivo: object) -> str:
    """Garante que o rotulo usado como metrica/tag pertence ao conjunto conhecido."""
    texto = str(motivo or "").strip()
    return texto if texto in MOTIVOS_CONHECIDOS else MOTIVO_DESCONHECIDO


# ---------------------------------------------------------------------------
# Scaffolding: texto FIXO, sem nenhum dado do material de origem.
# Mudar estas frases exige revisar `verificar_sem_fabricacao`.
# ---------------------------------------------------------------------------
_FRASE_SEM_RESUMO_EDITORIAL = (
    "Resumo editorial nao gerado pelo portal: o servico de sumarizacao nao "
    "estava disponivel na publicacao. O texto integral e a atualizacao de "
    "hoje devem ser lidos na fonte original."
)
_FRASE_FONTE = "Fonte da materia:"
_FRASE_CATEGORIA = "Categoria informada pela fonte:"
_FRASE_LOCALIDADE = "Localidade informada pela fonte:"

# Todas as palavras de scaffolding, normalizadas, para a verificacao
# anti-fabricacao: uma palavra do resumo fora deste conjunto tem de existir
# no material de origem.
_re_palavras = re.compile(r"[0-9A-Za-zÀ-ÿ]+")
_re_digitos = re.compile(r"[0-9]")


def _palavra_normalizada(palavra: str) -> str:
    """Minusculas e sem acento — comparacao insensivel a acentuacao/casing."""
    decomposto = unicodedata.normalize("NFKD", str(palavra or ""))
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return sem_acento.casefold()


_PALAVRAS_SCAFFOLDING: frozenset[str] = frozenset(
    _palavra_normalizada(palavra)
    for frase in (
        _FRASE_SEM_RESUMO_EDITORIAL,
        _FRASE_FONTE,
        _FRASE_CATEGORIA,
        _FRASE_LOCALIDADE,
    )
    for palavra in _re_palavras.findall(frase)
    if _palavra_normalizada(palavra)
)


@dataclass(frozen=True)
class ResultadoFallbackLocal:
    """Saida de `gerar_resumo_local`.

    `suficiente=False` significa "o material de origem nao sustenta um
    resumo honesto": o gerador propositalmente NAO preenche e o item segue
    para revisao humana (resumo vazio) em vez de publicar texto invented.
    """

    resumo: str
    suficiente: bool
    violacoes: tuple[str, ...] = ()

def _limpar(valor: object) -> str:
    return " ".join(str(valor or "").split())


def material_de_origem(item: ItemBruto) -> dict[str, str]:
    """Campos do `ItemBruto` que o fallback tem o direito de reutilizar.

    Deliberadamente NAO inclui `conteudo_bruto`/`conteudo_completo`: o texto
    integral da fonte e exibido pela pagina de detalhe com credito e link
    (BRD secao 18) e nunca pode virar `resumo_proprio` — nem como copia
    literal (o proprio pipeline bloqueia copia/quase-copia em
    `_resumo_e_copia_ou_quase_copia`).
    """
    return {
        "titulo": _limpar(getattr(item, "titulo", "")),
        "fonte": _limpar(getattr(item, "nome_fonte", "")),
        "categoria": _limpar(getattr(item, "categoria", "")),
        "estado": _limpar(getattr(item, "estado_fonte", "")),
        "pais": _limpar(getattr(item, "pais_fonte", "")),
    }


def verificar_sem_fabricacao(resumo: str, item: ItemBruto) -> list[str]:
    """
    Retorna a lista de violacoes anti-fabricacao de `resumo` contra o material
    de origem de `item` (vazia = resumo honesto).

    Duas regras, ambas verificadas em tempo de execucao:

    1. Nenhum digito do resumo pode estar ausente do material de origem
       (nenhum numero/cifra inventado).
    2. Toda palavra do resumo que nao seja palavra de scaffolding tem de
       existir no material de origem (nenhum nome de fonte/entidade/categoria
       inventado).
    """
    if not resumo:
        return []

    campos = material_de_origem(item)
    digitos_da_origem = {c for valor in campos.values() for c in str(valor) if c.isdigit()}

    violacoes: list[str] = []
    digitos_inventados = sorted({c for c in _re_digitos.findall(resumo) if c not in digitos_da_origem})
    if digitos_inventados:
        violacoes.append(f"digitos_ausentes_do_material:{''.join(digitos_inventados)}")

    palavras_da_origem = {
        _palavra_normalizada(palavra)
        for valor in campos.values()
        for palavra in _re_palavras.findall(valor)
        if _palavra_normalizada(palavra)
    }
    palavras_inventadas = sorted(
        {
            palavra
            for palavra in (_palavra_normalizada(p) for p in _re_palavras.findall(resumo))
            if palavra and palavra not in _PALAVRAS_SCAFFOLDING and palavra not in palavras_da_origem
        }
    )
    if palavras_inventadas:
        violacoes.append(f"palavras_ausentes_do_material:{','.join(palavras_inventadas[:5])}")
    return violacoes


def gerar_resumo_local(item: ItemBruto) -> ResultadoFallbackLocal:
    """
    Gera o `resumo` deterministico do fallback local (sem rede, sem LLM).

    Determinismo: a saida depende EXCLUSIVAMENTE dos campos de
    `material_de_origem(item)` — mesma entrada, mesma saida, sempre.

    Retorna `suficiente=False` (resumo vazio) quando o material de origem
    nao sustenta um resumo honesto — o que, para um `NewsItem`, significa
    ausencia de TITULO (a manchete e o unico campo que identifica a noticia;
    `nome_fonte` e obrigatorio por `NewsItem.clean()`, e categoria/localidade
    sao best-effort). Sem manchete nao existe materia a descrever: publicar
    uma entrada cuja unica informacao e "veja a fonte original" seria a
    meia-noticia que este backlog proibe. Nesse caso o item NAO e publicado
    (revisao humana) e o motivo `conteudo_insuficiente` e emitido — o
    fallback sinaliza a falta em vez de preencher.
    """
    campos = material_de_origem(item)

    if not campos["titulo"]:
        return ResultadoFallbackLocal(resumo="", suficiente=False)

    partes: list[str] = []
    if campos["titulo"]:
        partes.append(campos["titulo"].rstrip("."))
    partes.append(_FRASE_SEM_RESUMO_EDITORIAL)
    if campos["fonte"]:
        partes.append(f"{_FRASE_FONTE} {campos['fonte']}.")
    if campos["categoria"]:
        partes.append(f"{_FRASE_CATEGORIA} {campos['categoria']}.")
    localidade = ", ".join(valor for valor in (campos["estado"], campos["pais"]) if valor)
    if localidade:
        partes.append(f"{_FRASE_LOCALIDADE} {localidade}.")

    resumo = " ".join(partes)
    violacoes = verificar_sem_fabricacao(resumo, item)
    if violacoes:
        # Defesa em profundidade: se a montagem violar a regra anti-fabricacao
        # (nao deveria — e por isso que isto e verificado), NAO publicamos o
        # texto. Sinalizamos a insufficiency para a revisao humana.
        logger.error(
            "Fallback local rejeitado por verificacao anti-fabricacao (%s) — "
            "item enviado para revisao humana em vez de publicar texto nao verificavel.",
            "; ".join(violacoes),
        )
        return ResultadoFallbackLocal(resumo="", suficiente=False, violacoes=tuple(violacoes))

    return ResultadoFallbackLocal(resumo=resumo, suficiente=True)


__all__ = [
    "MOTIVOS_CONHECIDOS",
    "MOTIVO_APLICADO",
    "MOTIVO_CONTEUDO_INSUFICIENTE",
    "MOTIVO_DESCONHECIDO",
    "MOTIVO_ERRO_DO_PROVIDER",
    "MOTIVO_ERRO_HTTP",
    "MOTIVO_RATE_LIMIT",
    "MOTIVO_RESPOSTA_INVALIDA",
    "MOTIVO_SEM_CREDENCIAL",
    "MOTIVO_TETO_DE_GASTO",
    "MOTIVO_TIMEOUT",
    "PREFIXO_TAG_MOTIVO",
    "PREFIXO_TAG_TECNICA",
    "TAG_ORIGEM_FALLBACK",
    "ResultadoFallbackLocal",
    "eh_tag_tecnica",
    "gerar_resumo_local",
    "marcadores_tags",
    "material_de_origem",
    "motivo_fallback_local",
    "normalizar_motivo",
    "origem_fallback_local",
    "verificar_sem_fabricacao",
]
