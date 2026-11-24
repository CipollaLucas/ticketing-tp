## Context
Issue #22; rama feat/ticket-purchasing basada en feat/ticket-inventory (PR #23).
Autorización de ejecución: solicitud de atender ambos issues y abrir PR para Lucas.
## Goals / Non-Goals
Garantizar compra simulada todo o nada, idempotencia y propiedad. No pago real,
refunds, colas ni UI nueva. Reutilizar servicios y librerías actuales.
## Decisions
Alternativas: locks por zona escalan mejor pero complican publicación y compras
multi-zona; lock por evento es más simple, serializa ventas del mismo evento y
comparte orden con publicación/configuración. Elegir lock Event, luego zonas en
orden UUID, con decremento condicional y UNIQUE de seat_id como defensas extra.
No usar locks en memoria: múltiples procesos comparten PostgreSQL.

POST /api/v1/orders: solo customer; Idempotency-Key ASCII visible 1..128 obligatorio.
Payload estricto {event_id,items:[{zone_id,quantity,seat_ids:[]}]}: 1..20 zonas únicas,
quantity entero estricto 1..100, hasta 100 unidades totales; UUID de asiento sin
repetir. General no recibe asientos; numbered quantity == len(seat_ids).
Precio/moneda/owner/status enviados por cliente se rechazan 422. Una orden solo
contiene un evento y moneda; moneda se deriva de zonas, total int64.

Lock User del cliente antes de consultar idempotencia y revalidar role; serializa
reintentos del mismo cliente incluso con distintos eventos. Luego lock Event;
releer estado y futuro. User -> Event -> Zone es orden estable de compra.
Order contiene UNIQUE(customer_id,idempotency_key), request_hash SHA256 de JSON
canónico (items/seat_ids ordenados), estado confirmed y total/currency históricos.
La orden sirve de registro idempotente, sin tabla redundante. Replay previo a
validar evento/stock permite recuperar respuesta aun si empieza el evento.
Mismo cliente/key/payload: 200, misma orden y Idempotent-Replayed:true; distinto
payload:409. Primer éxito 201 y header false. Clave por cliente, sin expiración
ni consumo por fallos. GET no expone clave/hash.

OrderItem: UUID, order FK, zone FK, quantity, unit_price_minor y subtotal históricos;
UNIQUE(order_id,zone_id), CHECK cantidad/importes. Ticket: UUID, item FK, zone FK,
seat_id nullable; UNIQUE(seat_id) y FK compuestas garantizan asiento de zona del
item. Un ticket por unidad, estado valid; sin duplicar customer. ID UUID es código
opaco; acceso solo por orden propia o admin. No hay scan/validación de entrada.
Todas las escrituras, stock, orden, items, tickets e idempotencia se confirman en
un commit; excepción revierte todo. Tests inyectarán fallo SQL tras reducir cupo.
No se responde 201 antes del commit. UNIQUE histórico de asiento debe revisarse
para devoluciones de Etapa III.

GET /orders/{id}: propietario/admin; otro usuario 403, desconocido 404.
GET /me/tickets?limit=20&offset=0: usuario autenticado, únicamente sus tickets,
paginación 1..100, total real; admin no obtiene tickets ajenos por esta ruta.
Disponibilidad numbered usa anti-join de tickets, general usa available.
Events.transition impide unpublish con Order confirmado, bajo mismo lock Event;
esto justifica modificar events.py dentro del alcance de este change.

## Risks / Trade-offs
Serializar evento y cliente limita throughput, aceptado para Core. No afirmar escala
masiva. SQLite prueba contratos/rollback; concurrencia requiere PostgreSQL real.
No hay modificación/borrado de zonas/precios tras ventas, ni órdenes pendientes.
## Validation
Tests HTTP SQLite: permisos, replay/collision/normalización, validación, precio
servidor, ambas modalidades, venta mixta, último stock, rollback y lectura privada.
PostgreSQL migrado: dos clientes último asiento/cupo, replay/collision concurrentes,
stress inicial 20 requests/5 cupos, fallo antes de emisión y estado íntegro.
Migración reversible conservando inventario; Ruff/mypy/pytest/OpenSpec y CI.
CI debe correr también PRs con base feat/ticket-inventory mientras esté apilado.
