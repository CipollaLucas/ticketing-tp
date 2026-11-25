"""HTTP request audit with safe correlation and monotonic duration."""
import logging
import re
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request

logger = logging.getLogger("events.http")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
_SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


def install_http_audit(app: FastAPI) -> None:
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
            # Exclude request query, body, credentials, cookies and raw headers.
            # 500 is logged when an unhandled application exception bubbles up.
            logger.info(
                "request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
                request_id,
                request.method,
                request.url.path,
                status,
                (perf_counter() - started) * 1000,
            )
