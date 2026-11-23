# Ticketing TP — Tópicos II 2026

Trabajo práctico grupal (3 integrantes). Basado metodológicamente en [ticketin](https://github.com/jwackito/ticketin); implementación propia.

## Estado
**Bootstrap validado localmente y en CI (PR #1).** Backend: 2 tests, Ruff/mypy OK; frontend y Docker: CI verde. No hay venta real implementada. Esta rama agrega autenticación y roles; ver [guía](docs/AUTENTICACION.md).

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
docker compose exec backend pytest -q
docker compose exec frontend npm run lint
docker compose exec frontend npx tsc --noEmit
docker compose exec frontend npm test
```

## Cambios y etapas
- Etapa I: núcleo, identidad, eventos, catálogo, inventario, compra, mockups.
- Etapa II: recomendación + cache.
- Etapa III: colas, devoluciones, búsqueda avanzada y stress tests.

Ver `docs/PLAN-EQUIPO.md`, `docs/ADR-0001.md`, `docs/BITACORA.md` y `CONTRIBUTE.md`.

## Advertencias
- Backend en un proceso: la separación real en microservicios y la estrategia de consistencia se definirán en changes posteriores.
- Auditoría HTTP a logs sin credenciales; autenticación Bearer y roles disponibles en esta rama.
- Alembic crea usuarios y sesiones. Eventos, inventario y compras requieren changes posteriores.
- Docker y CI del bootstrap fueron verificados. La validación mediante CLI OpenSpec y el archivado del change siguen pendientes.
