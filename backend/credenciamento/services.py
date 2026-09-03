"""
Serviço de domínio de credenciamento (implementation-contract.md run
20260902-1503-credenciamento-jornalistas).
"""

from __future__ import annotations

from django.utils import timezone

from .models import PerfilJornalista, SolicitacaoCredenciamento


def solicitar(user, **dados) -> SolicitacaoCredenciamento:
    return SolicitacaoCredenciamento.objects.create(user=user, **dados)


def decidir(
    solicitacao: SolicitacaoCredenciamento,
    decisor,
    novo_status: str,
    motivo: str = "",
) -> SolicitacaoCredenciamento:
    """
    Critério de aceite 2/3: aplica a decisão do admin (aprovar/reprovar/
    pedir informação), registrando quem decidiu e por quê. Aprovação cria
    (ou reativa) o `PerfilJornalista`.
    """
    solicitacao.status = novo_status
    solicitacao.decidido_em = timezone.now()
    solicitacao.decidido_por = decisor
    solicitacao.motivo_decisao = motivo
    solicitacao.save()

    if novo_status == SolicitacaoCredenciamento.STATUS_APROVADO:
        # Copia foto/mini_bio/dados_profissionais da solicitação aprovada
        # para o perfil VIVO — a partir daqui, o jornalista edita o perfil
        # via `atualizar_perfil`, não reabrindo a solicitação (que
        # permanece um registro histórico imutável da candidatura).
        PerfilJornalista.objects.update_or_create(
            user=solicitacao.user,
            defaults={
                "selo_ativo": True,
                "suspenso": False,
                "motivo_suspensao": "",
                "foto": solicitacao.foto,
                "mini_bio": solicitacao.mini_bio,
                "dados_profissionais": solicitacao.dados_profissionais,
            },
        )

    return solicitacao


# Campos que o próprio jornalista pode editar no perfil vivo via
# `atualizar_perfil` — nunca `selo_ativo`/`suspenso`/`motivo_suspensao`
# (controlados por `decidir`/`suspender`/`reativar`, não pelo jornalista).
CAMPOS_PERFIL_EDITAVEIS = ["foto", "mini_bio", "dados_profissionais"]


class PerfilInexistenteError(Exception):
    pass


def atualizar_perfil(user, **dados) -> PerfilJornalista:
    """BRD §14 — "Gerenciar perfil profissional"."""
    perfil = PerfilJornalista.objects.filter(user=user).first()
    if perfil is None:
        raise PerfilInexistenteError("Usuário não tem um perfil de jornalista credenciado.")

    campos_alterados = []
    for campo, valor in dados.items():
        if campo not in CAMPOS_PERFIL_EDITAVEIS:
            continue
        setattr(perfil, campo, valor)
        campos_alterados.append(campo)

    if campos_alterados:
        perfil.save(update_fields=campos_alterados)
    return perfil


def suspender(perfil: PerfilJornalista, motivo: str) -> PerfilJornalista:
    """Critério de aceite 6 — usado também por moderacao-reputacao-governanca.md."""
    perfil.suspenso = True
    perfil.motivo_suspensao = motivo
    perfil.save(update_fields=["suspenso", "motivo_suspensao"])
    return perfil


def reativar(perfil: PerfilJornalista) -> PerfilJornalista:
    perfil.suspenso = False
    perfil.motivo_suspensao = ""
    perfil.save(update_fields=["suspenso", "motivo_suspensao"])
    return perfil


def pode_publicar(user) -> bool:
    """
    Critério de aceite 7 — função pública que qualquer outro módulo
    (`comunidade`) deve usar para checar se um usuário pode publicar
    opinião/análise. Nunca consultar `PerfilJornalista` diretamente fora
    deste app.

    Consulta via `PerfilJornalista.objects.filter(user=user)` (nunca via
    `user.perfil_jornalista`) deliberadamente: bug real encontrado por
    execução de teste real (test_suspender_impede_publicar) — o acessor
    reverso `user.perfil_jornalista` fica CACHEADO na instância de `user`
    assim que qualquer código atribui o lado direto do OneToOneField (ex.:
    `PerfilJornalista.objects.update_or_create(user=..., ...)` em
    `decidir()`), mesmo sem `user.perfil_jornalista` nunca ter sido acessado
    explicitamente antes. Se o perfil for suspenso DEPOIS disso (via uma
    instância obtida por outra query), o cache no `user` continua
    apontando para o objeto antigo, não suspenso — `pode_publicar`
    retornaria `True` para um jornalista suspenso. Uma query direta pelo
    manager nunca sofre desse problema.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    perfil = PerfilJornalista.objects.filter(user=user).first()
    if perfil is None:
        return False
    return perfil.credenciamento_valido
