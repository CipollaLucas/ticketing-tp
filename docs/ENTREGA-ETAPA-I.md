# Entrega Etapa I — Core (Tópicos II 2026)

Estado al 24/11/2026: **backend y catálogo integrados en `main`; frontend funcional de Etapa I preparado en PR #28, con aceptación visual pendiente**.

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
| Replay idempotente | Captura de Swagger mostró `idempotent-replayed: true` para la operación repetida; misma orden observada | Comportamiento validado; conservar evidencia del status HTTP 200 en el acta final |
| UI real vs modo demo | CI frontend y OpenSpec válidos; UAT visual final sobre `main` | Pendiente prueba visual final |
| Flujo HTTP de compra desde React | PR #28 implementa ingreso real, evento y zona, compra simulada y listado de tickets | Implementado en rama del PR #28; pendiente UAT visual y merge |

## Pruebas concurrentes automatizadas

La suite del PR #25 verifica en PostgreSQL real:
- Último cupo/asiento, sin doble venta.
- Reintento concurrente con misma idempotency key y colisión por payload diferente.
- 20 solicitudes / cupo 5: cinco órdenes, quince conflictos (estrés **inicial**, no prueba masiva).
- Rollback de inventario, órdenes y tickets ante fallo inyectado.
- Carrera entre despublicación y compra.

**No** presentar estas pruebas como demostración de colas masivas ni de una arquitectura de microservicios desplegada de modo independiente.

## Pendientes explícitos de aceptación de Etapa I

1. Guardar evidencia completa del replay HTTP `200` junto con el header `Idempotent-Replayed: true` y los IDs coincidentes (el header ya fue observado).
2. Completar UAT visual del PR #28: catálogo real, ingreso, owner/zonas/publicación, cliente/compra/tickets, modos demo y errores; recoger capturas.
3. Confirmar `alembic current: 0004_purchasing (head)` después de actualizar al commit final de `main`.
4. Revisar y archivar changes OpenSpec aceptados. El proyecto venía con `project-bootstrap` sin deltas/skip_specs; revisar la validación global, además de las validaciones específicas exitosas.
5. El recorrido de compra simulada desde React está implementado en PR #28, sin pago real ni QR. Validarlo antes de la primera entrega; no confundir compra simulada con transacción financiera.

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

## Interfaz funcional en Etapa I

El PR #28 incorpora un acceso **Operar ticketera** desde React con registro/login, permisos de usuario reales, creación/publicación de eventos, configuración de zonas generales o numeradas, compra idempotente y consulta de tickets de prueba. Se conserva el catálogo editorial y el modo demo. Ver [guía de demostración](ETAPA-I-DEMO-GUIA.md).

## Próximas etapas
- Etapa II: recomendación personalizada por historial/preferencias y estrategia de caché con TTL e invalidación.
- Etapa III: colas/backpressure, devoluciones, búsqueda multicriterio, pruebas de carga y validación de arquitectura de microservicios/fallos parciales.
