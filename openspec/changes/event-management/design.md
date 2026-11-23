## Contexto y estado
Issue #13, sobre main d9acfcc (PR #12 integrado). FastAPI, SQLAlchemy,
PostgreSQL y sesiones Bearer ya existen. No hay eventos ni inventario.
Rama de trabajo: feat/event-management. Alcance confirmado por el usuario: resolver únicamente #13.
Diseño detallado antes de implementar; validaciones reales en la evidencia del issue.

El objetivo de este incremento es resolver #13 como parte del Core. No cierra por
sí solo Etapa I: faltan inventario, compra idempotente y tickets. El enunciado
propone un change por etapa, mientras main conserva changes por capacidad; su consolidación queda fuera del alcance de #13. No importar silenciosamente
la rama local feat/phase-1 ni dar por aceptadas sus tareas.

## Alternativas y decisión de implementación
1. Exigir zonas para publicar: respeta literalmente el contrato propuesto, pero
   bloquea la publicación porque #13 excluye inventario.
2. Permitir publicar metadatos válidos sin zonas (recomendado): entrega catálogo
   funcional y reserva la habilitación de compra para la validación de inventario.
   Requiere ajustar explícitamente API-ETAPA-I y DOMINIO; no implica vender entradas.
3. Incluir inventario y compra: permite completar más del Core, pero excede #13 y
   exige un diseño transaccional adicional y ampliar proposal/specs/tasks.

Se aplica la alternativa 2 como decisión del implementador, comunicada al usuario
al confirmar el alcance de #13 y documentada para revisión de Lucas. No se atribuye
al equipo una aprobación de implementación ni se implementa compra.

## Modelo propuesto
- Event: UUID id; owner_id FK users.id sin borrado en cascada; name (1–200),
  description (hasta 5000), venue (1–300); start_at/end_at con zona horaria;
  status draft/published; created_at/updated_at UTC asignados por servidor.
- Usar name y start_at según el contrato existente, no title ni starts_at.
- No capacity, zones, seats, precios ni disponibilidad ficticia en esta tabla/API.
- Fechas requeridas, normalizadas UTC sin overflow, end_at > start_at. Texto sin bytes NUL. Nombre y lugar sin
  espacios vacíos. Crear/editar exige inicio futuro; descripción puede estar
  vacía en draft y debe tener contenido para publicar.
- Restricciones de base: FK, estado válido, longitudes/cadenas no vacías y orden
  de fechas. La comparación con hora actual se valida en aplicación.
- Migración Alembic 0002 posterior a 0001_identity, reversible sin eliminar
  identidad; índice para catálogo por status/start_at/id y listado por propietario.

## API y permisos propuestos
- Reutilizar require_event_owner y require_owner_or_admin de app/auth.py.
  Administrator puede gestionar eventos ajenos, consistente con el guard y el
  rol de gestión completa; un owner solo los propios. Customer recibe 403;
  Bearer ausente/inválido 401; ID desconocido 404.
- POST /api/v1/events: 201 draft, owner_id del usuario autenticado. Rechazar
  campos extra, owner_id y status con 422.
- PATCH /api/v1/events/{id}: subconjunto no vacío de name, description, venue,
  start_at, end_at; campos null/extra inválidos. Solo draft; published recibe
  409 y debe despublicarse primero. Validar combinación con valores persistidos
  antes de mutar. Error de permiso/validación no cambia contenido ni estado.
- POST /api/v1/events/{id}/publish y /unpublish: body {} requerido. Publicar
  valida datos completos e inicio futuro; error 422 conserva draft. Repetir la
  transición al mismo estado devuelve 200 sin cambiarlo. En este incremento no
  hay ventas: cuando existan, impedir despublicar con ventas en su change.
- GET /api/v1/owner/events: owner ve propios, admin todos; incluye borradores.
- GET /api/v1/events: solo published con inicio futuro, orden start_at/id.
  GET /api/v1/events/{id}: published incluso pasado; draft/inexistente 404.
- Listados: limit 1–100 (20), offset >= 0 (0), respuesta
  {items, limit, offset, total}; total filtrado antes de paginar; página vacía 200.
- Errores conservan formato FastAPI existente; ninguna credencial en respuestas.

## Implementación prevista
Modelos en app/models.py y router/esquemas/operaciones en app/events.py, registrado
en app/main.py. Sesión por request y transacción única por escritura. Usar bloqueo
de fila para serializar cambios/transiciones en PostgreSQL y comprobar estado tras
adquirirlo. No agregar dependencias ni desplegar servicios nuevos. Mantener el
backend modular actual sin afirmar microservicios físicos.

## Validación y entrega
Tests primero: creación, roles y propiedad reales, admin, 401/403/404/409/422,
campos protegidos, fechas con/sin timezone, edición parcial inválida sin mutación,
transiciones y publicación incompleta, ocultamiento de drafts, eventos pasados,
orden/paginación/total/listado owner. Migraciones upgrade/downgrade/upgrade y
comparación de metadata, también PostgreSQL real con el mecanismo de tests existente.
Ejecutar Ruff, mypy, pytest, checks frontend y OpenSpec estricto; registrar resultados
reales, incluidos skips o bloqueos. Actualizar contrato, dominio, README, bitácora y
evidencia. Abrir PR a main y solicitar revisión a CipollaLucas. No archivar ni marcar
Etapa I completa antes de implementación, revisión y CI verificados.
