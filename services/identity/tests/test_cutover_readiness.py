"""Cutover checker cannot write or certify a system before identities agree."""
from uuid import UUID

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from identity.adapters.persistence import Base, UserRow
from identity.backfill import backfill
from identity.cutover_readiness import assess

LEGACY_ID = UUID("00000000-0000-0000-0000-000000000011")


@pytest.fixture
def databases(tmp_path):
    source = f"sqlite+pysqlite:///{tmp_path / 'legacy-readiness.db'}"
    target = f"sqlite+pysqlite:///{tmp_path / 'identity-readiness.db'}"
    src = create_engine(source)
    dst = create_engine(target)
    with src.begin() as connection:
        connection.execute(text(
            "CREATE TABLE users (id VARCHAR(36), username TEXT, display_name TEXT, "
            "password_hash TEXT, role TEXT)"
        ))
        connection.execute(text("CREATE TABLE events (owner_id VARCHAR(36))"))
        connection.execute(text("CREATE TABLE orders (customer_id VARCHAR(36))"))
        connection.execute(text("CREATE TABLE auth_sessions (token_hash TEXT)"))
        connection.execute(text(
            "INSERT INTO users VALUES (:id, 'owner', 'Owner', 'argon2-hash', 'event_owner')"
        ), {"id": str(LEGACY_ID)})
        connection.execute(text("INSERT INTO events VALUES (:id)"), {"id": str(LEGACY_ID)})
        connection.execute(text("INSERT INTO orders VALUES (:id)"), {"id": str(LEGACY_ID)})
        connection.execute(text("INSERT INTO auth_sessions VALUES ('legacy-only')"))
    Base.metadata.create_all(dst)
    src.dispose()
    dst.dispose()
    return source, target


def test_readiness_refuses_missing_identity_without_writing(databases):
    source, target = databases
    report = assess(source, target)
    assert report.legacy_users == 1 and report.identity_users == 0
    assert report.referenced_ids == 1
    assert report.missing_accounts == 1 and report.missing_references == 1
    assert report.legacy_sessions == 1
    assert not report.ready_for_review
    again = assess(source, target)
    assert again == report


def test_readiness_after_explicit_backfill_preserves_legacy_sessions(databases):
    source, target = databases
    preview = backfill(source, target)
    backfill(source, target, apply=True, expected_fingerprint=preview.fingerprint)
    report = assess(source, target)
    assert report.ready_for_review
    assert report.referenced_ids == 1
    assert report.missing_references == 0
    assert report.legacy_sessions == 1


def test_conflicting_identity_is_not_ready(databases):
    source, target = databases
    engine = create_engine(target)
    with Session(engine) as session:
        session.add(UserRow(
            id=LEGACY_ID, username="owner", display_name="Other",
            password_hash="argon2-hash", role="event_owner",
        ))
        session.commit()
    engine.dispose()
    report = assess(source, target)
    assert report.missing_accounts == 0
    assert report.mismatched_accounts == 1
    assert not report.ready_for_review


def test_missing_reference_detected_even_when_legacy_user_missing(databases):
    source, target = databases
    engine = create_engine(source)
    with engine.begin() as connection:
        connection.execute(text(
            "UPDATE orders SET customer_id = '00000000-0000-0000-0000-000000000099'"
        ))
    engine.dispose()
    preview = backfill(source, target)
    backfill(source, target, apply=True, expected_fingerprint=preview.fingerprint)
    report = assess(source, target)
    assert report.missing_accounts == 0
    assert report.missing_references == 1
    assert not report.ready_for_review
