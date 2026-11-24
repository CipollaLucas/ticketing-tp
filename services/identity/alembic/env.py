"""Alembic migrations for Identity only, no legacy backend models."""
from sqlalchemy import create_engine, pool

from alembic import context
from identity.adapters.persistence import Base
from identity.settings import settings

config = context.config
url = settings.database_url

if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
