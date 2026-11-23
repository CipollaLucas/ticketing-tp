# Integración del catálogo público — Issue #19

## Alcance
React consume la API de eventos publicada por el equipo en PR #18. Se preserva el diseño del PR #17.

## Comportamiento esperado
- Modo inicial: Eventos reales; mientras carga se muestra progreso, catálogo vacío muestra mensaje explícito.
- Eventos reales publicados: título, lugar y fecha local, sin precios, botones de venta ni inventario ficticios.
- Selección de evento: consulta por ID real y trata 404/error sin mostrar un ejemplo como si fuera real.
- Alternar a Demostración muestra eventos ficticios separados; no se emite ningún ticket.
- Vite envía /api a FastAPI por proxy; no se usa autenticación.

## Validación pendiente
CI, OpenSpec CLI y prueba manual de escritorio/móvil. Registrar salidas concretas antes de declarar terminado.
