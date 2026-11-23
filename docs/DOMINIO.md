# Modelo de dominio de la ticketera

Modelo del issue #4. Event implementado por #13; inventario implementado por #21; órdenes y tickets implementados por #22; devoluciones todavía propuestas. [ADR de consistencia](ADR-0002.md).

## Entidades y relaciones

| Entidad | Datos y relaciones principales |
|---|---|
| User (Identity) | id, username único, password_hash, role; un usuario tiene muchas sesiones y órdenes |
| Event (Events) | id, owner_id → User, nombre, descripción, lugar, inicio/fin UTC, estado draft/published; un propietario tiene muchos eventos |
| Zone (Ticketing) | id, event_id → Event, nombre, modo numbered/general, precio en centavos, moneda; un evento tiene muchas zonas |
| Seat (Ticketing) | id, zone_id → Zone, etiqueta única dentro de zona; existe solo en zona numbered; estado available/sold |
| Capacity (Ticketing) | una fila por zona general, capacity y available; no existe para numbered |
| Order | id, customer_id → User, created_at UTC, total, currency, estado confirmed/refunded/partially_refunded; muchos OrderItems |
| OrderItem | id, order_id, zone_id, cantidad y precio unitario histórico; suma de subtotales = total de Order |
| Ticket | id, order_item_id, seat_id nullable, estado valid/refunded; exactamente un ticket por unidad comprada |
| Refund (Etapa III) | id, ticket_id único, requested_by → User, amount histórico, requested_at UTC, status pending/approved/rejected, reviewed_by → User nullable, reviewed_at UTC nullable y rejection_reason nullable; una solicitud por ticket en la propuesta inicial |
| IdempotencyRecord | customer_id, operation, key únicos en conjunto; request_hash y order_id; comparte transacción con Order |

Los vínculos entre límites son referencias por ID; no autorizan a escribir tablas de otro módulo. Una orden pertenece a un solo evento y moneda. La cantidad debe ser positiva; dinero no usa float. El precio se copia en OrderItem para que el historial no cambie. Ticket no duplica propietario: se obtiene por su orden. No se exponen códigos de tickets a otros clientes ni al catálogo público.

## Ciclos de vida y restricciones
- Event: draft → published → draft si no tiene ventas. Publicar exige propietario autorizado (o administrador), nombre, descripción, lugar, inicio futuro y fin posterior. En #13 no exige zonas: publicación da visibilidad, sin habilitar compra. Editar requiere draft e inicio futuro; publicar/despublicar repetido conserva estado. Cuando existan ventas, integrar la restricción de despublicación y exigir inventario para comprar. No hay endpoint de borrado.
- Seat: available → sold → available al devolver. Para general se reduce/aumenta available. No se mezclan modos dentro de una zona ni se cambia el modo después de publicar.
- Order: confirmed → partially_refunded → refunded, o confirmed → refunded cuando se devuelve todo. No se crea una orden pending sin pago real; una compra rechazada no persiste orden.
- Ticket: valid → refunded, sin transición inversa. No incluye validación de acceso al recinto en esta etapa.
- Refund (Etapa III): el cliente propietario solicita → pending; solo un administrador decide pending → approved o pending → rejected. Solicitar y rechazar no cambian el ticket ni el inventario. Solo aprobar cambia el ticket a refunded y repone el lugar en un commit. Propuesta de elegibilidad: solicitar y aprobar antes del inicio; rechazar puede cerrar solicitudes pendientes después. Una decisión terminal no se revierte y repetir la misma decisión es idempotente. No hay pasarela de dinero real. La política inicial de una solicitud por ticket no contempla reapertura tras rechazo; requiere revisión del equipo antes de implementar.

## Invariantes
1. Un asiento no tiene más de una venta activa; cupos nunca negativos ni superiores a capacity.
2. Una compra multi-item es todo o nada. Cantidad de tickets = unidades de la orden.
3. Reintentar una compra no crea otra orden ni descuenta dos veces.
4. Una solicitud pendiente o rechazada no libera inventario ni invalida tickets. Solo la aprobación administrativa repone una vez; un ticket devuelto no vuelve a ser válido.
5. Cliente solo accede a sus órdenes/tickets; owner solo edita sus eventos. Rol y propiedad se verifican en backend.
6. Error de notificación no altera la venta confirmada.

## Interfaces propuestas
- Identity entrega usuario autenticado y rol; el servidor asigna owner_id/customer_id desde esa identidad.
- Events expone catálogo paginado y detalle de publicados. La edición de borradores requiere owner o administrador.
- Ticketing recibe `{event_id, items: [{zone_id, quantity, seat_ids}]}` e `Idempotency-Key`. En numbered, quantity coincide con la longitud de seat_ids; en general seat_ids vacío. Responde orden con tickets, importes calculados y moneda.
- `POST /api/v1/orders`, `GET /api/v1/orders/{id}`, `GET /api/v1/me/tickets`, `POST /api/v1/tickets/{id}/refund` solicita una devolución pendiente; `POST /api/v1/admin/refunds/{id}/approve` y `/reject` resuelven la solicitud. Las tres rutas de devolución corresponden a Etapa III. Las rutas de compra están implementadas por #22; devoluciones son futuras. Eventos y catálogo están implementados en #13. El contrato de frontend del issue #3 detallará ejemplos; detalla el alcance disponible en esta rama.

## Matriz de aceptación planificada

| Caso | Preparación/acción | Resultado a verificar |
|---|---|---|
| Último asiento | Dos conexiones PostgreSQL compran mismo seat_id, sincronizadas antes del lock | Una orden/ticket válidos, un 409; seat sold |
| Último cupo | capacity=1, dos conexiones independientes | Una venta, un 409, available=0 |
| Multi-item | Un item libre y otro agotado | 409; item libre conserva inventario, cero órdenes/tickets nuevos |
| Replay | Misma identidad, key y payload, secuencial y concurrente | Misma orden; un descuento, mismo total; header de replay |
| Colisión | Misma key con payload diferente | 409; orden e inventario originales intactos |
| Clave por usuario | Dos clientes usan mismo texto de key | Operaciones independientes, sujetas a disponibilidad |
| Error antes de commit | Inyectar fallo entre descuento y creación de tickets | Rollback total; retry con misma key puede confirmar |
| Solicitud repetida (III) | Dos solicitudes del propietario para mismo ticket | Un Refund pending; inventario y ticket intactos |
| Aprobación (III) | Administrador aprueba solicitud pendiente elegible | Refund approved y actor/fecha auditados; inventario +1; ticket refunded en un commit |
| Aprobación repetida (III) | Dos aprobaciones concurrentes del mismo Refund | Misma decisión; una sola reposición |
| Rechazo (III) | Administrador rechaza con motivo | Refund rejected y actor/fecha/motivo auditados; inventario y ticket intactos |
| Decisión sin permiso (III) | Cliente u owner intenta aprobar/rechazar | 403; ninguna mutación |
| Decisiones opuestas (III) | Aprobación y rechazo concurrentes | Una decisión terminal; la contraria recibe 409; reposición solo si ganó aprobar |
| Devolución ajena | Otro cliente intenta devolver | 403; snapshot de tablas idéntico |
| Solicitud/aprobación tardía (III) | Evento iniciado | 409; sin cambios; aún se permite rechazar una solicitud pendiente |
| Revender asiento | Solicitar, aprobar como administrador y recomprar con nueva orden | Ticket anterior inválido; exactamente uno nuevo válido |
| Publicación incompleta | Sin descripción o fecha inválida | 422; estado draft. Sin zonas sí se permite publicar metadatos (#13), sin habilitar compra |
| Edición ajena | Owner B edita evento de A | 403; contenido y estado intactos |
| Notificación caída | Falla consumidor después del commit | Orden confirmada; entrega pendiente/reintentable |

Las pruebas de compra/eventos corresponden a Etapa I; las de devolución a Etapa III. SQLite o mocks no demuestran locks ni concurrencia de PostgreSQL. La evidencia de #21/#22 registra los tests reales de inventario, compra, rollback y concurrencia PostgreSQL. Las devoluciones continúan sin implementación.

Implementación #21: Zone integra Capacity en columnas nullable exclusivas de general. Seat tiene UUID global y etiqueta única por zona; FK zona/modo impide asientos en general. Ver ADR-0004.

Implementación #22: Order integra el registro de idempotencia (UNIQUE customer/key,
request_hash), sin tabla separada; estado único confirmed. Ticket tiene UNIQUE seat_id
histórico y FK compuestas para zona/asiento/item. Total y precios históricos usan
BIGINT y sufijo `_minor`. Stock y emisión se confirman juntos; restricciones de
refund/venta activa de Etapa III requerirán ampliar este modelo mediante otro change.
