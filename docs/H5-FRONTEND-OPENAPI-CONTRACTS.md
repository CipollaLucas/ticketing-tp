# H5 — React-to-OpenAPI public route ownership matrix

This acceptance increment verifies the **12 public API operations implemented in `frontend/src/coreApi.ts`** against the live OpenAPI documents exposed by the three independent disposable FastAPI containers.

| React function | Method and route | Owner |
| --- | --- | --- |
| register | POST /api/v1/auth/register | Identity |
| login | POST /api/v1/auth/login | Identity |
| me | GET /api/v1/auth/me | Identity |
| logout | POST /api/v1/auth/logout | Identity |
| changeRole | PATCH /api/v1/admin/users/{user_id}/role | Identity |
| ownerEvents | GET /api/v1/owner/events | Events |
| createEvent | POST /api/v1/events | Events |
| publishEvent | POST /api/v1/events/{event_id}/publish | Events |
| createZone | POST /api/v1/events/{event_id}/zones | Ticketing |
| getInventory | GET /api/v1/events/{event_id}/inventory | Ticketing |
| purchase | POST /api/v1/orders | Ticketing |
| myTickets | GET /api/v1/me/tickets | Ticketing |

The CI check:
- Requires disposable Compose project `h5-gateway-ci`, accesses `/openapi.json` only from inside each corresponding container using loopback and no Legacy
- Ensures each React exported API function retains its path reference, its owning service declares the expected method/path, and no other service declares that method/path
- Checks presence of critical Gateway ownership/denial rules, while the existing static Gateway test separately asserts regex routing priority and forwarding
- Runs before the existing real HTTP and Chromium browser journeys; CI failures block the change

**Limitations:** Method/path compatibility does not prove full response schema, complete error parity, timeout/retry semantics, every HTTP status or actual routing of each operation. Existing H5 smoke and browser tests cover selected end-to-end paths. Dynamic authorization, full normalized request/response validation, unknown route behavior and cutover/rollback remain independently gated.

This is a documented inventory, not production migration approval. OpenSpec `h5-gateway-stage-i-cutover` remains open pending final review.
