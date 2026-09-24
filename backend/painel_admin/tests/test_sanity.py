from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection, transaction
from django.db.models.query import QuerySet
from django.test import Client, RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from assinatura.models import Plan, Subscription
from catalogo_noticias.admin import NewsItemAdmin
from catalogo_noticias.models import NewsCluster, NewsItem
from gating.models import FeatureLimit
from moderacao.models import Denuncia
from comunidade.models import Publicacao, Comentario
from django.contrib.contenttypes.models import ContentType

pytestmark = pytest.mark.django_db

User = get_user_model()


def _admin():
    return User.objects.create_user(email="admin-painel@example.com", password="senha123", papel="admin")


def _free():
    return User.objects.create_user(email="free-painel@example.com", password="senha123", papel="free")


# ---------------------------------------------------------------------------
# Critério 1 e 2 — 401 sem token, 404 disfarçado para não-admin autenticado.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/api/admin/usuarios/",
        "/api/admin/fila/",
        "/api/admin/planos/",
        "/api/admin/limites/",
        "/api/admin/assinaturas/",
        "/api/admin/moderacao/denuncias/",
    ],
)
def test_sem_autenticacao_retorna_401(path):
    client = APIClient()
    resposta = client.get(path)
    assert resposta.status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/api/admin/usuarios/",
        "/api/admin/fila/",
        "/api/admin/planos/",
        "/api/admin/limites/",
        "/api/admin/assinaturas/",
        "/api/admin/moderacao/denuncias/",
    ],
)
def test_usuario_nao_admin_recebe_404_disfarcado(path):
    free = _free()
    client = APIClient()
    client.force_authenticate(user=free)
    resposta = client.get(path)
    assert resposta.status_code == 404
    assert "admin" not in str(resposta.data).lower()


# ---------------------------------------------------------------------------
# Critério 3 e 4 — usuários: listar/buscar/alterar papel/ativar-desativar.
# ---------------------------------------------------------------------------


def test_admin_lista_usuarios_com_busca():
    admin = _admin()
    User.objects.create_user(email="joaosilva@example.com", password="senha123", nome="Joao Silva", papel="free")
    User.objects.create_user(email="outra@example.com", password="senha123", nome="Outra Pessoa", papel="free")
    client = APIClient()
    client.force_authenticate(user=admin)

    resposta = client.get("/api/admin/usuarios/?search=joaosilva")

    assert resposta.status_code == 200
    assert resposta.data["count"] == 1
    assert resposta.data["results"][0]["email"] == "joaosilva@example.com"


def test_admin_altera_papel_e_status_do_usuario_com_auditoria():
    admin = _admin()
    alvo = _free()
    client = APIClient()
    client.force_authenticate(user=admin)

    resposta = client.patch(f"/api/admin/usuarios/{alvo.id}/", {"papel": "premium", "is_active": False}, format="json")

    assert resposta.status_code == 200
    alvo.refresh_from_db()
    assert alvo.papel == "premium"
    assert alvo.is_active is False

    from painel_admin.models import AuditoriaAdmin

    assert AuditoriaAdmin.objects.filter(acao="usuario_update", alvo_id=str(alvo.id)).exists()


# ---------------------------------------------------------------------------
# Critério 5 — fila editorial: listar pendentes, aprovar/rejeitar reflete no feed.
# ---------------------------------------------------------------------------


def test_admin_aprova_item_da_fila_e_reflete_no_feed():
    admin = _admin()
    item = NewsItem.objects.create(
        titulo="Noticia pendente",
        resumo_proprio="resumo proprio autoral",
        url_fonte_original="https://exemplo.com/materia-1",
        nome_fonte="Fonte Teste",
        status_revisao=NewsItem.STATUS_PENDENTE,
    )
    client = APIClient()
    client.force_authenticate(user=admin)

    resposta_lista = client.get("/api/admin/fila/?status=pendente")
    assert resposta_lista.status_code == 200
    assert resposta_lista.data["count"] == 1

    resposta = client.post(f"/api/admin/fila/{item.id}/decisao/", {"acao": "aprovar"}, format="json")
    assert resposta.status_code == 200
    item.refresh_from_db()
    assert item.status_revisao == NewsItem.STATUS_APROVADO

    resposta_feed = APIClient().get("/api/feed/")
    titulos = [e["titulo"] for e in resposta_feed.data["results"]]
    assert "Noticia pendente" in titulos


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "painel-admin-autocomplete-invalidation",
        }
    }
)
@pytest.mark.parametrize(
    ("acao", "status_esperado"),
    [
        ("aprovar", NewsItem.STATUS_APROVADO),
        ("rejeitar", NewsItem.STATUS_REJEITADO),
    ],
)
def test_admin_decisao_invalida_autocomplete(acao, status_esperado):
    admin = _admin()
    item = NewsItem.objects.create(
        titulo="Notícia decidida para autocomplete",
        url_fonte_original=f"https://exemplo.com/materia-cache-{acao}",
        nome_fonte="Fonte Teste",
        status_revisao=NewsItem.STATUS_PENDENTE,
    )
    chaves = {
        f"feed:autocomplete:v2:{sufixo}": ["snapshot-antigo"]
        for sufixo in ("categorias", "titulos", "populares")
    }
    for chave, valor in chaves.items():
        cache.set(chave, valor, 300)

    client = APIClient()
    client.force_authenticate(user=admin)
    resposta = client.post(
        f"/api/admin/fila/{item.id}/decisao/", {"acao": acao}, format="json"
    )

    assert resposta.status_code == 200
    assert resposta.data["status_revisao"] == status_esperado
    assert all(cache.get(chave) is None for chave in chaves)


@pytest.mark.django_db(transaction=True)
@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "native-admin-autocomplete-invalidation-actions",
        }
    }
)
@pytest.mark.parametrize(
    ("metodo", "status_esperado"),
    [
        ("marcar_como_aprovado", NewsItem.STATUS_APROVADO),
        ("marcar_como_rejeitado", NewsItem.STATUS_REJEITADO),
    ],
)
def test_admin_nativo_action_invalida_autocomplete(metodo, status_esperado):
    item = NewsItem.objects.create(
        titulo="Notícia decidida no admin nativo",
        url_fonte_original=f"https://exemplo.com/nativa-{metodo}",
        nome_fonte="Fonte Teste",
        status_revisao=NewsItem.STATUS_PENDENTE,
    )
    chaves = {
        f"feed:autocomplete:v2:{sufixo}": ["snapshot-antigo"]
        for sufixo in ("categorias", "titulos", "populares")
    }
    for chave, valor in chaves.items():
        cache.set(chave, valor, 300)

    model_admin = NewsItemAdmin(NewsItem, admin.site)
    request = RequestFactory().post("/admin/catalogo_noticias/newsitem/")
    getattr(model_admin, metodo)(request, NewsItem.objects.filter(pk=item.pk))

    item.refresh_from_db()
    assert item.status_revisao == status_esperado
    assert all(cache.get(chave) is None for chave in chaves)


@pytest.mark.django_db(transaction=True)
@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "native-admin-action-noop-preserves-cache",
        }
    }
)
@pytest.mark.parametrize(
    ("metodo", "status_destino"),
    [
        ("marcar_como_aprovado", NewsItem.STATUS_APROVADO),
        ("marcar_como_rejeitado", NewsItem.STATUS_REJEITADO),
    ],
)
def test_admin_nativo_action_sem_mudanca_preserva_cache(metodo, status_destino):
    from feed.busca import invalidar_cache_autocomplete

    itens = [
        NewsItem.objects.create(
            titulo=f"Notícia já no destino {indice}",
            url_fonte_original=(
                f"https://exemplo.com/nativa-sem-mudanca-{metodo}-{indice}"
            ),
            nome_fonte="Fonte Teste",
            status_revisao=status_destino,
        )
        for indice in (1, 2)
    ]
    chaves = {
        f"feed:autocomplete:v2:{sufixo}": ["snapshot-antigo"]
        for sufixo in ("categorias", "titulos", "populares")
    }
    for chave, valor in chaves.items():
        cache.set(chave, valor, 300)

    model_admin = NewsItemAdmin(NewsItem, admin.site)
    request = RequestFactory().post("/admin/catalogo_noticias/newsitem/")
    updates = []
    original_update = QuerySet.update

    def tracking_update(queryset, *args, **kwargs):
        result = original_update(queryset, *args, **kwargs)
        updates.append(result)
        return result

    with patch(
        "feed.busca.invalidar_cache_autocomplete",
        wraps=invalidar_cache_autocomplete,
    ) as invalidar, patch.object(QuerySet, "update", tracking_update):
        assert not connection.in_atomic_block
        resultado = getattr(model_admin, metodo)(
            request, NewsItem.objects.filter(pk__in=[item.pk for item in itens])
        )

    assert resultado is None
    assert updates == [0]
    invalidar.assert_not_called()
    assert set(
        NewsItem.objects.filter(pk__in=[item.pk for item in itens]).values_list(
            "status_revisao", flat=True
        )
    ) == {status_destino}
    assert all(cache.get(chave) == ["snapshot-antigo"] for chave in chaves)


@pytest.mark.django_db(transaction=True)
@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "native-admin-action-mixed-invalidates-on-commit",
        }
    }
)
@pytest.mark.parametrize(
    ("metodo", "status_destino", "outro_status"),
    [
        (
            "marcar_como_aprovado",
            NewsItem.STATUS_APROVADO,
            NewsItem.STATUS_REJEITADO,
        ),
        (
            "marcar_como_rejeitado",
            NewsItem.STATUS_REJEITADO,
            NewsItem.STATUS_APROVADO,
        ),
    ],
)
def test_admin_nativo_action_mista_invalida_uma_vez_apos_commit(
    metodo, status_destino, outro_status
):
    from feed.busca import invalidar_cache_autocomplete

    itens = [
        NewsItem.objects.create(
            titulo=f"Notícia misto {status}",
            url_fonte_original=(
                f"https://exemplo.com/nativa-misto-{metodo}-{status}"
            ),
            nome_fonte="Fonte Teste",
            status_revisao=status,
        )
        for status in (status_destino, NewsItem.STATUS_PENDENTE, outro_status)
    ]
    chaves = {
        f"feed:autocomplete:v2:{sufixo}": ["snapshot-antigo"]
        for sufixo in ("categorias", "titulos", "populares")
    }
    for chave, valor in chaves.items():
        cache.set(chave, valor, 300)

    model_admin = NewsItemAdmin(NewsItem, admin.site)
    request = RequestFactory().post("/admin/catalogo_noticias/newsitem/")
    with patch(
        "feed.busca.invalidar_cache_autocomplete",
        wraps=invalidar_cache_autocomplete,
    ) as invalidar:
        with CaptureQueriesContext(connection) as queries:
            with transaction.atomic():
                resultado = getattr(model_admin, metodo)(
                    request, NewsItem.objects.filter(pk__in=[item.pk for item in itens])
                )

                assert resultado is None
                invalidar.assert_not_called()
                assert all(
                    cache.get(chave) == ["snapshot-antigo"] for chave in chaves
                )

            invalidar.assert_called_once_with()

    updates = [
        query["sql"]
        for query in queries.captured_queries
        if query["sql"].lstrip().upper().startswith("UPDATE")
    ]
    assert len(updates) == 1
    assert "NOT" in updates[0].upper()

    assert set(
        NewsItem.objects.filter(pk__in=[item.pk for item in itens]).values_list(
            "status_revisao", flat=True
        )
    ) == {status_destino}
    assert all(cache.get(chave) is None for chave in chaves)


@pytest.mark.django_db(transaction=True)
@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "native-admin-autocomplete-invalidation-edit",
        }
    }
)
def test_admin_nativo_edicao_de_status_invalida_autocomplete():
    item = NewsItem.objects.create(
        titulo="Notícia editada no admin nativo",
        url_fonte_original="https://exemplo.com/nativa-edicao",
        nome_fonte="Fonte Teste",
        status_revisao=NewsItem.STATUS_PENDENTE,
    )
    chaves = {
        f"feed:autocomplete:v2:{sufixo}": ["snapshot-antigo"]
        for sufixo in ("categorias", "titulos", "populares")
    }
    for chave, valor in chaves.items():
        cache.set(chave, valor, 300)

    model_admin = NewsItemAdmin(NewsItem, admin.site)
    request = RequestFactory().post("/admin/catalogo_noticias/newsitem/")
    item.status_revisao = NewsItem.STATUS_APROVADO
    model_admin.save_model(request, item, object(), change=True)

    item.refresh_from_db()
    assert item.status_revisao == NewsItem.STATUS_APROVADO
    assert all(cache.get(chave) is None for chave in chaves)


@pytest.mark.django_db(transaction=True)
@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "native-admin-form-invalidation",
        }
    }
)
def test_formulario_admin_nativo_invalida_autocomplete():
    superuser = User.objects.create_superuser(
        email="admin-form@example.com", password="senha123"
    )
    item = NewsItem.objects.create(
        titulo="Notícia editada pelo formulário nativo",
        url_fonte_original="https://exemplo.com/nativa-formulario",
        nome_fonte="Fonte Teste",
        status_revisao=NewsItem.STATUS_PENDENTE,
    )
    chaves = {
        f"feed:autocomplete:v2:{sufixo}": ["snapshot-antigo"]
        for sufixo in ("categorias", "titulos", "populares")
    }
    for chave, valor in chaves.items():
        cache.set(chave, valor, 300)

    client = Client()
    client.force_login(superuser)
    resposta = client.post(
        reverse("admin:catalogo_noticias_newsitem_change", args=[item.pk]),
        {
            "titulo": item.titulo,
            "url_fonte_original": item.url_fonte_original,
            "nome_fonte": item.nome_fonte,
            "status_revisao": NewsItem.STATUS_APROVADO,
            "tags": "[]",
        },
    )

    assert resposta.status_code in (200, 302)
    item.refresh_from_db()
    assert item.status_revisao == NewsItem.STATUS_APROVADO
    assert all(cache.get(chave) is None for chave in chaves)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("caminho", ["save_model", "marcar_como_aprovado"])
@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "native-admin-invalidation-on-commit",
        }
    }
)
def test_admin_nativo_invalida_autocomplete_somente_depois_do_commit(caminho):
    from feed.busca import invalidar_cache_autocomplete

    item = NewsItem.objects.create(
        titulo="Notícia com commit atômico",
        url_fonte_original=f"https://exemplo.com/nativa-on-commit-{caminho}",
        nome_fonte="Fonte Teste",
        status_revisao=NewsItem.STATUS_PENDENTE,
    )
    chaves = {
        f"feed:autocomplete:v2:{sufixo}": ["snapshot-antigo"]
        for sufixo in ("categorias", "titulos", "populares")
    }
    for chave, valor in chaves.items():
        cache.set(chave, valor, 300)

    model_admin = NewsItemAdmin(NewsItem, admin.site)
    request = RequestFactory().post("/admin/catalogo_noticias/newsitem/")
    with patch(
        "feed.busca.invalidar_cache_autocomplete",
        wraps=invalidar_cache_autocomplete,
    ) as invalidar:
        with transaction.atomic():
            if caminho == "save_model":
                item.status_revisao = NewsItem.STATUS_APROVADO
                model_admin.save_model(request, item, object(), change=True)
            else:
                model_admin.marcar_como_aprovado(
                    request, NewsItem.objects.filter(pk=item.pk)
                )

            invalidar.assert_not_called()
            assert all(cache.get(chave) == ["snapshot-antigo"] for chave in chaves)

        invalidar.assert_called_once_with()

    assert all(cache.get(chave) is None for chave in chaves)


@pytest.mark.django_db(transaction=True)
@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "native-admin-invalidation-rollback",
        }
    }
)
def test_rollback_admin_nativo_nao_invalida_autocomplete():
    from feed.busca import invalidar_cache_autocomplete

    item = NewsItem.objects.create(
        titulo="Notícia com rollback",
        url_fonte_original="https://exemplo.com/nativa-rollback",
        nome_fonte="Fonte Teste",
        status_revisao=NewsItem.STATUS_PENDENTE,
    )
    chaves = {
        f"feed:autocomplete:v2:{sufixo}": ["snapshot-antigo"]
        for sufixo in ("categorias", "titulos", "populares")
    }
    for chave, valor in chaves.items():
        cache.set(chave, valor, 300)

    model_admin = NewsItemAdmin(NewsItem, admin.site)
    request = RequestFactory().post("/admin/catalogo_noticias/newsitem/")
    with patch(
        "feed.busca.invalidar_cache_autocomplete",
        wraps=invalidar_cache_autocomplete,
    ) as invalidar:
        with pytest.raises(RuntimeError, match="rollback de teste"):
            with transaction.atomic():
                item.status_revisao = NewsItem.STATUS_APROVADO
                model_admin.save_model(request, item, object(), change=True)

                invalidar.assert_not_called()
                assert all(
                    cache.get(chave) == ["snapshot-antigo"] for chave in chaves
                )
                raise RuntimeError("rollback de teste")

        invalidar.assert_not_called()

    item.refresh_from_db()
    assert item.status_revisao == NewsItem.STATUS_PENDENTE
    assert all(cache.get(chave) == ["snapshot-antigo"] for chave in chaves)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "cache-failure-is-not-fatal",
        }
    }
)
def test_falha_de_cache_nao_torna_decisao_editorial_fatal():
    admin = _admin()
    item = NewsItem.objects.create(
        titulo="Notícia com cache indisponível",
        url_fonte_original="https://exemplo.com/cache-indisponivel",
        nome_fonte="Fonte Teste",
        status_revisao=NewsItem.STATUS_PENDENTE,
    )
    client = APIClient()
    client.force_authenticate(user=admin)

    with patch("feed.busca.cache.delete", side_effect=RuntimeError("cache offline")):
        resposta = client.post(
            f"/api/admin/fila/{item.id}/decisao/",
            {"acao": "aprovar"},
            format="json",
        )

    assert resposta.status_code == 200
    assert resposta.data["status_revisao"] == NewsItem.STATUS_APROVADO


def test_admin_rejeita_item_da_fila():
    admin = _admin()
    item = NewsItem.objects.create(
        titulo="Noticia a rejeitar",
        resumo_proprio="resumo",
        url_fonte_original="https://exemplo.com/materia-2",
        nome_fonte="Fonte Teste",
        status_revisao=NewsItem.STATUS_PENDENTE,
    )
    client = APIClient()
    client.force_authenticate(user=admin)

    resposta = client.post(f"/api/admin/fila/{item.id}/decisao/", {"acao": "rejeitar"}, format="json")
    assert resposta.status_code == 200
    item.refresh_from_db()
    assert item.status_revisao == NewsItem.STATUS_REJEITADO


# ---------------------------------------------------------------------------
# Critério 6 — planos e limites com auditoria antes/depois.
# ---------------------------------------------------------------------------


def test_admin_cria_e_edita_plano():
    admin = _admin()
    client = APIClient()
    client.force_authenticate(user=admin)

    resposta = client.post(
        "/api/admin/planos/", {"nome": "Plano Teste", "preco": "19.90", "duracao_dias": 30}, format="json"
    )
    assert resposta.status_code == 201
    plano_id = resposta.data["id"]

    resposta_patch = client.patch(f"/api/admin/planos/{plano_id}/", {"ativo": False}, format="json")
    assert resposta_patch.status_code == 200
    assert resposta_patch.data["ativo"] is False

    from painel_admin.models import AuditoriaAdmin

    assert AuditoriaAdmin.objects.filter(acao="plan_create", alvo_id=str(plano_id)).exists()
    assert AuditoriaAdmin.objects.filter(acao="plan_update", alvo_id=str(plano_id)).exists()


def test_admin_edita_limite_e_gera_log_de_auditoria():
    admin = _admin()
    limite = FeatureLimit.objects.create(chave="alertas_personalizados", plano="free", valor="1")
    client = APIClient()
    client.force_authenticate(user=admin)

    resposta = client.patch(f"/api/admin/limites/{limite.id}/", {"valor": "5"}, format="json")

    assert resposta.status_code == 200
    limite.refresh_from_db()
    assert limite.valor == "5"

    from gating.models import FeatureLimitAlteracaoLog
    from painel_admin.models import AuditoriaAdmin

    assert FeatureLimitAlteracaoLog.objects.filter(feature_limit_chave="alertas_personalizados", valor_novo="5").exists()
    assert AuditoriaAdmin.objects.filter(acao="limite_update", alvo_id=str(limite.id)).exists()


# ---------------------------------------------------------------------------
# Critério 7 — assinaturas: filtro por status, detalhe + histórico.
# ---------------------------------------------------------------------------


def test_admin_lista_assinaturas_filtradas_por_status_e_ve_detalhe():
    admin = _admin()
    usuario = _free()
    plano = Plan.objects.create(nome="Semestral", preco="20.00", duracao_dias=180)
    sub_ativa = Subscription.objects.create(
        user=usuario, plan=plano, status=Subscription.STATUS_ATIVA, preco_cobrado="20.00", duracao_dias_no_momento=180
    )
    outro = User.objects.create_user(email="cancelado@example.com", password="senha123", papel="free")
    Subscription.objects.create(
        user=outro, plan=plano, status=Subscription.STATUS_CANCELADA, preco_cobrado="20.00", duracao_dias_no_momento=180
    )

    client = APIClient()
    client.force_authenticate(user=admin)

    resposta = client.get("/api/admin/assinaturas/?status=ativa")
    assert resposta.status_code == 200
    assert resposta.data["count"] == 1
    assert resposta.data["results"][0]["status"] == "ativa"

    resposta_detalhe = client.get(f"/api/admin/assinaturas/{sub_ativa.id}/")
    assert resposta_detalhe.status_code == 200
    assert "pagamentos" in resposta_detalhe.data


# ---------------------------------------------------------------------------
# Critério 8 — moderação: listar denúncias por status e aplicar ação.
# ---------------------------------------------------------------------------


def test_admin_lista_denuncias_pendentes_e_aplica_acao():
    admin = _admin()
    autor = _free()
    denunciante = User.objects.create_user(email="denunciante@example.com", password="senha123", papel="free")
    publicacao = Publicacao.objects.create(
        autor=autor, titulo="Post", conteudo="conteudo", tipo=Publicacao.TIPO_OPINIAO, status=Publicacao.STATUS_PUBLICADO
    )
    denuncia = Denuncia.objects.create(
        denunciante=denunciante,
        motivo=Denuncia.MOTIVO_SPAM,
        content_type=ContentType.objects.get_for_model(Publicacao),
        object_id=publicacao.id,
    )
    client = APIClient()
    client.force_authenticate(user=admin)

    resposta_lista = client.get("/api/admin/moderacao/denuncias/?status=pendente")
    assert resposta_lista.status_code == 200
    assert resposta_lista.data["count"] == 1

    resposta = client.post(
        f"/api/admin/moderacao/denuncias/{denuncia.id}/acao/",
        {"tipo": "remocao_conteudo", "motivo": "spam confirmado", "procedente": True},
        format="json",
    )
    assert resposta.status_code == 200
    denuncia.refresh_from_db()
    assert denuncia.status == Denuncia.STATUS_PROCEDENTE
    publicacao.refresh_from_db()
    assert publicacao.oculto is True
