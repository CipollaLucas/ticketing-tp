"""Owner-scoped event drafts and a public published-events catalog."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, Db, require_event_owner, require_owner_or_admin
from app.models import Event, EventStatus, Role, User

router = APIRouter(prefix="/api/v1", tags=["Events"])
EventOwner = Annotated[User, Depends(require_event_owner)]


class EventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, max_length=160)
    description: str | None = None
    venue: str | None = Field(default=None, max_length=200)
    start_at: datetime | None = None
    end_at: datetime | None = None

    @field_validator("name", "venue", "description")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None

    @field_validator("start_at", "end_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Dates require an explicit UTC offset")
        return value.astimezone(UTC) if value is not None else None


class EventUpdate(EventInput):
    pass


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    owner_id: UUID
    name: str | None
    description: str | None
    venue: str | None
    start_at: datetime | None
    end_at: datetime | None
    status: EventStatus


class EventPage(BaseModel):
    items: list[EventResponse]
    limit: int
    offset: int
    total: int


def require_access(db: Session, event_id: UUID, user: User) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    require_owner_or_admin(user, event.owner_id)
    return event


def validate_date_range(event: Event) -> None:
    if event.start_at is not None and event.end_at is not None:
        if event.end_at <= event.start_at:
            raise HTTPException(422, "end_at must be later than start_at")


def apply_update(event: Event, payload: EventInput) -> None:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    validate_date_range(event)


@router.post("/events", response_model=EventResponse, status_code=201)
def create_event(payload: EventInput, owner: EventOwner, db: Db) -> Event:
    event = Event(owner_id=owner.id, status=EventStatus.DRAFT.value)
    apply_update(event, payload)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.patch("/events/{event_id}", response_model=EventResponse)
def edit_event(event_id: UUID, payload: EventUpdate, owner: EventOwner, db: Db) -> Event:
    event = require_access(db, event_id, owner)
    if event.status != EventStatus.DRAFT:
        raise HTTPException(409, "Published events cannot be edited")
    apply_update(event, payload)
    db.commit()
    db.refresh(event)
    return event


@router.get("/owner/events", response_model=EventPage)
def list_owner_events(
    owner: EventOwner,
    db: Db,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EventPage:
    query = select(Event)
    if owner.role != Role.ADMINISTRATOR:
        query = query.where(Event.owner_id == owner.id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.order_by(Event.id).limit(limit).offset(offset)).all()
    return EventPage(items=[EventResponse.model_validate(x) for x in items], limit=limit, offset=offset, total=total)


@router.get("/events", response_model=EventPage)
def public_catalog(
    db: Db,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EventPage:
    query = select(Event).where(Event.status == EventStatus.PUBLISHED)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.order_by(Event.start_at, Event.id).limit(limit).offset(offset)).all()
    return EventPage(items=[EventResponse.model_validate(x) for x in items], limit=limit, offset=offset, total=total)


@router.get("/events/{event_id}", response_model=EventResponse)
def public_event_detail(event_id: UUID, db: Db) -> Event:
    event = db.get(Event, event_id)
    if event is None or event.status != EventStatus.PUBLISHED:
        raise HTTPException(404, "Event not found")
    return event


@router.post("/events/{event_id}/publish", response_model=EventResponse)
def publish_event(event_id: UUID, owner: EventOwner, db: Db) -> Event:
    event = require_access(db, event_id, owner)
    if event.status != EventStatus.DRAFT:
        raise HTTPException(409, "Event already published")
    if not all((event.name, event.venue, event.start_at, event.end_at)):
        raise HTTPException(422, "Complete the event details before publishing")
    validate_date_range(event)
    if event.start_at is not None and event.start_at <= datetime.now(UTC):
        raise HTTPException(422, "Event must start in the future")
    # Zones/inventory belong to the next change. Never publish saleable events without them.
    raise HTTPException(422, "Ticket zones must be configured before publishing")


@router.post("/events/{event_id}/unpublish", response_model=EventResponse)
def unpublish_event(event_id: UUID, owner: EventOwner, db: Db) -> Event:
    event = require_access(db, event_id, owner)
    if event.status != EventStatus.PUBLISHED:
        raise HTTPException(409, "Event is not published")
    # A future inventory/ordering service must check committed sales before this transition.
    raise HTTPException(409, "Unpublishing is unavailable until sales checks exist")
