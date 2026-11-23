## Context
El bootstrap usa FastAPI, SQLAlchemy y PostgreSQL. El equipo debe definir la identidad y permisos antes de abrir escrituras en eventos y órdenes.

## Decisions to validate
- Almacenar hashes de contraseña mediante algoritmo de hashing moderno; nunca contraseñas en texto plano.
- Acceso autenticado mediante tokens o sesiones: documentar elección y protección de credenciales antes de implementar.
- Centralizar autorización en dependencias/servicios del backend, sin confiar en el rol recibido del cliente.
- El alta pública crea únicamente clientes; cambios de rol requieren autorización administrativa.
- Evitar exponer datos personales en la bitácora HTTP.

## Scope boundaries
No desarrollar pagos, paneles de producción ni microservicios de identidad independientes en este change sin ADR adicional.
