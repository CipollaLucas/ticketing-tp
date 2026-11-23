## Plan de implementación — ticket-purchasing
Objetivo: resolver #22 sobre #21. Stack existente FastAPI/SQLAlchemy/PostgreSQL.
Spec: specs/ticket-purchasing/spec.md; decisiones y riesgos: design.md.
Foco: canonicalización, fallo tras descuento, última localidad, propiedad, moneda mixta.
- [x] 1. Escribir proposal/specs/design/tasks y validar OpenSpec previo a código.
- [x] 2. Escribir tests HTTP de compra, replay y autorización; ejecutar RED.
- [x] 3. Crear Order/OrderItem/Ticket y migración 0004; router purchasing.py con transacción, locks y constraints.
- [x] 4. Integrar disponibilidad y guard de despublicación; verificar tests SQLite.
- [x] 5. Añadir pruebas PostgreSQL de concurrencia, estrés inicial y rollback, y migración reversible.
- [x] 6. Documentar API/dominio/bitácora/evidencia; ejecutar suite, Ruff, mypy, OpenSpec y revisión independiente.
- [ ] 7. Abrir PR apilado, pedir revisión a Lucas y verificar CI.
- [ ] 8. Aprobar y fusionar PRs en orden; no archivar hasta cumplir revisión/CI (fuera de esta ejecución).
