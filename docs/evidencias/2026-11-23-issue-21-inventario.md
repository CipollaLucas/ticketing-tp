# Evidencia #21 — ticket-inventory
Fecha local: 2026-11-23. Base main a6a55ce; rama feat/ticket-inventory.

## Alcance y resultados reales
Proposal/specs/design/tasks anteriores a implementación. OpenSpec CLI 2.1.1:
`npx --yes @fission-ai/openspec validate ticket-inventory --strict`: válido.
Tests primero: 18 fallos por rutas faltantes (404); luego 18/18 HTTP verdes.

Verificación final dentro de Compose:
- `docker compose exec backend ruff check .`: All checks passed.
- `docker compose exec backend mypy app`: sin errores, 9 archivos.
- `docker compose exec -e TEST_POSTGRES_URL=postgresql+psycopg://ticketing:local-dev-only@db:5432/ticketing backend pytest -q`: **123 passed**, 0 skips, 3.40 s.
- PostgreSQL real 16: schemas temporales por prueba, sin tocar tablas operativas.
  Constraints inválidos rechazados, creación concurrente de zona duplicada 201/409,
  migración downgrade 0002 / upgrade head con identidad/eventos conservados y metadata idéntica.
- Frontend: lint, tsc, 2 tests y build correctos, sin modificaciones de producto.
- `git diff --check`: sin errores.

Warning existente: Starlette depreca TestClient/httpx; no se agrega dependencia
ajena al alcance para ocultarlo. Revisión independiente por subagente: sin hallazgos
Critical/Important. Límites menores: listado completo y consultas por zona; cobertura
específica publicación concurrente/fecha vencida mejorable. Las protecciones están
implementadas. Inventario numerado todavía no tiene ventas, por alcance de #21.

## Entrega y pendientes
PR a main con revisión de CipollaLucas; registrar CI real después de abrirlo.
No archivar change ni declarar aprobada/cerrada Etapa I. Arquitectura física de
microservicios y consolidación de changes por etapa siguen pendientes del equipo.
