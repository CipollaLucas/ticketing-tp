"""Create the first administrator interactively in Identity's own database."""
import argparse
from getpass import getpass

from pydantic import SecretStr, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from identity.adapters.http import RegisterRequest, passwords
from identity.adapters.persistence import SqlAlchemyIdentityStore, UserRow
from identity.database import engine
from identity.domain.model import Role


def main() -> None:
    parser = argparse.ArgumentParser(description="Create Identity admin after Alembic migration")
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", default="Administrator")
    args = parser.parse_args()
    password = getpass("Password (12-128 characters): ")
    if password != getpass("Repeat password: "):
        parser.exit(1, "Passwords do not match\n")
    try:
        payload = RegisterRequest(
            username=args.username, display_name=args.display_name,
            password=SecretStr(password),
        )
        with Session(engine) as db:
            store = SqlAlchemyIdentityStore(db)
            store.create(
                payload.username, payload.display_name,
                passwords.hash(payload.password.get_secret_value()),
            )
            row = db.query(UserRow).filter(UserRow.username == payload.username).one()
            row.role = Role.ADMINISTRATOR.value
            db.commit()
            print(f"Administrator created: {payload.username}")
    except ValidationError:
        parser.exit(1, "Invalid username, display name or password length\n")
    except IntegrityError:
        parser.exit(1, "Username already exists\n")


if __name__ == "__main__":
    main()
