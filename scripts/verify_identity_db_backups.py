#!/usr/bin/env python3
"""Backup BOTH running development PostgreSQL instances and verify isolated restores.

Uses docker CLI + Python standard library. No local PostgreSQL client required.
All verification containers are temporary, have --network none and no published ports.
Never runs pg_restore against live containers.
"""
import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LABELS = {"legacy": "db", "identity": "identity-db"}
TABLES = {
    "legacy": ("users", "auth_sessions", "events", "orders"),
    "identity": ("users", "auth_sessions"),
}
IMAGE = "postgres:16-alpine"
SAFE_NAME = re.compile(r"^[a-zA-Z0-9_.-]+$")


class BackupError(RuntimeError):
    pass


def cmd(args, *, output=None, timeout=120, operation="Docker operation"):
    # Only allow an explicit, non-secret operation label in error output.
    # Never echo argv (contains POSTGRES_PASSWORD during docker run) or raw stderr.
    result = subprocess.run(
        args, stdout=output if output is not None else subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=timeout, check=False,
    )
    if result.returncode != 0:
        # Never print subprocess stderr: some clients may echo database environment.
        lines = result.stderr.decode("utf-8", errors="replace").splitlines()
        safe_errors = []
        for line in lines:
            stripped = line.strip()
            # PostgreSQL-generated error category only: redact SQL literals and
            # values, do not echo arbitrary Docker diagnostics or SQL statements.
            if stripped.startswith(("pg_restore: error:", "psql: error:", "ERROR:")):
                reason = stripped.split(":", 2)[-1].strip()
                reason = re.sub(r"'[^']*'", "'[redacted]'", reason)
                reason = re.sub(r'password\s*[:=]\s*\S+', 'password=[redacted]', reason, flags=re.I)
                safe_errors.append(reason[:180])
        suffix = f" | PostgreSQL: {'; '.join(safe_errors[:2])}" if safe_errors else ""
        raise BackupError(f"{operation} failed (exit {result.returncode}){suffix}")
    return result.stdout.decode("utf-8", errors="replace").strip() if output is None else ""


def compose_args(kind):
    base = ["docker", "compose", "-f", str(ROOT / "docker-compose.yml")]
    if kind == "identity":
        base += ["-f", str(ROOT / "docker-compose.identity.yml"), "--profile", "identity"]
    return base


def service_container(kind):
    environment_key = "IDENTITY_INTERNAL_TOKEN"
    if kind == "identity" and not os.environ.get(environment_key):
        # Compose needs the variable to parse the opt-in overlay; this value is not
        # given to any existing container, nor used to authenticate to Identity.
        os.environ[environment_key] = "backup-compose-config-only-" + secrets.token_hex(24)
    value = cmd(compose_args(kind) + ["ps", "-q", LABELS[kind]]).strip()
    if not value or len(value.splitlines()) != 1:
        raise BackupError(f"{kind} database container is not running")
    return value


def inspect_config(container_id):
    keys = {}
    for variable in ("POSTGRES_USER", "POSTGRES_DB"):
        value = cmd([
            "docker", "exec", container_id, "sh", "-c",
            f'printf "%s" "${variable}"',
        ])
        if not value or not SAFE_NAME.fullmatch(value):
            raise BackupError(f"Invalid {variable} in {container_id[:12]}")
        keys[variable] = value
    return keys["POSTGRES_USER"], keys["POSTGRES_DB"]


def source_table_counts(container_id, user, database, tables):
    query = "SELECT " + ", ".join(
        f"(SELECT count(*) FROM public.{table})" for table in tables
    ) + ";"
    output = cmd([
        "docker", "exec", container_id, "psql", "-U", user, "-d", database,
        "-X", "-A", "-t", "-F", "|", "-c", query,
    ], operation="read table counts")
    try:
        counts = [int(v) for v in output.splitlines()[-1].split("|")]
    except (IndexError, ValueError) as error:
        raise BackupError("Cannot read source table counts") from error
    if len(counts) != len(tables):
        raise BackupError("Unexpected source table count response")
    return dict(zip(tables, counts))


def dump_source(container_id, user, database, destination):
    with destination.open("wb") as file:
        cmd([
            "docker", "exec", container_id, "pg_dump", "-U", user,
            "-d", database, "--format=custom", "--no-owner", "--no-acl",
        ], output=file, timeout=180)
    if destination.stat().st_size < 256:
        raise BackupError("Backup is unexpectedly small")
    return hashlib.sha256(destination.read_bytes()).hexdigest()


def restore_isolated(kind, archive, expected_counts):
    # Separate, throwaway PostgreSQL. No host ports, no network, no application mounts.
    name = "ticketing-verify-" + kind + "-" + secrets.token_hex(5)
    password = secrets.token_urlsafe(24)
    started = False
    try:
        cmd([
            "docker", "run", "-d", "--rm", "--network", "none", "--name", name,
            "-e", "POSTGRES_USER=verify", "-e", "POSTGRES_DB=verify",
            "-e", f"POSTGRES_PASSWORD={password}", IMAGE,
        ])
        started = True
        for _ in range(50):
            ready = subprocess.run(
                ["docker", "exec", name, "pg_isready", "-U", "verify", "-d", "verify"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.4)
        else:
            raise BackupError("Isolated PostgreSQL did not become ready")
        print(f"VERIFY {kind}: restoring archive into temporary offline PostgreSQL", flush=True)
        cmd(["docker", "cp", str(archive), f"{name}:/tmp/verify.dump"],
            operation=f"copy {kind} archive to temporary PostgreSQL")
        cmd([
            "docker", "exec", name, "pg_restore",
            "-U", "verify", "-d", "verify",
            "--exit-on-error", "--no-owner", "--no-acl", "/tmp/verify.dump",
        ], timeout=180, operation=f"pg_restore {kind} in temporary PostgreSQL")
        print(f"VERIFY {kind}: checking restored table counts", flush=True)
        actual = source_table_counts(name, "verify", "verify", TABLES[kind])
        if actual != expected_counts:
            raise BackupError(
                f"Restore counts differ for {kind}; source may have changed during dump"
            )
        return actual
    finally:
        if started:
            subprocess.run(
                ["docker", "stop", "--time", "2", name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )


def main():
    parser = argparse.ArgumentParser(
        description="pg_dump both live DBs, restore to two disconnected containers and compare counts"
    )
    parser.add_argument(
        "--output-dir", default=str(ROOT / "backups" / "verified"),
        help="Local private destination for archives and manifest",
    )
    args = parser.parse_args()
    target = Path(args.output_dir).expanduser().resolve()
    if target == ROOT or target.is_relative_to(ROOT / ".git"):
        parser.error("Choose an output directory outside the .git directory")
    target.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        parser.error("Backup directory cannot be a symlink")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest = {"timestamp_utc": stamp, "verified": False, "databases": {}}
    try:
        # Backup both first; then restore both. Never replace or delete existing archives.
        for kind in ("legacy", "identity"):
            container = service_container(kind)
            user, database = inspect_config(container)
            counts = source_table_counts(container, user, database, TABLES[kind])
            archive = target / f"{kind}-{stamp}-{secrets.token_hex(4)}.dump"
            sha256 = dump_source(container, user, database, archive)
            manifest["databases"][kind] = {
                "archive": archive.name, "sha256": sha256,
                "bytes": archive.stat().st_size, "source_counts": counts,
            }
            print(f"BACKUP {kind}: {archive.name} ({archive.stat().st_size} bytes)")
        for kind in ("legacy", "identity"):
            data = manifest["databases"][kind]
            archive = target / data["archive"]
            if hashlib.sha256(archive.read_bytes()).hexdigest() != data["sha256"]:
                raise BackupError(f"Archive checksum changed for {kind}")
            counts = restore_isolated(kind, archive, data["source_counts"])
            data["restored_counts"] = counts
            data["restore_verified"] = True
            print(f"RESTORE {kind}: PASS, isolated and offline, counts={counts}")
        manifest["verified"] = True
        report = target / f"verification-{stamp}-{secrets.token_hex(4)}.json"
        with report.open("x", encoding="utf-8") as file:
            json.dump(manifest, file, indent=2)
            file.write("\n")
        print(f"PASS: both restored independently. Manifest: {report}")
        print("No source volumes, schemas, users or sessions were modified.")
    except (BackupError, OSError, subprocess.TimeoutExpired) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        print("Do not run Identity backfill --apply. Inspect archives and retry.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
