# Cómo contribuir

## Flujo para las tres personas
1. Actualizar `main`: `git switch main && git pull --ff-only`.
2. Crear rama: `git switch -c feat/<nombre>`.
3. Crear un change OpenSpec (proposal, specs si aplican, design, tasks).
4. Implementar únicamente las tareas del change con tests.
5. Ejecutar lint, tipos y tests mediante Docker (ver README).
6. Commit: `feat: descripción breve` (o docs/fix/test/chore).
7. Push de la rama y PR a `main` con evidencia.
8. Otro integrante revisa, CI debe estar verde y luego squash merge.
9. Archivar change OpenSpec en un PR de documentación, enlazando el PR de implementación.

## Reglas
- Nadie trabaja directo en `main`.
- Cada PR debe tener una persona revisora distinta del autor.
- Evitar ramas de más de una capacidad a la vez.
- Si un cambio altera esquema/API, coordinar antes de desarrollar en paralelo.
- No guardar secretos ni archivos `.env` reales.
