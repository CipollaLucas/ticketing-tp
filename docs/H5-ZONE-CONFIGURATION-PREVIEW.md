# H5 — Configuración de zonas en Ticketing (preview)

Change: `openspec/changes/h5-gateway-stage-i-cutover`. Contrato de React: `POST /api/v1/events/{event_id}/zones`.

## Contrato y controles

- Opción `ZONE_CONFIGURATION_ENABLED=false` por defecto. El overlay H4 descartable la habilita solo para UAT.
- Ticketing consulta a Events `/api/v1/owner/events/{event_id}/sale-gate-readiness` con el bearer de usuario, y exige UUID exacto, draft y `ready_for_gate_provisioning=true`. La validación de owner/admin e Identity permanece en Events.
- Timeout/error remoto: rechazar; sin autorización no hay escritura local. No se acepta un `owner_id` externo.
- SQL local a Ticketing; creación de zona y asientos en una sola transacción. Constraints protegen zonas duplicadas y labels repetidos; gate local abierto bloquea la modificación.
- El Gateway dirige la ruta `/api/v1/events/{id}/zones` a Ticketing antes del prefijo Events. Nunca redirige a Legacy.
- Se conserva el contrato Legacy: zonas general/numbered, precio en unidades menores, capacidad, asientos y respuesta de disponibilidad.

## Limitación que bloquea el cutover

La verificación HTTP de estado draft sucede antes de la transacción local, sin serialización distribuida con la publicación de Events. Por tanto existe una carrera (TOCTOU) si el propietario publica mientras la creación de zona está en tránsito. El lock local de `sale_gates` serializa únicamente transacciones de Ticketing; **no garantiza** una validación atómica del estado draft de Events.

No activar comercialmente hasta establecer y probar un protocolo de congelación de configuración por revisión de evento o publicación versionada, con UAT concurrente `publish vs zone creation`. Tampoco se declara implementada la paridad de compras `POST /api/v1/orders`.

## Validación antes del merge

- `cd services/ticketing && python -m ruff check . && python -m mypy ticketing_service && python -m pytest -q`
- `python scripts/h5_gateway_contract_check.py`
- CI de OpenSpec y tres servicios, NGINX y UAT PostgreSQL real
- Revisión del riesgo TOCTOU y del plan de coordinación antes de cutover

No se ejecutó Docker local durante la generación de este PR; no archivar el change.


## H5 follow-up: shared gate-row serialization

The proposed H5 fix ensures that the Ticketing transaction first inserts the event's closed gate with `INSERT ... ON CONFLICT DO NOTHING`, then locks that row `FOR UPDATE` before inserting the zone and seats. The event UUID has already been checked with the protected Events draft/owner endpoint; an existing open gate is never reset, and an open gate rejects inventory writes with 409.

Publication's Ticketing gate-open CAS acquires the same row lock. As a result, if zone creation wins the local lock, it commits before the gate opens. If publication wins, the zone operation observes an open gate and cannot add inventory. PostgreSQL uniqueness on event ID serializes concurrent creation of the row.

This is **not** a distributed transaction or a global lock on Events' metadata. The relative moment of a public 201 and final Events status remains governed by each service's separate transactions. The safety assertion is limited to inventory changes being serialized before the Ticketing gate opens, with draft ownership validated at the start of each request.

New tests cover local closed/open gate preservation, PostgreSQL gate-opening-versus-zone-creation, and a real Gateway request to add inventory after publication. Do not declare this evidence accepted until CI and the PostgreSQL test run green.
