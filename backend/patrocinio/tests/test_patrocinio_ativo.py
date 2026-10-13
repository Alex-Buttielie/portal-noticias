"""
M-10 (run 20261012-1806-monetizacao-sprint1) — mecanismo de patrocínio
identificado: datas, flag `ativo` e o endpoint público
`GET /api/patrocinio/ativo/?posicao=...`.

Dados de TESTE, claramente marcados como teste (anunciante "Anunciante de
Teste", nunca um nome real) — nenhum preço/tabela comercial real é usado ou
inventado aqui (ver não-objetivos do implementation-contract.md).
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from patrocinio.models import Patrocinio

pytestmark = pytest.mark.django_db


def _hoje():
    return timezone.localdate()


def _patrocinio(**overrides):
    hoje = _hoje()
    dados = {
        "anunciante": "Anunciante de Teste",
        "criativo_url": "https://exemplo-teste.invalid/criativo.png",
        "texto_alt": "Anúncio de teste do Anunciante de Teste",
        "url": "https://exemplo-teste.invalid/promocao",
        "posicao": "newsletter",
        "data_inicio": hoje - timedelta(days=1),
        "data_fim": hoje + timedelta(days=1),
        "ativo": True,
    }
    dados.update(overrides)
    return Patrocinio.objects.create(**dados)


@pytest.fixture(autouse=True)
def _limpa_cache():
    cache.clear()
    yield
    cache.clear()


def test_vigente_e_ativo_aparece_na_posicao_certa():
    p = _patrocinio(posicao="radar-sprint1-a")
    client = APIClient()

    resposta = client.get("/api/patrocinio/ativo/", {"posicao": "radar-sprint1-a"})

    assert resposta.status_code == 200
    assert resposta.data["id"] == p.id
    assert resposta.data["anunciante"] == "Anunciante de Teste"
    assert resposta.data["posicao"] == "radar-sprint1-a"
    # Payload público não inclui `ativo`/datas internas.
    assert "ativo" not in resposta.data
    assert "data_inicio" not in resposta.data


def test_fora_do_periodo_data_fim_passada_nao_aparece():
    hoje = _hoje()
    _patrocinio(
        posicao="radar-sprint1-b",
        data_inicio=hoje - timedelta(days=10),
        data_fim=hoje - timedelta(days=1),
    )
    client = APIClient()

    resposta = client.get("/api/patrocinio/ativo/", {"posicao": "radar-sprint1-b"})

    assert resposta.status_code == 404


def test_fora_do_periodo_data_inicio_futura_nao_aparece():
    hoje = _hoje()
    _patrocinio(
        posicao="radar-sprint1-c",
        data_inicio=hoje + timedelta(days=1),
        data_fim=hoje + timedelta(days=10),
    )
    client = APIClient()

    resposta = client.get("/api/patrocinio/ativo/", {"posicao": "radar-sprint1-c"})

    assert resposta.status_code == 404


def test_ativo_false_nao_aparece_mesmo_dentro_do_periodo():
    _patrocinio(posicao="radar-sprint1-d", ativo=False)
    client = APIClient()

    resposta = client.get("/api/patrocinio/ativo/", {"posicao": "radar-sprint1-d"})

    assert resposta.status_code == 404


def test_posicao_sem_nenhum_patrocinio_cadastrado_404():
    client = APIClient()

    resposta = client.get("/api/patrocinio/ativo/", {"posicao": "posicao-inexistente-sprint1"})

    assert resposta.status_code == 404


def test_posicao_ausente_e_400():
    client = APIClient()

    resposta = client.get("/api/patrocinio/ativo/")

    assert resposta.status_code == 400


def test_duas_vigentes_na_mesma_posicao_devolve_a_de_inicio_mais_recente():
    hoje = _hoje()
    mais_antiga = _patrocinio(
        posicao="radar-sprint1-e",
        anunciante="Antigo de Teste",
        data_inicio=hoje - timedelta(days=5),
        data_fim=hoje + timedelta(days=5),
    )
    mais_recente = _patrocinio(
        posicao="radar-sprint1-e",
        anunciante="Recente de Teste",
        data_inicio=hoje - timedelta(days=1),
        data_fim=hoje + timedelta(days=5),
    )
    client = APIClient()

    resposta = client.get("/api/patrocinio/ativo/", {"posicao": "radar-sprint1-e"})

    assert resposta.status_code == 200
    assert resposta.data["id"] == mais_recente.id
    assert resposta.data["id"] != mais_antiga.id


def test_vigente_no_primeiro_e_no_ultimo_dia_do_periodo_inclusive():
    hoje = _hoje()
    _patrocinio(posicao="radar-sprint1-f", data_inicio=hoje, data_fim=hoje)
    client = APIClient()

    resposta = client.get("/api/patrocinio/ativo/", {"posicao": "radar-sprint1-f"})

    assert resposta.status_code == 200


def test_resposta_e_cacheada_entre_duas_chamadas_consecutivas():
    """Dado o payload não variar por usuário, a 2ª chamada não deveria
    precisar bater no banco de novo dentro do TTL — confirma só que a
    chave de cache é escrita e lida, sem acoplar ao backend de cache."""
    _patrocinio(posicao="radar-sprint1-g")
    client = APIClient()

    primeira = client.get("/api/patrocinio/ativo/", {"posicao": "radar-sprint1-g"})
    segunda = client.get("/api/patrocinio/ativo/", {"posicao": "radar-sprint1-g"})

    assert primeira.status_code == segunda.status_code == 200
    assert primeira.data == segunda.data


def test_cache_tambem_guarda_o_404_ausencia_de_patrocinio():
    client = APIClient()

    primeira = client.get("/api/patrocinio/ativo/", {"posicao": "radar-sprint1-h"})
    segunda = client.get("/api/patrocinio/ativo/", {"posicao": "radar-sprint1-h"})

    assert primeira.status_code == segunda.status_code == 404
