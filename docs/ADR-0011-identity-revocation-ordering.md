# ADR-0011 — Ordering role revocation against Ticketing purchases

Status: Proposed, decision pending. Stage I; no cutover authorized.

## Problem
Legacy Ticketing holds a PostgreSQL lock on its local User row while authorizing and committing purchases. Identity owns roles and sessions in a separate PostgreSQL database. Remote HTTP introspection is a separate transaction: even two successful checks cannot establish permission validity at Ticketing commit time.

## Safety contract
Immediate revocation linearizable with purchase commit is NOT provided by remote introspection alone.

1. Revocation completed before purchase starts: deny.
2. Revocation between initial authorization and a post-lock recheck: deny with no inventory/order writes.
3. Identity unavailable at a required verification: fail closed, rollback.
4. Revocation after final remote check and before local commit: unresolved race requiring coordination or explicitly accepted bounded staleness.
5. Idempotent replay must not bypass authorization or duplicate tickets.
6. Failed writes must restore inventory and keep idempotency behavior consistent.

## Options
**A. Identity-owned grants/leases and revocation coordination.** Must define crash recovery, grant expiry, loss of acknowledgement, fencing and an explicit serialization point. TTL by itself does not guarantee immediate revocation.

**B. Bounded-staleness policy.** Accept a documented in-flight authorization window, with measurable bound, logging, timeouts and explicit team approval. Does not provide immediate revocation.

**C. Single transactional authority for business writes.** Keep purchase authorization and purchase locks under one authority pending cross-service coordination; physical separation proceeds elsewhere.

## Decision gate
Do not turn on Identity authorization for write endpoints until A/B/C is selected and demonstrated against real PostgreSQL concurrent role changes, session revocation, idempotent replay, rollback and failure recovery. Keep Legacy write auth unchanged.

The accompanying race contract tests demonstrate the post-check vulnerability. They do not fix it or certify cutover readiness.