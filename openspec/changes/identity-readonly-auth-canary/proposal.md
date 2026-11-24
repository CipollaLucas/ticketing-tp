## Why

Identity's accounts now match the four Legacy accounts, with zero missing UUID references. However, authorization for purchases/events is still coupled to Legacy User rows, locks and sessions, so replacing get_current_user now would invalidate transactional revocation guarantees and might break existing UI sessions.

## What changes

- Introduce a disabled-by-default, read-only Identity canary route at `GET /api/v1/identity/canary`.
- Require a current token verified by the existing remote Identity HTTP port and cross-check UUID, username and role against Legacy.
- Deny missing/expired/revoked credentials, Identity unavailability and local identity drift without fallback.
- Add fake-port tests covering successes, 401, 503, 409, missing bearer and disabled 404.
- Keep all production auth, purchases, event/stock and session tables unchanged.

## Out of scope

No runtime auth cutover. No new user migration. No FK deletion. No gateway replacement. The canary is a read-only diagnostic, not evidence that microservices are fully separated.
