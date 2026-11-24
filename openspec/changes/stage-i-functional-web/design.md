## Diseño
- Se preserva el diseño editorial de la UI existente y su modo demostración.
- Nuevo componente CoreWorkspace separa las operaciones reales del catálogo editorial y de los datos de ejemplo.
- Cliente HTTP coreApi centraliza tipos, token bearer, errores y header Idempotency-Key.
- Token de acceso en estado React exclusivamente: no localStorage/sessionStorage ni cookies permanentes.
- El usuario crea cuentas customer. La promoción a event_owner necesita administrador; UI administrativa ofrece cambio de rol mediante UUID de usuario.
- El owner/admin crea borrador, configura zona general/numerada, publica. La compra solo funciona para customer. El backend sigue haciendo todas las autorizaciones.
- Precio mostrado = unidad menor /100, el backend es fuente de verdad de precio/stock.
- Reintentos de compra utilizan la misma key (guardada en el estado) mientras el payload no cambie. Después de compra confirmada la UI deshabilita duplicados hasta seleccionar nueva compra.
- Se usa POST /api/v1/orders (compra simulada persistida), GET /me/tickets y consulta de inventario.
- La compra desde el frontend no representa pago efectuado ni código de acceso QR.

## Riesgos / límites
- Recargar pierde sesión: seguridad de demostración antes que persistencia de token.
- UI de administración necesita UUID de otro usuario proporcionado por el equipo; no hay búsqueda general de usuarios.
- Se muestra primera página de resultados de tickets/eventos (limit 20); paginación visual avanzada no es parte de este change.
- Falta verificar manualmente todo el recorrido en navegador contra la BD de desarrollo tras aprobación del PR.
