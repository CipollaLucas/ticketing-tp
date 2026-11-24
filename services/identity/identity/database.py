"""Service-private engine. Never access legacy backend tables or sessions."""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from identity.settings import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)


def get_db() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
