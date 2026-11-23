# Autenticación y roles — Etapa I

Issue #6. [Diseño y decisiones](ADR-0003.md). Esta rama implementa identidad; catálogo, eventos y compras siguen pendientes.

## Ejecutar

Desde la raíz:
```bash
cp .env.example .env
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.create_admin --username admin --display-name Administrador
```
La contraseña administrativa se solicita dos veces de forma oculta, no se pasa en la línea de comando. No hay usuario/password predefinidos. El alta repetida de un username falla; no eleva una cuenta cliente existente. Para otorgar roles, iniciar sesión como administrador y utilizar la ruta protegida de roles.

Para desarrollo sin Docker: Python >=3.12, `pip install -e './backend[dev]'`; definir DATABASE_URL con PostgreSQL accesible, ejecutar `alembic upgrade head` desde backend y `python -m app.create_admin --username admin`. No se crean tablas automáticamente. Nunca usar downgrade sobre datos que deban conservarse: downgrade base elimina usuarios y sesiones.

## Contratos implementados

Base `/api/v1`. JSON. Roles `customer`, `event_owner`, `administrator`.

| Ruta | Payload | Respuesta / permiso |
|---|---|---|
| POST /auth/register | username, password, display_name | 201 User; público, siempre customer |
| POST /auth/login | username, password | 200 access_token, token_type=bearer, expires_in |
| GET /auth/me | Sin body | 200 User; Bearer válido |
| POST /auth/logout | Sin body | 204; revoca solo sesión actual |
| PATCH /users/{UUID} | display_name | 200 User; propio perfil o admin |
| PATCH /admin/users/{UUID}/role | role | 200 User; solo admin, nunca rol propio |

Username: 3–50 caracteres `[a-z0-9_-]`, trim/minúsculas antes de validar. display_name: trim, 1–100 caracteres. Password: 12–128 caracteres en registro, no se recorta ni normaliza. Campos adicionales: 422. UUID inválido: 422. Sesiones de una hora por defecto; SESSION_TTL_SECONDS entre 60 y 86400. Cambiar TTL no modifica sesiones ya emitidas.

Registro de ejemplo, exclusivamente con datos de prueba:
```bash
curl -i http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"ana_demo","display_name":"Ana","password":"frase-local-de-ejemplo-2026"}'
```
User de respuesta:
```json
{"id":"00000000-0000-0000-0000-000000000001","username":"ana_demo","display_name":"Ana","role":"customer"}
```
Login usa el mismo username y password, sin display_name. Respuesta:
```json
{"access_token":"TOKEN_OPACO_DE_EJEMPLO","token_type":"bearer","expires_in":3600}
```
Para Swagger en `/docs`: registrar/login, copiar access_token en **Authorize** como valor Bearer y probar `/auth/me`. El token se devuelve únicamente al crearlo; el login lleva `Cache-Control: no-store`. No copiar tokens reales a documentación, logs ni chats. Cerrar sesión mediante `/auth/logout`; el token revocado deja de funcionar. Otros dispositivos/sesiones siguen activos.

## Errores
- 401 con `WWW-Authenticate: Bearer`: credenciales incorrectas, ausentes, inválidas, revocadas o vencidas. Login devuelve `{"detail":"Invalid username or password"}` tanto para usuario desconocido como para password incorrecto.
- 403: rol o propiedad insuficiente, sin mutación. Para perfiles el guard compara el ID del path con identidad; no consulta datos del perfil ajeno antes de denegar.
- 404: un administrador consulta/modifica un usuario inexistente.
- 409: username duplicado normalizado o intento de cambiar el propio rol.
- 422: datos inválidos/campos extra, `{"detail":[{"loc":["body","password"],"msg":"...","type":"..."}]}`; no contiene input ni secretos.

Errores de base/infraestructura no se presentan como login exitoso. Migrar antes de usar rutas de identidad.

## Reutilizar autorización en eventos futuros
`get_current_user` valida identidad; `require_event_owner` exige owner/admin; `require_owner_or_admin(user, event.owner_id)` verifica propiedad antes de editar. Ambos controles son necesarios en escritura de eventos. Nunca confiar en el rol ni owner_id del body. Las pruebas usan una ruta de evento exclusiva del fixture para comprobar customer rechazado, owner ajeno sin mutación y owner propio/admin permitidos; esta rama no añade endpoints de eventos ficticios a producción.

## Verificación
Desde backend: `ruff check .`, `mypy app`, `pytest -q`. Tests HTTP con sesiones SQLite aisladas y foreign keys activas; migración upgrade/downgrade/reupgrade y comparación con metadata. Para incluir migración y concurrencia PostgreSQL, definir `TEST_POSTGRES_URL` apuntando a una base de pruebas donde se puedan crear/eliminar schemas temporales; sin esa variable se omiten explícitamente tres tests. CI define esa base con un servicio PostgreSQL 16. La evidencia de PostgreSQL/Docker, frontend y limitaciones se registra en docs/evidencias. No confundir tests locales con CI del futuro PR.
