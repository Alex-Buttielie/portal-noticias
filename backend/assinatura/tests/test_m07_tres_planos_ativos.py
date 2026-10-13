"""
M-07 (implementation-contract.md run 20261012-1806-monetizacao-sprint1) —
critério de aceite 7: "Dado 3 planos ativos no banco (free, premium
semestral, premium anual), quando /planos renderiza, então aparecem 3
cartões [...]". Este módulo cobre a parte de dados/API que alimenta
`frontend/app/planos/page.tsx` (que itera sobre o que
`GET /api/assinatura/planos/` devolve) — o projeto não tem runner de
renderização de componente (ver notas de M-10/M-09 no
implementation-history.md desta run), então a prova de "3 cartões" fica
dividida em duas pontas, cada uma testada no seu nível:
  1. a API pública devolve exatamente os 3 planos ativos esperados (este
     módulo);
  2. `calcularDestaquePlanos`/`planoPagoMaisBarato` calculam a economia e o
     preço a partir desses 3 planos sem número fixo
     (`frontend/testes/planos.test.mjs`, já existente, caso "3 planos
     ativos no banco").
A página em si (`planos/page.tsx`) apenas faz `planos.filter(...).map(...)`
sobre o array devolvido pela API — dado 1 e 2 provados, o 3º cartão é
consequência direta de código já lido e não de comportamento adicional a
provar de novo aqui.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from assinatura.models import Plan

pytestmark = pytest.mark.django_db


def test_api_publica_devolve_os_tres_planos_ativos_free_semestral_anual():
    # "Premium Semestral" já existe em TODA base (migration
    # `0003_seed_plano_semestral`, inclusive na de teste) — `get_or_create`
    # aqui, e não `.create()`, para não duplicar a linha (mesma razão da
    # migration, ver `assinatura/migrations/0003_seed_plano_semestral.py`).
    Plan.objects.create(nome="Free", preco=Decimal("0.00"), duracao_dias=0, ativo=True)
    Plan.objects.get_or_create(
        nome="Premium Semestral",
        defaults={"preco": Decimal("20.00"), "duracao_dias": 180, "ativo": True},
    )
    Plan.objects.create(nome="Premium Anual", preco=Decimal("30.00"), duracao_dias=365, ativo=True)
    Plan.objects.create(nome="Plano Descontinuado", preco=Decimal("15.00"), duracao_dias=180, ativo=False)
    client = APIClient()

    resposta = client.get("/api/assinatura/planos/")

    assert resposta.status_code == 200
    nomes = {p["nome"] for p in resposta.data}
    assert nomes == {"Free", "Premium Semestral", "Premium Anual"}
    assert "Plano Descontinuado" not in nomes
    assert len(resposta.data) == 3


def test_api_publica_nao_expoe_planos_inativos_isoladamente():
    Plan.objects.create(nome="So Inativo", preco=Decimal("10.00"), duracao_dias=30, ativo=False)
    client = APIClient()

    resposta = client.get("/api/assinatura/planos/")

    assert resposta.status_code == 200
    nomes = {p["nome"] for p in resposta.data}
    assert "So Inativo" not in nomes
