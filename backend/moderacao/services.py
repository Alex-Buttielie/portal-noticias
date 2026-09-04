"""Serviço de domínio de moderação/reputação (run 20260902-1510-moderacao-reputacao-governanca)."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import AcaoModeracao, Denuncia, RecursoModeracao, Reputacao, ReputacaoEventoLog

# Delta de reputação por tipo de ação — valores de referência (task-plan.md,
# "Suposições assumidas"), não a decisão final de produto.
DELTA_POR_TIPO_ACAO = {
    AcaoModeracao.TIPO_AVISO: -5,
    AcaoModeracao.TIPO_REMOCAO: -15,
    AcaoModeracao.TIPO_BLOQUEIO_TEMP: -30,
    AcaoModeracao.TIPO_BLOQUEIO_PERMANENTE: -100,
}


def denunciar(denunciante, motivo, *, comentario=None, publicacao=None) -> Denuncia:
    """Critério de aceite 1."""
    alvo = comentario or publicacao
    if alvo is None:
        raise ValueError("Informe 'comentario' ou 'publicacao' para denunciar.")
    return Denuncia.objects.create(
        denunciante=denunciante,
        motivo=motivo or Denuncia.MOTIVO_OUTRO,
        content_type=ContentType.objects.get_for_model(alvo),
        object_id=alvo.pk,
    )


def fila_de_moderacao():
    """
    Critério de aceite 2: fila pendente, priorizada por reputação do
    denunciante (não usada como único critério de DECISÃO — só de ordenação
    de fila, ver `services.aplicar_acao`, que sempre exige um moderador
    humano). Achado de revisão: a implementação original era FIFO puro, sem
    nenhuma referência a reputação, contrariando este próprio docstring e o
    requisito funcional 2 do spec — corrigido para de fato ordenar por
    reputação do denunciante primeiro (denúncias de usuários mais confiáveis
    aparecem antes), com `criado_em` como desempate.
    """
    return (
        Denuncia.objects.filter(status=Denuncia.STATUS_PENDENTE)
        .annotate(_reputacao_denunciante=Coalesce("denunciante__reputacao__pontuacao", Value(100)))
        .order_by("-_reputacao_denunciante", "criado_em")
    )


def resolver_denuncia(denuncia: Denuncia, moderador, procedente: bool, motivo: str = "") -> Denuncia:
    """Critério de aceite 3."""
    denuncia.status = Denuncia.STATUS_PROCEDENTE if procedente else Denuncia.STATUS_IMPROCEDENTE
    denuncia.resolvido_em = timezone.now()
    denuncia.resolvido_por = moderador
    denuncia.resolucao_motivo = motivo
    denuncia.save()
    return denuncia


def registrar_evento_reputacao(user, delta: int, motivo: str) -> Reputacao:
    reputacao, _ = Reputacao.objects.get_or_create(user=user)
    reputacao.pontuacao += delta
    reputacao.save(update_fields=["pontuacao", "atualizado_em"])
    ReputacaoEventoLog.objects.create(user=user, delta=delta, motivo=motivo)
    return reputacao


def obter_reputacao(user) -> Reputacao:
    reputacao, _ = Reputacao.objects.get_or_create(user=user)
    return reputacao


class UsuarioBloqueadoError(Exception):
    pass


def usuario_esta_bloqueado(user) -> bool:
    """
    BRD seção 16 — "Bloqueios temporários e permanentes" precisa ter efeito
    de verdade, não só ficar registrado em `AcaoModeracao`. Gap real
    encontrado na análise do BRD: nada no sistema consultava isto antes de
    permitir publicar/comentar. Ponto único de verdade — qualquer código que
    precise checar se um usuário está bloqueado deve chamar esta função,
    nunca consultar `AcaoModeracao` diretamente.

    Bloqueio permanente: sempre ativo. Bloqueio temporário: ativo se
    `ativo_ate` for nulo (sem data de término definida — tratado como ainda
    em vigor, nunca expira "sozinho" por omissão) ou ainda estiver no
    futuro.
    """
    agora = timezone.now()
    return AcaoModeracao.objects.filter(
        usuario_alvo=user, tipo=AcaoModeracao.TIPO_BLOQUEIO_PERMANENTE
    ).exists() or AcaoModeracao.objects.filter(
        usuario_alvo=user, tipo=AcaoModeracao.TIPO_BLOQUEIO_TEMP
    ).filter(Q(ativo_ate__isnull=True) | Q(ativo_ate__gt=agora)).exists()


def aplicar_acao(
    usuario_alvo,
    tipo: str,
    motivo: str,
    aplicado_por,
    *,
    ativo_ate=None,
    denuncia: Denuncia | None = None,
) -> AcaoModeracao:
    """
    Critérios de aceite 4 e 6: `aplicado_por` é OBRIGATÓRIO e sempre um
    usuário humano (moderador/admin) — não existe caminho de chamada desta
    função sem um decisor explícito, então reputação nunca decide sozinha.
    """
    if aplicado_por is None:
        raise ValueError("Toda ação de moderação exige um moderador humano responsável.")

    acao = AcaoModeracao.objects.create(
        usuario_alvo=usuario_alvo,
        tipo=tipo,
        motivo=motivo,
        aplicado_por=aplicado_por,
        denuncia_relacionada=denuncia,
        ativo_ate=ativo_ate,
    )
    delta = DELTA_POR_TIPO_ACAO.get(tipo, 0)
    if delta:
        registrar_evento_reputacao(usuario_alvo, delta, motivo=f"Ação de moderação: {tipo}")

    if tipo == AcaoModeracao.TIPO_REMOCAO and denuncia is not None:
        _ocultar_conteudo_denunciado(denuncia)

    return acao


def _ocultar_conteudo_denunciado(denuncia: Denuncia) -> None:
    """
    Achado de revisão de segurança (blocker, BRD §16): uma ação de tipo
    "remocao_conteudo" só descontava reputação — o Comentario/Publicacao
    denunciado continuava 100% visível nas listagens públicas. Usa o
    GenericForeignKey `denuncia.alvo` (nunca importa `comunidade` aqui, ver
    comentário em models.py) para setar o mesmo campo `oculto` que existe em
    ambos os models denunciáveis. O registro em si nunca é apagado (BRD §16,
    requisito 8 — "não apagar silenciosamente"): fica fora das listagens
    públicas, mas auditável via AcaoModeracao/Denuncia.
    """
    alvo = denuncia.alvo
    if alvo is None or not hasattr(alvo, "oculto"):
        return
    alvo.oculto = True
    alvo.ocultado_em = timezone.now()
    alvo.save(update_fields=["oculto", "ocultado_em"])


def criar_recurso(acao: AcaoModeracao, usuario, texto: str) -> RecursoModeracao:
    """Critério de aceite 5."""
    return RecursoModeracao.objects.create(acao=acao, usuario=usuario, texto=texto)
