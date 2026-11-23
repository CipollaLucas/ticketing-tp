import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.auth import router as auth_router
from app.events import router as events_router
from app.inventory import router as inventory_router
from app.settings import settings

logger = logging.getLogger("ticketing.http")
app = FastAPI(title="Ticketing TP", version="0.1.0")
app.include_router(auth_router)
app.include_router(events_router)
app.include_router(inventory_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def audit_http(request: Request, call_next):
    started = perf_counter()
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        duration_ms = round((perf_counter() - started) * 1000, 2)
        logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%s",
            request_id, request.method, request.url.path, status, duration_ms,
        )


@app.get("/health")
def health():
    try:
        with create_engine(settings.database_url, pool_pre_ping=True).connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "error"})
    return {"status": "ok", "database": "ok"}


@app.get("/api/v1")
def api_root():
    return {"message": "Ticketing API v1", "stage": "bootstrap"}


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Preserve FastAPI's 422 shape while omitting credentials submitted as input.
    errors = [{key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})
