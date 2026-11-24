# ADR-0010 — Remote authorization rechecks before business writes

Status: Proposed. No runtime cutover.

The current Legacy backend serializes purchase role checks with local `users` row locks, but the Identity service owns a separate PostgreSQL database. A remote introspection call cannot participate in that local database transaction, and an Identity role can change immediately after introspection. **Two remote checks do not provide atomic authorization with respect to remote revocations.**

This increment introduces only a pure application-side `verify_remote_authorization` gate with no transport, ORM or FastAPI dependency. It validates roles against each fresh Identity response, compares UUID/username with the initial snapshot and propagates remote session rejection and availability failures. Tests simulate revocation, role changes, identity drift and outages between initial and subsequent checks. No endpoint invokes the gate yet; current Legacy purchase locking and session authority stay unchanged.

## Required cutover decision

Before switching write endpoints to Identity, define a synchronization/fencing protocol or a business policy that explicitly accepts authorization timing windows. Rechecking after acquiring the local resource lock narrows the window but does not eliminate it; a separate service may revoke the role immediately after the second verification. Do not treat this gate as an atomic replacement for the Legacy lock.

## Release constraints

- Keep remote authentication disabled for business writes until cutover design and integration tests are approved.
- Maintain rollback procedure and service-unavailable fail-closed behavior.
- Verify concurrency, idempotency and session revocation across real containers before cutover.
- Do not migrate or delete Legacy user/session records in this PR.
