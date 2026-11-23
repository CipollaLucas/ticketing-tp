# Proposal — project-bootstrap

## Why
El equipo necesita un entorno reproducible, colaboración por PR y validación automática antes de las funcionalidades.

## What changes
Monorepo FastAPI+React+PostgreSQL, Docker Compose, CI, tests iniciales, documentación, bitácora y protocolo de contribución.

## Non-goals
No implementa autenticación, venta, dominio de eventos, colas ni microservicios independientes.

## Validation
Levantar con Docker, comprobar `/health` y frontend; lint, typecheck, tests y CI verde.
