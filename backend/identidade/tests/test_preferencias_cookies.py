"""
Cobertura do endpoint GET/PUT /api/preferencias-cookies/
(`identidade.views.PreferenciasCookiesView`) — código-review-contract.md,
run 20260903-1134-seo-lgpd-design-system, Finding 3: este endpoint grava
dado pessoal de usuário autenticado (o gatilho que tornou a revisão de LGPD
obrigatória) e não tinha nenhum teste automatizado.

Segue a mesma convenção de `identidade/tests/test_acceptance_criteria.py`
(pytest-django, `APIClient`, `force_authenticate`).
"""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from identidade import services

User = get_user_model()

pytestmark = pytest.mark.django_db

URL = "/api/preferencias-cookies/"


def _criar_usuario(email="cookies@example.com"):
    return User.objects.create_user(email=email, password="SenhaForte123")


class TestPreferenciasCookiesAutenticacao:
    def test_get_sem_autenticacao_retorna_401_ou_403(self):
        client = APIClient()
        resp = client.get(URL)
        assert resp.status_code in (401, 403), resp.data

    def test_put_sem_autenticacao_retorna_401_ou_403(self):
        client = APIClient()
        resp = client.put(URL, {"analytics": True, "personalizacao": False}, format="json")
        assert resp.status_code in (401, 403), resp.data


class TestPreferenciasCookiesGet:
    def test_get_autenticado_sem_preferencia_salva_retorna_defaults_falsos(self):
        user = _criar_usuario()
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.get(URL)

        assert resp.status_code == 200, resp.data
        assert resp.data["analytics"] is False
        assert resp.data["personalizacao"] is False
        assert resp.data["atualizado_em"] is None

    def test_get_autenticado_reflete_preferencia_ja_persistida(self):
        user = _criar_usuario()
        services.atualizar_preferencias_cookies(user, {"analytics": True, "personalizacao": False})
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.get(URL)

        assert resp.status_code == 200, resp.data
        assert resp.data["analytics"] is True
        assert resp.data["personalizacao"] is False
        assert resp.data["atualizado_em"] is not None


class TestPreferenciasCookiesPut:
    def test_put_autenticado_persiste_via_service_layer(self):
        user = _criar_usuario()
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.put(URL, {"analytics": True, "personalizacao": True}, format="json")

        assert resp.status_code == 200, resp.data
        assert resp.data["analytics"] is True
        assert resp.data["personalizacao"] is True
        assert resp.data["atualizado_em"] is not None

        # Confirma persistência real no banco (não só na resposta) — mesmo
        # dado exposto por `services.atualizar_preferencias_cookies`, único
        # ponto de mutação (convenção DDD do projeto).
        user.refresh_from_db()
        assert user.preferencias_cookies == {"analytics": True, "personalizacao": True}
        assert user.preferencias_cookies_atualizado_em is not None

    def test_put_atualiza_timestamp_a_cada_chamada(self):
        user = _criar_usuario()
        client = APIClient()
        client.force_authenticate(user=user)

        client.put(URL, {"analytics": True, "personalizacao": False}, format="json")
        user.refresh_from_db()
        primeira_atualizacao = user.preferencias_cookies_atualizado_em
        assert primeira_atualizacao is not None

        client.put(URL, {"analytics": False, "personalizacao": True}, format="json")
        user.refresh_from_db()
        assert user.preferencias_cookies == {"analytics": False, "personalizacao": True}
        assert user.preferencias_cookies_atualizado_em >= primeira_atualizacao

    def test_put_so_afeta_o_proprio_usuario_autenticado_request_user(self):
        """
        A view não recebe nem aceita nenhum identificador de usuário na URL
        ou no corpo (`services.atualizar_preferencias_cookies` sempre opera
        sobre o `request.user` da requisição) — confirma que um PUT
        autenticado como usuário A nunca grava preferência em usuário B,
        mesmo que um `id`/`user_id` seja injetado no payload.
        """
        usuario_a = _criar_usuario(email="usuario-a@example.com")
        usuario_b = _criar_usuario(email="usuario-b@example.com")
        services.atualizar_preferencias_cookies(usuario_b, {"analytics": False, "personalizacao": False})

        client = APIClient()
        client.force_authenticate(user=usuario_a)

        resp = client.put(
            URL,
            {"analytics": True, "personalizacao": True, "id": usuario_b.pk, "user_id": usuario_b.pk},
            format="json",
        )

        assert resp.status_code == 200, resp.data
        usuario_a.refresh_from_db()
        usuario_b.refresh_from_db()
        assert usuario_a.preferencias_cookies == {"analytics": True, "personalizacao": True}
        assert usuario_b.preferencias_cookies == {"analytics": False, "personalizacao": False}

    def test_put_so_grava_chaves_do_allow_list_categorias_opcionais(self):
        """
        `services.CATEGORIAS_OPCIONAIS` é o allow-list de chaves persistíveis
        (`("analytics", "personalizacao")`) — "essenciais" e qualquer outra
        chave arbitrária injetada no payload não podem acabar gravadas em
        `preferencias_cookies`.
        """
        user = _criar_usuario()
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.put(
            URL,
            {
                "analytics": True,
                "personalizacao": True,
                "essenciais": False,
                "campo_arbitrario": "valor-malicioso",
            },
            format="json",
        )

        assert resp.status_code == 200, resp.data
        user.refresh_from_db()
        assert set(user.preferencias_cookies.keys()) == set(services.CATEGORIAS_OPCIONAIS)
        assert user.preferencias_cookies == {"analytics": True, "personalizacao": True}


class TestServiceAtualizarPreferenciasCookies:
    """Cobertura direta de `identidade.services.atualizar_preferencias_cookies`,
    o único ponto de mutação desta funcionalidade (convenção DDD do projeto)."""

    def test_valores_ausentes_no_dict_de_entrada_viram_false(self):
        user = _criar_usuario()
        resultado = services.atualizar_preferencias_cookies(user, {"analytics": True})

        assert resultado.preferencias_cookies == {"analytics": True, "personalizacao": False}

    def test_define_o_timestamp_de_atualizacao(self):
        user = _criar_usuario()
        antes = timezone.now()

        resultado = services.atualizar_preferencias_cookies(user, {"analytics": True, "personalizacao": True})

        assert resultado.preferencias_cookies_atualizado_em is not None
        assert resultado.preferencias_cookies_atualizado_em >= antes
