## Context
El bootstrap usa FastAPI, SQLAlchemy y PostgreSQL. El equipo debe definir la identidad y permisos antes de abrir escrituras en eventos y órdenes.

## Enfoques considerados
1. JWT: evita consultar sesiones, pero agrega claves, validación de claims y revocación.
2. Cookie de sesión: adecuada para navegador, pero requiere definir CSRF y política de cookies.
3. **Sesión opaca enviada como Bearer (propuesta elegida para implementar):** una consulta a PostgreSQL, revocación directa y ninguna infraestructura adicional.

## Diseño propuesto para revisión
- `User`: UUID, username ASCII de 3–50 caracteres normalizado a minúsculas y único, display_name de 1–100 caracteres, password_hash y role (`customer`, `event_owner`, `administrator`). Sin email ni recuperación de contraseña en este incremento.
- Contraseñas de 12–128 caracteres con Argon2 mediante `pwdlib[argon2]`. Esta dependencia evita implementar criptografía propia. Hash y credenciales nunca se serializan ni se registran.
- `AuthSession`: SHA-256 de un token aleatorio de 32 bytes, usuario y vencimiento UTC. El token original solo aparece en la respuesta de login. Duración por defecto 3600 segundos, configurable entre 60 y 86400. Borrado de sesión al salir; la consulta rechaza expiradas. Limpieza programada de expiradas fuera de alcance.
- `POST /api/v1/auth/register` (201), `POST /api/v1/auth/login` (200), `POST /api/v1/auth/logout` (204), `GET /api/v1/auth/me` (200).
- Registro solo acepta username, password y display_name; campos extra, incluso role, producen 422. Duplicados normalizados: 409. Login inválido: 401 genérico; verificar también contra un hash ficticio cuando no existe el usuario.
- `PATCH /api/v1/users/{id}` solo cambia display_name: el usuario puede editar su propio perfil y el administrador cualquier perfil. Un event owner no puede editar perfiles ajenos. Control reutilizable `require_owner_or_admin(user, owner_id)` para futuros eventos; probarlo con una ruta de prueba de edición de eventos sin implementar el dominio de eventos.
- `PATCH /api/v1/admin/users/{id}/role`: exclusivo de administrador. Prohibida la modificación del rol propio (409), para conservar un administrador. El rol se lee de la base en cada request: una sesión no conserva privilegios antiguos. Serializar cambios de rol bloqueando filas de administradores en orden estable y volver a verificar el rol del actor después de adquirir locks, para evitar degradación mutua concurrente.
- Bearer ausente, malformado, desconocido o vencido: 401 con `WWW-Authenticate: Bearer`. Autenticado sin permiso: 403 antes de mutar. IDs desconocidos accesibles: 404. Errores HTTP usan `{"detail": "..."}`; validación conserva el 422 nativo de FastAPI.
- SQLAlchemy con sesión por request; Alembic crea tablas, restricciones e índices. Tests SQLite aislados para comportamiento y migraciones; verificar PostgreSQL mediante Docker cuando esté disponible.
- Alta inicial de administrador por comando local con contraseña oculta, sin credenciales por defecto. Nunca permitir escalada en registro ni bootstrap administrativo por HTTP.
- Frontend futuro mantiene el token en memoria, lo borra al salir y usa HTTPS fuera de localhost. El prototipo del issue #3 no integra autenticación ni guarda tokens.

## Archivos y responsabilidades
- `app/database.py`: engine, Base y dependencia de sesión.
- `app/models.py`: User y AuthSession.
- `app/auth.py`: schemas, hashing, autenticación, guards y rutas pequeñas.
- `app/create_admin.py`: bootstrap administrativo local.
- `alembic/`: migración de identidad y sesiones.
- `tests/test_auth.py`, `tests/test_migrations.py`: contratos, permisos, persistencia y migración reversible.

## Validación y aceptación
Probar registro/normalización/duplicados, rechazo de role y contraseñas inválidas, login sin filtraciones, almacenamiento seguro, logout/vencimiento, 401/403, edición propia y administrativa, bloqueo de edición ajena sin mutación, cambios de rol y migraciones upgrade/downgrade. Ejecutar Ruff, mypy, Pytest y compatibilidad frontend. Registrar lo ejecutado y dejar revisión/CI/archivado pendientes hasta comprobarlos.

## Scope boundaries
No desarrollar pagos, paneles de producción ni microservicios de identidad independientes en este change sin ADR adicional.
