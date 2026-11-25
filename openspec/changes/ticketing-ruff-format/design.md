## Design

Use Ruff formatter with current `services/ticketing/pyproject.toml` settings. Do not refactor logic, change database migrations, introduce dependency upgrades, or alter API contracts. Apply a formatting-only commit in the existing isolated branch `chore/ticketing-ruff-format`.

Review the Git diff for purely stylistic transformations (spacing, indentation, wrapping, blank lines, formatting of expressions), including files under `alembic`, scripts, and tests. Verify no sensitive or generated files are tracked.

## Verification

- `python -m ruff check .`
- `python -m ruff format --check .`
- `python -m mypy ticketing_service`
- `python -m pytest -q -rs`
- Git diff inspection and full GitHub Actions

PostgreSQL-dependent tests are not covered by the local run; require the existing CI job to verify them.

No automatic deployment, archival, or direct merge into main.
