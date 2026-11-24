# Entrega Etapa I — Core (Tópicos II 2026)

Estado al 24/11/2026: **Etapa I aceptada funcionalmente por el equipo para la primera entrega**. Backend y frontend React integrados en `main` (PR #28), CI 4/4 aprobado y recorrido de UAT desde React completado. No se incluye pago real.

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
| UI real vs modo demo | Capturas del frontend local y checklist informado como 9/9 completo por el usuario | UAT funcional aceptada |
| Flujo HTTP de compra desde React | PR #28 mergeado en `main`; pruebas manuales con roles, publicación, zona General, dos compras, stock agotado y listado de tickets | Implementado y aceptado |

## Pruebas concurrentes automatizadas

La suite del PR #25 verifica en PostgreSQL real:
- Último cupo/asiento, sin doble venta.
- Reintento concurrente con misma idempotency key y colisión por payload diferente.
- 20 solicitudes / cupo 5: cinco órdenes, quince conflictos (estrés **inicial**, no prueba masiva).
- Rollback de inventario, órdenes y tickets ante fallo inyectado.
- Carrera entre despublicación y compra.

**No** presentar estas pruebas como demostración de colas masivas ni de una arquitectura de microservicios desplegada de modo independiente.

## Acta de aceptación funcional — 24/11/2026

El equipo informó que completó el checklist de **9 pruebas** de Etapa I desde la interfaz React. Las capturas muestran pantallas de administrador, organizador, cliente, inventario sin stock y tickets emitidos. El usuario aclaró que, en la primera prueba, había omitido presionar **Agregar zona**, y luego completó correctamente el recorrido con un evento nuevo.

| Verificación | Resultado comunicado |
| --- | --- |
| Autenticación y roles | Aprobada: administrador, event_owner, customer |
| Borrador de evento | Aprobada: alta en UI |
| Configuración de inventario | Aprobada: zona General con cupo y precio |
| Publicación y catálogo | Aprobada: evento publicado y consultable |
| Primera y segunda compra | Aprobadas: órdenes y tickets persistidos |
| Sobreventa | Aprobada: agotamiento del cupo; UI bloquea compra adicional |
| Listado de tickets | Aprobada: se muestran tickets realmente emitidos |
| Idempotencia | Aprobada según checklist comunicado; el header `idempotent-replayed: true` también fue observado previamente en Swagger |

La evidencia corresponde a pruebas manuales realizadas por el equipo en su máquina local y no equivale a una auditoría de usabilidad ni de navegadores. La validación automatizada de concurrencia se respalda por los **146 tests PostgreSQL** y el CI integrado. Las órdenes no procesan pagos bancarios.

### Limitaciones y mejoras diferidas, no bloqueantes
- Mensajes de validación de fechas más claros antes del POST.
- Mostrar inventario configurado en la vista de organizador y confirmar la publicación de un evento sin zonas.
- Mejorar presentación, navegación y estados de stock agotado de la UI.
- Completar archivado OpenSpec de changes aprobados con la herramienta CLI y revisar la anomalía histórica de `project-bootstrap` en validación global.
- Registrar las capturas originales de UAT en un soporte compartido del equipo si la cátedra exige anexos.

**Alcance aprobado para la primera entrega:** backend/API, mockups, frontend funcional de prueba, roles, eventos, zonas y compra simulada segura. Etapas II y III permanecen excluidas.

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

El PR #28, ya mergeado en `main`, incorpora un acceso **Operar ticketera** desde React con registro/login, permisos de usuario reales, creación/publicación de eventos, configuración de zonas generales o numeradas, compra idempotente y consulta de tickets de prueba. Se conserva el catálogo editorial y el modo demo. Ver [guía de demostración](ETAPA-I-DEMO-GUIA.md).

## Próximas etapas
- Etapa II: recomendación personalizada por historial/preferencias y estrategia de caché con TTL e invalidación.
- Etapa III: colas/backpressure, devoluciones, búsqueda multicriterio, pruebas de carga y validación de arquitectura de microservicios/fallos parciales.
