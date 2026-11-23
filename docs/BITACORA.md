# Bitácora documental

| Fecha | Autor | Change | Evidencia | Estado |
|---|---|---|---|---|
| 2026-11-23 | Equipo | project-bootstrap | Estructura y archivos iniciales preparados | Pendiente de ejecución y CI |

Registrar decisiones, enlace a PR, resultados de tests, fallos y correcciones por cada change.
| 2026-11-23 | Equipo | fix/bootstrap-validation-inc001 | Corrección de imports/configuración en raíz; CI inicial falló por Ruff; ver docs/INCIDENTES.md | Pendiente de CI y revisión |
| 2026-11-23 | Coordinación | project-bootstrap / INC-001 | PR #1 mergeado; local pytest 2/2, Ruff/mypy OK; CI 3/3 OK; advertencia Starlette no bloqueante | Validado |
| 2026-11-23 | Coordinación | Issue #2 | Evidencias exclusivas migradas a raíz y copia duplicada eliminada en rama chore/consolidate-repository-structure | Pendiente de CI y PR |
| 2026-11-23 | Coordinación | Etapa I planificación | Propuestas OpenSpec de autenticación, eventos y frontend preparadas en rama docs/stage-i-openspec-planning; vinculadas a Issues #3, #4 y #6 | Pendiente de revisión y validación OpenSpec |
| 2026-11-23 | karmanino + Codex | domain-and-service-boundaries / #4 | [Evidencia](evidencias/2026-11-23-issue-4-dominio.md): OpenSpec estricto válido; entrega documental, concurrencia solo planificada | Rama local; PR/revisión/CI pendientes |
| 2026-11-23 | karmanino + Codex | frontend-core-mockups / #3 | [Evidencia](evidencias/2026-11-23-issue-3-mockups.md): OpenSpec válido, sintaxis/JSON/links y recorrido real de demo | PR #9 CI verde; integración mediante rama de resolución por conflicto documental |
| 2026-11-23 | karmanino + Codex | authentication-and-roles / #6 | [Evidencia](evidencias/2026-11-23-issue-6-auth.md): implementación con migración y tests PostgreSQL; PR #10, CI verde; integración reconciliada luego de PR #8 y #11 | Pendiente de CI de integración y merge |
| 2026-11-23 | Coordinación y equipo | Aceptación posmerge Etapa I (PR #8/#11/#12) | [Validación local](evidencias/2026-11-23-validacion-local-auth-posmerge.md): Docker healthy, Alembic sin error, Pytest 43 passed/3 skipped, Ruff/mypy OK, login 200/logout 204; CI final main verde | Incremento de autenticación aceptado en alcance probado; eventos/venta pendientes |
| 2026-11-23 | karmanino + Codex | event-management / #13 | [Evidencia](evidencias/2026-11-23-issue-13-eventos.md): eventos, publicación sin inventario y catálogo; migración reversible; 102 tests host/Docker con PostgreSQL, Ruff/mypy y frontend OK; revisión independiente y regresiones | Implementación validada localmente; PR/revisión humana/CI pendientes; Etapa I no completa |
