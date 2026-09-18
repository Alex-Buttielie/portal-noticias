"""FastAPI — Servico de Ingestao (Frente A: esqueleto)."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from app import db
from app.observability import get_logger, inc, snapshot

from app.routers import config_router, feed, fila, fontes, ingestao, painel, system

logger = get_logger("ingestao")

app = FastAPI(title="Serviço de Ingestão", docs_url="/docs", openapi_url="/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _contadores(request: Request, call_next):
    inc("requisicoes_total", 1)
    try:
        response = await call_next(request)
        if response.status_code >= 500:
            inc("erros_total", 1)
        return response
    except Exception:
        inc("erros_total", 1)
        raise


@app.exception_handler(Exception)
async def _erro_nao_tratado(request: Request, exc: Exception):
    logger.error(f"erro nao tratado em {request.url.path}: {exc}")
    return JSONResponse(status_code=500, content={"detail": "erro interno"})


@app.get("/healthz", tags=["sistema"])
def healthz():
    """Healthcheck real: pinga o Mongo. Sem auth (contrato)."""
    mongo_ok = db.ping_db()
    logger.info("healthz mongo_up=%s" % mongo_ok)
    return {"status": "ok" if mongo_ok else "degraded", "mongo": "up" if mongo_ok else "down"}


@app.get("/metrics", tags=["sistema"])
def metrics():
    """Contadores em memoria (sem auth na raiz; sob /api/v1 exige token)."""
    return snapshot()


app.include_router(fontes.router, prefix="/api/v1", tags=["fontes"])
app.include_router(ingestao.router, prefix="/api/v1", tags=["ingestao"])
app.include_router(fila.router, prefix="/api/v1", tags=["fila"])
app.include_router(config_router.router, prefix="/api/v1", tags=["config"])
app.include_router(feed.router, prefix="/api/v1", tags=["feed"])
app.include_router(painel.router, prefix="/api/v1", tags=["painel"])
app.include_router(system.router, prefix="/api/v1", tags=["sistema"])


@app.get("/painel", include_in_schema=False, response_class=HTMLResponse)
def painel_raiz():
    """Alias sem auth do painel de controle (uso via navegador, sem o portal)."""
    from app.routers.painel import coletar_status, construir_html

    return HTMLResponse(construir_html(coletar_status()))
