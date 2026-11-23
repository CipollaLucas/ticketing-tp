# Contratos HTTP propuestos — Etapa I

Issue #3. Propuesta de integración para revisión cruzada; no declara endpoints futuros implementados. Base: `/api/v1`. JSON UTF-8. IDs: UUID. Fechas ISO 8601 UTC. Precios en unidades menores enteras con moneda ISO, nunca float. Campos desconocidos de escritura se rechazan (422). Roles: `customer`, `event_owner`, `administrator`.

## Disponibilidad y permisos

| Método/ruta | Acceso | Éxito | Disponibilidad |
|---|---|---|---|
| POST /auth/register | Público, siempre crea customer | 201 User | Implementación en rama feat/authentication-and-roles (#6) |
| POST /auth/login | Público | 200 Token | Rama #6 |
| POST /auth/logout | Bearer válido | 204 sin body | Rama #6 |
| GET /auth/me | Bearer válido | 200 User | Rama #6 |
| PATCH /users/{user_id} | Mismo usuario o administrador | 200 User | Rama #6 |
| PATCH /admin/users/{user_id}/role | Administrador | 200 User | Rama #6 |
| GET /events?limit=20&offset=0 | Público, solo published | 200 página | Futura, event-management |
| GET /events/{event_id} | Público, solo published | 200 Event | Futura |
| GET /owner/events?limit=20&offset=0 | Owner, solo propios; admin todos | 200 página | Futura |
| POST /events | Owner/admin, owner_id del servidor | 201 Event draft | Futura |
| PATCH /events/{event_id} | Owner propio/admin | 200 Event | Futura |
| POST /events/{event_id}/publish | Owner propio/admin | 200 Event | Futura |
| POST /events/{event_id}/unpublish | Owner propio/admin, sin ventas | 200 Event draft | Futura |
| POST /orders | Customer, Idempotency-Key obligatorio | 201 Order | Futura, compra simulada sin pago |
| GET /orders/{order_id} | Customer propietario/admin | 200 Order | Futura |
| GET /me/tickets?limit=20&offset=0 | Customer, solo propios | 200 página | Futura |
| POST /tickets/{ticket_id}/refund | Customer propietario, antes del inicio (política propuesta) | 201 Refund pending; replay 200 | Futura, Etapa III |
| POST /admin/refunds/{refund_id}/approve | Administrador, antes del inicio (política propuesta) | 200 Refund approved | Futura, Etapa III |
| POST /admin/refunds/{refund_id}/reject | Administrador, motivo obligatorio | 200 Refund rejected | Futura, Etapa III |

Los tres PRs se mantienen independientes: #3 documenta la interfaz; #6 la implementa parcialmente; #4 propone el dominio. La tabla describe el destino esperado después de revisar/mergear, no el estado de main.

## Identidad (contrato acordado con el diseño #6)

Registro:
```json
{"username":"ana_demo","password":"una-frase-segura-2026","display_name":"Ana"}
```
Username: 3–50 ASCII alfanuméricos, `_` o `-`, normalizado a minúsculas y sin espacios externos. Password: 12–128 caracteres. display_name: 1–100 después de trim. `role`, `id`, `password_hash` y campos extra: 422. Duplicado: 409. Respuesta User:
```json
{"id":"00000000-0000-0000-0000-000000000001","username":"ana_demo","display_name":"Ana","role":"customer"}
```
Login: `{"username":"ana_demo","password":"una-frase-segura-2026"}`. Respuesta (token ilustrativo, no utilizable):
```json
{"access_token":"TOKEN_OPACO_SOLO_DE_EJEMPLO","token_type":"bearer","expires_in":3600}
```
Enviar `Authorization: Bearer <access_token>` en operaciones protegidas. Guardar en memoria en el frontend futuro, borrar al salir y usar HTTPS fuera de localhost. El servidor conserva solo el hash del token, rechaza expirados y revoca en logout. Logout repetido con el token revocado devuelve 401. No hay refresh token; volver a iniciar sesión. La duración se configura entre 60 y 86400 segundos.

`PATCH /users/{user_id}`: `{"display_name":"Ana Pérez"}`. Solo ese campo; role en esta ruta: 422. `PATCH /admin/users/{user_id}/role`: `{"role":"event_owner"}`. No se permite modificar el rol propio (409). Los roles se consultan en cada request; una sesión existente no conserva privilegios revocados.

## Eventos y catálogo (futuros)

Paginación: limit 1–100, por defecto 20; offset >=0, por defecto 0; orden estable por start_at e id. Filtros avanzados fuera de alcance. Página vacía es 200, nunca 404:
```json
{"items":[],"limit":20,"offset":0,"total":0}
```
Event público propuesto:
```json
{"id":"00000000-0000-0000-0000-000000000010","name":"Noche de bandas","description":"Música local","venue":"Centro Cultural, La Plata","start_at":"2027-05-15T23:00:00Z","end_at":"2027-05-16T02:00:00Z","status":"published","zones":[{"id":"00000000-0000-0000-0000-000000000020","name":"General","mode":"general","unit_price":1200000,"currency":"ARS","available":100,"seats":[]}]}
```
Crear borrador recibe name, description, venue, start_at y end_at; no owner_id ni status. Edición recibe subconjunto de esos campos. Zonas/inventario tendrán un change propio: no se infiere que event-management deba implementarlos. Publicar/despublicar recibe `{}`; publicar requiere datos completos, fechas válidas y zonas configuradas. Borrador no es visible en catálogo ni detalle público (404). Falta de configuración: 422; cambios en eventos con ventas: 409. Sin zona numerada: seats vacío; en numbered: seats contiene `{id,label,available}`. Disponibilidad es informativa hasta confirmar transacción.

## Órdenes, tickets y devoluciones (futuros)

Header `Idempotency-Key: compra-demo-001`. Request sin precio, total ni customer_id:
```json
{"event_id":"00000000-0000-0000-0000-000000000010","items":[{"zone_id":"00000000-0000-0000-0000-000000000020","quantity":1,"seat_ids":[]}]}
```
En numerado, quantity coincide con cantidad de seat_ids distintos. En general, seat_ids vacío. Items no vacíos; cantidades enteras positivas; un solo evento/moneda. El servidor canoniza el payload y calcula precios/total. Confirmación simulada, sin pago externo:
```json
{"id":"00000000-0000-0000-0000-000000000030","event_id":"00000000-0000-0000-0000-000000000010","status":"confirmed","currency":"ARS","total":1200000,"items":[{"zone_id":"00000000-0000-0000-0000-000000000020","quantity":1,"unit_price":1200000}],"tickets":[{"id":"00000000-0000-0000-0000-000000000040","zone_id":"00000000-0000-0000-0000-000000000020","seat_id":null,"status":"valid"}]}
```
Misma identidad/key/payload: mismo Order, 201 y `Idempotency-Replayed: true`; key con payload diferente: 409; inventario agotado: 409 sin orden ni tickets; fallo transitorio: 503, reintentar con misma key. Validación o rollback no consume la key. Clave de 1–128 caracteres, ámbito cliente + operación, persistida con la orden sin TTL en esta etapa.

`GET /me/tickets`: página de tickets con event_id/name/start_at, order_id, zone_id/name, seat_id/label nullable y status. Nunca devuelve tickets ajenos. No incluye QR real en el mockup.

### Devoluciones — propuesta para Etapa III

El cliente propietario solicita con `POST /tickets/{ticket_id}/refund`, body `{}`. Respuesta inicial 201:
```json
{"id":"00000000-0000-0000-0000-000000000050","ticket_id":"00000000-0000-0000-0000-000000000040","amount":1200000,"currency":"ARS","status":"pending","reviewed_by":null,"reviewed_at":null,"rejection_reason":null}
```
El ticket sigue válido y el inventario no se libera. Repetir devuelve la misma solicitud (200), incluso si ya fue resuelta; no crea otra solicitud ni muta su decisión. La propuesta inicial admite una solicitud por ticket; reapertura tras rechazo queda por acordar.

Solo administrador decide:
- `POST /admin/refunds/{refund_id}/approve`, body `{}`: 200 con status approved, reviewed_by y reviewed_at. En la misma transacción invalida el ticket, actualiza la orden y libera el lugar exactamente una vez.
- `POST /admin/refunds/{refund_id}/reject`, body `{"reason":"No cumple la política de devolución"}`: 200 con status rejected, reviewed_by, reviewed_at y rejection_reason. El motivo no puede estar vacío. No cambia ticket, orden ni inventario.

Repetir la misma decisión devuelve el resultado previo (200) sin nuevos efectos; intentar la decisión opuesta recibe 409. En una carrera gana una sola transición terminal. Cliente u owner que intenta decidir: 403; solicitud sobre ticket ajeno: 403. Propuesta de fechas: solicitar/aprobar antes del inicio (409 después); rechazar pendientes sigue permitido. No representa devolución monetaria real. Estas rutas no se implementan ni se exigen para cerrar Etapa I.

## Errores y tratamiento en UI

Errores de dominio/HTTP: `{"detail":"mensaje"}`. Validación nativa FastAPI 422: `{"detail":[{"loc":["body","username"],"msg":"...","type":"..."}]}`. El cliente discrimina string/list sin asumir siempre texto.

| Código | Significado | UI |
|---|---|---|
| 401 | Login inválido o Bearer ausente/inválido/vencido; `WWW-Authenticate: Bearer` | Pedir acceso; descartar token inválido; no reintentar compra sin misma key |
| 403 | Rol o propiedad insuficiente | Mostrar acceso denegado; no simular éxito |
| 404 | Recurso inexistente o borrador no público | Volver al listado |
| 409 | Usuario duplicado, cupo/asiento ocupado, idempotencia incompatible o transición inválida | Mostrar conflicto; refrescar disponibilidad; preservar key de reintento |
| 422 | Payload/campos/fechas inválidos | Asociar errores a campos; conservar datos no sensibles |
| 503 / red | Operación no disponible | Mostrar error y retry; nunca afirmar una compra sin respuesta confirmada |

Primero autenticar y verificar permisos; para escritura por ID verificar propietario antes de mutar. Un recurso conocido de otro propietario da 403. No se registran passwords, tokens ni bodies sensibles. Estado vacío/cargando/error nunca se muestra como compra exitosa. Tokens de ejemplo y montos del prototipo no se usan en producción.
