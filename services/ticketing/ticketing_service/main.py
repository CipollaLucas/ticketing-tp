"""Opt-in independent Ticketing H4 foundation; NO purchase or gate write HTTP routes."""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ticketing_service.persistence import engine
from ticketing_service.provision_http import router as provision_router
from ticketing_service.purchase_http import router as purchase_router
from ticketing_service.sale_http import router as sale_router
from ticketing_service.settings import settings

app = FastAPI(title="Ticketing Service — H4 foundation", version="0.1.0")
app.include_router(sale_router)
app.include_router(provision_router)
app.include_router(purchase_router)


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "error"})
    return {"status": "ok", "database": "ok"}


@app.get("/api/v1/internal/sales/availability")
def availability():
    # H4 does NOT serve actual sales yet and intentionally offers no write endpoint.
    return {
        "sale_commands_enabled": settings.sale_commands_enabled,
        "gate_provisioning_enabled": settings.gate_provisioning_enabled,
        "purchases_enabled": settings.purchases_enabled,
    }
