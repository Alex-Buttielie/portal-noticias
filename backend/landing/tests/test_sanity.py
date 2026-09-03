from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from landing.models import InscricaoListaEspera

pytestmark = pytest.mark.django_db


def test_inscricao_publica_sem_autenticacao():
    client = APIClient()
    resposta = client.post(
        "/api/landing/lista-espera/",
        {"nome": "Ana", "email": "ana@example.com", "aceite_comunicacao": True},
        format="json",
    )
    assert resposta.status_code == 201
    assert InscricaoListaEspera.objects.filter(email="ana@example.com").exists()


def test_email_duplicado_nao_cria_segundo_registro():
    client = APIClient()
    dados = {"nome": "Bia", "email": "bia@example.com", "aceite_comunicacao": True}
    client.post("/api/landing/lista-espera/", dados, format="json")
    client.post("/api/landing/lista-espera/", dados, format="json")

    assert InscricaoListaEspera.objects.filter(email="bia@example.com").count() == 1


def test_sem_aceite_e_rejeitado():
    client = APIClient()
    resposta = client.post(
        "/api/landing/lista-espera/",
        {"nome": "Caio", "email": "caio@example.com", "aceite_comunicacao": False},
        format="json",
    )
    assert resposta.status_code == 400
    assert not InscricaoListaEspera.objects.filter(email="caio@example.com").exists()
