from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from credenciamento import services
from credenciamento.models import PerfilJornalista, SolicitacaoCredenciamento

pytestmark = pytest.mark.django_db

User = get_user_model()


def _usuario(email="jorn@example.com"):
    return User.objects.create_user(email=email, password="senha123", papel="free")


def _documento():
    return SimpleUploadedFile("diploma.pdf", b"conteudo-fake-pdf", content_type="application/pdf")


def test_solicitar_cria_pendente():
    usuario = _usuario()
    solicitacao = services.solicitar(usuario, documento=_documento(), cidade="São Paulo", uf="SP")
    assert solicitacao.status == SolicitacaoCredenciamento.STATUS_PENDENTE


def test_aprovar_cria_perfil_jornalista_e_permite_publicar():
    usuario = _usuario()
    admin = _usuario(email="admin@example.com")
    solicitacao = services.solicitar(usuario, documento=_documento())

    services.decidir(solicitacao, admin, SolicitacaoCredenciamento.STATUS_APROVADO, motivo="ok")

    assert PerfilJornalista.objects.filter(user=usuario, selo_ativo=True).exists()
    assert services.pode_publicar(usuario) is True


def test_reprovar_nao_cria_perfil():
    usuario = _usuario()
    admin = _usuario(email="admin2@example.com")
    solicitacao = services.solicitar(usuario, documento=_documento())

    services.decidir(solicitacao, admin, SolicitacaoCredenciamento.STATUS_REPROVADO, motivo="sem diploma")

    assert not PerfilJornalista.objects.filter(user=usuario).exists()
    assert services.pode_publicar(usuario) is False


def test_suspender_impede_publicar():
    usuario = _usuario()
    admin = _usuario(email="admin3@example.com")
    solicitacao = services.solicitar(usuario, documento=_documento())
    services.decidir(solicitacao, admin, SolicitacaoCredenciamento.STATUS_APROVADO)

    perfil = PerfilJornalista.objects.get(user=usuario)
    services.suspender(perfil, motivo="violação de regras")

    assert services.pode_publicar(usuario) is False


def test_usuario_sem_solicitacao_nao_pode_publicar():
    usuario = _usuario()
    assert services.pode_publicar(usuario) is False


# ---------------------------------------------------------------------------
# BRD §13/§14 — telefone opcional no cadastro básico, e o jornalista
# consegue "gerenciar perfil profissional" depois de aprovado. Gaps reais
# encontrados na análise do BRD.
# ---------------------------------------------------------------------------


def test_solicitacao_aceita_telefone_opcional():
    usuario = _usuario("telefone@example.com")
    solicitacao = services.solicitar(usuario, documento=_documento(), telefone="+55 11 99999-0000")
    assert solicitacao.telefone == "+55 11 99999-0000"


def test_solicitacao_sem_telefone_continua_funcionando():
    usuario = _usuario("sem-telefone@example.com")
    solicitacao = services.solicitar(usuario, documento=_documento())
    assert solicitacao.telefone == ""


def test_aprovacao_copia_bio_e_dados_profissionais_para_o_perfil_vivo():
    usuario = _usuario("perfil-copia@example.com")
    admin = _usuario("admin-copia@example.com")
    solicitacao = services.solicitar(
        usuario,
        documento=_documento(),
        mini_bio="Repórter de política há 10 anos.",
        dados_profissionais="Registro profissional 12345.",
    )

    services.decidir(solicitacao, admin, SolicitacaoCredenciamento.STATUS_APROVADO)

    perfil = PerfilJornalista.objects.get(user=usuario)
    assert perfil.mini_bio == "Repórter de política há 10 anos."
    assert perfil.dados_profissionais == "Registro profissional 12345."


def test_jornalista_aprovado_atualiza_o_proprio_perfil():
    usuario = _usuario("perfil-editavel@example.com")
    admin = _usuario("admin-editavel@example.com")
    solicitacao = services.solicitar(usuario, documento=_documento(), mini_bio="Bio antiga")
    services.decidir(solicitacao, admin, SolicitacaoCredenciamento.STATUS_APROVADO)

    perfil_atualizado = services.atualizar_perfil(usuario, mini_bio="Bio nova e atualizada")

    perfil_atualizado.refresh_from_db()
    assert perfil_atualizado.mini_bio == "Bio nova e atualizada"


def test_atualizar_perfil_sem_credenciamento_levanta_erro():
    usuario = _usuario("sem-perfil@example.com")
    with pytest.raises(services.PerfilInexistenteError):
        services.atualizar_perfil(usuario, mini_bio="Tentativa")


def test_atualizar_perfil_ignora_campos_fora_da_lista_permitida():
    usuario = _usuario("perfil-campos@example.com")
    admin = _usuario("admin-campos@example.com")
    solicitacao = services.solicitar(usuario, documento=_documento())
    services.decidir(solicitacao, admin, SolicitacaoCredenciamento.STATUS_APROVADO)

    perfil_atualizado = services.atualizar_perfil(usuario, mini_bio="Nova bio", suspenso=True, selo_ativo=False)

    assert perfil_atualizado.mini_bio == "Nova bio"
    assert perfil_atualizado.suspenso is False
    assert perfil_atualizado.selo_ativo is True
