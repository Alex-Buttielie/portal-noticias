"""
Matriz de papéis/permissões do B2B (backlog P1-13 — workstream WS-12).

Este módulo é a fonte única de verdade de "quem pode fazer o quê" no app
B2B. Ele não inventa um sistema de papéis paralelo: o papel continua sendo o
campo que já existe, `MembroOrganizacao.papel_na_organizacao`, com os dois
valores do model (`admin_organizacao` e `membro`). O que existia antes era o
papel aplicado num único ponto, dentro de `services.adicionar_membro` /
`services.remover_membro` — isto é, a autorização de membros era implícita,
late e dependente de o handler chegar até lá. Hoje ela é explícita, está
escrita aqui, e é verificada ANTES de qualquer leitura ou escrita do handler.

Matriz (a política, em uma tabela)
----------------------------------
======================  ==========================  =====================
Ação                    admin_organizacao           membro
======================  ==========================  =====================
ver o próprio painel    sim                         sim
criar critério          sim                         sim
excluir critério        sim                         sim
ver membros             sim                         sim
convidar membro         sim                         NÃO
remover membro          sim                         NÃO
rebaixar/promover papel sim                         NÃO
======================  ==========================  =====================

Racional de produto: o painel é de monitoramento de mídia — qualquer
analista da empresa precisa cadastrar a palavra-chave que quer acompanhar.
O que é sensível é a **composição da empresa** (quem entra, com que papel),
e isso é privativo do administrador. Note que esta matriz **preserva o
comportamento efetivo atual** de `b2b/views.py`: até aqui qualquer membro da
organização já criava/excluía critérios; o que faltava era isso estar
escrito, testado e garantido antes do handler.

O papel de plataforma (`User.papel` em `identidade/`: free/premium/admin) é
outra dimensão e não é usado aqui: nenhuma regra B2B depende dele, e
`metricas/views.py` já restringe as métricas de negócio (que contam
organizações) a `papel == "admin"`.
"""

from __future__ import annotations

from .models import MembroOrganizacao


class PermissaoNegadaError(Exception):
    """
    Falha de autorização dentro do domínio. As views traduzem para 403 com
    `str(exc)` como `detail` — a mensagem é sobre o papel do REQUISITANTE,
    nunca sobre a existência do recurso alvo (ver `b2b/tests/
    test_isolamento_tenant.py`).
    """


#: Ações gerenciadas só pelo administrador da organização.
APENAS_ADMIN = frozenset(
    {
        "convidar_membro",
        "remover_membro",
        "alterar_papel_membro",
    }
)

#: Ações liberadas a qualquer membro da organização (inclusive o admin).
QUALQUER_MEMBRO = frozenset(
    {
        "ver_painel",
        "criar_criterio",
        "excluir_criterio",
        "ver_membros",
    }
)


def membro_da_organizacao(user, organizacao):
    """
    `MembroOrganizacao` do usuário NA organização, ou `None`.

    A consulta é escopada nos dois eixos (usuário E organização): é a mesma
    checagem usada para autorizar, então um usuário de outra empresa nunca
    produz um objeto de membro daqui.
    """
    if not getattr(user, "is_authenticated", False):
        return None
    if getattr(organizacao, "pk", None) is None:
        return None
    return MembroOrganizacao.objects.filter(user=user, organizacao=organizacao).first()


def eh_admin_da_organizacao(user, organizacao) -> bool:
    membro = membro_da_organizacao(user, organizacao)
    return bool(membro and membro.papel_na_organizacao == MembroOrganizacao.PAPEL_ADMIN)


def pode(user, organizacao, acao: str) -> bool:
    """
    `True` se `user` pode executar `acao` em `organizacao`.

    Convite: uma organização é composta só de usuários **dentro** dela, então
    o convite é uma ação interna. Um membro comum poderia trazer para dentro
    qualquer conta da plataforma — incluindo o admin de outra organização —
    o que o tornaria um elevador de privilégio cross-tenant. Daí exigir
    `admin_organizacao`.
    """
    if acao in QUALQUER_MEMBRO:
        return membro_da_organizacao(user, organizacao) is not None
    if acao in APENAS_ADMIN:
        return eh_admin_da_organizacao(user, organizacao)
    raise ValueError(f"Ação B2B desconhecida: {acao!r}")


def exigir(user, organizacao, acao: str) -> None:
    """Levanta `PermissaoNegadaError` se `user` não pode executar `acao`."""
    if pode(user, organizacao, acao):
        return
    if acao in APENAS_ADMIN:
        raise PermissaoNegadaError("Só o administrador da organização pode fazer isso.")
    raise PermissaoNegadaError("Usuário não pertence a esta organização.")
