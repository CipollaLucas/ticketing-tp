# Ticketing TP — Tópicos II 2026

Trabajo práctico grupal (3 integrantes). Basado metodológicamente en [ticketin](https://github.com/jwackito/ticketin); implementación propia.

## Estado
**Etapa I — Core implementado e integrado; UAT final del frontend funcional pendiente de aceptación.**
Identidad y roles, eventos, inventario de zonas/asientos, compra simulada idempotente, tickets y catálogo React real. En **Operar ticketera** se ofrecen ingreso, creación y publicación de eventos, configuración de inventario, compra simulada y consulta de tickets.

En PostgreSQL local: **146 tests aprobados**, cero omisiones. La UAT manual del backend confirmó idempotencia y rechazo de sobreventa. Sin pagos reales.

Ver [guía de demo](docs/ETAPA-I-DEMO-GUIA.md), [entrega Etapa I](docs/ENTREGA-ETAPA-I.md) y [contratos API](docs/API-ETAPA-I.md). Etapa II (recomendación/caché) sin iniciar.

## Ejecutar en local (Docker Desktop)
```bash
cp .env.example .env
docker compose up --build -d
docker compose exec backend alembic upgrade head
```
En Windows PowerShell: `Copy-Item .env.example .env`.

- Frontend: http://localhost:5173 (usar **Operar ticketera**)
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
- Changes OpenSpec: [ticket-inventory](openspec/changes/ticket-inventory/proposal.md), [ticket-purchasing](openspec/changes/ticket-purchasing/proposal.md) y [stage-i-functional-web](openspec/changes/stage-i-functional-web/proposal.md). Archivar tras UAT final.
