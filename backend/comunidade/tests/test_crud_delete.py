from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from comunidade import services
from comunidade.models import Comentario, Publicacao
from credenciamento.services import decidir, solicitar
from credenciamento.models import SolicitacaoCredenciamento

pytestmark = pytest.mark.django_db

User = get_user_model()


def _usuario(email, papel="free"):
    return User.objects.create_user(email=email, password="senha123", papel=papel)


def _jornalista(email="jorn-del@example.com"):
    usuario = _usuario(email)
    admin = _usuario(f"admin-{email}", papel="admin")
    doc = SimpleUploadedFile("diploma.pdf", b"conteudo", content_type="application/pdf")
    solicitacao = solicitar(usuario, documento=doc)
    decidir(solicitacao, admin, SolicitacaoCredenciamento.STATUS_APROVADO)
    return usuario


def _publicacao(autor):
    return services.criar_rascunho(autor, titulo="T", conteudo="C", tipo=Publicacao.TIPO_OPINIAO)


def test_autor_exclui_propria_publicacao():
    autor = _jornalista()
    pub = _publicacao(autor)
    client = APIClient()
    client.force_authenticate(user=autor)
    resposta = client.delete(f"/api/comunidade/publicacoes/{pub.id}/")
    assert resposta.status_code == 204
    assert not Publicacao.objects.filter(pk=pub.pk).exists()


def test_outro_usuario_nao_exclui_publicacao_alheia():
    autor = _jornalista("a@example.com")
    outro = _jornalista("b@example.com")
    pub = _publicacao(autor)
    client = APIClient()
    client.force_authenticate(user=outro)
    resposta = client.delete(f"/api/comunidade/publicacoes/{pub.id}/")
    assert resposta.status_code == 403
    assert Publicacao.objects.filter(pk=pub.pk).exists()


def test_admin_exclui_publicacao_alheia():
    autor = _jornalista()
    admin = _usuario("admin-del@example.com", papel="admin")
    pub = _publicacao(autor)
    client = APIClient()
    client.force_authenticate(user=admin)
    resposta = client.delete(f"/api/comunidade/publicacoes/{pub.id}/")
    assert resposta.status_code == 204


def test_excluir_publicacao_anonimo_401_e_inexistente_404():
    autor = _jornalista()
    pub = _publicacao(autor)
    anon = APIClient()
    assert anon.delete(f"/api/comunidade/publicacoes/{pub.id}/").status_code == 401
    client = APIClient()
    client.force_authenticate(user=autor)
    assert client.delete("/api/comunidade/publicacoes/999999/").status_code == 404


def test_excluir_publicacao_apaga_comentarios_em_cascata():
    autor = _jornalista()
    pub = _publicacao(autor)
    services.enviar_para_publicacao(pub)
    leitor = _usuario("leitor@example.com")
    comentario = services.comentar(leitor, "ótimo texto", publicacao=pub)
    client = APIClient()
    client.force_authenticate(user=autor)
    assert client.delete(f"/api/comunidade/publicacoes/{pub.id}/").status_code == 204
    assert not Comentario.objects.filter(pk=comentario.pk).exists()


def test_autor_exclui_proprio_comentario():
    autor = _jornalista()
    pub = _publicacao(autor)
    services.enviar_para_publicacao(pub)
    leitor = _usuario("leitor2@example.com")
    comentario = services.comentar(leitor, "texto", publicacao=pub)
    client = APIClient()
    client.force_authenticate(user=leitor)
    resposta = client.delete(f"/api/comunidade/comentarios/{comentario.id}/")
    assert resposta.status_code == 204
    assert not Comentario.objects.filter(pk=comentario.pk).exists()


def test_outro_usuario_nao_exclui_comentario_alheio_mas_admin_sim():
    autor = _jornalista()
    pub = _publicacao(autor)
    services.enviar_para_publicacao(pub)
    leitor = _usuario("leitor3@example.com")
    outro = _usuario("outro@example.com")
    admin = _usuario("admin-com@example.com", papel="admin")
    comentario = services.comentar(leitor, "texto", publicacao=pub)
    client = APIClient()
    client.force_authenticate(user=outro)
    assert client.delete(f"/api/comunidade/comentarios/{comentario.id}/").status_code == 403
    client.force_authenticate(user=admin)
    assert client.delete(f"/api/comunidade/comentarios/{comentario.id}/").status_code == 204


def test_excluir_comentario_anonimo_401_e_inexistente_404():
    leitor = _usuario("leitor4@example.com")
    anon = APIClient()
    assert anon.delete("/api/comunidade/comentarios/1/").status_code == 401
    client = APIClient()
    client.force_authenticate(user=leitor)
    assert client.delete("/api/comunidade/comentarios/999999/").status_code == 404
