# Evidencia — issue #13: eventos y catálogo

Fecha: 2026-11-23 (America/Argentina/Salta). Rama: `feat/event-management`.
Base: `main` actualizado con `git pull --ff-only` a `d9acfcc` (PR #14).
Issue: https://github.com/CipollaLucas/ticketing-tp/issues/13.
Change: [event-management](../../openspec/changes/event-management/proposal.md).

## Alcance y decisiones

El usuario confirmó resolver solo #13 en este PR, como avance del Core. Se
implementan eventos, publicación y catálogo; no inventario, compra ni tickets.
No se declara cerrada Etapa I ni arquitectura de microservicios físicos.

Decisión de implementación: publicar metadatos válidos sin exigir zonas evita
bloquear #13 con inventario explícitamente excluido. Publicar no habilita venta.
Se ajustaron API-ETAPA-I y DOMINIO para que esta diferencia sea revisable por el
equipo. Al incorporar ventas será necesario validar inventario y restringir
edición/despublicación de eventos con ventas. Administrator gestiona todos los
eventos; un event_owner solo los propios, reutilizando guards reales existentes.

Se conserva el change de capacidad existente señalado por #13. Consolidar los
otros changes en una etapa implica otro alcance; no se importa la rama local
feat/phase-1 ni se archiva documentación ajena. Proposal/specs/design/tasks se
prepararon antes del código. El plan y su progreso están en tasks.md.

## Pruebas y resultados reales

Base antes de implementar: **43 passed, 3 skipped** (sin TEST_POSTGRES_URL).
Prueba inicial nueva de alta: **1 failed**, 404 en lugar de 201, antes de crear rutas.
Prueba de migración nueva: **1 failed**, tabla events ausente antes de agregar 0002.

Resultados finales:

| Entorno / comando | Resultado |
|---|---|
| Host, Python 3.13, pytest con TEST_POSTGRES_URL a PostgreSQL 16 local | **102 passed**, sin skips, 1 warning de Starlette |
| Docker, Python 3.12, `docker compose exec -e TEST_POSTGRES_URL=postgresql+psycopg://ticketing:local-dev-only@db:5432/ticketing backend pytest -q` | **102 passed**, sin skips, 1 warning de Starlette |
| Ruff en host y Docker | All checks passed |
| mypy app en host y Docker | Success: no issues found in 8 source files |
| Frontend host y Docker: npm run lint, npx tsc --noEmit, npm test, npm run build | Todos exit 0; **1 test passed**; Vite build correcto |
| docker compose build | Backend y frontend construidos correctamente |
| docker compose config --quiet | Exit 0 |
| OpenSpec 1.14.2: validate event-management --strict | Válido |
| OpenSpec 1.14.2: validate --all --strict | 4 válidos, 1 fallo previo: project-bootstrap sin delta specs |
| Docker: alembic upgrade head / alembic current | Exit 0; **0002_events (head)** |
| HTTP real GET /health y GET /api/v1/events | 200; base ok y página pública vacía válida |

La advertencia deprecatoria de Starlette/httpx ya aparecía en la base. No se
agregaron dependencias para resolverla fuera de alcance.

Los **7 casos PostgreSQL** incluyen migración identity original, carrera de roles
original, identidad original, migración Event, flujo HTTP Event sobre esquema
migrado y dos carreras de Event. Cada test crea un schema aislado y lo elimina;
los tests no hacen downgrade de la base de desarrollo.

Cobertura agregada: 56 casos sobre la base de 46 con PostgreSQL, incluyendo
401/403, ownership sin mutación ajena, gestión administrativa, campos protegidos,
fechas/timezones, PATCH parcial y null, publicación sin inventario, drafts 404,
paginación/orden/total, eventos pasados, restricciones y reversibilidad Alembic
conservando usuarios. El flujo PostgreSQL usa registro/login reales y sesiones
independientes por request.

## Concurrencia y revisión

La prueba de carrera retiene un lock en una conexión, autentica y precarga el
evento desde otra sesión, confirma por pg_stat_activity que espera un lock y
aplica publicación o revocación del actor antes de liberar. La edición responde
409 o 403 respectivamente y conserva el nombre original. No se usa SQLite para
probar locks.

Mutaciones de comprobación, restauradas inmediatamente: quitar with_for_update
hizo fallar el caso publish-409; quitar populate_existing también lo hizo fallar.
Ambos ensayos terminaron exit 1 y la suite final restaurada pasa.

Revisión independiente mediante subagente: identificó dos P2 reproducibles,
corregidos con validación de entrada y regresiones:

- Byte NUL en name/venue/description: PostgreSQL lo rechazaba al persistir. Ahora
  devuelve 422 en alta y PATCH sin mutación; probado también en PostgreSQL HTTP.
- Overflow al normalizar fechas extremas a UTC: convertir OverflowError en error
  de validación, 422 en alta/PATCH. Cinco regresiones fallaron antes de corregir;
  suite final **102 passed**. Sin hallazgos menores diferidos.

## Fallos intermedios registrados

- El test de restricciones esperaba IntegrityError para toda entrada inválida;
  PostgreSQL devuelve DataError al exceder varchar. Se ajustó el test para aceptar
  ambos rechazos y comprobar rollback mediante savepoint; no se debilitó la API.
- OpenSpec global detectó project-bootstrap sin delta specs (bootstrap técnico). Ese
  change no fue modificado respecto a main; event-management sí valida estricto.
  Se registra el fallo previo sin corregir un change ajeno a #13.
- El primer lint frontend encontró 1087 errores en un dist generado preexistente.
  Se preservó ese artefacto fuera del repo y se ejecutaron los checks sin dist;
  todos pasaron. Los outputs nuevos dist/tsbuildinfo se retiraron tras verificar
  build. No se modificó código/configuración del frontend para ampliar este issue.

## Entrega remota

PR [#18](https://github.com/CipollaLucas/ticketing-tp/pull/18) abierto contra main,
con `Closes #13` y revisión solicitada a `CipollaLucas`. Commit de implementación:
`e4a008b8ce569ad6d6a5055fffddd85bbabadeda`.

Git HTTPS local no dispone de credenciales (push terminó exit 128). Se publicó
mediante la conexión GitHub autenticada como karmanino; árbol remoto y local
idénticos: `9e5ae6edf1c5618b16680ff45b45f0a89b19d9f9`. Fetch y rebase omitieron
el commit local equivalente, dejando la rama sincronizada con origin.

CI del commit de implementación: [run 45272093621](https://github.com/CipollaLucas/ticketing-tp/actions/runs/45272093621),
**3/3 jobs completed/success** (backend, frontend y docker), verificados por API.
Este registro se agrega en un commit documental posterior; el estado del último
head se vuelve a comprobar y se mantiene en el PR antes de entregar.
La revisión humana, aceptación y archivado siguen pendientes. No se hizo commit,
push ni merge sobre main.
