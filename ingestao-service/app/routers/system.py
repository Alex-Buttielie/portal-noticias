"""Rotas de sistema sob /api/v1 (healthz alias + metrics com auth)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app import db
from app.deps import exigir_token
from app.observability import snapshot

router = APIRouter(dependencies=[Depends(exigir_token)])


@router.get("/healthz")
def healthz_v1():
    mongo_ok = db.ping_db()
    return {"status": "ok" if mongo_ok else "degraded", "mongo": "up" if mongo_ok else "down"}


@router.get("/metrics")
def metrics_v1():
    return snapshot()

