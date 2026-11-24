# Entrega Etapa I — Core (Tópicos II 2026)

Estado al 24/11/2026: **implementación de core integrada en `main`; validación automatizada satisfactoria; aceptación funcional manual parcialmente completada**.

## Alcance previsto por el enunciado
Backend, APIs, autenticación, compra de tickets y mockups, mediante changes OpenSpec incrementales. No incluye recomendaciones/caché (Etapa II), ni colas masivas, devoluciones, búsqueda avanzada y estrés completo (Etapa III).

## Evidencias y trazabilidad

| Componente | Evidencia | Estado |
| --- | --- | --- |
| Base Docker/PostgreSQL, CI | Workflows de main; `docker compose up --build -d` | Implementado y comprobado |
| Autenticación y tres roles | PR #12, `/api/v1/auth/*` y guardias de rol | Implementado |
| Eventos, CRUD y publicación | PR #18, migración `0002_events` | Implementado |
| Inventario, generales/numeradas | PR #23, migración `0003_inventory`, constraint de modo, cupo y asiento | Implementado |
| Compra segura/idempotencia | PR #24 integrado mediante #25, migración `0004_purchasing` | Implementado |
| Catálogo React real y mockups | PR #20 integrado mediante #26, modo demo explícito | Implementado |
| OpenSpec | changes por módulo; `frontend-live-catalog --strict` válido | Validaciones específicas satisfactorias |
| Pruebas en Docker PostgreSQL | `146 passed, 1 warning in 27.53s`, sin skips | Comprobadas localmente |
| Static checks | `ruff check .` y `mypy app`, 10 archivos | Comprobados localmente |
| Comportamiento manual | Dos órdenes confirmadas con un ticket cada una; tercer intento excediendo cupo = HTTP 409 `Insufficient capacity` | Comprobado |
| Replay idempotente | Usuario informó que la misma solicitud devolvió la misma orden y el mismo JSON | Comportamiento observado, pendiente evidencia explícita de HTTP 200 y header `Idempotent-Replayed: true` |
| UI real vs modo demo | CI frontend y OpenSpec válidos; UAT visual final sobre `main` | Pendiente prueba visual final |
| Flujo HTTP de compra desde React | Backend tiene `/orders`; frontend real mantiene venta deshabilitada deliberadamente | No implementado; alcance UI de compra pendiente de decisión |

## Pruebas concurrentes automatizadas

La suite del PR #25 verifica en PostgreSQL real:
- Último cupo/asiento, sin doble venta.
- Reintento concurrente con misma idempotency key y colisión por payload diferente.
- 20 solicitudes / cupo 5: cinco órdenes, quince conflictos (estrés **inicial**, no prueba masiva).
- Rollback de inventario, órdenes y tickets ante fallo inyectado.
- Carrera entre despublicación y compra.

**No** presentar estas pruebas como demostración de colas masivas ni de una arquitectura de microservicios desplegada de modo independiente.

## Pendientes explícitos de aceptación de Etapa I

1. Reproducir la compra original con la misma clave: guardar respuesta `200`, header `Idempotent-Replayed: true` y mismo `order.id` y `ticket.id`.
2. Probar visualmente en el frontend integrado a `main`: catálogo con evento publicado, detalle, ausencia de compra real, modo demo, estados vacíos/error.
3. Confirmar `alembic current: 0004_purchasing (head)` después de actualizar al commit final de `main`.
4. Revisar y archivar changes OpenSpec aceptados. El proyecto venía con `project-bootstrap` sin deltas/skip_specs; revisar la validación global, además de las validaciones específicas exitosas.
5. Decidir explícitamente si la entrega exige un recorrido de compra **desde React** o si el backend/API más mockup satisfacen la Etapa I; documentar el resultado según criterio docente.

## Comandos de reproducción

```powershell
git switch main
git pull --ff-only origin main
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current
docker compose exec -e TEST_POSTGRES_URL=postgresql+psycopg://ticketing:local-dev-only@db:5432/ticketing backend pytest -q
docker compose exec backend ruff check .
docker compose exec backend mypy app
```

Frontend: `http://localhost:5173`; Swagger: `http://localhost:8000/docs`. Ejecutar solo contra desarrollo local.

## Próximas etapas
- Etapa II: recomendación personalizada por historial/preferencias y estrategia de caché con TTL e invalidación.
- Etapa III: colas/backpressure, devoluciones, búsqueda multicriterio, pruebas de carga y validación de arquitectura de microservicios/fallos parciales.
