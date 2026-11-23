# Tasks — project-bootstrap

- [x] Crear estructura base backend/frontend/infra/documentación.
- [x] Agregar endpoint raíz y health de PostgreSQL.
- [x] Preparar Docker Compose y Dockerfiles.
- [x] Agregar tests básicos y reglas de lint/types.
- [x] Preparar GitHub Actions.
- [x] Documentar flujo Git, PR, roles del equipo y bitácora.
- [ ] Ejecutar `docker compose up --build` en una máquina del equipo.
- [ ] Ejecutar todos los checks locales y registrar resultados (primera ejecución parcial; backend falló, ver `docs/INCIDENTES.md` INC-001).
- [ ] Publicar repositorio remoto, abrir PR de bootstrap y verificar CI.
- [ ] Validar el change con la CLI de OpenSpec.
- [ ] Archivar change tras aprobar y mergear.

## Hallazgos de validación

- [x] Registrar resultados reales de primera ejecución en bitácora y evidencias.
- [x] Preparar corrección reproducible del problema de imports y Ruff (`INC-001`).
- [ ] Revalidar después del rebuild: pytest (ambas invocaciones), Ruff, mypy y checks frontend.
- [ ] Registrar resultado CI y enlaces de PR antes de cerrar INC-001.
