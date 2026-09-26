"""
Caminho de escrita pelo **Admin do Django** passa pela politica de limites
(P1-01b — defesa em profundidade do lado da escrita).

O P1-01 fechou a injecao de ``<script>`` em ``NewsItem.titulo`` na camada de
**ingestao** (RSS e LLM). Ele NAO fechou o caminho do **Admin**: medido neste
item, um POST de changeform com ``titulo`` contendo ``</script>`` devolvia
HTTP 302 e o titulo voltava do banco **byte-identico** (evidencia:
``docs/evidencias/p101b-prova-antes.txt``). A razao e simples —
``NewsItemAdmin`` declara ``readonly_fields = ["timestamp_ingestao"]``, logo
``titulo`` e editavel, e ``save_model`` nao chamava ``services.limites``; o
mesmo para ``NewsClusterAdmin.titulo_acontecimento``.

Este modulo existe para que nenhum caminho de escrita do Admin escape da
politica. Ele **nao cria uma politica**: reaproveita
``catalogo_noticias/services/limites.py`` inteiro, incluindo a fonte da
verdade dos tetos (``Model._meta.get_field(campo).max_length`` — a mesma
metadada que gera o DDL). Um ``max_length`` novo no modelo vale aqui sem
ninguem editar este arquivo, exatamente como vale na ingestao.

Por que ``save_model`` e nao ``ModelForm.save()``
-------------------------------------------------
``save_model`` e a **ultima** porta antes do INSERT na tela de mudanca, e e
chamado por TODO POST aceito pelo changeform, inclusive o que vem do
formulario com campo invalido reexibido. Como ``ModelAdmin.save_model`` nao
chama ``full_clean``, e o ponto onde a politica precisa morar de novo —
``services/ingestao.py`` faz exatamente isso, e o comentario la ("a ULTIMA
porta antes do INSERT ... qualquer chamador novo (outro servico, script de
carga, tarefa futura) herdaria a garantia") e o mesmo motivo.

A politica do Admin (decisao, e nao heranca por acidente)
-----------------------------------------------------------
O guarda do P1-01 ja deixou escrito que, **no Admin**, truncar e aceitavel
porque o operador esta vendo e corrigindo. E o que este modulo faz, com uma
condicao que a ingestao nao tem: **o operador tem de ficar sabendo**.

* ``TRUNCAR`` (``titulo``, ``resumo_proprio``, ``categoria``,
  ``titulo_acontecimento``, ...) — o valor e limpo de HTML e cortado com
  elipse, e o Admin emite um aviso dizendo **quais campos** mudaram. O
  operador ve o aviso na propria tela logo apos o redirect, entao o corte
  nunca e silencioso. Nao se usa erro de formulario aqui: erro impede
  salvar, e travar a aprovacao de uma noticia por causa da cauda de um titulo
  trocaria um risco de exibicao por um risco operacional (fila de revisao
  parada).
* ``DESCARTAR_CAMPO`` (``imagem_url``) — mesmo tratamento, tambem avisado.
* ``RECUSAR_ITEM`` (``url_fonte_original``) — **nao se trunca**. Cortar
  ``https://a.test/noticia-de-rio`` nao produziria a mesma materia,
  produziria outra, e a rastreabilidade (BRD secao 18) exige o valor real.
  Aqui a resposta e **recusar com mensagem clara**, e por isso a checagem
  acontece no ``ModelForm`` (``checar_campos_recusaveis``), onde vira erro
  de campo com o texto do motivo. Um ``save_model`` levantando excecao
  devolveria HTTP 500: recusa sem mensagem, pior do que o defeito.

Idempotencia (pre-requisito, nao detalhe)
-----------------------------------------
``limpar_html_para_texto`` e ``truncar`` sao idempotentes por construcao
(``limites_texto.py``). Sem isso, um operador que editasse **apenas**
``status_revisao`` de uma noticia cujo titulo a ingestao ja truncou veria o
titulo re-truncado ou, pior, uma segunda elipse empilhada. ``truncar``
devolve o proprio valor quando ele ja cabe, entao o aviso so aparece quando
algo mudou de verdade — e um operador nunca ve aviso ao mexer so no status.
"""

from __future__ import annotations

import logging

from django.contrib import admin, messages
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.forms.models import ModelForm

from .models import NewsCluster, NewsItem
from .services import limites

logger = logging.getLogger(__name__)

#: Politica por model, lida do modulo em vez de reescrita aqui: uma segunda
#: tabela de campos dentro do Admin seria uma segunda politica — exatamente o
#: que o P1-01 proibe ao extrair `services/limites.py` do pipeline.
APLICAR_LIMITES_POR_MODEL = {
    NewsItem: limites.aplicar_limites_news_item,
    NewsCluster: limites.aplicar_limites_news_cluster,
}

#: Campos de texto comparados antes/depois para produzir o aviso. Derivado
#: das tuas de politica (`CAMPOS_TRUNCAVEIS` + `CAMPOS_DESCARTAVEIS`), e nao
#: uma lista de nomes: um campo novo declarado na politica entra no aviso sem
#: ninguem editar este arquivo.
_CAMPOS_AVISADOS = limites.CAMPOS_TRUNCAVEIS + limites.CAMPOS_DESCARTAVEIS


def _tem_campo(modelo, campo: str) -> bool:
    """True se o modelo tem o campo (o mesmo nome pode existir em `NewsItem`
    e nao em `NewsCluster`)."""
    try:
        modelo._meta.get_field(campo)
    except FieldDoesNotExist:
        return False
    return True


def _campos_avisaveis(modelo) -> list[str]:
    return [campo for campo in _CAMPOS_AVISADOS if _tem_campo(modelo, campo)]


def aplicar_limites_no_admin(instancia) -> list[str]:
    """Aplica a politica de limites a `instancia` (um ``NewsItem`` ou um
    ``NewsCluster``) IN PLACE e devolve as **notas** do que mudou.

    Notas, e nao logs, porque quem chama e o ``ModelAdmin``: o que o operador
    precisa ver e um aviso na tela. Lista vazia = nada mudou = o valor ja
    estava dentro da politica (o caso comum, e o que mantem a edicao legitima
    silenciosa).

    Levanta ``CampoForaDoLimiteError`` se algum campo ``RECUSAR_ITEM`` passou
    do limite. Isso e a resposta correta, nao um defeito — e, no Admin, o
    ``ModelForm`` desta mesma politica ja recusou antes de chegar aqui (ver
    modulo), entao o que resta e a ultima linha de defesa para um chamador que
    nao passe pelo formulario.
    """
    modelo = type(instancia)
    aplicar = APLICAR_LIMITES_POR_MODEL.get(modelo)
    if aplicar is None:
        # Este mixin e opt-in: um ModelAdmin de outro model nao entra aqui e
        # nao vira erro. A politica de `services/limites.py` cobre
        # NewsItem/NewsCluster; a varredura dos demais ModelAdmin esta
        # registrada no relatorio do item (ver `docs/evidencias/`).
        logger.debug(
            "Admin: %s fora da politica de limites do catalogo; nada a aplicar.",
            modelo.__name__,
        )
        return []

    antes = {campo: getattr(instancia, campo, "") for campo in _campos_avisaveis(modelo)}
    aplicar(instancia)  # <- a MESMA politica da ingestao, nao uma copia
    notas = []
    for campo, valor in antes.items():
        depois = getattr(instancia, campo, "")
        if depois != valor:
            notas.append(
                f"'{campo}' foi ajustado pela politica de limites do catalogo "
                f"({len(str(valor or ''))} -> {len(str(depois or ''))} caracteres; "
                f"HTML removido e/ou corte em {limites.limite_de(modelo, campo)}). "
                f"Revise o valor exibido."
            )
    if notas:
        logger.info(
            "Admin: politica de limites ajustou %s(pk=%s): %s",
            modelo.__name__,
            instancia.pk,
            "; ".join(notas),
        )
    return notas


class LimitesModelFormMixin(ModelForm):
    """Recusa, no formulario, o que a politica manda recusar.

    Deliberadamente so isso: e o unico caso em que a resposta correta exige
    que o operador mude o valor. Os campos truncaveis **nao** sao alterados
    aqui — o operador precisa ver o que digitou, e o corte acontece no
    ``save_model`` com aviso. Alterar o valor no ``clean()`` deixaria o campo
    aparentemente aceito sem nenhum rastro, que e o oposto de avisar.

    A checagem reusa ``limites.checar_campos_recusaveis`` — a mesma funcao que
    a ingestao usa, com o mesmo teto lido do modelo.

    **Por que uma instancia-sombra e nao ``self.instance``:** o Django chama
    ``clean()`` a partir de ``_clean_form()``, que roda ANTES de
    ``construct_instance()``. Portanto, em ``clean()`` o ``self.instance``
    ainda tem os valores do BANCO (ou esta vazio num add), nunca o que o
    operador digitou. A sombra carrega so os campos recusaveis, lidos de
    ``cleaned_data`` (ja filtrados pelos validadores do proprio campo), e a
    politica roda nela. Uma instancia nova nao custa query e nao pode ser
    confundida com o objeto que sera salvo.
    """

    def clean(self):
        cleaned_data = super().clean()
        instancia = getattr(self, "instance", None)
        if instancia is not None:
            sombra = type(instancia)()
            for campo in limites.CAMPOS_RECURSAVEIS:
                if _tem_campo(type(sombra), campo):
                    setattr(sombra, campo, cleaned_data.get(campo) or "")
            try:
                limites.checar_campos_recusaveis(sombra)
            except limites.CampoForaDoLimiteError as exc:
                # Erro DE CAMPO, e nao erro de formulario: o operador le a
                # frase logo abaixo do campo e corrige. Um `ValidationError`
                # com dict mapeia para `form.add_error(campo, ...)`.
                raise ValidationError({exc.campo: str(exc)}) from exc
        return cleaned_data


class LimitesAdminMixin:
    """``ModelAdmin`` cujas escritas passam pela politica de limites.

    Aplicar nas subclasses de ``admin.ModelAdmin`` dos modelos que a politica
    de ``services/limites.py`` cobre (``NewsItem``, ``NewsCluster``). Modelos
    fora dessa lista sao ignorados: o mixin nao trava nenhum outro Admin do
    projeto.
    """

    #: `ModelForm` derivado do `ModelAdmin`, com a checagem de recusa. O
    #: `ModelAdmin.form` e so leitura; e aqui que o mixin injeta a sua.
    form = LimitesModelFormMixin

    def save_model(self, request, obj, form, change):
        notas = aplicar_limites_no_admin(obj)
        super().save_model(request, obj, form, change)
        # A mensagem so DEPOIS do save: se o INSERT falhar, a tela
        # reapresenta o formulario e um aviso sobre um registro que nao foi
        # salvo seria mentira. O redirect so acontece em caso de sucesso,
        # entao la a mensagem ja descreve o que ficou no banco.
        for nota in notas:
            self.message_user(request, nota, level=messages.WARNING)


__all__ = [
    "APLICAR_LIMITES_POR_MODEL",
    "LimitesAdminMixin",
    "LimitesModelFormMixin",
    "aplicar_limites_no_admin",
]
