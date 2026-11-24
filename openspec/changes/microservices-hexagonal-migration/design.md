# Diseño de reconversión arquitectónica

Ver `docs/ADR-0005-microservices-hexagonal.md` y `docs/ARCHITECTURE-MIGRATION.md`.

## Bounded contexts

- Identity: cuentas, sesiones y roles.
- Events: metadatos del evento, permisos sobre propietario, publicación.
- Ticketing: inventario, precios, órdenes, tickets y registro de idempotencia.

Cada servicio tiene sus modelos y DB. No FK entre servicios, no importaciones ORM transversales. Comunicación pública por gateway; clientes HTTP internos con timeout y propagación de request ID.

## Hexagonal

La política de dominio se modela con objetos/errores puros. Un caso de uso conoce puertos abstractos; los adaptadores FastAPI/SQLAlchemy implementan esa frontera. Una `PurchaseIntent` de dominio se construye desde el DTO Pydantic de entrada; se mantiene hash canónico idéntico al legado para preservar replays. Los puertos nuevos deben conectarse a adaptadores reales antes de considerar un módulo 'hexagonal completo'.

## Concurrencia

Ticketing conserva inventario y compra en la misma transacción local PostgreSQL. La validación síncrona de Events por sí sola es insuficiente ante la carrera con despublicación. Bloquear temporalmente cambios comerciales remotos o implementar coordinación serializada con Ticketing antes de habilitar operaciones peligrosas; probar fallos y carreras.

## Migración

PR Foundation: políticas puras/puertos y tests. PRs siguientes: Identity, Events, Ticketing, gateway y pruebas integradas. El frontend seguirá invocando los endpoints actuales.
