## Why
La Etapa I requiere autenticación y permisos para administradores, event owners y clientes. Actualmente no existe identidad ni autorización.

## What Changes
- Registro e inicio de sesión de usuarios.
- Autorización por rol, con denegación por defecto.
- Un propietario de eventos solo administra recursos propios; los clientes pueden consultar su perfil.
- Contratos HTTP y casos de error uniformes.

## Impact
Backend API, modelo de usuarios y migraciones, pruebas y documentación. Los flujos de venta quedan fuera de este change.
