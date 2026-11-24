# Contratos HTTP — Etapa I

Issues #3, #6, #13, #21 y #22. Identidad y eventos integrados; inventario y compra implementados en los changes ticket-inventory y ticket-purchasing. Devoluciones pendientes de Etapa III. Base: `/api/v1`. JSON UTF-8. IDs: UUID. Fechas ISO 8601 UTC. Precios en unidades menores enteras con moneda ISO, nunca float. Campos desconocidos de escritura se rechazan (422). Roles: `customer`, `event_owner`, `administrator`.

## Disponibilidad y permisos

| Método/ruta | Acceso | Éxito | Disponibilidad |
|---|---|---|---|
| POST /auth/register | Público, siempre crea customer | 201 User | Implementada (PR #12) |
| POST /auth/login | Público | 200 Token | Implementada (PR #12) |
| POST /auth/logout | Bearer válido | 204 sin body | Implementada (PR #12) |
| GET /auth/me | Bearer válido | 200 User | Implementada (PR #12) |
| PATCH /users/{user_id} | Mismo usuario o administrador | 200 User | Implementada (PR #12) |
| PATCH /admin/users/{user_id}/role | Administrador | 200 User | Implementada (PR #12) |
| GET /events?limit=20&offset=0 | Público, solo published | 200 página | Implementada (#13) |
| GET /events/{event_id} | Público, solo published | 200 Event | Implementada (#13) |
| GET /owner/events?limit=20&offset=0 | Owner, solo propios; admin todos | 200 página | Implementada (#13) |
| POST /events | Owner/admin, owner_id del servidor | 201 Event draft | Implementada (#13) |
| PATCH /events/{event_id} | Owner propio/admin | 200 Event | Implementada (#13) |
| POST /events/{event_id}/publish | Owner propio/admin | 200 Event | Implementada (#13) |
| POST /events/{event_id}/unpublish | Owner propio/admin; sin ventas | 200 Event draft | Implementada (#13) |
| POST /orders | Customer, Idempotency-Key obligatorio | 201 Order; replay 200 | Implementada (#22), sin pago real |
| GET /orders/{order_id} | Customer propietario/admin | 200 Order | Implementada (#22) |
| GET /me/tickets?limit=20&offset=0 | Bearer, solo propios | 200 página | Implementada (#22) |
| POST /tickets/{ticket_id}/refund | Customer propietario, antes del inicio (política propuesta) | 201 Refund pending; replay 200 | Futura, Etapa III |
| POST /admin/refunds/{refund_id}/approve | Administrador, antes del inicio (política propuesta) | 200 Refund approved | Futura, Etapa III |
| POST /admin/refunds/{refund_id}/reject | Administrador, motivo obligatorio | 200 Refund rejected | Futura, Etapa III |

Esta rama requiere `alembic upgrade head` (0004_purchasing). Órdenes y tickets son compras simuladas persistidas. Devoluciones no están implementadas.

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

## Eventos y catálogo (#13)

Paginación: limit 1–100, por defecto 20; offset >=0, por defecto 0; orden estable
por start_at e id. Página vacía es 200, nunca 404:
```json
{"items":[],"limit":20,"offset":0,"total":0}
```
`total` cuenta todos los eventos del filtro antes de paginar. El catálogo público
incluye solo published con inicio futuro; el detalle público conserva eventos
published pasados. Draft o ID inexistente: 404. El listado `/owner/events` incluye
borradores propios; administrator ve todos, customer recibe 403.

Crear borrador (campos requeridos):
```json
{"name":"Noche de bandas","description":"Música local","venue":"Centro Cultural, La Plata","start_at":"2040-05-15T23:00:00Z","end_at":"2040-05-16T02:00:00Z"}
```
Respuesta 201 (UUID y timestamps ilustrativos):
```json
{"id":"00000000-0000-0000-0000-000000000010","owner_id":"00000000-0000-0000-0000-000000000001","name":"Noche de bandas","description":"Música local","venue":"Centro Cultural, La Plata","start_at":"2040-05-15T23:00:00Z","end_at":"2040-05-16T02:00:00Z","status":"draft","created_at":"2026-11-23T21:00:00Z","updated_at":"2026-11-23T21:00:00Z"}
```
Nombre: 1–200; lugar: 1–300; descripción: hasta 5000 caracteres; se recortan
espacios externos. Descripción vacía permitida en draft. Fechas con zona horaria,
normalizadas UTC, inicio futuro y fin posterior. Bytes NUL en texto y fechas que
desbordan al convertir a UTC se rechazan con 422. El servidor asigna owner_id;
rechaza owner_id/status, campos extra y null con 422. Administrator puede crear
borradores propios y gestionar los ajenos sin transferir su propiedad.

PATCH acepta un subconjunto no vacío de los cinco campos de creación; valida
el resultado completo antes de mutar. Solo draft, con inicio futuro. Editar
published recibe 409: despublicar primero. Un owner ajeno recibe 403 sin mutación.
Autenticación Bearer y guards reales de identidad; sesión revocada/rol degradado
no conservan permisos. UUID inválido: 422.

Publicar/despublicar requiere body `{}` y devuelve 200 Event. Repetir el mismo
estado devuelve 200 sin cambiar timestamps. Publicar exige descripción no vacía y
fechas válidas/futuras; 422 conserva draft.

**Publicación e inventario (ADR-0004):** publicar sin zonas sigue permitido y da
visibilidad a metadatos. Comprar exige published, inicio futuro y stock suficiente.
Con ventas se rechaza despublicar (409); la edición ya exige draft. El bloqueo
compartido de Event serializa compra y despublicación.

### Recorrido por API

Con Docker levantado y `alembic upgrade head`, crear un administrador con el
comando de [autenticación](AUTENTICACION.md), iniciar sesión y usar su Bearer.
También se puede promover un usuario a event_owner mediante el endpoint admin.

```bash
# TOKEN contiene una sesión del owner o administrador, sin escribirla en documentación.
curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"Noche de bandas","description":"Música local","venue":"Centro Cultural","start_at":"2040-05-15T23:00:00Z","end_at":"2040-05-16T02:00:00Z"}'
# Usar el id devuelto como EVENT_ID.
curl "http://localhost:8000/api/v1/owner/events?limit=20&offset=0" \
  -H "Authorization: Bearer $TOKEN"
curl -X POST "http://localhost:8000/api/v1/events/$EVENT_ID/publish" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}'
curl 'http://localhost:8000/api/v1/events?limit=20&offset=0'
curl "http://localhost:8000/api/v1/events/$EVENT_ID"
```

## Órdenes y tickets — issue #22

`POST /orders`: rol customer, Bearer e `Idempotency-Key: compra-demo-001` obligatorios.
Request sin precio, total, moneda ni customer_id (campos extra: 422):
```json
{"event_id":"00000000-0000-0000-0000-000000000010","items":[{"zone_id":"00000000-0000-0000-0000-000000000020","quantity":1,"seat_ids":[]}]}
```
En numbered quantity coincide con seat_ids distintos y existentes en la zona;
en general seat_ids vacío u omitido. 1..20 zonas únicas, quantity entero estricto
1..100, máximo 100 unidades por orden, un solo evento y moneda. Inventario/fechas
se revalidan bajo locks PostgreSQL. No hay reserva previa ni pago externo.

Respuesta 201: `{id,customer_id,event_id,status:"confirmed",currency,total_minor,
created_at,items:[{id,zone_id,quantity,unit_price_minor,subtotal_minor}],
tickets:[{id,order_item_id,zone_id,seat_id,status:"valid"}]}`. Todos los importes son
enteros en unidades menores, históricos y calculados por servidor; total usa int64.
Se ajustan los nombres del contrato antes propuesto (`total`, `unit_price`) a
`total_minor`, `unit_price_minor`, explicitando unidad. IDs opacos generados por servidor.

Mismo cliente/key/payload canónico: **200**, idéntica orden y header
`Idempotent-Replayed: true`; primer éxito 201 y header false. Orden de items/asientos
no cambia identidad del payload. Misma key con otro payload: 409. Clave ASCII visible
1..128, persistida sin TTL con la orden; ámbito cliente, sin consumo ante rollback.
Replay funciona incluso después de agotarse stock o empezar el evento.

Cupo/asiento agotado o evento fuera de venta: 409, sin orden ni tickets parciales.
Evento/zona desconocidos o zona de otro evento: 404. Modalidad, asiento ajeno a zona,
monedas mezcladas o payload inválido: 422. Falta Bearer: 401; rol distinto de customer:403.
Una excepción de infraestructura revierte la transacción y puede producir 500;
no hay traducción general a 503 en este incremento. Tras error de red/servidor,
reintentar con la misma key, sin dar la compra por fallida hasta consultar el resultado.

`GET /orders/{id}`: propietario o administrador, misma respuesta sin key/hash;
ajena 403, desconocida 404. `GET /me/tickets?limit=20&offset=0`: Bearer, solo tickets
propios; `{items:[Ticket],limit,offset,total}` ordenado por UUID. limit 1..100,
offset >=0; no incluye datos de eventos/zonas expandidos ni QR. El detalle público
de eventos y el inventario permiten resolver sus nombres; no entregan códigos
ni tickets de terceros. La UI de compra queda fuera de estos issues backend.

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

## Inventario — issue #21
- POST `/events/{event_id}/zones`: owner propio/admin, draft futuro. General:
  `{"name":"Campo","mode":"general","capacity":100,"price_minor":1500,"currency":"ARS"}`.
  Numerada: `{"name":"Platea","mode":"numbered","seats":[{"label":"A1"}],"price_minor":2500,"currency":"ARS"}`.
- GET `/events/{event_id}/inventory`: público, solo published; borrador/inexistente 404.
- GET `/owner/events/{event_id}/inventory`: owner propio/admin, incluye borrador.
- Respuesta: `{event_id,zones:[{id,name,mode,price_minor,currency,capacity,available,seats:[{id,label,available}]}]}`.
  En numbered capacity es null; available cuenta asientos disponibles.
- 201 creación; 401/403 permisos, 409 publicado/pasado/duplicado, 422 payload inválido.
  Enteros estrictos; precio 0..2147483647, cupo 1..1000000; 1..1000 asientos
  numerados con etiquetas únicas (1..50). Nombre 1..100 único por evento.
  Monedas ISO soportadas: ARS, USD, EUR. Zonas inmutables, sin edición/borrado.
- Publicar no requiere zonas (ADR-0004). La disponibilidad no reserva ni garantiza compra.
