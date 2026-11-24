## Context
Issue #21, rama feat/ticket-inventory desde main a6a55ce. Ejecutar por autorización
del usuario para atender #21/#22; decisiones del implementador sujetas a revisión de Lucas.
## Goals / Non-Goals
Inventario persistido y autorización real; no emitir tickets ni reservar stock aquí.
## Decisions
- Mantener backend modular y dependencias existentes. No crear servicio distribuido.
- Alternativas: reemplazar inventario completo facilita UI pero pone en riesgo IDs;
  crear zonas inmutables conserva referencias y simplifica compras. Elegir creación
  atómica de zona/asientos, sin edición/borrado por ahora.
- Zone: UUID, event_id FK, name único por evento, mode general/numbered,
  price_minor entero 0..2147483647, currency ISO 4217 soportada (ARS, USD, EUR),
  capacity y available positivos/no negativos solo en general. CHECK 0<=available<=capacity.
  Numbered tiene capacity/available NULL; Seat: UUID, zone_id FK, label único por zona.
  Identificador UUID global único implica único por zona. FK compuesta zona/modo
  impide asientos en general. Cupo entero estricto 1..1000000.
- POST /api/v1/events/{id}/zones: owner/admin, solo draft futuro. General recibe
  capacity y seats vacío; numbered recibe seats [{label}], capacity omitido.
  1..1000 asientos por zona; nombres/etiquetas sin NUL, recortados, no vacíos.
  Duplicados 422 en payload y 409 contra DB. Moneda normalizada no: exigir mayúsculas.
- GET /api/v1/events/{id}/inventory: público solo published; GET
  /api/v1/owner/events/{id}/inventory: owner propio/admin incluso draft.
  Respuesta {event_id,zones:[{id,name,mode,price_minor,currency,capacity,available,seats}]}.
  available numerada cuenta asientos; aquí ninguno vendido. GET sin locks de escritura.
- Bloquear Event con FOR UPDATE antes de configurar y revalidar rol/propiedad;
  mismo lock de publicación. DB constraints como última defensa. No afirmar que
  SQLite demuestra concurrencia de PostgreSQL.
- Publicar sin zonas sigue permitido; ADR-0004 separa visibilidad y compra.
## Risks / Trade-offs
Sin edición implica agregar correctamente en draft. Listado acotado por zona, sin
paginación de asientos en este incremento. Compra futura reutilizará lock del evento
antes de inventario, decremento condicional y unicidad de asiento vendido.
## Validation
Tests HTTP SQLite de ambos modos, permisos, duplicados y límites; migración reversible
con comparación metadata en PostgreSQL y SQLite; requests concurrentes PostgreSQL
creando misma zona: exactamente un 201 y un 409. Ruff, mypy, pytest y OpenSpec CLI.
