"""Config central do servico de ingestao (Frente A - esqueleto)."""
from __future__ import annotations

import os


def _getenv(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _getenv_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _getenv_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


class Settings:
    """Settings lidas de env (sem dependencia obrigatoria de pydantic-settings)."""

    MONGO_URL: str = _getenv("MONGO_URL", "mongodb://localhost:27017")
    DB_NAME: str = _getenv("DB_NAME", "ingestao")
    INGESTAO_API_TOKEN: str = _getenv("INGESTAO_API_TOKEN", "dev-token-trocar")
    PORT: int = _getenv_int("PORT", 8001)

    # LLM
    LLM_MODEL: str = _getenv("LLM_MODEL", "gpt-4o-mini")
    LLM_BASE_URL: str = _getenv("LLM_BASE_URL", "")
    LLM_API_KEY: str = _getenv("LLM_API_KEY", "")
    LLM_LOTE: int = _getenv_int("LLM_LOTE", 10)
    LLM_MAX_TOKENS: int = _getenv_int("LLM_MAX_TOKENS", 220)
    LLM_TETO_USD: float = _getenv_float("LLM_TETO_USD", 5.0)
    LLM_PRECO_1K: float = _getenv_float("LLM_PRECO_1K", 0.15)
    LLM_TIMEOUT: int = _getenv_int("LLM_TIMEOUT", 30)


settings = Settings()
