"""Read-only preflight for Identity cutover; cannot migrate, alter or delete rows.

This audit verifies the independent Identity DB contains the same UUIDs and
credentials as the legacy system, including all referenced owner/customer IDs.
It is intentionally separate from the backfill command and runtime adapters.
"""
import argparse
import os
from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from identity.backfill import BackfillRejected, _fingerprint, _read_users


@dataclass(frozen=True)
class ReadinessReport:
    legacy_users: int
    identity_users: int
    referenced_ids: int
    missing_accounts: int
    mismatched_accounts: int
    missing_references: int
    legacy_sessions: int
    fingerprint: str

    @property
    def ready_for_review(self) -> bool:
        return (
            self.legacy_users > 0
            and self.missing_accounts == 0
            and self.mismatched_accounts == 0
            and self.missing_references == 0
        )


def _count(connection, table_name: str) -> int:
    return int(connection.scalar(text(f"SELECT count(*) FROM {table_name}")) or 0)


def assess(source_url: str, target_url: str) -> ReadinessReport:
    if make_url(source_url) == make_url(target_url):
        raise BackfillRejected("Source and target databases must be different")
    source_engine = create_engine(source_url, pool_pre_ping=True)
    target_engine = create_engine(target_url, pool_pre_ping=True)
    try:
        with source_engine.connect() as source, target_engine.connect() as target:
            if source.dialect.name == "postgresql":
                source.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            if target.dialect.name == "postgresql":
                target.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))

            legacy = _read_users(source)
            independent = _read_users(target)
            legacy_by_id = {user[0]: user for user in legacy}
            independent_by_id = {user[0]: user for user in independent}
            reference_rows = source.execute(text(
                "SELECT owner_id AS user_id FROM events "
                "UNION SELECT customer_id AS user_id FROM orders"
            ))
            references = {row.user_id for row in reference_rows}
            # SQLAlchemy UUIDs on PostgreSQL and string UUIDs on SQLite.
            from uuid import UUID
            references = {UUID(str(value)) for value in references if value is not None}

            missing_accounts = sum(uid not in independent_by_id for uid in legacy_by_id)
            mismatched_accounts = sum(
                independent_by_id.get(uid) is not None
                and independent_by_id[uid] != legacy_row
                for uid, legacy_row in legacy_by_id.items()
            )
            missing_references = sum(uid not in independent_by_id for uid in references)
            return ReadinessReport(
                legacy_users=len(legacy),
                identity_users=len(independent),
                referenced_ids=len(references),
                missing_accounts=missing_accounts,
                mismatched_accounts=mismatched_accounts,
                missing_references=missing_references,
                legacy_sessions=_count(source, "auth_sessions"),
                fingerprint=_fingerprint(legacy),
            )
    finally:
        source_engine.dispose()
        target_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only Identity cutover readiness audit; does not apply migrations"
    )
    parser.parse_args()
    source = os.environ.get("LEGACY_DATABASE_URL")
    target = os.environ.get("DATABASE_URL")
    if not source or not target:
        parser.error("LEGACY_DATABASE_URL and DATABASE_URL must both be set")
    try:
        report = assess(source, target)
    except BackfillRejected as error:
        parser.exit(2, f"ABORT: {error}\n")
    print(
        f"Legacy users: {report.legacy_users} | Identity users: {report.identity_users} | "
        f"Referenced owners/customers: {report.referenced_ids}"
    )
    print(
        f"Missing accounts: {report.missing_accounts} | "
        f"Mismatched accounts: {report.mismatched_accounts} | "
        f"Missing referenced UUIDs: {report.missing_references}"
    )
    print(f"Legacy sessions (not migrated): {report.legacy_sessions}")
    print(f"Source fingerprint: {report.fingerprint}")
    print("READ ONLY: No schema, user, password or session records changed.")
    if not report.ready_for_review:
        parser.exit(2, "NOT READY: Existing identities or references do not match.\n")
    print(
        "READY FOR MANUAL REVIEW ONLY: identity consistency verified. "
        "Live auth routing, schema separation and rollout are NOT yet implemented."
    )


if __name__ == "__main__":
    main()
