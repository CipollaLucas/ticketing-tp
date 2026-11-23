"""Local administrative bootstrap. Never expose this operation through HTTP."""

import argparse
from getpass import getpass

from pydantic import SecretStr, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import RegisterRequest, password_hasher
from app.database import engine
from app.models import Role, User


def create_administrator(db: Session, username: str, password: str, display_name: str) -> User:
    payload = RegisterRequest(
        username=username, password=SecretStr(password), display_name=display_name
    )
    user = User(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=password_hasher.hash(payload.password.get_secret_value()),
        role=Role.ADMINISTRATOR.value,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("Username already exists") from None
    db.refresh(user)
    return user


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a local administrator (run migrations first)"
    )
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", default="Administrator")
    args = parser.parse_args()
    password = getpass("Password (12–128 characters): ")
    if password != getpass("Repeat password: "):
        parser.exit(1, "Passwords do not match\n")
    try:
        with Session(engine) as db:
            user = create_administrator(db, args.username, password, args.display_name)
            print(f"Administrator created: {user.username}")
    except ValidationError:
        # Pydantic exceptions contain raw inputs; never print credentials.
        parser.exit(1, "Invalid username, display name or password length\n")
    except ValueError:
        parser.exit(1, "Username already exists\n")


if __name__ == "__main__":
    main()
