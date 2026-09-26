"""
PAPEIS E PERMISSÕES B2B — a matriz aplicada (backlog P1-13, workstream WS-12).

O papel é o que já existia: `MembroOrganizacao.papel_na_organizacao`, com
`admin_organizacao` e `membro`. Nada de sistema paralelo foi inventado (e
nenhum papel novo pode ser adicionado aqui sem migration — ver o relatório).

Este arquivo fixa a matriz declarada em `b2b/permissions.py` em três níveis,
porque os três já falharam de formas diferentes em algum momento:

1. **Unidade** — `permissions.pode()` para cada (papel, ação).
2. **Endpoint** — a mesma matriz pelo HTTP, com o usuário real de cada papel.
   É aqui que o teste vale: prova que a checagem acontece ANTES do handler
   tocar no banco, e não por acidente dentro do serviço.
3. **Invariante** — a organização nunca fica sem administrador.

Um teste de papel só tem valor se o caso PROIBIDO também estiver no arquivo.
Por isso a matriz é percorrida em bloco, e não caso a caso.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from b2b import services
from b2b.models import MembroOrganizacao, Organizacao
from b2b.permissions import PermissaoNegadaError, pode, exigir

pytestmark = pytest.mark.django_db

User = get_user_model()

# (papel, ação, permitido?) — espelha a tabela de `b2b/permissions.py`.
MATRIZ = [
    (MembroOrganizacao.PAPEL_ADMIN, "ver_painel", True),
    (MembroOrganizacao.PAPEL_ADMIN, "ver_membros", True),
    (MembroOrganizacao.PAPEL_ADMIN, "criar_criterio", True),
    (MembroOrganizacao.PAPEL_ADMIN, "excluir_criterio", True),
    (MembroOrganizacao.PAPEL_ADMIN, "convidar_membro", True),
    (MembroOrganizacao.PAPEL_ADMIN, "remover_membro", True),
    (MembroOrganizacao.PAPEL_ADMIN, "alterar_papel_membro", True),
    (MembroOrganizacao.PAPEL_MEMBRO, "ver_painel", True),
    (MembroOrganizacao.PAPEL_MEMBRO, "ver_membros", True),
    (MembroOrganizacao.PAPEL_MEMBRO, "criar_criterio", True),
    (MembroOrganizacao.PAPEL_MEMBRO, "excluir_criterio", True),
    (MembroOrganizacao.PAPEL_MEMBRO, "convidar_membro", False),
    (MembroOrganizacao.PAPEL_MEMBRO, "remover_membro", False),
    (MembroOrganizacao.PAPEL_MEMBRO, "alterar_papel_membro", False),
]


def _usuario(email):
    return User.objects.create_user(email=email, password="senha123", papel="free")


def _org_com_os_dois_papeis(nome):
    admin = _usuario(f"papeis-{nome}-admin@example.com")
    membro = _usuario(f"papeis-{nome}-membro@example.com")
    organizacao = services.criar_organizacao_com_admin(nome, admin, Organizacao.PLANO_ENTERPRISE)
    services.adicionar_membro(organizacao, membro, quem_adiciona=admin)
    return organizacao, admin, membro


# ---------------------------------------------------------------------------
# 1. A matriz, em nível de unidade
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("papel,acao,permitido", MATRIZ, ids=[f"{p}-{a}-{r}" for p, a, r in MATRIZ])
def test_matriz_de_permissoes_por_papel(papel, acao, permitido):
    """Cada célula da matriz, para os dois papéis que existem."""
    organizacao, admin, membro = _org_com_os_dois_papeis(f"matriz-{papel}-{acao}")
    alvo = admin if papel == MembroOrganizacao.PAPEL_ADMIN else membro

    assert pode(alvo, organizacao, acao) is permitido
    if permitido:
        exigir(alvo, organizacao, acao)  # não levanta
    else:
        with pytest.raises(PermissaoNegadaError):
            exigir(alvo, organizacao, acao)


def test_acao_desconhecida_e_erro_de_programacao_nao_permissao_negada():
    """Uma ação fora da matriz falha alto, em vez de ser liberada por omissão."""
    organizacao, admin, _ = _org_com_os_dois_papeis("acao-desconhecida")
    with pytest.raises(ValueError):
        pode(admin, organizacao, "dar_o_mundo")


def test_usuario_de_outra_organizacao_nao_herda_papel_por_ser_admin():
    """
    Ser admin DA PRÓPRIA empresa não dá nada na outra. É o cruzamento entre o
    eixo de papel e o de tenant: sem ele, `pode()` poderia ser chamado com o
    usuário certo e a organização errada e passar.
    """
    org_a, admin_a, _ = _org_com_os_dois_papeis("herda-a")
    org_b, _, _ = _org_com_os_dois_papeis("herda-b")

    assert pode(admin_a, org_a, "convidar_membro") is True
    assert pode(admin_a, org_b, "convidar_membro") is False
    assert pode(admin_a, org_b, "ver_painel") is False


# ---------------------------------------------------------------------------
# 2. A matriz, pelo HTTP
# ---------------------------------------------------------------------------


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_membro_comum_cria_e_exclui_criterio_da_propria_empresa():
    """A permissão que o membro TEM: o painel é de uso do analista."""
    organizacao, _, membro = _org_com_os_dois_papeis("criterio-membro")
    client = _client(membro)

    criado = client.post(
        "/api/b2b/criterios/", {"tipo": "palavra_chave", "valor": "energia"}, format="json"
    )
    assert criado.status_code == 201

    removido = client.delete(f"/api/b2b/criterios/{criado.json()['id']}/")
    assert removido.status_code == 204


def test_membro_comum_ve_o_painel_e_os_membros_da_propria_empresa():
    organizacao, admin, membro = _org_com_os_dois_papeis("painel-membro")
    client = _client(membro)

    assert client.get("/api/b2b/criterios/").status_code == 200
    assert client.get("/api/b2b/itens-monitorados/").status_code == 200
    assert client.get("/api/b2b/resumo-executivo/").status_code == 200
    lista = client.get("/api/b2b/membros/")
    assert lista.status_code == 200
    assert {m["email"] for m in lista.json()} == {admin.email, membro.email}


def test_membro_comum_nao_convida_nem_remove_membro_pela_api():
    organizacao, _, membro = _org_com_os_dois_papeis("membros-membro")
    alvo = _usuario("papeis-alvo-convite@example.com")
    client = _client(membro)

    convidado = client.post("/api/b2b/membros/", {"email": alvo.email}, format="json")
    removido = client.delete("/api/b2b/membros/", {"email": alvo.email}, format="json")

    assert convidado.status_code == 403
    assert removido.status_code == 403
    assert not MembroOrganizacao.objects.filter(user=alvo).exists()


def test_membro_comum_nao_consegue_se_promover_a_admin():
    """
    O payload traz `papel_na_organizacao: admin_organizacao` do próprio
    membro. Sem a guarda de papel no início do handler, a escalada chegava
    ao INSERT.
    """
    organizacao, admin, membro = _org_com_os_dois_papeis("auto-promoção")
    client = _client(membro)
    alvo = _usuario("papeis-alvo-promocao@example.com")

    resposta = client.post(
        "/api/b2b/membros/",
        {"email": alvo.email, "papel_na_organizacao": MembroOrganizacao.PAPEL_ADMIN},
        format="json",
    )

    assert resposta.status_code == 403
    assert not MembroOrganizacao.objects.filter(user=alvo).exists()
    vinculo = MembroOrganizacao.objects.get(organizacao=organizacao, user=membro)
    assert vinculo.papel_na_organizacao == MembroOrganizacao.PAPEL_MEMBRO


def test_admin_convida_membro_com_o_papel_escolhido():
    organizacao, admin, _ = _org_com_os_dois_papeis("convite-com-papel")
    alvo = _usuario("papeis-alvo-com-papel@example.com")
    client = _client(admin)

    resposta = client.post(
        "/api/b2b/membros/",
        {"email": alvo.email, "papel_na_organizacao": MembroOrganizacao.PAPEL_ADMIN},
        format="json",
    )

    assert resposta.status_code == 201
    assert resposta.json()["papel_na_organizacao"] == MembroOrganizacao.PAPEL_ADMIN
    assert pode(alvo, organizacao, "convidar_membro") is True


def test_admin_nao_inventa_papel_inexistente():
    """Papel fora de `PAPEL_CHOICES` é recusado, não gravado cru no banco."""
    organizacao, admin, _ = _org_com_os_dois_papeis("papel-invalido")
    alvo = _usuario("papeis-alvo-papel-ruim@example.com")
    client = _client(admin)

    resposta = client.post(
        "/api/b2b/membros/", {"email": alvo.email, "papel_na_organizacao": "superadmin"}, format="json"
    )

    assert resposta.status_code == 403
    assert not MembroOrganizacao.objects.filter(user=alvo).exists()


def test_convite_sem_email_ou_com_email_branco_e_400_do_admin():
    """A entrada malformada é 400 antes de qualquer consulta de usuário."""
    organizacao, admin, _ = _org_com_os_dois_papeis("email-vazio")
    client = _client(admin)

    assert client.post("/api/b2b/membros/", {}, format="json").status_code == 400
    assert client.post("/api/b2b/membros/", {"email": "   "}, format="json").status_code == 400


def test_admin_sem_organizacao_ou_com_organizacao_desativada_nao_altera_nada():
    """
    `_organizacao_ou_erro` (403) vem antes de qualquer escrita. Uma
    organização desativada ainda resolve para o usuário — o painel de quem
    pagou continua respondendo — então este teste cobre o 403 do handler, não
    o caso de negócio.
    """
    _org_com_os_dois_papeis("sem-org")
    cliente = _client(_usuario("papeis-sem-org@example.com"))

    assert cliente.post(
        "/api/b2b/membros/", {"email": "alguem@example.com"}, format="json"
    ).status_code == 403
    assert cliente.delete("/api/b2b/membros/", {"email": "alguem@example.com"}, format="json").status_code == 403
    assert cliente.post(
        "/api/b2b/criterios/", {"tipo": "palavra_chave", "valor": "x"}, format="json"
    ).status_code == 403
    assert cliente.delete("/api/b2b/criterios/1/").status_code == 403


# ---------------------------------------------------------------------------
# 3. Invariante: a organização nunca fica sem administrador
# ---------------------------------------------------------------------------


def test_ultimo_admin_nao_pode_ser_removido():
    """
    Sem esta guarda, remover o único admin deixa a organização órfã: a partir
    dali TODO mundo toma 403 em `/membros/` e não há mais caminho de volta
    pela API. O sintoma não aponta para a causa.
    """
    organizacao, admin, _ = _org_com_os_dois_papeis("sem-admin")
    client = _client(admin)

    resposta = client.delete("/api/b2b/membros/", {"email": admin.email}, format="json")

    assert resposta.status_code == 403
    assert MembroOrganizacao.objects.filter(organizacao=organizacao, user=admin).exists()


def test_admin_pode_se_remover_depois_de_promover_outro():
    """O caminho de saída existe, e é o oposto do teste anterior."""
    organizacao, admin, membro = _org_com_os_dois_papeis("troca-admin")
    MembroOrganizacao.objects.filter(organizacao=organizacao, user=membro).update(
        papel_na_organizacao=MembroOrganizacao.PAPEL_ADMIN
    )
    client = _client(admin)

    resposta = client.delete("/api/b2b/membros/", {"email": admin.email}, format="json")

    assert resposta.status_code == 204
    assert MembroOrganizacao.objects.filter(organizacao=organizacao).count() == 1
    assert pode(membro, organizacao, "convidar_membro") is True


def test_remover_membro_comum_deixa_o_admin_de_pe():
    organizacao, admin, membro = _org_com_os_dois_papeis("remove-comum")
    client = _client(admin)

    resposta = client.delete("/api/b2b/membros/", {"email": membro.email}, format="json")

    assert resposta.status_code == 204
    assert MembroOrganizacao.objects.filter(organizacao=organizacao, user=membro).exists() is False
    assert pode(admin, organizacao, "convidar_membro") is True


def test_servico_tambem_bloqueia_ultimo_admin_sem_passar_pela_view():
    """A guarda é invariante do domínio, não só da camada HTTP."""
    organizacao, admin, _ = _org_com_os_dois_papeis("servico-sem-admin")
    with pytest.raises(services.PermissaoNegadaError):
        services.remover_membro(organizacao, admin, quem_remove=admin)
    assert MembroOrganizacao.objects.filter(organizacao=organizacao, user=admin).exists()
