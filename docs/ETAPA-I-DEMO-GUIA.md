# Guía de demostración — primera entrega Tópicos II 2026

## Objetivo
Demostrar la Etapa I desde el frontend React (además de Swagger), con roles y compra simulada segura, sin atribuir pago real ni funcionalidades de Etapas II/III.

## Iniciar
```powershell
git switch main
git pull --ff-only origin main
docker compose up --build -d
docker compose exec backend alembic upgrade head
```
Abrir http://localhost:5173 y elegir **Operar ticketera**.

## Recorrido sugerido (local)
1. **Administrador:** iniciar sesión como usuario admin preexistente; promover otro usuario customer a `event_owner` en la pestaña **Roles**, introduciendo su UUID.
2. **Organizador:** cerrar sesión e ingresar como owner. Crear un evento futuro con descripción/lugar/fechas. Agregar zona general de cupo 2 y precio en ARS. Publicar.
3. **Visitante:** abrir catálogo real y verificar que el evento aparece. El frontend lo muestra como publicado, no como pago realizado.
4. **Cliente:** desde Operar ticketera iniciar sesión como customer, elegir evento y zona. Comprar una entrada. Obtener orden confirmada y ticket identificable.
5. **Tickets:** consultar **Mis tickets** para verificar persistencia.
6. **Stock:** hacer una segunda compra con una clave nueva y agotar el cupo; el intento siguiente devuelve HTTP 409 sin crear orden.
7. **Idempotencia:** en Swagger repetir una compra con la misma key, validar HTTP 200 y `idempotent-replayed: true`. Los tests del frontend validan lectura del header y uso de key estable en reintento.

## Evidencia anterior aceptada
- Docker + Alembic head `0004_purchasing`.
- Suite PostgreSQL real: 146 passed, 0 skipped (un warning de Starlette no bloqueante).
- UAT compra y agotamiento de cupo (409); replay con `idempotent-replayed: true` confirmado por captura.
- Controles Ruff/mypy y CI verdes en PRs de core.

## Aceptación y archivo
- CI de PR #28 aprobado 4/4 y recorrido funcional desde React comunicado como completo (9/9 pruebas, 24/11/2026).
- Evidencias de roles, zona, compra, sobreventa y tickets observadas en las capturas del equipo.
- Mantener como tarea administrativa posterior el archivo de los changes OpenSpec mediante CLI y la revisión de `project-bootstrap`.
- No se requiere añadir recomendaciones/caché ni pagos reales para esta entrega.

## Exclusiones explícitas
Sin pago externo, reembolsos, recomendación personalizada, cache distribuida, colas masivas ni stress test de Etapa III.
