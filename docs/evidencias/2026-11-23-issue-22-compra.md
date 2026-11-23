# Evidencia #22 — ticket-purchasing
Fecha local: 2026-11-23. Base: PR #23, ceff9048. Rama feat/ticket-purchasing.

## Requisitos entregados
- POST /api/v1/orders con Bearer customer y key obligatoria; precio servidor.
- Canonicalización items/asientos, replay 200, colisión 409, key por cliente.
- Lock PostgreSQL User → Event → Zone; guard de publicación/fecha tras lock.
- Decremento condicional general y UNIQUE asiento; orden, líneas, tickets y key
  en una transacción; importes BIGINT. FKs compuestas para correspondencia zona.
- GET orden propietario/admin y listado paginado de tickets propios.
- Disponibilidad real y prohibición de despublicar con ventas bajo lock compartido.
- Alembic 0004 reversible; CI también para PR apilado sobre feat/ticket-inventory.

## Resultados reales
Antes de código: proposal/specs/design/tasks y CLI 2.1.1 validando ticket-purchasing.
Tests iniciales: 12 fallos por rutas/modelos ausentes. Luego 12 pasan y se amplía cobertura.

Verificación final dentro de Compose:
- `docker compose exec backend ruff check .`: All checks passed.
- `docker compose exec backend mypy app`: sin errores, 10 archivos.
- `docker compose exec -e TEST_POSTGRES_URL=postgresql+psycopg://ticketing:local-dev-only@db:5432/ticketing backend pytest -q`: **146 passed**, 0 skips, 4.74 s.
- Warning existente TestClient/httpx de Starlette, sin ocultarlo.
- Frontend sin cambios de producto: lint/tsc/2 tests/build correctos durante #21.
- `git diff --check`: sin errores.
- `docker compose config --quiet` y `docker compose build`: éxito para backend/frontend.

Pruebas PostgreSQL real 16, schemas temporales y sesiones independientes:
- Último cupo y último asiento: [201,409], una orden y un ticket.
- Replay concurrente [200,201] misma orden; colisión [201,409].
- Estrés inicial: 20 solicitudes, 10 workers, cupo 5: cinco 201 y quince 409,
  available=0, cinco órdenes/tickets. No se presenta como prueba de escala masiva.
- Fallo inyectado al INSERT de tickets tras descontar: sin orden/líneas/tickets,
  cupo intacto y retry misma key confirma.
- Carrera compra/despublicación: venta y published, o draft sin venta; nunca
  tickets para evento despublicado por la operación concurrente.
- Migración downgrade 0003 / upgrade head conserva inventario y coincide con
  metadata SQLite/PostgreSQL. DB rechaza asiento duplicado, FK zona incompatible
  y duplicación de key/cliente.

Tests SQLite adicionales: venta mixta, todo o nada multi-item, moneda mixta y
asiento/zona de otro evento rechazados, replay tras inicio, orden canónico de
asientos/items, misma key entre clientes, precios históricos, enteros estrictos,
campos de precio rechazados, permisos y paginación.

OpenSpec `validate --all --strict`: **7 válidos, 1 fallo preexistente** en
project-bootstrap por falta de deltas/specs y skip_specs. Ambos changes nuevos
son válidos. No se modifica bootstrap fuera del alcance #21/#22. No se afirma que
la validación global sea verde.

Revisión independiente de código por subagente: sin Critical/Important.
Las brechas menores indicadas (monedas, replay tardío, orden de asientos y carrera
compra/despublicación) quedaron cubiertas por pruebas añadidas después de su lectura.
Limitaciones aceptadas: locks serializan evento/cliente, listado de inventario
completo, sin UI nueva, ni pago, refunds o colas; UNIQUE histórico de asiento deberá
adaptarse cuando se apruebe devolución/reventa en Etapa III.

## Entrega
PR #23 de inventario: CI run 45281920148 concluido success, revisión CipollaLucas
solicitada. Compra se entrega en PR dependiente; fusionar #23 primero y retargetear
compra a main. No fusionar automáticamente ni archivar changes antes de aprobación
humana y CI verificado. La fase completa requiere revisar pendientes del TP
(microservicios físicos y organización de changes por etapa incluidos).
