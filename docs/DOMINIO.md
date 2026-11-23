# Modelo de dominio de la ticketera

Propuesta del issue #4. Sin implementación ni migraciones de este dominio en este PR. [ADR de consistencia](ADR-0002.md).

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
| Refund | id, ticket_id único, requested_by → User, monto histórico, created_at UTC; como máximo uno por ticket |
| IdempotencyRecord | customer_id, operation, key únicos en conjunto; request_hash y order_id; comparte transacción con Order |

Los vínculos entre límites son referencias por ID; no autorizan a escribir tablas de otro módulo. Una orden pertenece a un solo evento y moneda. La cantidad debe ser positiva; dinero no usa float. El precio se copia en OrderItem para que el historial no cambie. Ticket no duplica propietario: se obtiene por su orden. No se exponen códigos de tickets a otros clientes ni al catálogo público.

## Ciclos de vida y restricciones
- Event: draft → published → draft si no tiene ventas. Publicar exige propietario autorizado, nombre, lugar, inicio futuro, fin posterior y al menos una zona configurada. No hay borrado de eventos con ventas.
- Seat: available → sold → available al devolver. Para general se reduce/aumenta available. No se mezclan modos dentro de una zona ni se cambia el modo después de publicar.
- Order: confirmed → partially_refunded → refunded, o confirmed → refunded cuando se devuelve todo. No se crea una orden pending sin pago real; una compra rechazada no persiste orden.
- Ticket: valid → refunded, sin transición inversa. No incluye validación de acceso al recinto en esta etapa.
- Refund: operación finalizada atómica, sin pending ni pasarela. Solo antes del inicio del evento. Administrador puede gestionar devoluciones, pero respeta fecha e inventario.

## Invariantes
1. Un asiento no tiene más de una venta activa; cupos nunca negativos ni superiores a capacity.
2. Una compra multi-item es todo o nada. Cantidad de tickets = unidades de la orden.
3. Reintentar una compra no crea otra orden ni descuenta dos veces.
4. Devolver no duplica reembolso ni reposición. Un ticket devuelto no vuelve a ser válido.
5. Cliente solo accede a sus órdenes/tickets; owner solo edita sus eventos. Rol y propiedad se verifican en backend.
6. Error de notificación no altera la venta confirmada.

## Interfaces propuestas
- Identity entrega usuario autenticado y rol; el servidor asigna owner_id/customer_id desde esa identidad.
- Events expone catálogo paginado y detalle de publicados. La edición de borradores requiere owner o administrador.
- Ticketing recibe `{event_id, items: [{zone_id, quantity, seat_ids}]}` e `Idempotency-Key`. En numbered, quantity coincide con la longitud de seat_ids; en general seat_ids vacío. Responde orden con tickets, importes calculados y moneda.
- `POST /api/v1/orders`, `GET /api/v1/orders/{id}`, `GET /api/v1/me/tickets`, `POST /api/v1/tickets/{id}/refund`. Todas son rutas futuras. El contrato de frontend del issue #3 detallará ejemplos; no existen en el bootstrap.

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
| Devolución repetida | Dos solicitudes concurrentes para mismo ticket | Un Refund; inventario +1; ticket refunded |
| Devolución ajena | Otro cliente intenta devolver | 403; snapshot de tablas idéntico |
| Devolución tardía | Evento iniciado | 409; sin cambios |
| Revender asiento | Devolver, recomprar con nueva orden | Ticket anterior inválido; exactamente uno nuevo válido |
| Publicación incompleta | Sin zona o fecha inválida | 422; estado draft |
| Edición ajena | Owner B edita evento de A | 403; contenido y estado intactos |
| Notificación caída | Falla consumidor después del commit | Orden confirmada; entrega pendiente/reintentable |

Estas pruebas se implementarán con compra/eventos. SQLite o mocks no demuestran locks ni concurrencia de PostgreSQL. La aceptación documental actual consiste en trazabilidad de cada regla y escenarios OpenSpec válidos; no se reportan ventas ni pruebas de concurrencia ejecutadas.
