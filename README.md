# Ticketing TP — Tópicos II 2026

Trabajo práctico grupal (3 integrantes). Basado metodológicamente en [ticketin](https://github.com/jwackito/ticketin); implementación propia.

## Estado
**Bootstrap inicial preparado, pendiente de primera ejecución y validación del equipo.** No hay venta real implementada.

## Ejecutar en local (Docker Desktop)
```bash
cp .env.example .env
docker compose up --build
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
- Auditoría HTTP inicial a logs; autenticación aún no existe.
- Alembic figura como dependencia, pero las migraciones y modelos del dominio se implementarán en un change posterior.
- La primera ejecución, las pruebas CI y la validación OpenSpec deben ser verificadas en el entorno del equipo.
