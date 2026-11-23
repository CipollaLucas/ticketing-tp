# Evidencia — issue #3

Rama: `docs/frontend-core-mockups`. Change: `frontend-core-mockups`.

- `npx --yes @fission-ai/openspec@1.14.2 validate frontend-core-mockups --strict`: exit 0, válido.
- `node --check docs/mockups/prototype.js`: exit 0.
- Parser HTML: IDs únicos, links internos y destinos de labels válidos; ejemplos JSON del contrato parseados sin errores.
- Navegador real: recorrido catálogo → detalle → compra → confirmación de demo; aviso observado: no cobró, reservó cupo ni emitió tickets. Selector de rol → organizador: navegación Mis eventos y borrador visibles. Inspección visual en viewport angosto: sin desbordes observados en la vista de organizador.
- No se verificó exhaustivamente accesibilidad ni todas las combinaciones de viewport. Estados restantes tienen recorrido manual en mockups/README.md.
- `git diff --check`: sin errores. No se modificó React ni se implementó lógica de negocio. No se agregan tests Vitest que solo dupliquen documentación.
- Enfoque publicado en https://github.com/CipollaLucas/ticketing-tp/issues/3#issuecomment-7112000821.
- PR/CI/revisión cruzada pendientes: usuario pidió conservar ramas locales hasta tener acceso. No archivado.
- Título sugerido: `docs: agregar mockups y contratos de Etapa I (issue #3)`. Body: prototipo independiente, contratos de identidad alineados con #6 y dominio propuesto #4, operaciones futuras explícitas; `Closes #3` al abrir PR.
