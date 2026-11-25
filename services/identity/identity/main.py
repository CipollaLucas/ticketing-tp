"""Standalone Identity FastAPI app, independently deployable on port 8001."""
import logging
import re
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from identity.adapters.http import router
from identity.database import engine

app = FastAPI(title="Ticketing Identity Service", version="0.1.0")
app.include_router(router)
logger = logging.getLogger("identity.http")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
_SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


@app.middleware("http")
async def audit(request: Request, call_next):
    started = perf_counter()
    raw_id = request.headers.get("X-Request-ID", "")
    request_id = raw_id if _SAFE_ID.fullmatch(raw_id) else uuid4().hex
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        # Never log query parameters, bodies, Authorization or cookies.
        logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            status,
            (perf_counter() - started) * 1000,
        )


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    # Never echo password inputs in a validation error.
    errors = [{key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "error"})
    return {"status": "ok", "database": "ok"}
