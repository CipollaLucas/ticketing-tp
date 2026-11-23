from sqlalchemy import func, select

from app.models import User


def test_bootstrap_admin_hashes_password_and_refuses_duplicate(db):
    import pytest

    from app.create_admin import create_administrator

    user = create_administrator(db, " Admin ", "safe-test-passphrase-2026", " Administrator ")
    assert user.role == "administrator"
    assert user.username == "admin"
    assert user.display_name == "Administrator"
    assert user.password_hash.startswith("$argon2id$")
    with pytest.raises(ValueError, match="Username already exists"):
        create_administrator(db, "ADMIN", "safe-test-passphrase-2026", "Other")
    assert db.scalar(select(func.count()).select_from(User)) == 1


def test_bootstrap_admin_validates_before_writing(db):
    import pytest
    from pydantic import ValidationError

    from app.create_admin import create_administrator

    with pytest.raises(ValidationError):
        create_administrator(db, "admin", "tiny", "Administrator")
    assert db.scalar(select(func.count()).select_from(User)) == 0
