"""Testes de "Seguir fonte" (GET/POST/DELETE /api/feed/fontes-seguidas/)."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

User = get_user_model()


def test_anonimo_recebe_401():
    client = APIClient()
    resposta = client.get("/api/feed/fontes-seguidas/")
    assert resposta.status_code == 401


def test_seguir_listar_deixar_de_seguir():
    usuario = User.objects.create_user(email="segue-fonte@example.com", password="senha123")
    client = APIClient()
    client.force_authenticate(user=usuario)

    resposta = client.post("/api/feed/fontes-seguidas/", {"nome_fonte": "G1"}, format="json")
    assert resposta.status_code == 201

    resposta_get = client.get("/api/feed/fontes-seguidas/")
    assert resposta_get.status_code == 200
    assert resposta_get.data == ["G1"]

    resposta_del = client.delete("/api/feed/fontes-seguidas/", {"nome_fonte": "G1"}, format="json")
    assert resposta_del.status_code == 204

    resposta_get2 = client.get("/api/feed/fontes-seguidas/")
    assert resposta_get2.data == []


def test_seguir_a_mesma_fonte_duas_vezes_e_idempotente():
    usuario = User.objects.create_user(email="segue-fonte2@example.com", password="senha123")
    client = APIClient()
    client.force_authenticate(user=usuario)

    client.post("/api/feed/fontes-seguidas/", {"nome_fonte": "Folha"}, format="json")
    resposta = client.post("/api/feed/fontes-seguidas/", {"nome_fonte": "Folha"}, format="json")

    assert resposta.status_code == 201
    assert client.get("/api/feed/fontes-seguidas/").data == ["Folha"]


def test_sem_nome_fonte_vira_400():
    usuario = User.objects.create_user(email="segue-fonte3@example.com", password="senha123")
    client = APIClient()
    client.force_authenticate(user=usuario)

    resposta = client.post("/api/feed/fontes-seguidas/", {}, format="json")
    assert resposta.status_code == 400


def test_fontes_de_um_usuario_nao_vazam_pra_outro():
    usuario_a = User.objects.create_user(email="fonte-a@example.com", password="senha123")
    usuario_b = User.objects.create_user(email="fonte-b@example.com", password="senha123")

    client_a = APIClient()
    client_a.force_authenticate(user=usuario_a)
    client_a.post("/api/feed/fontes-seguidas/", {"nome_fonte": "G1"}, format="json")

    client_b = APIClient()
    client_b.force_authenticate(user=usuario_b)
    assert client_b.get("/api/feed/fontes-seguidas/").data == []
