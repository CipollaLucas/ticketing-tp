# H3 Events read-only independent runtime — first vertical slice

This increment is the **first runnable part** of the Events independent service, not complete H3. The active Legacy backend and React continue to serve `/api/v1` on port 8000. The new Events preview is isolated on 127.0.0.1:8002, and only exposes public catalog GET plus health. No mutation endpoints, no auth cutover, no shared DB or migration of active demo records.

## Local opt-in

```powershell
git switch feat/h3-events-service-runtime
docker compose -f docker-compose.yml -f docker-compose.events.yml --profile events up -d --build events-db
docker compose -f docker-compose.yml -f docker-compose.events.yml --profile events run --rm --no-deps events alembic upgrade head
docker compose -f docker-compose.yml -f docker-compose.events.yml --profile events up -d --build events
```

Verify `http://127.0.0.1:8002/health` and `http://127.0.0.1:8002/api/v1/events`. The empty catalog is expected until records are migrated/imported in a later approved change. Legacy still runs at 8000, React at 5173.

Stopping preview: `docker compose -f docker-compose.yml -f docker-compose.events.yml --profile events stop events events-db`. Never run `--remove-orphans` or `down -v`.

## Hexagonal and data boundaries

- `events_service.domain` is pure immutable event semantics; application uses an EventReader protocol.
- `events_service.persistence` owns a standalone events table, with an external owner UUID, **no FK to users**.
- A read-only FastAPI adapter invokes the application use case.
- Missing parts: authenticated commands, Identity port, transactional coordination of publish/unpublish with Ticketing, import/reconcile from demo data, gateway, 3-service UAT.
- CI must test independent Alembic migration and container health, not just importability.
