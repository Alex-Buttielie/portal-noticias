from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from b2b import services
from b2b.models import CriterioMonitoramento, MembroOrganizacao
from catalogo_noticias.models import NewsItem

pytestmark = pytest.mark.django_db

User = get_user_model()


def _usuario(email):
    return User.objects.create_user(email=email, password="senha123", papel="free")


def test_membro_comum_nao_pode_adicionar_outros():
    admin = _usuario("admin-org@example.com")
    organizacao = services.criar_organizacao_com_admin("Empresa X", admin)
    membro = _usuario("membro-org@example.com")
    novo = _usuario("novo-org@example.com")
    services.adicionar_membro(organizacao, membro, quem_adiciona=admin)

    with pytest.raises(services.PermissaoNegadaError):
        services.adicionar_membro(organizacao, novo, quem_adiciona=membro)


def test_admin_da_organizacao_adiciona_membro_com_sucesso():
    admin = _usuario("admin2-org@example.com")
    organizacao = services.criar_organizacao_com_admin("Empresa Z", admin)
    membro = _usuario("membro2-org@example.com")

    services.adicionar_membro(organizacao, membro, quem_adiciona=admin)

    assert MembroOrganizacao.objects.filter(organizacao=organizacao, user=membro).exists()


def test_isolamento_estrito_entre_organizacoes():
    org_a = services.criar_organizacao("Org A")
    org_b = services.criar_organizacao("Org B")
    usuario_a = _usuario("usera@example.com")
    usuario_b = _usuario("userb@example.com")
    MembroOrganizacao.objects.create(organizacao=org_a, user=usuario_a, papel_na_organizacao=MembroOrganizacao.PAPEL_ADMIN)
    MembroOrganizacao.objects.create(organizacao=org_b, user=usuario_b, papel_na_organizacao=MembroOrganizacao.PAPEL_ADMIN)

    assert services.organizacao_do_usuario(usuario_a).id == org_a.id
    assert services.organizacao_do_usuario(usuario_b).id == org_b.id
    assert services.organizacao_do_usuario(usuario_a).id != services.organizacao_do_usuario(usuario_b).id


def test_admin_convida_membro_por_email_via_api():
    from rest_framework.test import APIClient

    admin = _usuario("admin-api@example.com")
    services.criar_organizacao_com_admin("Empresa API", admin)
    convidado = _usuario("convidado-api@example.com")

    client = APIClient()
    client.force_authenticate(user=admin)
    resposta = client.post("/api/b2b/membros/", {"email": convidado.email}, format="json")

    assert resposta.status_code == 201
    assert MembroOrganizacao.objects.filter(user=convidado).exists()


def test_membro_comum_nao_convida_via_api():
    from rest_framework.test import APIClient

    admin = _usuario("admin-api2@example.com")
    organizacao = services.criar_organizacao_com_admin("Empresa API2", admin)
    membro = _usuario("membro-api2@example.com")
    services.adicionar_membro(organizacao, membro, quem_adiciona=admin)
    alvo = _usuario("alvo-api2@example.com")

    client = APIClient()
    client.force_authenticate(user=membro)
    resposta = client.post("/api/b2b/membros/", {"email": alvo.email}, format="json")

    assert resposta.status_code == 403
    assert not MembroOrganizacao.objects.filter(user=alvo).exists()


def test_convidar_usuario_ja_pertencente_a_outra_organizacao_retorna_conflito():
    from rest_framework.test import APIClient

    admin_a = _usuario("admin-conflito-a@example.com")
    services.criar_organizacao_com_admin("Org Conflito A", admin_a)
    admin_b = _usuario("admin-conflito-b@example.com")
    services.criar_organizacao_com_admin("Org Conflito B", admin_b)

    client = APIClient()
    client.force_authenticate(user=admin_a)
    resposta = client.post("/api/b2b/membros/", {"email": admin_b.email}, format="json")

    assert resposta.status_code == 409


def test_criterio_casa_com_itens_publicaveis():
    organizacao = services.criar_organizacao("Empresa Y")
    NewsItem.objects.create(
        titulo="Empresa Y anuncia expansão",
        resumo_proprio="Resumo",
        conteudo_bruto="Bruto",
        url_fonte_original="https://g1/empresa-y",
        nome_fonte="G1",
        categoria="economia",
        status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
    )
    criterio = services.criar_criterio(organizacao, CriterioMonitoramento.TIPO_EMPRESA, "Empresa Y")

    resultado = services.itens_monitorados(organizacao)

    assert len(resultado[criterio.id]["itens"]) == 1


# ---------------------------------------------------------------------------
# BRD §19 — "Alertas" quando novo conteúdo bate em um critério monitorado.
# Gap real encontrado na análise do BRD.
# ---------------------------------------------------------------------------


def test_alerta_e_enviado_quando_ha_item_novo_e_marca_ultimo_alerta():
    from django.core import mail

    admin = _usuario("admin-alerta@example.com")
    organizacao = services.criar_organizacao_com_admin("Empresa Alerta", admin)
    criterio = services.criar_criterio(organizacao, CriterioMonitoramento.TIPO_EMPRESA, "Empresa Alerta")

    NewsItem.objects.create(
        titulo="Empresa Alerta lança novo produto",
        resumo_proprio="Resumo",
        conteudo_bruto="Bruto",
        url_fonte_original="https://g1/empresa-alerta-1",
        nome_fonte="G1",
        categoria="economia",
        status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
    )

    resultado = services.verificar_e_enviar_alertas()

    assert resultado["total_alertas_enviados"] == 1
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [admin.email]
    criterio.refresh_from_db()
    assert criterio.ultimo_alerta_em is not None


def test_alerta_nao_reenvia_o_mesmo_item_duas_vezes():
    from django.core import mail

    admin = _usuario("admin-alerta2@example.com")
    organizacao = services.criar_organizacao_com_admin("Empresa Alerta 2", admin)
    services.criar_criterio(organizacao, CriterioMonitoramento.TIPO_EMPRESA, "Empresa Alerta 2")
    NewsItem.objects.create(
        titulo="Empresa Alerta 2 é destaque",
        resumo_proprio="Resumo",
        conteudo_bruto="Bruto",
        url_fonte_original="https://g1/empresa-alerta-2",
        nome_fonte="G1",
        categoria="economia",
        status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
    )

    primeiro = services.verificar_e_enviar_alertas()
    segundo = services.verificar_e_enviar_alertas()

    assert primeiro["total_alertas_enviados"] == 1
    assert segundo["total_alertas_enviados"] == 0
    assert len(mail.outbox) == 1


def test_sem_item_novo_nao_envia_alerta():
    admin = _usuario("admin-alerta3@example.com")
    organizacao = services.criar_organizacao_com_admin("Empresa Sem Alerta", admin)
    services.criar_criterio(organizacao, CriterioMonitoramento.TIPO_EMPRESA, "Empresa Sem Alerta")

    resultado = services.verificar_e_enviar_alertas()

    assert resultado["total_alertas_enviados"] == 0
