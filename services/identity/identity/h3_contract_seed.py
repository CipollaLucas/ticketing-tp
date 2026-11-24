"""Seed two accounts exclusively inside a disposable H3 Identity database.

Not a production bootstrap command. Refuses non-H3 databases and requires an
explicit opt-in. Only Identity owns/writes its user rows.
"""
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from identity.adapters.crypto import Argon2Passwords
from identity.adapters.persistence import UserRow
from identity.database import engine


def main() -> None:
    if os.getenv("H3_CONTRACT_SEED") != "yes" or engine.url.database != "h3_identity_test":
        raise SystemExit("Refusing to seed a non-disposable H3 Identity database")
    password = os.environ["H3_TEST_PASSWORD"]
    if len(password) < 16:
        raise SystemExit("H3 test password must be at least 16 characters")
    hashed = Argon2Passwords().hash(password)
    with Session(engine) as db:
        if db.scalar(select(UserRow.id).limit(1)) is not None:
            raise SystemExit("H3 test database must be empty")
        db.add_all([
            UserRow(
                username="h3owner", display_name="H3 Owner",
                password_hash=hashed, role="event_owner",
            ),
            UserRow(
                username="h3customer", display_name="H3 Customer",
                password_hash=hashed, role="customer",
            ),
        ])
        db.commit()
    print("PASS: two disposable H3 Identity test accounts seeded")


if __name__ == "__main__":
    main()
