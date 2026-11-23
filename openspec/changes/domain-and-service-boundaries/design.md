# Diseño del dominio y límites de servicios

Estado: propuesta para revisión del equipo; entrega documental del issue #4.

## Enfoques
- Un microservicio por entidad: demasiadas transacciones distribuidas para este incremento.
- Un único modelo sin límites: simple inicialmente, pero dificulta identificar propietarios de datos.
- Elegido para esta propuesta: límites lógicos Identity, Events y Ticketing dentro del despliegue actual. Ticketing conserva toda la transacción crítica; extracción física posterior requiere otro ADR.

## Artefactos
`docs/DOMINIO.md` define entidades, estados, reglas y matriz de aceptación. `docs/ADR-0002.md` registra consistencia, idempotencia y comunicaciones. No cambia el bootstrap ni implementa compras.

## Decisiones
Montos en unidades monetarias menores enteras y moneda explícita; UUID para entidades. Inventario y órdenes en una misma base/transacción. La creación de una orden confirma inmediatamente una compra simulada sin pasarela de pago; no se modelan reservas temporales todavía. Devolución total por ticket, sin devolución parcial monetaria. Etapa III: cliente solicita pending; administrador aprueba o rechaza con auditoría. Solo aprobar libera inventario e invalida ticket, atómicamente y una sola vez. Solicitar/rechazar no afectan inventario. Solicitud/aprobación antes del inicio es política propuesta, no una exigencia textual del enunciado. Son decisiones propuestas, sujetas a revisión en el PR.

## Verificación
Validar OpenSpec en modo estricto, revisar cada criterio del issue contra la matriz de aceptación y comprobar referencias locales. Las pruebas de concurrencia se planifican con dos conexiones PostgreSQL independientes; no se declaran ejecutadas ni equivalentes a una prueba documental. No archivar hasta aceptación y CI.
