from sqlalchemy import create_engine, pool

from alembic import context
from app import models  # noqa: F401
from app.database import Base
from app.settings import settings

config = context.config
url = config.get_main_option("sqlalchemy.url") or settings.database_url

if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    connection = config.attributes["connection"]
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
    if connection.dialect.name == "sqlite":
        # SQLite DDL is non-transactional. A batch-table rebuild may commit
        # internally to toggle FK enforcement; persist Alembic's version row
        # after the migration callback returns, not inside the revision.
        connection.commit()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata)
            with context.begin_transaction():
                context.run_migrations()
            if connection.dialect.name == "sqlite":
                connection.commit()
    finally:
        engine.dispose()
