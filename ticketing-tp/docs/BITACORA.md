# Bitácora documental — Tópicos II 2026

Esta bitácora registra hechos verificables. Cada entrada debe indicar responsable, change, PR/commit, evidencia y estado. No se marca una tarea como terminada solo por generar archivos.

| Fecha | Responsable | Change | Actividad y evidencia | Estado |
|---|---|---|---|---|
| 2026-11-23 | Equipo (preparación) | `project-bootstrap` | Scaffolding de monorepo, Docker, pruebas y OpenSpec generado | Preparado, no validado |
| 2026-11-23 | Integrante que ejecutó Docker | `project-bootstrap` | Backend: `pytest` abortó en colección (`ModuleNotFoundError: app`); Ruff 6 errores; mypy OK (3 archivos) | Falló |
| 2026-11-23 | Integrante que ejecutó Docker | `project-bootstrap` | Frontend: lint OK, `tsc --noEmit` OK, Vitest 1/1 OK | Verificado localmente |
| 2026-11-23 | Equipo (corrección preparada) | `project-bootstrap` | Ajustes a Dockerfile, pytest, imports y permisos; ver `INC-001` | Pendiente de ejecutar tests y CI |

## Cómo registrar una actividad

1. Agregar una fila con la fecha y quien la hizo (evitar autores genéricos cuando haya responsable real).
2. Vincular change OpenSpec, issue y PR/commit si existen.
3. Conservar salida de comandos, decisiones técnicas y resultados reales, sin marcar checks que no pasaron.
4. Si hay un error, abrir sección en `docs/INCIDENTES.md` y registrar causa raíz, solución y revalidación.
5. Mantener `tasks.md` sincronizado con evidencias y, tras el merge, archivar el change según el workflow acordado.

## Evidencias y trazabilidad

Usar `docs/evidencias/YYYY-MM-DD-<tema>.md` con el formato de `docs/evidencias/TEMPLATE.md`; no incluir tokens, contraseñas ni datos personales en logs. Para pruebas en CI, enlazar la ejecución de GitHub Actions. Cada decisión relevante va a un ADR en `docs/`.
