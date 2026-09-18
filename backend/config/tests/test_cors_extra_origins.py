"""
`DJANGO_CORS_EXTRA_ORIGINS` — origens extras de contingência (acesso direto
por IP) somadas à origem canônica (`FRONTEND_BASE_URL`), sem abrir para
qualquer origem.
"""

from __future__ import annotations

from config.settings import _parse_extra_origins


def test_origem_canonica_sempre_presente():
    from django.conf import settings

    assert settings.FRONTEND_BASE_URL in settings.CORS_ALLOWED_ORIGINS
    assert isinstance(settings.CORS_ALLOWED_ORIGINS, list)


def test_parse_ignora_vazios_e_espacos():
    assert _parse_extra_origins("") == []
    assert _parse_extra_origins("  ,, ") == []
    assert _parse_extra_origins(
        "http://108.174.147.50:3103, https://x.example.com ,,"
    ) == ["http://108.174.147.50:3103", "https://x.example.com"]
