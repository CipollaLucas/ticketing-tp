# H5 — Gateway Stage I and microservices cutover readiness

## Why

Identity, Events and Ticketing already run as independently persisted services in isolated UAT. The only Gateway implementation currently in main is Identity-only preview: commercial routes deliberately return 503 and React still targets Legacy. Thus the three-service UAT does not yet prove browser-facing Stage I parity without Legacy. This change closes that gap without undoing proven H3/H4 safety properties.

## What changes

- Build an explicitly opt-in full Stage I Gateway mapping public /api/v1 routes to their owning service; never fall back to Legacy for a request authorized by Identity.
- Verify frontend contract parity, authentication, logging, correlation and user journeys with Legacy unavailable using isolated Compose infrastructure.
- Document rollout, restore, rollback and acceptance gates, including explicit human authorization before enabling a commercial cutover.
- Reconcile coverage with H1-H4 evidence and open PRs without treating green CI as automatic approval to deploy.

## Out of scope

Real payment processing, activation of production purchase/publication flags, migration of production users/sessions/orders, asynchronous broker/outbox, rewriting React, destructive volume operations, or archiving the umbrella migration change.

## Dependencies

PR #82 (lost ACK after commit) is open at proposal time; its real CI/merge state must be verified before relying on it. Other critical failure scenarios (process/TCP restart, restore) require separate evidence if not already covered.

## Safety

Start from main, use an isolated Compose project and disposable DBs. Preserve the existing Identity-only preview and legacy app. Default all new gateway/cutover settings to off. No production data or live routing changes in this documentation PR.
