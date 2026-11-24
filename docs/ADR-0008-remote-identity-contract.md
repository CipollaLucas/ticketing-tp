# ADR-0008 — Private Identity introspection from Ticketing

Status: Proposed / pending CI.

The Ticketing application owns the `IdentityPort` and typed `AuthenticatedPrincipal`. An HTTP outbound adapter in the infrastructure layer communicates with the already deployed independent Identity service via private Docker networking. Authorization uses a current, remotely verified role, not a JWT claim and not a locally cached role.

Only 200 plus a schema-valid principal establishes identity. The adapter returns a specific unauthorized error for 401 and treats denial of its internal credential, malformed responses, network failures and timeouts as unavailable. There is no fallback to legacy tables, redirects or token logging.

This PR proves the **contract** (unit tests plus Docker cross-container smoke). No live purchase or event route is switched over yet. Existing foreign keys from Orders and Events to legacy users are still in place, so a live cutover without a data migration would be unsafe. The next PR must address this explicitly, including role revocation after row-lock waits.
