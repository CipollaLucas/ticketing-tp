# Validación local posmerge — autenticación e integración de Etapa I

**Fecha:** 2026-11-23  
**Entorno:** Windows PowerShell, Docker Desktop, repositorio `CipollaLucas/ticketing-tp`, rama `main`.  
**Referencia:** PR #8 (dominio), PR #11 (integración de mockups de #9) y PR #12 (integración de autenticación de #10).  
**CI del merge final:** https://github.com/CipollaLucas/ticketing-tp/actions/runs/45265910499 — success (backend, frontend, Docker).

## Evidencia aportada por el equipo (capturas de ejecución local)

| Paso | Resultado observado |
|---|---|
| `docker compose up --build -d` | Backend/frontend construidos; PostgreSQL healthy; servicios iniciados |
| `docker compose exec backend alembic upgrade head` | Comando finalizado sin error visible; no se aporta consulta de tabla/migración posterior |
| `docker compose exec backend pytest -q` | **43 passed, 3 skipped, 1 warning** (8.44 s) |
| `docker compose exec backend ruff check .` | **All checks passed!** |
| `docker compose exec backend mypy app` | **Success: no issues found in 7 source files** |
| Swagger `POST /api/v1/auth/login` | **200**, Bearer de prueba emitido, `expires_in=3600` |
| Swagger `POST /api/v1/auth/logout` | **204**, con Authorization Bearer |

Las capturas demuestran el **login y logout exitosos**, pero **no documentan** explícitamente un GET `/auth/me` ni un intento posterior con token revocado que devuelva `401`. Los tests automatizados del proyecto sí cubren estos comportamientos, según la suite incorporada en PR #10/#12. Tampoco se adjuntan capturas del registro, aunque la persistencia del usuario queda implícita en el login.

## Límites y advertencias
- Tres tests locales quedaron **skipped** porque requieren `TEST_POSTGRES_URL`; el CI de integración incluye PostgreSQL 16 y pasó.
- Se observó un warning de deprecación `StarletteDeprecationWarning` relativo a `httpx`; no bloqueante.
- Las capturas muestran una credencial Bearer: **no reproducirla, copiarla ni almacenarla en este documento**; fue utilizada para el logout, y conviene confirmar su revocación con un 401.
- Validación exclusivamente de **desarrollo local**; no demuestra preparación para exposición pública ni existencia de venta de entradas.
- Los mockups pertenecen a una demo documental; no están integrados con la API de autenticación.

## Conclusión
**Aceptación técnica del incremento de autenticación en el alcance demostrado:** CI verde, migración sin error visible, 43 tests locales ejecutados con éxito, lint/tipos OK, login 200 y logout 204. Queda como prueba complementaria verificar en Swagger `GET /api/v1/auth/me` autorizado antes del logout y `401` con el token anterior luego del logout. No bloquear el avance de Etapa I por esta observación.

**Trabajo siguiente:** Issue #13, gestión de eventos, sin responsable asignado; acordar la dependencia de zonas/inventario antes de habilitar publicación.
