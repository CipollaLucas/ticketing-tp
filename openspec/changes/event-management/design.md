# Gestión de eventos — primera implementación del Issue #13

## Decisión de alcance
La primera entrega implementa **borradores de eventos**, edición con control de propietario y catálogo público seguro. Se mantiene la regla acordada: **no publicar sin zonas vendibles configuradas**.

Como las zonas y asientos pertenecen al change futuro de inventario/Ticketing (ADR-0002), esta entrega deliberadamente **no tiene transición efectiva a `published`**. El endpoint de publicación devuelve 422 con un mensaje claro y no cambia el estado; no simula zonas ni ventas. La despublicación queda bloqueada con 409 hasta que exista control de órdenes vendidas. Por lo tanto, el catálogo público permanece vacío en este incremento sobre una base nueva.

## Modelo y permisos
- Event: UUID, owner_id desde sesión autenticada, name, description, venue, start_at, end_at, status.
- Borradores permiten datos incompletos; campos desconocidos/owner_id/status provenientes del cliente: 422.
- Timestamps de entrada requieren zona horaria explícita y se normalizan a UTC; end_at posterior a start_at cuando ambos están definidos.
- event_owner edita solo sus propios eventos; administrator puede administrar todos; customer recibe 403.
- Public GET /events y GET /events/{id} muestran exclusivamente publicados; borradores: 404.
- Owner GET /owner/events pagina los suyos; administrador puede listar todos.

## Endpoints
`POST /api/v1/events` (201), `PATCH /api/v1/events/{id}` (200), `GET /api/v1/owner/events` (200), `GET /api/v1/events` (200), `GET /api/v1/events/{id}` (200/404), `POST /api/v1/events/{id}/publish` (422 sin zonas), `POST /api/v1/events/{id}/unpublish` (409 mientras no exista chequeo de ventas).

## Trabajo siguiente
Un change separado incorporará zonas/inventario y el chequeo transaccional de publicación. Entonces podrá habilitarse el catálogo con eventos publicados, y se añadirán pruebas end-to-end de publicación exitosa y visibilidad pública. No se declaran completas esas partes de event-management.

## Validación
Ruff/mypy/Pytest, migración Alembic y CI son requisitos del PR; archivar OpenSpec solo después de completar los requisitos del change, incluida publicación real.
