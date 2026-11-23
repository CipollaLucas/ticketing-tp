## Why
El issue #4 requiere acordar el modelo y la consistencia antes de implementar compras. El change event-management solo cubre eventos y no resuelve inventario, órdenes ni devoluciones.

## What Changes
- Modelo de dominio con inventario numerado y general, estados y cardinalidades.
- ADR de límites lógicos, transacciones, idempotencia y futura comunicación entre servicios.
- Escenarios de aceptación de concurrencia, reintentos y devoluciones.

## Impact
Solo documentación. No crea tablas, endpoints, brokers ni microservicios. Complementa event-management sin ampliar su implementación. Issue: https://github.com/CipollaLucas/ticketing-tp/issues/4.
