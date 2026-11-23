# Authentication and roles — implementation plan

**Goal:** implementar identidad y autorización simples para el issue #6.
**Architecture:** usuarios y sesiones SQLAlchemy; Bearer opaco revocable; guards compartidos FastAPI.
**Tech stack:** FastAPI, PostgreSQL, Alembic, pwdlib[argon2], pytest; SQLite solo para tests aislados.
**Spec:** specs/authentication/spec.md y design.md (diseño aprobado por usuario en la conversación 2026-11-23).
**Execution:** directa por Codex, autorizada por el usuario. Rama propia; sin push/PR por instrucción posterior.

## Restricciones y foco de revisión
No JWT, email, pagos ni CRUD de eventos. Contraseñas 12–128, username ASCII 3–50 normalizado y único, display_name 1–100 no vacío. Sesiones 3600s por defecto (60–86400). Revisar campos extra/escalada, expiración, revocación, credenciales en errores/logs y recursos ajenos sin mutación. Guardar solo hashes.

## 1. Persistencia y migraciones
Archivos: Dockerfile (incluir migraciones en imagen), app/database.py (Base, get_db), app/models.py (User, AuthSession), alembic.ini y alembic/env.py + versions/0001_identity.py; tests/test_migrations.py.
- [x] Verificar baseline: pytest actual (2 tests).
- [x] Escribir y observar test rojo de endpoint protegido sin credenciales (404 actual vs 401 requerido).
- [x] Preparar modelos con UUID, username único, role CHECK y sesiones con FK/expiración.
- [x] Probar upgrade/downgrade/reupgrade y restricciones; verificar metadata coincide con migración.

## 2. Registro y sesiones
Archivos: app/auth.py; tests/test_auth.py; app/main.py; pyproject.toml (única nueva dependencia: pwdlib[argon2]).
Interfaces: get_db() produce Session por request; get_current_user valida Bearer y consulta User; UserResponse nunca incluye secretos.
- [x] Escribir tests HTTP para registro/normalización/duplicados, campos extra, passwords, login válido/incorrecto, almacenamiento de hashes, logout y expiración; observar rojo antes de rutas.
- [x] Implementar schemas estrictos, hashes Argon2, sesiones aleatorias de 32 bytes y hash SHA-256, login con verificación ficticia para username inexistente.
- [x] Ejecutar pytest y corregir hasta verde.

## 3. Roles, propiedad y bootstrap admin
Archivos: app/auth.py (require_administrator, require_owner_or_admin), app/create_admin.py; tests/test_auth.py y tests/test_create_admin.py.
Interfaces: PATCH /users/{id} solo display_name; PATCH /admin/users/{id}/role solo admin; guard de propiedad reutilizable para eventos futuros.
- [x] Escribir/observar rojo: 403 de cliente/owner, no mutación ajena, acceso propio/admin, 404, auto cambio de rol 409 y privilegios actualizados en sesiones existentes.
- [x] Implementar guards y rutas pequeñas. Probar ruta de eventos exclusiva del fixture para demostrar edición ajena rechazada antes de mutar.
- [x] Implementar CLI de alta de administrador con password por getpass; probar creación y duplicado sin exponer hash/contraseña.

## 4. Documentación y verificación
Archivos: docs/ADR-0003.md, docs/AUTENTICACION.md, README.md, docs/BITACORA.md y docs/evidencias/2026-11-23-issue-6-auth.md; .env.example y docker-compose.yml para TTL configurable.
- [x] Documentar contrato y comandos de migración/administrador y límites operativos.
- [x] Ruff, mypy, pytest completo, OpenSpec estricto; frontend lint/tipos/test/build.
- [x] Verificar Docker/PostgreSQL si motor disponible; registrar sin inventar resultados.
- [x] Revisión final y corrección de problemas relevantes con tests.
- [x] Commit(s) Conventional Commits; rama local lista para abrir PR posteriormente.
- [ ] PR, revisión cruzada y CI pendientes hasta habilitar acceso; no archivar.
