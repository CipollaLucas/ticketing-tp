## Why

Ticketing passes Ruff lint and type checking but its existing source and tests are not uniformly formatted: local `ruff format --check .` identified 43 files requiring formatting. A formatting-only baseline reduces future PR noise and prevents recurring formatting divergence.

## What changes

Normalize formatting for the existing independent Ticketing service using Ruff. This change does not intentionally alter application semantics, PostgreSQL schema, OpenAPI routes, or feature flags.

## Scope

Only `services/ticketing/`. The local `.gitignore` change remains outside this PR.

## Evidence and caution

The formatting commit was already prepared locally before this OpenSpec record was added; this is a retrospective traceability record, not a claim that proposal approval preceded implementation. Local evidence supplied by contributor: `ruff check .` passed, `ruff format --check .` 45 formatted, `mypy ticketing_service` passed, `pytest -q` 92 passed / 15 skipped (PostgreSQL unavailable) / 1 warning. CI and independent PR review remain pending.
