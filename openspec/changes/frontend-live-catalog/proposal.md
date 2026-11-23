## Why
El backend del PR #18 expone el catálogo real de eventos publicados y el frontend del PR #17 solo contiene contenido ficticio. La Etapa I necesita que las pantallas consulten la API sin fingir ventas.

## What Changes
- Consultar `GET /api/v1/events` y `GET /api/v1/events/{id}` desde React.
- Manejar estados de carga, vacío, error, detalle inexistente y paginación.
- Mostrar fechas en Argentina y estados de publicación sin inventar precios ni cupos.
- Conservar el modo demo claramente separado para recorrer el diseño.
- Usar proxy de Vite en Docker y desarrollo local, sin tokens.

## Impact
Solo `frontend/`, configuración frontend de Docker Compose, documentación y pruebas. No modificar backend, base de datos, roles ni ventas.
