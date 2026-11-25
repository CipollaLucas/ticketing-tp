"""Seed H5-only administrator inside disposable Identity PostgreSQL.

Not a production or generic bootstrap. Requires the existing H3 test users.
"""
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from identity.adapters.crypto import Argon2Passwords
from identity.adapters.persistence import UserRow
from identity.database import engine


def main() -> None:
    if (
        os.getenv("H3_CONTRACT_SEED") != "yes"
        or os.getenv("H5_DISPOSABLE_ADMIN_SEED") != "yes"
        or engine.url.database != "h3_identity_test"
    ):
        raise SystemExit("REFUSED: administrator seed requires disposable H5 Identity")
    password = os.environ["H3_TEST_PASSWORD"]
    if len(password) < 16:
        raise SystemExit("H5 disposable password is too short")
    with Session(engine) as db:
        existing = set(db.scalars(select(UserRow.username)).all())
        if existing != {"h3owner", "h3customer"}:
            raise SystemExit("REFUSED: expected exactly two H3 disposable users")
        db.add(
            UserRow(
                username="h5admin",
                display_name="H5 Administrator",
                password_hash=Argon2Passwords().hash(password),
                role="administrator",
            )
        )
        db.commit()
    print("PASS: H5-only disposable administrator created")


if __name__ == "__main__":
    main()
