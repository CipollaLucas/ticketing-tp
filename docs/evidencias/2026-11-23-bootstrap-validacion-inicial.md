# Evidencia: primera validación del bootstrap

- Fecha: 2026-11-23 (hora exacta de la ejecución no confirmada)
- Responsable: integrante que ejecutó los comandos; asignación pendiente
- Rama/commit/PR: no informados
- Change OpenSpec: `project-bootstrap`
- Entorno: PowerShell en `D:\Desarrollos\ticketing-tp`, Docker Compose

## Resultados reportados

| Verificación | Observación | Estado |
|---|---|---|
| Backend `pytest -q` | `ModuleNotFoundError: No module named 'app'` durante colección | Falló |
| Backend `ruff check .` | 6 errores: `EXE002` x4, `I001` x2 | Falló |
| Backend `mypy app` | `Success: no issues found in 3 source files` | OK |
| Frontend `npm run lint` | Sin errores | OK |
| Frontend `npx tsc --noEmit` | Sin errores | OK |
| Frontend `npm test` | Vitest: 1 archivo, 1 test OK | OK |

## Corrección pendiente de validación

Ver `docs/INCIDENTES.md`, INC-001. La existencia de un ZIP actualizado **no acredita** tests backend ni CI verdes.
