# Design — project-bootstrap

## Decisiones
1. Monorepo para coordinar tres estudiantes.
2. FastAPI/React/PostgreSQL por proximidad al repo modelo.
3. Docker para entornos de desarrollo consistentes.
4. Feature branches + PR revisado por otro miembro + CI obligatorio.
5. OpenSpec por capacidad y archivo tras entrega.
6. API monolítica de arranque, sin afirmar cumplimiento de microservicios. La distribución se definirá en un ADR posterior.

## Riesgos
- Cambios concurrentes de API y frontend: acordar contratos de endpoints.
- PostgreSQL local usa puerto 5433 para minimizar conflictos.
- Sin pago externo hasta definir mecanismo de simulación y alcance académico.
