"""H5 CI-only independent restore of all three disposable PostgreSQL databases.

No remote Docker host, no persistent volumes, no published ports, no Legacy.
"""
import hashlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import UUID

from verify_identity_db_backups import (
    BackupError,
    dump_source,
    restore_isolated,
    source_table_counts,
)

PROJECT = "h5-gateway-ci"
DATABASES = {
    "identity": (
        "h3-identity-db", "h3_identity", "h3_identity_test",
        ("users", "auth_sessions"),
    ),
    "events": (
        "h3-events-db", "h3_events", "h3_events_test",
        ("events", "event_publication_intents", "event_unpublish_intents"),
    ),
    "ticketing": (
        "h4-ticketing-db", "h4_ticketing", "h4_ticketing_test",
        ("sale_gates", "sale_gate_commands", "zones", "seats", "orders",
         "order_items", "tickets"),
    ),
}
COMPOSE = [
    "-f", "docker-compose.h3-contract.yml",
    "-f", "docker-compose.h4-live.yml",
    "-f", "docker-compose.h5-gateway-preview.yml",
]


def run(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True, check=False, timeout=30)
    if result.returncode:
        raise BackupError("Disposable Compose container discovery failed")
    return result.stdout.strip()


def fixture(log: str, field: str) -> UUID:
    values = re.findall(
        rf"^H5_RESTART_{field}=([a-f0-9-]{{36}})$", log, re.MULTILINE
    )
    if len(values) != 1:
        raise BackupError(f"Missing or repeated disposable {field} fixture")
    return UUID(values[0])


def assert_source_references(containers: dict, event_id: UUID, order_id: UUID,
                             ticket_id: UUID, zone_id: UUID) -> None:
    # Fixed SQL structure: only canonical UUID values obtained from H5 smoke.
    probes = {
        "events": (
            "h3_events", "h3_events_test",
            f"SELECT count(*) FROM events WHERE id='{event_id}' AND status='published'",
        ),
        "ticketing": (
            "h4_ticketing", "h4_ticketing_test",
            "SELECT count(*) FROM orders o "
            "JOIN order_items oi ON oi.order_id=o.id "
            "JOIN tickets t ON t.order_item_id=oi.id "
            f"WHERE o.id='{order_id}' AND o.event_id='{event_id}' "
            f"AND oi.zone_id='{zone_id}' AND t.id='{ticket_id}'",
        ),
    }
    for service, (user, db, sql) in probes.items():
        output = run([
            "docker", "exec", containers[service],
            "psql", "-U", user, "-d", db, "-X", "-A", "-t", "-c", sql,
        ])
        if output != "1":
            raise BackupError(f"Disposable cross-service fixture missing from {service}")


def main() -> int:
    if (
        os.getenv("H5_DISPOSABLE_RESTORE_UAT") != "yes"
        or os.getenv("H5_PROJECT") != PROJECT
        or len(sys.argv) != 2
    ):
        raise SystemExit("REFUSED: H5 restore requires explicit disposable CI project")
    log = Path(sys.argv[1]).read_text(encoding="utf-8")
    event_id = fixture(log, "EVENT_ID")
    order_id = fixture(log, "ORDER_ID")
    ticket_id = fixture(log, "TICKET_ID")
    zone_id = fixture(log, "ZONE_ID")
    containers = {}
    for kind, (service, _, _, _) in DATABASES.items():
        container = run(["docker", "compose", "-p", PROJECT, *COMPOSE, "ps", "-q", service])
        if not re.fullmatch(r"[a-f0-9]{64}", container):
            raise BackupError(f"Unexpected disposable {kind} container identifier")
        # Never let project-name coincidence authorize targeting another container.
        name = run(["docker", "inspect", "-f", "{{index .Config.Labels \"com.docker.compose.project\"}}", container])
        identity = run(["docker", "inspect", "-f", "{{index .Config.Labels \"com.docker.compose.service\"}}", container])
        if name != PROJECT or identity != service:
            raise BackupError(f"REFUSED: unexpected Docker labels for {kind}")
        containers[kind] = container
    assert_source_references(containers, event_id, order_id, ticket_id, zone_id)

    # Backups live in a Python temporary directory, not a checked-in artifact.
    with tempfile.TemporaryDirectory(prefix="h5-three-db-restore-") as directory:
        archives = {}
        for kind, (_, user, db, tables) in DATABASES.items():
            archive = Path(directory) / f"{kind}.dump"
            counts = source_table_counts(containers[kind], user, db, tables)
            checksum = dump_source(containers[kind], user, db, archive)
            archives[kind] = (archive, checksum, counts)
            print(f"BACKUP {kind}: {archive.stat().st_size} bytes, sha256={checksum[:12]}", flush=True)
        for kind, (archive, checksum, counts) in archives.items():
            if hashlib.sha256(archive.read_bytes()).hexdigest() != checksum:
                raise BackupError(f"{kind} backup checksum mismatch")
            restored = restore_isolated(kind, archive, counts)
            if restored != counts:
                raise BackupError(f"{kind} restore count mismatch")
            print(f"RESTORE {kind}: PASS, offline and network-isolated", flush=True)
    print("PASS: three independently restored PostgreSQL databases, no production access")
    print("PASS: source Events/Ticketing purchase references verified")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (BackupError, OSError, subprocess.TimeoutExpired, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
