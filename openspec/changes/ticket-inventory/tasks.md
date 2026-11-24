## Plan de implementación — ticket-inventory
Objetivo: inventario real de #21. Stack: FastAPI, SQLAlchemy, Alembic, PostgreSQL.
Spec: specs/ticket-inventory/spec.md; decisiones: design.md.
Restricciones: una rama por change, sin infraestructura nueva, no archivar antes de revisión/CI.
Foco: enteros estrictos, monedas, modalidad/FK, atomicidad, autorización tras lock.
- [x] 1. Preparar proposal/specs/design/tasks antes de código y validar CLI.
- [x] 2. Escribir tests HTTP en backend/tests/test_inventory.py; ejecutar y observar 404.
- [x] 3. Implementar Zone/Seat en models.py, migración 0003 y router inventory.py; registrar en main.py.
- [x] 4. Ejecutar tests SQLite; probar constraints, migración reversible y creación concurrente PostgreSQL.
- [x] 5. Actualizar ADR-0004, API, dominio, bitácora y evidencia con resultados reales.
- [x] 6. Ejecutar Ruff/mypy/pytest y OpenSpec estricto; revisar diff y abrir PR para Lucas.
- [x] 7. Aprobación y merge de PR #23, CI verde y UAT de inventario (24/11/2026).
- [ ] 8. Archivo del change con CLI OpenSpec tras verificación de specs.
