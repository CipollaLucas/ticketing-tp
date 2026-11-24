## Why

La primera entrega requiere **microservicios** y **arquitectura hexagonal**; el monolito modular existente solo cumple los requisitos funcionales. Se necesita corregir la arquitectura sin perder las garantías de venta concurrente ni el frontend terminado.

## What changes

- Implementar tres servicios backend independientes: Identity, Events, Ticketing.
- Aplicar puertos/adaptadores y casos de uso aislados de frameworks a cada servicio.
- Aislar la propiedad y migración de datos por servicio y crear gateway para conservar /api/v1.
- Diseñar coordinación consistente entre ventas y cambios de publicación, y revalidar idempotencia/concurrencia.
- Migrar CI/Compose y capturar evidencia real de servicio independiente, fallos parciales y recorrido UI.

## Out of scope

Recomendaciones, caché, colas masivas, devoluciones y pasarelas reales. Este change se subdividirá en PRs; no atribuir implementación completa al PR de foundation.
