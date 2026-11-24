"""One-time offline user migration is dry-run by default, collision-safe and idempotent."""
from uuid import UUID

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from identity.adapters.persistence import Base, SessionRow, UserRow
from identity.backfill import BackfillRejected, backfill

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
SECOND_ID = UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture
def databases(tmp_path):
    source = f"sqlite+pysqlite:///{tmp_path / 'legacy.db'}"
    target = f"sqlite+pysqlite:///{tmp_path / 'identity.db'}"
    src = create_engine(source)
    dst = create_engine(target)
    with src.begin() as conn:
        conn.execute(text(
            "CREATE TABLE users (id VARCHAR(36), username TEXT, display_name TEXT, "
            "password_hash TEXT, role TEXT)"
        ))
        conn.execute(text(
            "INSERT INTO users VALUES (:id, :username, :display_name, :password_hash, :role)"
        ), {
            "id": str(USER_ID), "username": "demo", "display_name": "Legacy Demo",
            "password_hash": "$argon2id$v=19$sample-hash", "role": "event_owner",
        })
    Base.metadata.create_all(dst)
    src.dispose()
    dst.dispose()
    return source, target


def target_rows(url):
    engine = create_engine(url)
    try:
        with Session(engine) as db:
            return db.scalars(select(UserRow)).all()
    finally:
        engine.dispose()


def test_default_dry_run_never_writes(databases):
    source, target = databases
    report = backfill(source, target)
    assert (report.source_count, report.pending, report.unchanged) == (1, 1, 0)
    assert not report.applied
    assert len(report.fingerprint) == 64
    assert target_rows(target) == []


def test_apply_requires_snapshot_and_is_idempotent(databases):
    source, target = databases
    with pytest.raises(BackfillRejected, match="fingerprint"):
        backfill(source, target, apply=True)
    preview = backfill(source, target)
    result = backfill(
        source, target, apply=True, expected_fingerprint=preview.fingerprint,
    )
    assert result.applied and result.pending == 1
    account = target_rows(target)[0]
    assert account.id == USER_ID and account.role == "event_owner"
    assert account.password_hash.startswith("$argon2id$")
    second = backfill(
        source, target, apply=True, expected_fingerprint=preview.fingerprint,
    )
    assert second.pending == 0 and second.unchanged == 1
    engine = create_engine(target)
    try:
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(SessionRow)) == 0
    finally:
        engine.dispose()


def test_changed_source_fingerprint_aborts(databases):
    source, target = databases
    before = backfill(source, target)
    engine = create_engine(source)
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET role = 'customer' WHERE username = 'demo'"))
    engine.dispose()
    with pytest.raises(BackfillRejected, match="changed"):
        backfill(source, target, apply=True, expected_fingerprint=before.fingerprint)
    assert not target_rows(target)


def test_username_collision_is_reported_and_blocks_all_writes(databases):
    source, target = databases
    engine = create_engine(target)
    with Session(engine) as db:
        db.add(UserRow(
            id=SECOND_ID, username="demo", display_name="New Identity",
            password_hash="new-hash", role="customer",
        ))
        db.commit()
    engine.dispose()
    report = backfill(source, target)
    assert report.conflicts and not report.applied
    with pytest.raises(BackfillRejected, match="Conflicting"):
        backfill(source, target, apply=True, expected_fingerprint=report.fingerprint)
    assert len(target_rows(target)) == 1


def test_different_existing_uuid_attributes_cannot_be_overwritten(databases):
    source, target = databases
    engine = create_engine(target)
    with Session(engine) as db:
        db.add(UserRow(
            id=USER_ID, username="demo", display_name="Modified",
            password_hash="changed-hash", role="customer",
        ))
        db.commit()
    engine.dispose()
    report = backfill(source, target)
    assert report.conflicts and not report.applied


def test_unknown_role_is_not_imported(databases):
    source, target = databases
    engine = create_engine(source)
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET role = 'root'"))
    engine.dispose()
    report = backfill(source, target)
    assert report.conflicts
    assert target_rows(target) == []


def test_source_and_target_cannot_be_same_database(databases):
    source, _ = databases
    with pytest.raises(BackfillRejected, match="different"):
        backfill(source, source)
