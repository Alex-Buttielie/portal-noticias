"""
ISOLAMENTO DE TENANT B2B — a tentativa de acesso cruzado (backlog P1-13,
workstream WS-12, gate GP-9).

Este arquivo não testa o caminho de sucesso. Testa o **ataque**: o usuário da
empresa A, autenticado de verdade, tenta alcançar, ler, listar, contar, alterar
e apagar dados da empresa B — por id, por listagem e por agregação.

A propriedade central verificada aqui não é só "não vazou", é **"não
descobriu"**: para cada ataque, a resposta do recurso de B tem que ser
INDISTINGUÍVEL da resposta de um id que nunca existiu. Um 403 honesto mas
acompanhado de mensagem vazada ("critério 12 pertence à empresa Y") ainda é um
vazamento; o oráculo é a diferença entre "existe e é proibido" e "não existe".

Os testes de sucesso de A (com acesso legítimo) ficam nos demais arquivos: um
teste de isolamento que passa porque tudo retorna 403 — inclusive para o
dono legítimo — também passaria.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from b2b import services
from b2b.models import CriterioMonitoramento, MembroOrganizacao, Organizacao
from catalogo_noticias.models import NewsItem

pytestmark = pytest.mark.django_db

User = get_user_model()


def _usuario(email, papel="free"):
    return User.objects.create_user(email=email, password="senha123", papel=papel)


def _noticia(titulo, url, categoria="economia", status=NewsItem.STATUS_NAO_APLICAVEL):
    return NewsItem.objects.create(
        titulo=titulo,
        resumo_proprio=f"Resumo de {titulo}",
        conteudo_bruto="Conteudo bruto suficientemente longo para o modelo de resumo.",
        url_fonte_original=url,
        nome_fonte="G1",
        categoria=categoria,
        status_revisao=status,
    )


@pytest.fixture
def duas_empresas():
    """
    Empresa A e Empresa B, com dados deliberadamente idênticos no nome do
    critério: o que importa é que o payload de A e o de B sejam
    indistinguíveis a menos do nome/id da organização — é o que torna o teste
    de cache significativo. Se a chave de cache não tivesse o tenant, B
    receberia o payload de A, e estes dados iguais são justamente o que
    mostra que só o namespace da chave decide.
    """
    admin_a = _usuario("iso-admin-a@example.com")
    admin_b = _usuario("iso-admin-b@example.com")
    membro_a = _usuario("iso-membro-a@example.com")
    membro_b = _usuario("iso-membro-b@example.com")
    alvo_a = _usuario("iso-alvo-a@example.com")

    org_a = services.criar_organizacao_com_admin("Empresa Alfa", admin_a, Organizacao.PLANO_ENTERPRISE)
    org_b = services.criar_organizacao_com_admin("Empresa Beta", admin_b, Organizacao.PLANO_ENTERPRISE)
    services.adicionar_membro(org_a, membro_a, quem_adiciona=admin_a)
    services.adicionar_membro(org_b, membro_b, quem_adiciona=admin_b)

    # Critérios de mesmo tipo/valor nas duas empresas.
    criterio_a = CriterioMonitoramento.objects.create(
        organizacao=org_a, tipo="palavra_chave", valor="acordo", ativo=True
    )
    criterio_b = CriterioMonitoramento.objects.create(
        organizacao=org_b, tipo="palavra_chave", valor="acordo", ativo=True
    )

    _noticia("Acordo é assinado em Brasília", "https://g1/iso-acordo-1")
    _noticia("Outro acordo no Sul", "https://g1/iso-acordo-2", categoria="politica")

    return {
        "org_a": org_a,
        "org_b": org_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "membro_a": membro_a,
        "membro_b": membro_b,
        "alvo_a": alvo_a,
        "criterio_a": criterio_a,
        "criterio_b": criterio_b,
    }


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ---------------------------------------------------------------------------
# 1. TENTATIVA CRUZADA POR ID — o caso clássico
# ---------------------------------------------------------------------------


def test_admin_de_a_nao_exclui_criterio_de_b_e_nao_revela_a_existencia(duas_empresas):
    """
    O teste que vale o lote. DELETE do recurso de B pela URL com o id de B:
      - não pode apagar;
      - a resposta tem que ser byte-a-byte igual à de um id inexistente.
    """
    client = _client(duas_empresas["admin_a"])

    resposta_cruzado = client.delete(f"/api/b2b/criterios/{duas_empresas['criterio_b'].id}/")
    resposta_inexistente = client.delete("/api/b2b/criterios/999999999/")

    assert resposta_cruzado.status_code in (403, 404)
    assert resposta_cruzado.status_code == resposta_inexistente.status_code
    assert resposta_cruzado.content == resposta_inexistente.content
    # A empresa B continua inteira.
    assert CriterioMonitoramento.objects.filter(pk=duas_empresas["criterio_b"].pk).exists()


def test_membro_de_a_nao_exclui_criterio_de_b(duas_empresas):
    client = _client(duas_empresas["membro_a"])
    resposta = client.delete(f"/api/b2b/criterios/{duas_empresas['criterio_b'].id}/")
    assert resposta.status_code in (403, 404)
    assert CriterioMonitoramento.objects.filter(pk=duas_empresas["criterio_b"].pk).exists()


# ---------------------------------------------------------------------------
# 2. TENTATIVA CRUZADA POR LISTAGEM — A não vê nada de B
# ---------------------------------------------------------------------------


def test_listagem_de_criterios_de_a_nao_contem_criterio_de_b(duas_empresas):
    client = _client(duas_empresas["admin_a"])
    resposta = client.get("/api/b2b/criterios/")

    assert resposta.status_code == 200
    ids = {item["id"] for item in resposta.json()}
    assert ids == {duas_empresas["criterio_a"].id}
    assert duas_empresas["criterio_b"].id not in ids
    # Nem o valor monitorado da outra empresa vaza (aqui é igual por
    # construção; o campo `organizacao` também não pode aparecer).
    assert all("organizacao" not in item for item in resposta.json())


def test_listagem_de_membros_de_a_nao_contem_membro_de_b(duas_empresas):
    client = _client(duas_empresas["admin_a"])
    resposta = client.get("/api/b2b/membros/")

    assert resposta.status_code == 200
    emails = {item["email"] for item in resposta.json()}
    assert emails == {duas_empresas["admin_a"].email, duas_empresas["membro_a"].email}
    assert duas_empresas["membro_b"].email not in emails
    assert duas_empresas["admin_b"].email not in emails
    assert all("organizacao" not in item for item in resposta.json())


def test_itens_monitorados_de_a_so_trazem_os_criterios_de_a(duas_empresas):
    client = _client(duas_empresas["admin_a"])
    resposta = client.get("/api/b2b/itens-monitorados/")

    assert resposta.status_code == 200
    assert set(resposta.json().keys()) == {str(duas_empresas["criterio_a"].id)}
    assert str(duas_empresas["criterio_b"].id) not in resposta.json()


def test_resumo_executivo_de_a_nao_fala_da_empresa_b(duas_empresas):
    client = _client(duas_empresas["admin_a"])
    resposta = client.get("/api/b2b/resumo-executivo/")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["organizacao"] == "Empresa Alfa"
    assert "Empresa Beta" not in resposta.content.decode()
    assert [c["valor"] for c in corpo["criterios"]] == ["acordo"]


# ---------------------------------------------------------------------------
# 3. TENTATIVA CRUZADA DE ESCRITA — não altero nada de B
# ---------------------------------------------------------------------------


def test_admin_de_a_nao_convida_membro_que_ja_esta_em_b_e_nao_revela_o_motivo(duas_empresas):
    """
    Convidar o e-mail de um usuário de B é uma escrita que tentaria mover
    alguém para A. Precisa falhar — e falhar SEM dizer que o usuário existe
    nem que pertence a B.
    """
    client = _client(duas_empresas["admin_a"])
    resposta = client.post(
        "/api/b2b/membros/", {"email": duas_empresas["membro_b"].email}, format="json"
    )

    assert resposta.status_code == 400
    detalhe = resposta.json()["detail"]
    assert "Empresa Beta" not in detalhe
    # A mensagem antiga (409) afirmava a existência do vínculo: "Este usuário
    # JÁ PERTENCE a uma organização". A neutra diz o que verificar
    # ("ainda NÃO pertence"), que é instrução, não resposta.
    assert "já pertence a uma organização" not in detalhe
    # E a organização de B não mudou: o membro continua em B.
    assert MembroOrganizacao.objects.get(user=duas_empresas["membro_b"]).organizacao_id == (
        duas_empresas["org_b"].id
    )


def test_admin_de_a_nao_remove_membro_de_b(duas_empresas):
    client = _client(duas_empresas["admin_a"])
    resposta = client.delete(
        "/api/b2b/membros/", {"email": duas_empresas["membro_b"].email}, format="json"
    )

    # 204 como no caso "usuário não existe" — não confirma nada.
    assert resposta.status_code == 204
    assert MembroOrganizacao.objects.filter(
        organizacao=duas_empresas["org_b"], user=duas_empresas["membro_b"]
    ).exists()


def test_admin_de_a_nao_cria_criterio_em_b_via_payload(duas_empresas):
    """
    O payload traz `organizacao` explícita tentando fixar o tenant: o
    serializer nem tem o campo, e a criação usa a organização do usuário.
    """
    client = _client(duas_empresas["admin_a"])
    antes = CriterioMonitoramento.objects.filter(organizacao=duas_empresas["org_b"]).count()
    resposta = client.post(
        "/api/b2b/criterios/",
        {"tipo": "palavra_chave", "valor": "invadido", "organizacao": duas_empresas["org_b"].id},
        format="json",
    )
    assert resposta.status_code == 201
    assert CriterioMonitoramento.objects.filter(organizacao=duas_empresas["org_b"]).count() == antes
    criado = CriterioMonitoramento.objects.get(valor="invadido")
    assert criado.organizacao_id == duas_empresas["org_a"].id


# ---------------------------------------------------------------------------
# 4. INDISTINGUÍVEL — o oráculo de existência
# ---------------------------------------------------------------------------


def test_falha_de_convite_e_indistinguivel_entre_os_dois_motivos(duas_empresas):
    """
    As duas causas de falha de convite — e-mail não cadastrado na plataforma
    e e-mail de quem já pertence a outra organização — produzem status e
    corpo IDÊNTICOS. Sem isso, o par (400, 409)/(404, 409) é um oráculo de
    enumeração de contas: qualquer membro de qualquer empresa probe e-mails e
    descobre quem tem conta e de que empresa é.
    """
    _usuario("iso-inexistente@example.com")  # cadastro, mas SEM organização
    client = _client(duas_empresas["admin_a"])

    sem_conta = client.post("/api/b2b/membros/", {"email": "ninguem@exemplo.com"}, format="json")
    em_outra_org = client.post(
        "/api/b2b/membros/", {"email": duas_empresas["membro_b"].email}, format="json"
    )

    assert sem_conta.status_code == em_outra_org.status_code == 400
    assert sem_conta.json() == em_outra_org.json()
    assert "Empresa Beta" not in em_outra_org.content.decode()


def test_membro_comum_nao_obtem_oracular_de_convite(duas_empresas):
    """
    Um `membro` (não admin) nem chega à busca por e-mail: recebe 403 para
    qualquer e-mail, cadastrado ou não. Antes da P1-13 a guarda vivia dentro
    de `services.adicionar_membro`, ou seja, DEPOIS da busca — o membro
    recebia 404/409/403 distinguíveis.
    """
    client = _client(duas_empresas["membro_a"])
    _usuario("iso-cadastrado-sem-org@example.com")

    cadastrado_sem_org = client.post(
        "/api/b2b/membros/", {"email": "iso-cadastrado-sem-org@example.com"}, format="json"
    )
    inexistente = client.post("/api/b2b/membros/", {"email": "nada@exemplo.com"}, format="json")
    em_outra_org = client.post(
        "/api/b2b/membros/", {"email": duas_empresas["membro_b"].email}, format="json"
    )

    assert cadastrado_sem_org.status_code == inexistente.status_code == em_outra_org.status_code == 403
    assert cadastrado_sem_org.json() == inexistente.json() == em_outra_org.json()
    # Nenhum convite foi criado.
    assert MembroOrganizacao.objects.count() == 4


# ---------------------------------------------------------------------------
# 5. CONTAGEM — "não confie no filtro da view para query que vaza contagem"
# ---------------------------------------------------------------------------


def test_contagem_de_criterios_de_a_nao_inclui_criterios_de_b(duas_empresas):
    """
    `resumo_executivo.numero_itens` e a contagem de critérios ATIVOS são as
    duas agregações do painel. Se qualquer uma delas esquecesse o filtro de
    tenant, A veria o volume de B — o vazamento mais discreto dos três, e o
    que o filtro de view não cobre sozinho.
    """
    from b2b import limites

    client = _client(duas_empresas["admin_a"])
    corpo = client.get("/api/b2b/resumo-executivo/").json()

    assert corpo["criterios_ativos"] == 1
    assert limites.criterios_ativos_da_organizacao(duas_empresas["org_a"]) == 1
    # O total de itens do critério de A é o de A: os dois critérios casam com
    # as mesmas notícias, mas o total de A não inclui o critério de B.
    assert [c["numero_itens"] for c in corpo["criterios"]] == [2]


def test_itens_monitorados_de_a_nao_soma_o_corpo_do_criterio_de_b(duas_empresas):
    client = _client(duas_empresas["admin_a"])
    corpo = client.get("/api/b2b/itens-monitorados/").json()
    do_a = corpo[str(duas_empresas["criterio_a"].id)]

    assert do_a["total_itens"] == 2
    assert len(do_a["itens"]) == 2
    assert do_a["itens_truncados"] is False


# ---------------------------------------------------------------------------
# 6. SEM ORGANIZAÇÃO E ANÔNIMO — a porta de entrada
# ---------------------------------------------------------------------------


def test_usuario_sem_organizacao_nao_enxerga_nenhum_painel(duas_empresas):
    client = _client(_usuario("iso-sem-org@example.com"))
    for url in (
        "/api/b2b/criterios/",
        "/api/b2b/itens-monitorados/",
        "/api/b2b/resumo-executivo/",
        "/api/b2b/membros/",
    ):
        resposta = client.get(url)
        assert resposta.status_code == 403, url
        assert "Empresa" not in resposta.content.decode(), url


def test_anonimo_nao_enxerga_nenhum_painel(duas_empresas):
    anonimo = APIClient()
    for url in (
        "/api/b2b/criterios/",
        "/api/b2b/itens-monitorados/",
        "/api/b2b/resumo-executivo/",
        "/api/b2b/membros/",
    ):
        assert anonimo.get(url).status_code == 401, url
