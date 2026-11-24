# Fail-closed canary design

A feature flag `IDENTITY_CANARY_ENABLED` (false by default) gates the test-only read path. The handler accepts a user Bearer token and delegates verification to `HttpIdentityAdapter` over private HTTP with a server-only internal credential and bounded timeout.

After the remote Identity authority verifies the token, the handler uses a read-only legacy lookup to confirm that the same UUID, username and role exist in the current database. It never creates a legacy session or updates any local row. Missing/mismatched data returns 409, invalid token 401, remote error 503. Responses are no-store.

The route is **not used** by Events, Ticketing, or authorization dependencies and provides no authorization to perform writes. It is an observable pre-cutover gate for checking verified identity consistency before the full service split.

Turning on the flag does not affect the default React flow or change transaction locks. Security-sensitive role revocation while a purchase waits on locks remains a separate acceptance gate for the actual cutover.
