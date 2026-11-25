# Ticketing formatting baseline

## Requirement: Stable Ruff formatting
All tracked Python files under `services/ticketing` SHALL comply with the configured Ruff formatter.

### Scenario: Formatting verification
- **WHEN** `python -m ruff format --check .` is executed within `services/ticketing`
- **THEN** it exits successfully without modifying files.

## Requirement: No behavior changes
The normalization SHALL not introduce changes to business logic, database schema semantics, authorization, stock constraints, idempotency, or HTTP contracts.

### Scenario: Regression
- **WHEN** lint, type checking, unit and PostgreSQL suites run
- **THEN** the existing behavior continues to pass and every skipped scenario is disclosed.

## Requirement: Isolated review
The formatting SHALL be merged only through an approved PR, without including unrelated local `.gitignore` changes.
