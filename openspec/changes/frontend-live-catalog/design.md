## Decisions
- La fuente por defecto es **eventos reales**. El selector `Demostración` permite recorrer mockups sin confundirlos con el catálogo público.
- API cliente de solo lectura en `eventApi.ts`, validando el shape mínimo, manejo de HTTP no OK y `AbortController` para cambios rápidos de vista/página.
- `GET /api/v1/events?limit=20&offset=N` con `items,limit,offset,total` y `GET /api/v1/events/{id}`. Nunca solicitar borradores.
- Proxy `/api` en Vite. En Docker: `http://backend:8000`; sin Docker: `http://localhost:8000`. `VITE_API_BASE_URL` permite configurar una base absoluta si el despliegue cambia.
- Las fechas se presentan con `Intl.DateTimeFormat('es-AR')` y zona `America/Argentina/Buenos_Aires`.
- Un evento publicado **no implica disponibilidad de entradas**: el frontend no muestra compra real, precio, capacidad ni checkout en este modo.
- Modos demo y real no comparten identidad, sesiones ni lógica de compra.

## Open questions
- Se requiere producción/hosting separado: configurar reverse proxy equivalente en despliegue, no incluido.
- Las vistas de organizador/administrador aún son maquetas. Integración con auth/CRUD en change posterior.
