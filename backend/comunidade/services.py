"""Serviço de domínio de comunidade (run 20260902-1506-comunidade-blog)."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils import timezone

from credenciamento.services import pode_publicar

from .models import Comentario, Publicacao, Seguidor


class PermissaoNegadaError(Exception):
    pass


class RespostaAninhadaError(Exception):
    pass


def _checar_nao_bloqueado(user) -> None:
    """
    BRD seção 16 — usuário sob bloqueio de moderação (temporário ou
    permanente) não pode publicar nem comentar. Import LOCAL, mesmo padrão
    já usado por `denunciar()` abaixo (evita import no topo do módulo —
    `moderacao` foi implementado depois de `comunidade` nesta sessão; não é
    dependência circular real).
    """
    from moderacao.services import usuario_esta_bloqueado

    if usuario_esta_bloqueado(user):
        raise PermissaoNegadaError("Sua conta está sob bloqueio de moderação e não pode publicar/comentar.")


def criar_rascunho(autor, **dados) -> Publicacao:
    _checar_nao_bloqueado(autor)
    if not pode_publicar(autor):
        raise PermissaoNegadaError("Usuário não é um jornalista credenciado.")
    return Publicacao.objects.create(autor=autor, status=Publicacao.STATUS_RASCUNHO, **dados)


# Campos que o próprio autor pode editar via `editar_publicacao` — nunca
# `status`/`autor`/`destaque`/`publicado_em` (controlados pelo fluxo de
# publicação/curadoria, não pelo autor diretamente).
CAMPOS_EDITAVEIS_PELO_AUTOR = ["titulo", "conteudo", "categoria", "tags", "news_cluster", "news_item"]


def editar_publicacao(publicacao: Publicacao, autor, **dados) -> Publicacao:
    """
    BRD seção 14 — "Editar conteúdo dentro das regras" é um poder explícito
    do autor credenciado. Gap real encontrado na análise do BRD: só havia
    criação de rascunho e envio para publicação, nenhum caminho para editar
    depois. "Dentro das regras": só o PRÓPRIO autor edita a PRÓPRIA
    publicação (nunca a de outro autor, nem um admin usando este caminho —
    correção editorial por terceiros é responsabilidade de
    `catalogo_noticias`/moderação, não deste endpoint), e só os campos de
    conteúdo (`CAMPOS_EDITAVEIS_PELO_AUTOR`) — nunca status/autor/destaque.
    """
    if publicacao.autor_id != autor.id:
        raise PermissaoNegadaError("Só o autor da publicação pode editá-la.")
    _checar_nao_bloqueado(autor)

    campos_alterados = []
    for campo, valor in dados.items():
        if campo not in CAMPOS_EDITAVEIS_PELO_AUTOR:
            continue
        setattr(publicacao, campo, valor)
        campos_alterados.append(campo)

    if campos_alterados:
        publicacao.save(update_fields=campos_alterados)
    return publicacao


def enviar_para_publicacao(publicacao: Publicacao) -> Publicacao:
    """Critério de aceite 1 — reconfirma o credenciamento no momento do envio, não só na criação."""
    _checar_nao_bloqueado(publicacao.autor)
    if not pode_publicar(publicacao.autor):
        raise PermissaoNegadaError("Autor não está mais credenciado — publicação não pode ser enviada.")
    return publicar(publicacao)


def publicar(publicacao: Publicacao) -> Publicacao:
    publicacao.status = Publicacao.STATUS_PUBLICADO
    publicacao.publicado_em = timezone.now()
    publicacao.save(update_fields=["status", "publicado_em"])
    return publicacao


def comentar(autor, conteudo, *, publicacao=None, news_item=None, resposta_de=None) -> Comentario:
    """Critério de aceite 3."""
    _checar_nao_bloqueado(autor)
    if bool(publicacao) == bool(news_item):
        raise ValidationError("Comentário precisa de exatamente um alvo: publicação OU notícia.")
    if resposta_de is not None and resposta_de.resposta_de_id is not None:
        raise RespostaAninhadaError("Só é permitido 1 nível de resposta.")
    return Comentario.objects.create(
        autor=autor, conteudo=conteudo, publicacao=publicacao, news_item=news_item, resposta_de=resposta_de
    )


def seguir(seguidor, autor) -> Seguidor:
    """Critério de aceite 4 — idempotente via get_or_create."""
    obj, _ = Seguidor.objects.get_or_create(seguidor=seguidor, autor=autor)
    return obj


def deixar_de_seguir(seguidor, autor) -> None:
    Seguidor.objects.filter(seguidor=seguidor, autor=autor).delete()


def denunciar(denunciante, motivo, *, comentario=None, publicacao=None):
    """
    Critério de aceite 7. Import LOCAL (não no topo do módulo): o app
    `moderacao` ainda não existia quando `comunidade` foi implementado nesta
    sessão — importar no topo quebraria o carregamento de `comunidade`
    isoladamente. Sem risco de dependência circular real (moderacao usa
    ContentType genérico, não importa `comunidade`).
    """
    from moderacao.services import denunciar as denunciar_em_moderacao

    return denunciar_em_moderacao(denunciante, motivo, comentario=comentario, publicacao=publicacao)
