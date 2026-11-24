## Why
Issue #22 requiere cerrar el componente de compra segura de Etapa I sobre inventario #21.
## What Changes
Compra simulada autenticada/idempotente, órdenes y tickets atómicos, sin doble venta;
consultas protegidas, disponibilidad real y prohibición de despublicar con ventas.
## Capabilities
### New Capabilities
- `ticket-purchasing`: compra idempotente y emisión atómica.
## Impact
Backend modular, Alembic 0004, constraints y locks PostgreSQL, API/evidencia/CI.
Depende de ticket-inventory / PR #23; sin pagos reales, devoluciones ni colas.
