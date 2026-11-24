## ADDED Requirements
### Requirement: Compra idempotente autenticada
El sistema SHALL aceptar compras solo de clientes autenticados con Idempotency-Key,
calcular precios desde inventario y preservar respuesta para reintentos equivalentes.
#### Scenario: Replay
- **WHEN** el mismo cliente repite key y payload canónico
- **THEN** obtiene la misma orden sin volver a descontar ni emitir
#### Scenario: Colisión
- **WHEN** el mismo cliente usa la key con otro payload
- **THEN** obtiene 409 sin mutaciones
### Requirement: Emisión atómica sin overselling
El sistema SHALL confirmar inventario, orden y todos sus tickets en una transacción
PostgreSQL, únicamente para evento publicado futuro y zonas con misma moneda.
#### Scenario: Última localidad concurrente
- **WHEN** dos clientes compran simultáneamente el último asiento o cupo
- **THEN** exactamente una orden confirma y la otra recibe 409
#### Scenario: Fallo de emisión
- **WHEN** falla una escritura tras descontar stock
- **THEN** no persiste orden, ticket, clave ni descuento y el retry puede comprar
### Requirement: Propiedad y estado de evento
El sistema SHALL restringir órdenes/tickets a su propietario o administrador y
conservar publicado un evento con ventas.
#### Scenario: Orden ajena
- **WHEN** otro cliente consulta una orden existente
- **THEN** recibe 403 y no ve tickets
#### Scenario: Despublicación tras venta
- **WHEN** el owner intenta despublicar un evento con orden confirmada
- **THEN** recibe 409 y el evento sigue publicado
