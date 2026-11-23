## Why
Issue #21 completa inventario previo a compra de Etapa I, sobre eventos del PR #18.
## What Changes
Zonas generales con cupo y numeradas con asientos; precios enteros y moneda ISO;
configuración owner/admin, lectura pública de publicados, migración y pruebas reales.
## Capabilities
### New Capabilities
- `ticket-inventory`: inventario y disponibilidad por evento.
## Impact
Backend SQLAlchemy/FastAPI, Alembic 0003, API, ADR y CI existente. Sin órdenes ni pagos.
