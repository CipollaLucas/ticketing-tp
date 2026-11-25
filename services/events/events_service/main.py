"""Independent read-only Events preview; no Legacy or Identity DB access."""
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from events_service.application import public_catalog, public_event_detail
from events_service.commands import router as protected_router
from events_service.http_audit import install_http_audit
from events_service.persistence import SqlAlchemyEventReader, engine

app = FastAPI(title="Ticketing Events Service (Preview)", version="0.1.0")
install_http_audit(app)
app.include_router(protected_router)


def session_scope():
    with Session(engine) as session:
        yield session


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    owner_id: UUID
    name: str
    description: str
    venue: str
    start_at: datetime
    end_at: datetime
    status: str
    created_at: datetime
    updated_at: datetime


class CatalogResponse(BaseModel):
    items: list[EventResponse]
    total: int
    limit: int
    offset: int


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "error"})
    return {"status": "ok", "database": "ok"}


@app.get("/api/v1/events", response_model=CatalogResponse)
def catalog(
    db: Annotated[Session, Depends(session_scope)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CatalogResponse:
    rows, count = public_catalog(SqlAlchemyEventReader(db), datetime.now(UTC), limit, offset)
    return CatalogResponse(
        items=[EventResponse.model_validate(row) for row in rows],
        total=count, limit=limit, offset=offset,
    )


@app.get("/api/v1/events/{event_id}", response_model=EventResponse)
def public_event(
    event_id: UUID,
    db: Annotated[Session, Depends(session_scope)],
) -> EventResponse:
    """Legacy public detail contract: published even after start, draft => 404."""
    record = public_event_detail(SqlAlchemyEventReader(db), event_id)
    if record is None:
        raise HTTPException(404, "Event not found")
    return EventResponse.model_validate(record)
