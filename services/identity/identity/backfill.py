"""One-time offline Identity backfill from the legacy users table.

Dry-run by default. This is a migration utility, NEVER a runtime database
adapter. The normal Identity service cannot read legacy tables.
"""
import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from identity.adapters.persistence import UserRow
from identity.domain.model import Role


class BackfillRejected(Exception):
    """A precondition failed; neither database should be modified."""


@dataclass(frozen=True)
class BackfillReport:
    source_count: int
    pending: int
    unchanged: int
    conflicts: tuple[str, ...]
    fingerprint: str
    applied: bool


def _read_users(connection) -> list[tuple[UUID, str, str, str, str]]:
    result = connection.execute(text(
        "SELECT id, username, display_name, password_hash, role FROM users ORDER BY id"
    ))
    return [
        (
            UUID(str(row.id)), str(row.username), str(row.display_name),
            str(row.password_hash), str(row.role),
        )
        for row in result
    ]


def _fingerprint(users: list[tuple[UUID, str, str, str, str]]) -> str:
    # Includes password hashes when hashing, but never prints or persists them.
    canonical = json.dumps(
        [[str(user_id), username, display_name, hashed, role]
         for user_id, username, display_name, hashed, role in users],
        separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def backfill(
    source_url: str,
    target_url: str,
    *,
    apply: bool = False,
    expected_fingerprint: str | None = None,
) -> BackfillReport:
    if make_url(source_url) == make_url(target_url):
        raise BackfillRejected("Source and target databases must be different")
    if apply and not expected_fingerprint:
        raise BackfillRejected("Apply requires --expect-fingerprint from a prior dry-run")

    source_engine = create_engine(source_url, pool_pre_ping=True)
    target_engine = create_engine(target_url, pool_pre_ping=True)
    try:
        with source_engine.connect() as source, Session(target_engine) as target:
            # PostgreSQL: the migration reads a stable source snapshot.
            if source.dialect.name == "postgresql":
                source.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            users = _read_users(source)
            fingerprint = _fingerprint(users)
            if apply and fingerprint != expected_fingerprint:
                raise BackfillRejected(
                    "Legacy users changed since dry-run; repeat the audit before applying"
                )

            existing = target.scalars(select(UserRow)).all()
            by_id = {row.id: row for row in existing}
            by_name = {row.username: row for row in existing}
            pending = []
            unchanged = 0
            conflicts = []

            for user_id, username, display_name, password_hash, role in users:
                if role not in {value.value for value in Role}:
                    conflicts.append(f"Unknown role for user {user_id}")
                    continue
                matched_by_id = by_id.get(user_id)
                matched_by_name = by_name.get(username)
                if matched_by_id is not None:
                    if (
                        matched_by_id.username == username
                        and matched_by_id.display_name == display_name
                        and matched_by_id.password_hash == password_hash
                        and matched_by_id.role == role
                    ):
                        unchanged += 1
                    else:
                        conflicts.append(f"Different attributes for existing UUID {user_id}")
                elif matched_by_name is not None:
                    conflicts.append(
                        f"Username collision: {username} belongs to different UUID"
                    )
                else:
                    pending.append(
                        UserRow(
                            id=user_id, username=username, display_name=display_name,
                            password_hash=password_hash, role=role,
                        )
                    )

            report = BackfillReport(
                source_count=len(users), pending=len(pending),
                unchanged=unchanged, conflicts=tuple(conflicts),
                fingerprint=fingerprint, applied=False,
            )
            if conflicts and apply:
                raise BackfillRejected(
                    "Conflicting target identities. No changes applied: "
                    + "; ".join(conflicts)
                )
            if apply:
                target.add_all(pending)
                target.flush()
                target.commit()
                report = BackfillReport(
                    source_count=len(users), pending=len(pending),
                    unchanged=unchanged, conflicts=(),
                    fingerprint=fingerprint, applied=True,
                )
            else:
                target.rollback()
            return report
    finally:
        source_engine.dispose()
        target_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit or import legacy users into Identity without moving sessions"
    )
    parser.add_argument("--apply", action="store_true", help="Explicitly enable writes")
    parser.add_argument(
        "--expect-fingerprint",
        help="64-character fingerprint printed by an earlier dry-run",
    )
    args = parser.parse_args()
    legacy = os.environ.get("LEGACY_DATABASE_URL")
    identity = os.environ.get("DATABASE_URL")
    if not legacy or not identity:
        parser.error("Both LEGACY_DATABASE_URL and DATABASE_URL must be set")
    try:
        result = backfill(
            legacy, identity, apply=args.apply,
            expected_fingerprint=args.expect_fingerprint,
        )
    except BackfillRejected as error:
        parser.exit(2, f"ABORT: {error}\n")
    print(
        f"Identity backfill: source={result.source_count}, pending={result.pending}, "
        f"unchanged={result.unchanged}, conflicts={len(result.conflicts)}, "
        f"applied={result.applied}"
    )
    print(f"Snapshot fingerprint: {result.fingerprint}")
    for conflict in result.conflicts:
        print(f"CONFLICT: {conflict}")
    if result.conflicts:
        parser.exit(2, "No writes performed. Resolve all collisions before any apply.\n")
    if not args.apply:
        print("DRY RUN ONLY. No rows imported and no sessions copied.")


if __name__ == "__main__":
    main()
