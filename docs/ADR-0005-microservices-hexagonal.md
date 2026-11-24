# ADR-0005 — Migración a microservicios y arquitectura hexagonal

Estado: **propuesta implementada parcialmente**, 24/11/2026. Sustituye la visión futura simplificada del ADR-0002; no convierte automáticamente la Etapa I en microservicios.

## Contexto y objetivo

La consigna exige **microservicios desplegados independientemente** y **arquitectura hexagonal**. El estado anterior es un monolito modular (React/Vite + un backend FastAPI + PostgreSQL). Docker Compose con varios contenedores no demuestra microservicios si solo existe un backend. Reutilizar el core y sus pruebas; migrar de forma incremental, con una rama/PR por paso y sin reemplazar `main` sin CI y UAT.

## Decisión: límites de servicio por capacidad de negocio

| Servicio | Propiedad exclusiva | API pública/interna | Persistencia |
| --- | --- | --- | --- |
| Identity | User, AuthSession, roles | register/login/logout/me, /internal/auth/introspect, administración de usuarios | identity_db |
| Events | Event, ciclo draft/published, metadatos | /events, /owner/events, /internal/events/{id}/sales-status | events_db |
| Ticketing | Zone, Seat, Order, OrderItem, Ticket, claves idempotentes | /events/{id}/zones, /inventory, /orders, /me/tickets, /internal/events/{id}/sales-summary | ticketing_db |

Se conservan los contratos públicos `/api/v1` detrás de un gateway (reverse proxy) para no reescribir React. Los servicios deben tener procesos/healthchecks propios, imágenes y migraciones independientes; `docker compose up` debe levantar **identity**, **events**, **ticketing**, **gateway**, **frontend** y persistencia independiente.

En local puede existir un solo clúster PostgreSQL, pero con tres bases/usuarios sin permisos cruzados; no compartir tablas, FKs entre servicios, sesiones SQLAlchemy ni imports de modelos ajenos. **No partir Ticketing en inventario y órdenes**: deben seguir dentro de una transacción ACID local.

## Regla hexagonal por servicio

- `domain/`: entidades, valores y reglas puras sin FastAPI, SQLAlchemy, HTTP, Pydantic ni variables de entorno.
- `application/use_cases/`: orquestación; depende de **ports**, no de drivers.
- `application/ports/`: Protocols/interfaz del repositorio, UoW, consultas a otros servicios, clock.
- `adapters/inbound/http/`: FastAPI/Pydantic; mapea HTTP y errores a comandos/resultados.
- `adapters/outbound/persistence/`: SQLAlchemy + transacciones + constraints.
- `adapters/outbound/http/`: clientes HTTP con timeout, mapeo de 404/409/503 y autenticación entre servicios.
- `bootstrap/`: ensamblado explícito de dependencias.

**Prohibiciones verificables:** el dominio no importa FastAPI, Pydantic, SQLAlchemy ni otros servicios; los casos de uso no importan adaptadores. Tests unitarios de dominio funcionan sin PostgreSQL; integración real usa PostgreSQL.

## Consistencia crítica y límites de una simple llamada HTTP

El contrato previo permite `Event.status=published` sin zonas, y solo Ticketing tiene stock. Si Ticketing consulta Events por HTTP y luego descuenta inventario, la despublicación puede ocurrir entre ambas operaciones (TOCTOU).

Para evitar falsas garantías, extracción dividida en dos hitos:

1. **Hito de extracción con política conservadora:** Events puede publicar sin stock, pero una vez publicado un evento con inventario/ventas bajo este contrato, las acciones de despublicar o editar su estado comercial se **bloquean temporalmente** hasta introducir coordinación de estado. Ticketing valida `published` y fecha por un contrato síncrono con timeout, trata fallos como operación no disponible (sin confirmación) y mantiene transacción local.
2. **Hito de coordinación explícita:** definir un protocolo comprobable para iniciar/cerrar ventas. Propuesta preferida: Ticketing es autoridad sobre `sale_state` y mantiene proyección/versionado del evento; Events solicita transición, Ticketing serializa el cambio con el lock que protege compras. Sin transacción distribuida; fallo de comunicación no habilita ventas ni reversiones incorrectas. Probar carreras publicación/despublicación/compra, reinicios y timeouts.

Se debe escoger, diseñar, implementar y testear el protocolo antes de habilitar despublicación remota. Una llamada `GET published` aislada **no** conserva la garantía del monolito.

## Autenticación entre servicios

Identity expone introspección **interna** de token Bearer (sin exponer hash ni password). Gateway reenvía token al servicio; cada servicio consulta Identity mediante port/adapter con timeout corto, autenticación de servicio y fallo cerrado. En una evolución se puede cachear identidad por TTL con invalidación al revocar roles, pero no antes de probar seguridad y revocación.

## Política de errores y observabilidad

- Propagar `X-Request-ID` entre servicios; logs sin tokens ni datos sensibles.
- Timeouts HTTP acotados; fallo de Identity/Events impide **nuevas** operaciones que requieren esas consultas; no revertir compras ya confirmadas.
- No afirmar que existe mensajería, outbox, gateway ni bases aisladas hasta mostrar evidencias de su ejecución.
- Un broker y Transactional Outbox se introducen solo si el enunciado o la Etapa III requieren eventos asíncronos. **Propuesta, no implementado**.

## Alternativas evaluadas

1. **Solo reorganizar carpetas**: insuficiente; no cumple despliegue independiente.
2. **Dividir todas las entidades en servicios separados**: crea coordinación distribuida en el núcleo de compra y riesgo de sobreventa.
3. **Reescribir de cero**: desperdicia 146 pruebas previas y el frontend validado.

Se elige separación por capacidad (Identity / Events / Ticketing) con Ticketing transaccional, migrando por adaptadores y conservando contratos públicos.

## Puertas de aceptación

- 3 backends independientes en Compose, cada uno con healthcheck, imagen, configuración y base privada.
- Al detener Identity, Ticketing/Events no dan acceso inseguro; al detener Events, no se confirman ventas nuevas sin verificar estado.
- Ningún acceso SQL cruzado entre servicios.
- Dependencias de dominio hacia afuera prohibidas por test/lint.
- Todas las pruebas unitarias anteriores conservadas o sustituidas con equivalentes; suites PostgreSQL de concurrencia/idempotencia migradas y verdes en el **nuevo despliegue**.
- UAT completa desde React contra gateway; CI y documentación C4 reflejan el despliegue real.

## Estado de implementación inicial

PR de `refactor/hexagonal-foundation`: primera regla de dominio pura para `PurchaseIntent`, hash canónico y choque de claves, y puertos preliminares. Los puertos todavía no están conectados a adaptadores reales; **el backend continúa siendo monolito**. Los siguientes PRs materializarán separación completa.
