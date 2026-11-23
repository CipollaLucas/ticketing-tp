# Evidencia — issue #4

Rama: `docs/domain-and-service-boundaries`. Change: `domain-and-service-boundaries`.

- `npx --yes @fission-ai/openspec@1.14.2 validate domain-and-service-boundaries --strict`: exit 0, change válido.
- Revisión de referencias Markdown locales en DOMINIO.md y ADR-0002.md: 2 documentos, OK.
- `git diff --check`: sin errores.
- Trazabilidad: entidades y modos de inventario → DOMINIO.md; no doble venta/idempotencia/transacciones → ADR-0002.md; límites sync/async → ADR-0002.md; criterios → matriz de DOMINIO.md y spec.
- No se modificó código ejecutable. Pruebas de venta/concurrencia planificadas, no ejecutadas. CI no ejecutado para esta rama local.
- Enfoque comentado en https://github.com/CipollaLucas/ticketing-tp/issues/4#issuecomment-7112000393.
- PR pendiente por decisión del usuario: conservar rama local hasta contar con acceso. Revisión cruzada, CI y archivo pendientes.
- Título sugerido: `docs: definir dominio y límites de servicios (issue #4)`. Body: describe entidades, invariantes, ADR y matriz de aceptación; `Closes #4` al abrir PR.
