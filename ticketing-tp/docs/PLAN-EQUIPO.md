# Plan de trabajo para 3 integrantes

Los responsables se identifican provisoriamente como A, B y C. Cada PR necesita una revisión cruzada.

## Arranque: PRs no conflictivos
| PR | Responsable | Revisor | Entregable | Dependencias |
|---|---|---|---|---|
| #1 bootstrap | A | B | Compose, backend/frontend mínimos, CI, OpenSpec | Ninguna |
| #2 contratos y mockups | B | C | Figma/Markdown: pantallas cliente, owner y admin; contratos API | #1 |
| #3 arquitectura + modelos | C | A | ADR de microservicios, modelo entidad-relación, amenazas/concurrencia | #1 |

## Etapa I: desarrollo paralelo tras acordar contratos
| Línea | Owner | Primer change | Definición de terminado |
|---|---|---|---|
| Backend identidad y roles | A | authentication-and-roles | permisos ADMIN/OWNER/CLIENT, tests 401/403 |
| Frontend navegación y catálogo | B | frontend-catalog | mockups trazables, tests UI, integración con API |
| Dominio eventos/inventario | C | event-management | CRUD owner, modelos, migraciones y tests |

## Después
- A: flujo de órdenes, idempotencia y transacciones.
- B: compra UI, paneles, devoluciones UI, pruebas e2e.
- C: arquitectura de servicios, cache, colas, recomendaciones y stress tests (dividiendo entre todos).

## Reglas operativas
- 1 change y 1 feature branch por tarea; no ramas eternas.
- Reunión corta semanal con demo, riesgos y PRs bloqueados.
- Nunca se mergea un PR rojo; la implementación se revisa contra specs.
- Cambios de API/esquema primero como contrato documentado.
- Criterio de cierre: tests + docs + CI + PR + OpenSpec archivado.
