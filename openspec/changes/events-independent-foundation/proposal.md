## Why

Etapa I funciona en React/Legacy y el Identity Service es independiente, pero `backend/app/events.py` sigue en el backend combinado y los datos de eventos comparten la base con inventario/órdenes. La consigna exige tres microservicios independientes y arquitectura hexagonal. El siguiente hito del plan es **H3: Events**.

## What changes

- Extraer Events a un servicio FastAPI independiente, con su propio PostgreSQL/migraciones y healthcheck, sin compartir SQLAlchemy ni tablas con Identity/Ticketing.
- Mantener las reglas de dominio y casos de uso aislados de FastAPI/SQLAlchemy mediante puertos de repositorio, identidad y reloj.
- Definir un contrato HTTP interno con datos mínimos de publicación e identidad del propietario, no tablas cruzadas.
- Aislar el servicio primero de forma opt-in para que el frontend y compras sigan usando Legacy mientras se valida H3.
- Definir y probar la política conservadora de publicación/despublicación, sin prometer consistencia transaccional cross-service todavía.

## Out of scope

No mover inventario, órdenes o tickets a Events. No cambiar rutas públicas de React hasta H5 gateway. No activar autorización de compras por Identity remoto. No hacer migración de datos activos ni eliminar tablas Legacy en este hito. Sin Etapa II/III.
