"""Event metadata and publication; inventory and purchasing are separate work."""

from datetime import UTC, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)
from sqlalchemy import func, select

from app.auth import Db, StrictRequest, require_event_owner, require_owner_or_admin
from app.models import Event, Order, Role, User

router = APIRouter(prefix="/api/v1", tags=["Events"])
Owner = Annotated[User, Depends(require_event_owner)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Venue = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def utc(value: datetime) -> datetime:
    # SQLite loses timezone metadata; PostgreSQL preserves aware datetimes.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class EventCreate(StrictRequest):
    name: Name
    description: Description
    venue: Venue
    start_at: AwareDatetime
    end_at: AwareDatetime

    @field_validator("name", "venue", "description")
    @classmethod
    def postgres_text(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("Event text must not contain NUL bytes")
        return value

    @field_validator("start_at", "end_at")
    @classmethod
    def normalize_date(cls, value: datetime) -> datetime:
        try:
            return value.astimezone(UTC)
        except OverflowError:
            raise ValueError("Date is outside the supported UTC range") from None

    @model_validator(mode="after")
    def valid_dates(self) -> Self:
        if self.start_at <= datetime.now(UTC):
            raise ValueError("Event start must be in the future")
        if self.end_at <= self.start_at:
            raise ValueError("Event end must follow start")
        return self


class EventUpdate(StrictRequest):
    name: Name | None = None
    description: Description | None = None
    venue: Venue | None = None
    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def nonempty_nonnull_patch(self) -> Self:
        if not self.model_fields_set or any(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError("Provide at least one non-null event field")
        return self


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    owner_id: UUID
    name: str
    description: str
    venue: str
    start_at: datetime
    end_at: datetime
    status: Literal["draft", "published"]
    created_at: datetime
    updated_at: datetime

    @field_validator("start_at", "end_at", "created_at", "updated_at")
    @classmethod
    def serialize_utc(cls, value: datetime) -> datetime:
        return utc(value)


class EventPage(BaseModel):
    items: list[EventResponse]
    limit: int
    offset: int
    total: int


def event_values(event: Event) -> dict[str, object]:
    return {
        "name": event.name, "description": event.description, "venue": event.venue,
        "start_at": utc(event.start_at), "end_at": utc(event.end_at),
    }


def validate_event(values: dict[str, object]) -> EventCreate:
    try:
        return EventCreate.model_validate(values)
    except ValidationError:
        raise HTTPException(422, "Invalid event metadata or dates") from None


def writable_event(event_id: UUID, user: User, db: Db) -> Event:
    event = db.scalar(
        select(Event).where(Event.id == event_id).with_for_update()
        .execution_options(populate_existing=True)
    )
    if event is None:
        raise HTTPException(404, "Event not found")
    # Authorization must still hold after a request waits on a row lock.
    db.refresh(user)
    require_event_owner(user)
    require_owner_or_admin(user, event.owner_id)
    return event


@router.post("/events", response_model=EventResponse, status_code=201)
def create_event(payload: EventCreate, user: Owner, db: Db) -> Event:
    event = Event(owner_id=user.id, **payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.patch("/events/{event_id}", response_model=EventResponse)
def update_event(event_id: UUID, payload: EventUpdate, user: Owner, db: Db) -> Event:
    event = writable_event(event_id, user, db)
    if event.status != "draft":
        raise HTTPException(409, "Unpublish the event before editing")
    merged = validate_event({**event_values(event), **payload.model_dump(exclude_unset=True)})
    for field, value in merged.model_dump().items():
        setattr(event, field, value)
    event.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(event)
    return event


def transition(event_id: UUID, status: str, user: User, db: Db) -> Event:
    event = writable_event(event_id, user, db)
    if event.status == status:
        return event
    if status == "published":
        validate_event(event_values(event))
        if not event.description.strip():
            raise HTTPException(422, "Publication requires a description")
    if status == "draft" and db.scalar(select(Order.id).where(Order.event_id == event.id).limit(1)):
        raise HTTPException(409, "Cannot unpublish an event with sales")
    event.status = status
    event.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(event)
    return event


@router.post("/events/{event_id}/publish", response_model=EventResponse)
def publish_event(event_id: UUID, payload: StrictRequest, user: Owner, db: Db) -> Event:
    return transition(event_id, "published", user, db)


@router.post("/events/{event_id}/unpublish", response_model=EventResponse)
def unpublish_event(event_id: UUID, payload: StrictRequest, user: Owner, db: Db) -> Event:
    return transition(event_id, "draft", user, db)


def event_page(db: Db, limit: int, offset: int, *conditions) -> EventPage:
    query = select(Event).where(*conditions)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    events = db.scalars(query.order_by(Event.start_at, Event.id).limit(limit).offset(offset)).all()
    return EventPage(
        items=[EventResponse.model_validate(event) for event in events],
        total=total, limit=limit, offset=offset,
    )


@router.get("/events", response_model=EventPage)
def catalog(db: Db, limit: Limit = 20, offset: Offset = 0) -> EventPage:
    return event_page(
        db, limit, offset, Event.status == "published", Event.start_at > datetime.now(UTC)
    )


@router.get("/owner/events", response_model=EventPage)
def owner_events(user: Owner, db: Db, limit: Limit = 20, offset: Offset = 0) -> EventPage:
    conditions = [] if user.role == Role.ADMINISTRATOR else [Event.owner_id == user.id]
    return event_page(db, limit, offset, *conditions)


@router.get("/events/{event_id}", response_model=EventResponse)
def public_event(event_id: UUID, db: Db) -> Event:
    event = db.scalar(select(Event).where(Event.id == event_id, Event.status == "published"))
    if event is None:
        raise HTTPException(404, "Event not found")
    return event
