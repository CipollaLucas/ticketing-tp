# Architectural baseline and execution order — 24 Nov 2026

This inventory is grounded in README, docs/ARCHITECTURE-MIGRATION.md, ADR-0005, the OpenSpec microservices migration change, PLAN-EQUIPO, current backend/app and services/identity. It does not replace the original course handout, which was not located as a discrete file in this review.

| Hito | Existing evidence | Remaining acceptance |
| --- | --- | --- |
| H1 Hexagonal core | PurchaseIntent domain, purchase UoW, inventory and query ports/adapters in Legacy backend | Confirm dependency rules in all three eventual services; reconcile old unchecked boxes in broad OpenSpec tasks |
| H2 Identity independent | services/identity FastAPI, own PostgreSQL/Alembic, internal introspection and separate CI jobs; preflight, verified backup, read-only canary | Runtime auth cutover is intentionally blocked; do not equate readiness checks with completion |
| H3 Events independent | Events routes/validation currently in backend/app/events.py; owner UUID FK removed | **Next priority:** real Events service with owned schema, ports/adapters, HTTP and CI, conservative publication policy |
| H4 Ticketing independent | Purchase inventory/orders/tickets remain atomic in Legacy; simulated purchase and tests exist | Dedicated service/DB/migrations; preserve serializable purchase rules; separate event sale-state synchronization |
| H5 Gateway + UAT | React currently speaks existing /api/v1 Legacy, functional Stage I UAT recorded | Gateway to three service processes, exact URLs/contracts, partial failure/UAT and CI evidence |

## Delivery policy

1. Follow AGENTS.md: proposal, specs, design and tasks **before** implementation, then bounded code/test PR, CI, review, merge and only then archive.
2. Keep one H3 change under OpenSpec, break implementation into reviewable commits/PRs tied to the same H3 task list, not unrelated Identity micro-PRs.
3. No automatic assignments among the three contributors; review jointly before taking ownership.
4. PR #48 remains an independent pending draft. Do not merge it as a prerequisite for H3 or mistake its tests for a deployed third microservice.
5. Do not delete Legacy tables or change /api/v1 routing until independently deployable Events/Ticketing and gateway have passed contract and data reconciliation tests.
6. Preserve the Stage I functional demo as regression baseline; Etapa II/III remain outside the H3 scope.

## First H3 vertical slice

An Events API that can start independently with its own database, report health, apply initial migration and run a pure domain use case through a port-backed persistence adapter. It must be reachable on opt-in preview only; Legacy API and React remain unchanged until H5. Follow with protected actions and state coordination as separate proven steps.
