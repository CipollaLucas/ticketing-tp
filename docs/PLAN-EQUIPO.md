# Plan colaborativo — equipo de tres integrantes

## Principio de organización
Las tareas **no tienen responsables preasignados**. El equipo discute prioridades, dependencias, esfuerzo y preferencias antes de que cada integrante tome un issue voluntariamente. Las denominaciones A/B/C utilizadas en borradores anteriores no representan asignaciones.

## Backlog para acordar
| Línea de trabajo | Issue | Change OpenSpec | Estado |
|---|---|---|---|
| Mockups y contratos API | #3 | frontend-core-mockups | Para discutir |
| Modelo de dominio y arquitectura | #4 | event-management (parcialmente relacionado) | Para discutir |
| Autenticación y roles | #6 | authentication-and-roles | Para discutir |
| Gestión de eventos | Por crear al acordar alcance | event-management | Para discutir |
| Inventario, compra y concurrencia | Por definir | Change futuro | Pendiente de planificación |

Las especificaciones propuestas son borradores técnicamente validados con la CLI OpenSpec 1.14.2 (`--strict`), **no decisiones funcionales aprobadas por el equipo**.

## Reunión de planificación participativa
1. Revisar enunciado y cambios propuestos; cualquier integrante puede plantear mejoras o alternativas.
2. Acordar alcance de un primer incremento pequeño y sus contratos compartidos.
3. Revisar dependencias, complejidad e interés/disponibilidad de cada integrante.
4. Cada persona propone qué issues tomar; se acuerdan responsables y revisores sin imponer roles permanentes.
5. Registrar acuerdos, desacuerdos y decisiones pendientes en una minuta o ADR.
6. Actualizar los issues y el plan solo después de ese acuerdo.

## Reglas de contribución
- Cada tarea se desarrolla en rama propia con su change OpenSpec y PR.
- Toda propuesta tiene espacio para comentarios y revisión cruzada.
- CI verde, tests y evidencia documentada antes de mergear.
- La distribución de trabajo puede cambiar entre iteraciones.
- Mantener bitácora, ADR y evidencias de cada entrega.
- No archivar un change hasta que su implementación esté aceptada.

## Historial verificado
- 23/11/2026: PR #1 de corrección backend mergeado; INC-001 resuelta, pruebas locales OK, CI 3/3.
- 23/11/2026: PR #5 de consolidación del repositorio mergeado, duplicados eliminados con evidencias preservadas.
- 23/11/2026: tres changes de Etapa I validados con OpenSpec CLI 1.14.2 (`--strict`), sujetos a discusión de diseño y distribución colectiva.
