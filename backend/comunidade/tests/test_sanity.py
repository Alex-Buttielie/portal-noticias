from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from comunidade import services
from comunidade.models import Comentario, Publicacao, Seguidor
from credenciamento.services import decidir, solicitar
from credenciamento.models import SolicitacaoCredenciamento

pytestmark = pytest.mark.django_db

User = get_user_model()


def _usuario(email):
    return User.objects.create_user(email=email, password="senha123", papel="free")


def _jornalista(email="jorn@example.com"):
    usuario = _usuario(email)
    admin = _usuario(f"admin-{email}")
    doc = SimpleUploadedFile("diploma.pdf", b"conteudo", content_type="application/pdf")
    solicitacao = solicitar(usuario, documento=doc)
    decidir(solicitacao, admin, SolicitacaoCredenciamento.STATUS_APROVADO)
    return usuario


def test_usuario_nao_credenciado_nao_pode_criar_rascunho():
    usuario = _usuario("leitor@example.com")
    with pytest.raises(services.PermissaoNegadaError):
        services.criar_rascunho(usuario, titulo="X", conteudo="Y", tipo=Publicacao.TIPO_OPINIAO)


def test_jornalista_credenciado_publica():
    jornalista = _jornalista()
    rascunho = services.criar_rascunho(
        jornalista, titulo="Análise", conteudo="Texto", tipo=Publicacao.TIPO_ANALISE
    )
    publicada = services.enviar_para_publicacao(rascunho)
    assert publicada.status == Publicacao.STATUS_PUBLICADO
    assert publicada.publicado_em is not None


# ---------------------------------------------------------------------------
# BRD seção 16 — usuário bloqueado por moderação não pode publicar nem
# comentar. Gap real encontrado na análise do BRD (AcaoModeracao registrava
# o bloqueio, mas nada aqui checava isso antes desta correção).
# ---------------------------------------------------------------------------


def test_jornalista_bloqueado_nao_consegue_criar_rascunho():
    from moderacao.models import AcaoModeracao
    from moderacao.services import aplicar_acao

    jornalista = _jornalista("jorn-bloqueado@example.com")
    admin = _usuario("admin-bloqueio@example.com")
    aplicar_acao(jornalista, AcaoModeracao.TIPO_BLOQUEIO_PERMANENTE, "reincidência", aplicado_por=admin)

    with pytest.raises(services.PermissaoNegadaError):
        services.criar_rascunho(jornalista, titulo="X", conteudo="Y", tipo=Publicacao.TIPO_OPINIAO)


def test_jornalista_bloqueado_apos_ja_ter_rascunho_nao_consegue_enviar():
    from moderacao.models import AcaoModeracao
    from moderacao.services import aplicar_acao

    jornalista = _jornalista("jorn-bloqueado2@example.com")
    admin = _usuario("admin-bloqueio2@example.com")
    rascunho = services.criar_rascunho(
        jornalista, titulo="Análise", conteudo="Texto", tipo=Publicacao.TIPO_ANALISE
    )

    aplicar_acao(jornalista, AcaoModeracao.TIPO_BLOQUEIO_TEMP, "spam", aplicado_por=admin)

    with pytest.raises(services.PermissaoNegadaError):
        services.enviar_para_publicacao(rascunho)


def test_autor_edita_a_propria_publicacao():
    """BRD seção 14 — "Editar conteúdo dentro das regras"."""
    jornalista = _jornalista("jorn-edita@example.com")
    rascunho = services.criar_rascunho(
        jornalista, titulo="Título original", conteudo="Texto original", tipo=Publicacao.TIPO_ANALISE
    )

    editada = services.editar_publicacao(rascunho, jornalista, titulo="Título revisado", conteudo="Texto revisado")

    editada.refresh_from_db()
    assert editada.titulo == "Título revisado"
    assert editada.conteudo == "Texto revisado"


def test_outro_usuario_nao_pode_editar_publicacao_alheia():
    jornalista = _jornalista("jorn-dona@example.com")
    outro = _jornalista("jorn-intruso@example.com")
    rascunho = services.criar_rascunho(
        jornalista, titulo="Título", conteudo="Texto", tipo=Publicacao.TIPO_OPINIAO
    )

    with pytest.raises(services.PermissaoNegadaError):
        services.editar_publicacao(rascunho, outro, titulo="Hackeado")


def test_edicao_ignora_campos_fora_da_lista_permitida():
    """`status`/`destaque` não podem ser alterados por este caminho, mesmo se enviados."""
    jornalista = _jornalista("jorn-campos@example.com")
    rascunho = services.criar_rascunho(
        jornalista, titulo="Título", conteudo="Texto", tipo=Publicacao.TIPO_OPINIAO
    )

    editada = services.editar_publicacao(
        rascunho, jornalista, titulo="Novo título", status=Publicacao.STATUS_PUBLICADO, destaque=True
    )

    assert editada.titulo == "Novo título"
    assert editada.status == Publicacao.STATUS_RASCUNHO
    assert editada.destaque is False


def test_usuario_bloqueado_nao_consegue_comentar():
    from moderacao.models import AcaoModeracao
    from moderacao.services import aplicar_acao

    usuario = _usuario("leitor-bloqueado@example.com")
    admin = _usuario("admin-bloqueio3@example.com")
    jornalista = _jornalista("jorn-alvo-comentario@example.com")
    rascunho = services.criar_rascunho(
        jornalista, titulo="Análise", conteudo="Texto", tipo=Publicacao.TIPO_ANALISE
    )
    publicada = services.enviar_para_publicacao(rascunho)

    aplicar_acao(usuario, AcaoModeracao.TIPO_BLOQUEIO_PERMANENTE, "assédio", aplicado_por=admin)

    with pytest.raises(services.PermissaoNegadaError):
        services.comentar(usuario, "Comentário", publicacao=publicada)


def test_comentario_exige_exatamente_um_alvo():
    jornalista = _jornalista()
    rascunho = services.criar_rascunho(jornalista, titulo="X", conteudo="Y", tipo=Publicacao.TIPO_OPINIAO)
    publicada = services.enviar_para_publicacao(rascunho)
    leitor = _usuario("leitor2@example.com")

    comentario = services.comentar(leitor, "Ótimo texto!", publicacao=publicada)
    assert comentario.publicacao_id == publicada.id

    with pytest.raises(Exception):
        services.comentar(leitor, "Sem alvo")


def test_resposta_aninhada_e_recusada():
    jornalista = _jornalista(email="jorn2@example.com")
    rascunho = services.criar_rascunho(jornalista, titulo="X", conteudo="Y", tipo=Publicacao.TIPO_OPINIAO)
    publicada = services.enviar_para_publicacao(rascunho)
    leitor = _usuario("leitor3@example.com")

    comentario = services.comentar(leitor, "Primeiro nível", publicacao=publicada)
    resposta = services.comentar(leitor, "Resposta", publicacao=publicada, resposta_de=comentario)

    with pytest.raises(services.RespostaAninhadaError):
        services.comentar(leitor, "Resposta da resposta", publicacao=publicada, resposta_de=resposta)


def test_detalhe_de_publicacao_publicada_e_publico():
    from rest_framework.test import APIClient

    jornalista = _jornalista(email="jorn-detalhe@example.com")
    rascunho = services.criar_rascunho(jornalista, titulo="Título", conteudo="Corpo", tipo=Publicacao.TIPO_ANALISE)
    publicada = services.enviar_para_publicacao(rascunho)

    client = APIClient()
    resposta = client.get(f"/api/comunidade/publicacoes/{publicada.id}/")

    assert resposta.status_code == 200
    assert resposta.data["titulo"] == "Título"


def test_detalhe_de_rascunho_nao_e_visivel_a_outro_usuario():
    from rest_framework.test import APIClient

    jornalista = _jornalista(email="jorn-rascunho@example.com")
    rascunho = services.criar_rascunho(jornalista, titulo="Ainda não publicado", conteudo="X", tipo=Publicacao.TIPO_OPINIAO)
    outro_usuario = _usuario("outro@example.com")

    client = APIClient()
    client.force_authenticate(user=outro_usuario)
    resposta = client.get(f"/api/comunidade/publicacoes/{rascunho.id}/")

    assert resposta.status_code == 404


def test_seguir_e_idempotente():
    jornalista = _jornalista(email="jorn3@example.com")
    leitor = _usuario("leitor4@example.com")

    services.seguir(leitor, jornalista)
    services.seguir(leitor, jornalista)

    assert Seguidor.objects.filter(seguidor=leitor, autor=jornalista).count() == 1
