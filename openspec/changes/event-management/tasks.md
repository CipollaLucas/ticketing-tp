# Tasks

## Preparación del issue #13
- [x] Actualizar main con pull fast-forward y crear feat/event-management.
- [x] Leer issue, autenticación integrada, contratos y enunciado como referencia.
- [x] Detallar diseño propuesto y alternativas para la dependencia con inventario.
- [x] Confirmar alcance del PR: el usuario eligió resolver solo #13.

## Plan de ejecución del issue #13
Objetivo: entregar gestión de eventos y catálogo, reutilizando FastAPI/SQLAlchemy,
Bearer y PostgreSQL existentes, sin dependencias nuevas. Diseño: design.md.
Ejecución en la rama solicitada, por el agente actual. Publicación sin inventario
es una decisión de implementación explícita para resolver la dependencia del issue;
no representa aprobación de compras ni cierre de fase.

### 1. Eventos y ciclo de vida
Archivos: app/models.py, app/events.py, app/main.py y tests/test_events.py bajo backend/.
- [x] Escribir tests HTTP reales para alta draft, permisos, PATCH, transiciones y catálogo.
- [x] Ejecutarlos antes de implementar: deben fallar por rutas ausentes (404).
- [x] Implementar Event, esquemas estrictos y router con guards existentes.
- [x] Verificar tests nuevos y suite completa con pytest; Ruff y mypy.

### 2. Persistencia PostgreSQL
Archivos: backend/alembic/versions/0002_events.py, backend/tests/test_event_migrations.py,
backend/tests/test_postgres.py.
- [x] Escribir test de upgrade/downgrade conservando usuarios y eventos persistidos.
- [x] Verificar fallo por migración ausente y crear migración reversible.
- [x] Probar metadata/constraints y flujo de eventos sobre PostgreSQL migrado.
- [x] Probar escrituras concurrentes con sesiones independientes y bloqueo de fila.

### 3. Contratos, evidencia y PR
Archivos: docs/API-ETAPA-I.md, docs/DOMINIO.md, README.md, docs/BITACORA.md,
docs/evidencias/2026-11-23-issue-13-eventos.md y este change.
- [x] Documentar publicación sin zonas, límites y ejemplos reproducibles de API.
- [x] Verificar backend, frontend, Compose y OpenSpec estricto; registrar resultados reales.
- [ ] Revisar diff completo, hacer commit Conventional Commit y push de esta rama.
- [ ] Abrir PR contra main vinculado a #13 y solicitar revisión a CipollaLucas.
- [ ] Comprobar CI remoto; dejar revisión/aceptación y archivado pendientes.

Foco de revisión: PATCH null/fechas parciales; administración ajena sin transferir
propiedad; borradores inaccesibles; orden estable con fechas iguales; conservación
de identidad al revertir migración. Cada punto tiene cobertura en tareas 1 o 2.

## Aceptación posterior
- [ ] Obtener revisión humana y aprobación del PR.
- [ ] Archivar el change en PR documental solo después de aprobación y CI verificado.

## Registro de ejecución
- Base: 43 passed, 3 skipped sin PostgreSQL.
- RED de alta: 404 en lugar de 201; RED de migración: tabla events ausente.
- Suite final host/Docker con PostgreSQL: 102 passed, sin skips, 1 warning previo.
- Revisión independiente: dos P2 (NUL/overflow UTC), reproducidos y corregidos;
  cinco regresiones RED → GREEN y suite completa verde. Sin menores diferidos.
- Decisiones y fallos intermedios: ver evidencia del issue #13.
