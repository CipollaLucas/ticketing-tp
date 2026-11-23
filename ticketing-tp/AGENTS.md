# AGENTS.md

- No hacer commit, push ni merge directo a `main`.
- Una rama por change OpenSpec: `feat/<slug>` / `chore/<slug>` / `docs/<slug>`.
- Antes de implementar: proposal + specs (salvo bootstrap puramente técnico) + design + tasks.
- Implementar con tests, documentar evidencia y abrir PR.
- No archivar un change hasta aprobar PR, verificar CI y completar tasks.
- Seguir Conventional Commits.
- No inventar estado de tests: registrar el resultado real.
- Evitar dependencias o infraestructura fuera de alcance sin decisión documentada.
- No modificar código fuera del change aprobado sin justificarlo.
