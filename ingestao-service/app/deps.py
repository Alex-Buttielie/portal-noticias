"""Dependencia de autenticacao via header X-API-Token."""
from __future__ import annotations

from fastapi import Header, HTTPException, status
from typing import Optional

from app.config import settings


async def exigir_token(x_api_token: Optional[str] = Header(default=None)) -> str:
    if x_api_token != settings.INGESTAO_API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido ou ausente (header X-API-Token)",
        )
    return x_api_token
