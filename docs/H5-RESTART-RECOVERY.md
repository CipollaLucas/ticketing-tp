# H5 — Restart recovery and persisted purchase evidence

OpenSpec: `h5-gateway-stage-i-cutover` (implementation evidence only).

## What the H5 CI increment demonstrates

The disposable H5 HTTP smoke captures IDs of an already committed event, order, ticket, zone and its idempotency key. After the real React Chromium UAT, CI restarts **only** Identity, Events and Ticketing application containers. Their PostgreSQL containers and tmpfs volumes remain running and untouched. The Gateway stays the sole public HTTP entrypoint.

The post-restart verifier (host-side Python standard library) requires the explicit `H5_DISPOSABLE_RESTART_UAT=yes` opt-in, connects only to `127.0.0.1:8091`, and refuses an absent or malformed disposable smoke evidence record. It proves:
- A fresh customer authentication works after restarting Identity.
- The published event's available inventory remains unchanged after restarting Events/Ticketing.
- The previously issued ticket still belongs to the authenticated customer.
- Repeating `POST /api/v1/orders` with the original idempotency key returns status 200, header `Idempotent-Replayed: true`, the original order/ticket IDs, and does not decrement available capacity again.

This evidence requires the existing HTTP smoke and React browser UAT to succeed first, and is exercised only inside the disposable CI project. No production settings, persistent volumes, customer accounts or real payment provider are involved.

## Safety and limitations

- **Not a database restore test.** Restarting application processes while their databases remain alive validates durability across process restarts, not backup correctness or restoration from PostgreSQL dumps.
- No restart while an in-flight operation is held or network ACK is deliberately dropped; those require separate fault-injection evidence.
- Does not cover disaster recovery, data backfill, reconciliation against Legacy, production cutover or rollback.
- The idempotency key printed in smoke output belongs exclusively to a disposable fixture; never print live production keys.
- If tests fail, retain failure logs/screenshots from CI for review and do not authorize a cutover.

## Remaining H5 gates

1. Restore all independent database dumps into new disposable databases and validate cross-service invariants.
2. Reconcile change tasks against existing merged PRs and CI evidence, without marking unproven gates complete.
3. Establish a safe operator runbook for preflight, backup, backfill, activation, abort and post-write rollback strategy.
4. Obtain separate explicit human approval before any production traffic switch.
