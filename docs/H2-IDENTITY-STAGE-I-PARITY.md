# H2 — Identity contract parity against functional Stage I

Source of truth: `docs/API-ETAPA-I.md`, `backend/app/auth.py` and `frontend/src/coreApi.ts` from accepted PR #28 (baseline `68ed04997`). These tests run against the **independent Identity HTTP app** with an isolated database, not against the old monolith.

| Legacy route | Identity route | Parity acceptance |
| --- | --- | --- |
| POST /api/v1/auth/register | same | 201 exact User {id,username,display_name,role}, customer, trims username/display name, reject extra/injected and invalid fields 422, duplicate 409 |
| POST /api/v1/auth/login | same | 200 exact Token {access_token,token_type,expires_in}, no-store; wrong credentials 401 |
| GET /api/v1/auth/me | same | unchanged User shape, current role from independent DB, missing/revoked session 401 + Bearer challenge |
| POST /api/v1/auth/logout | same | 204; session revoked and second use 401 |
| PATCH /api/v1/users/{id} | same | own profile editable, role injection rejected 422, another user's profile 403 |
| PATCH /api/v1/admin/users/{id}/role | same | customer 403; admin can promote/demote; existing session observes new role |

## What it proves and doesn't prove

Tests hold the **contract of one service** against documented Legacy behavior. They do not yet prove two deployed applications return byte-identical bodies for every case, nor durable Legacy data migration, token transfer, frontend routing or independent PostgreSQL cutover. The other Identity tests (PostgreSQL, admin races, external UUID and revocation) remain gates. No behavior-changing code or public routing was added.

## Next required vertical acceptance

1. Confirm local and CI isolated Identity tests pass.
2. Compare these golden cases with the original Legacy HTTP tests and report any divergent behavior.
3. Run a reversible Identity-only gateway or routing switch in an isolated multi-service UAT, preserving public `/api/v1` and keeping Events/Orders/React functional.
4. Before changing routing, verify legacy UUID/backfill and token/session policy, and prove rollback. Do not use `docker compose down -v` or `--remove-orphans`.

This PR is a **parity gate**, not a cutover.
