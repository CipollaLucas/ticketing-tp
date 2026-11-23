# INC-001 — Validación del bootstrap (23/11/2026)

## Síntoma
- `docker compose exec backend pytest -q`: ModuleNotFoundError: No module named 'app'.
- `docker compose exec backend ruff check .`: EXE002 e I001 (6 reportes).
- `docker compose exec backend python -m pytest -q`: 2 passed, 1 warning.
- `docker compose exec backend mypy app`: OK.
- Frontend: ESLint, TypeScript y Vitest (1/1) OK.

## Diagnóstico
El repositorio quedó duplicado: existen `backend/` y `ticketing-tp/backend/`.
La versión corregida fue publicada dentro de `ticketing-tp/`, mientras Docker y CI utilizan las rutas de la raíz.
En GitHub Actions, ejecución 45179148416, el job backend falló en Ruff I001; Docker y frontend pasaron.

## Corrección propuesta (rama fix/bootstrap-validation-inc001)
- Sincronizar en raíz pyproject.toml, imports de app/main.py y tests/test_api.py.
- Ajustar Dockerfile para copiar paquete antes de instalación editable.
- Registrar evidencia y agregar control para evitar regresión.
- NO eliminar aún la carpeta duplicada: limpiar en un PR posterior tras verificar que no haya cambios exclusivos.

## Criterios de cierre
- CI backend/frontend/docker verde en PR.
- En Docker local: `pytest -q`, `python -m pytest -q`, `ruff check .`, `mypy app`.
- Completar estado con resultado real, SHA y URL de PR.
- Mantener pendiente warning de Starlette/httpx como mejora separada.

Estado: **Resuelta — 2026-11-23**. PR #1 mergeado (main 2ce1b192). Evidencia local: pytest 2 passed, 1 warning; Ruff sin errores; mypy sin errores. CI: 3/3 checks exitosos. Warning de Starlette/httpx pendiente como deuda técnica.
