# Registro de incidencias

## INC-001 — Falla en colección de tests y lint del bootstrap

- **Fecha:** 2026-11-23
- **Change:** `project-bootstrap`
- **Detectado por:** ejecución local de un integrante, Windows + Docker Desktop
- **Severidad:** bloqueante de CI/backend
- **Estado:** corrección preparada, **pendiente de validación local**

### Síntomas observados

- `docker compose exec backend pytest -q`: falla al importar `app` desde `tests/test_api.py` (`ModuleNotFoundError`). No se ejecutaron los tests de backend.
- `docker compose exec backend ruff check .`: seis errores, cuatro `EXE002` y dos `I001`.
- `docker compose exec backend mypy app`: OK, 3 archivos.
- Frontend: ESLint y TypeScript OK; Vitest 1/1 OK.
- El warning de Starlette/httpx no fue la causa del fallo y se deja como deuda no bloqueante para revisar compatibilidad.

### Análisis y corrección

1. El Dockerfile instalaba `-e '.[dev]'` antes de copiar `app/`: esto impedía instalar el paquete de aplicación de manera fiable. Ahora copia `app/` antes de instalar dependencias.
2. Se configura `[tool.pytest.ini_options] pythonpath = ["."]` para que el import del paquete funcione también al invocar `pytest` como binario.
3. Se ordenan imports conforme a Ruff.
4. Se retira el bit ejecutable de archivos Python en el ZIP. Como los bind mounts de Docker Desktop sobre Windows pueden mostrar igualmente todos los archivos como ejecutables, se excluye `EXE002` de Ruff para evitar falsos positivos dependientes del sistema operativo; las demás comprobaciones siguen activas.

### Criterio de cierre

Guardar la salida de los comandos:

```bash
docker compose up --build -d
docker compose exec backend python -m pytest -q
docker compose exec backend pytest -q
docker compose exec backend ruff check .
docker compose exec backend mypy app
docker compose exec frontend npm run lint
docker compose exec frontend npx tsc --noEmit
docker compose exec frontend npm test
```

Registrar fecha, responsable, commit y PR cuando CI esté verde. **No afirmar que la incidencia está resuelta antes de ejecutar el entorno del equipo.**
