"""
Ponto único de mutação de estado do app `identidade/` (convenção DDD do
projeto: toda mutação passa por `services.py`, views nunca escrevem direto
nos models). Este arquivo nasceu nesta run (20260903-1134-seo-lgpd-design-
system) para a nova funcionalidade de preferências de cookies — o restante
das views deste app (cadastro, login, onboarding etc.) já existia antes desta
run e não foi tocado/refatorado aqui (fora do escopo desta run, ver
implementation-history.md).
"""

from __future__ import annotations

from django.utils import timezone

CATEGORIAS_OPCIONAIS = ("analytics", "personalizacao")


def atualizar_preferencias_cookies(user, categorias: dict) -> "identidade.models.User":  # noqa: F821
    """
    Persiste a escolha de cookies não essenciais de um usuário autenticado
    (implementation-contract.md, escopo B). `categorias` só pode conter as
    chaves em `CATEGORIAS_OPCIONAIS` — "essenciais" nunca é aceito aqui
    porque é sempre ativo, não é uma escolha armazenável.
    """
    preferencias = {chave: bool(categorias.get(chave, False)) for chave in CATEGORIAS_OPCIONAIS}
    user.preferencias_cookies = preferencias
    user.preferencias_cookies_atualizado_em = timezone.now()
    user.save(update_fields=["preferencias_cookies", "preferencias_cookies_atualizado_em"])
    return user
