# Ticketing TP — Tópicos II 2026

Trabajo práctico grupal (3 integrantes). Basado metodológicamente en [ticketin](https://github.com/jwackito/ticketin); implementación propia.

## Estado
**Etapa I en curso.** Autenticación y roles integrados (PR #12). Esta rama resuelve #13: creación/edición de borradores, publicación y catálogo público paginado. Inventario, compras y tickets siguen pendientes; este PR no cierra toda la fase 1. Ver [contratos y ejemplos](docs/API-ETAPA-I.md), [autenticación](docs/AUTENTICACION.md) y [evidencia de eventos](docs/evidencias/2026-11-23-issue-13-eventos.md).

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
- Alembic crea usuarios, sesiones y eventos (0002_events). Publicar sin zonas permite mostrar metadatos; no ofrece venta ni disponibilidad.
- Change OpenSpec: [event-management](openspec/changes/event-management/proposal.md). Validaciones y estado de CI/revisión en su evidencia; no archivar hasta aceptar el PR.
