# Ticketing TP — Tópicos II 2026

Trabajo práctico grupal (3 integrantes). Basado metodológicamente en [ticketin](https://github.com/jwackito/ticketin); implementación propia.

## Estado
**Etapa I en curso.** Identidad y eventos integrados. Los changes #21/#22 agregan inventario, compra simulada idempotente, órdenes y tickets con tests de concurrencia PostgreSQL. Ver [contratos](docs/API-ETAPA-I.md), [evidencia de inventario](docs/evidencias/2026-11-23-issue-21-inventario.md) y [evidencia de compra](docs/evidencias/2026-11-23-issue-22-compra.md). Pendientes de revisión/merge: PRs #23 y dependiente de compra. No se declara cerrada toda la fase: arquitectura física de microservicios, consolidación de changes por etapa e integración de UI deben evaluarse con el equipo.

## Ejecutar en local (Docker Desktop)
```bash
cp .env.example .env
docker compose up --build -d
docker compose exec backend alembic upgrade head
```
En Windows PowerShell: `Copy-Item .env.example .env`.

- Frontend: http://localhost:5173
- API: http://localhost:8000/api/v1
- Swagger: http://localhost:8000/docs
- Health DB: http://localhost:8000/health
- PostgreSQL local: 127.0.0.1:5433

## Verificar
```bash
docker compose exec backend ruff check .
docker compose exec backend mypy app
docker compose exec -e TEST_POSTGRES_URL=postgresql+psycopg://ticketing:local-dev-only@db:5432/ticketing backend pytest -q
docker compose exec frontend npm run lint
docker compose exec frontend npx tsc --noEmit
docker compose exec frontend npm test
```

El comando de PostgreSQL usa las credenciales locales por defecto de Compose; ajustarlas si se cambiaron. Cada test crea y elimina solo su propio schema temporal.

## Cambios y etapas
- Etapa I: núcleo, identidad, eventos, catálogo, inventario, compra, mockups.
- Etapa II: recomendación + cache.
- Etapa III: colas, devoluciones, búsqueda avanzada y stress tests.

Ver `docs/PLAN-EQUIPO.md`, `docs/ADR-0001.md`, `docs/BITACORA.md` y `CONTRIBUTE.md`.

## Advertencias
- Backend en un proceso: la separación real en microservicios y la estrategia de consistencia se definirán en changes posteriores.
- Auditoría HTTP a logs sin credenciales; autenticación Bearer y roles disponibles en esta rama.
- Alembic head 0004_purchasing crea identidad, eventos, inventario, órdenes y tickets. Publicar sin zonas da visibilidad; comprar requiere inventario y evento futuro.
- Changes OpenSpec: [ticket-inventory](openspec/changes/ticket-inventory/proposal.md) y [ticket-purchasing](openspec/changes/ticket-purchasing/proposal.md). No archivar antes de aprobación/CI/merge.
