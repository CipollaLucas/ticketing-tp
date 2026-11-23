# Diseño de mockups y contratos — issue #3

## Alcance y enfoques
Entrega documental: prototipo HTML/CSS/JS autónomo en docs/mockups, sin modificar React ni integrar APIs. Se consideraron imágenes estáticas (no permiten recorrer flujos) y una aplicación React integrada (confunde demo con funcionalidad y amplía el alcance). Se elige HTML navegable por hash, sin dependencias, con roles simulados explícitos.

## Pantallas y comportamiento
Catálogo, detalle, registro/login, compra, mis tickets, panel de organizador y administración. Todas muestran aviso de demo. Selector de rol cambia solo navegación y vistas; nunca crea una sesión. Estados loading/empty/error del catálogo reproducibles. Los formularios y botones informan que no enviaron datos y no emiten tickets. El detalle enlaza compra y compra enlaza mis tickets; el historial es un ejemplo ficticio claramente rotulado.

## Accesibilidad y responsive
HTML semántico, labels explícitos, foco visible, skip link, avisos aria-live y grid que se adapta a 320px. Navegación con teclado; los formularios no tienen campos de contraseña para evitar capturar credenciales en un prototipo. La vista de acceso muestra el contrato de campos, sin pedir secretos reales.

## Contratos
`docs/API-ETAPA-I.md`: rutas, roles, request/response, errores y disponibilidad. Autenticación alineada con el diseño aprobado de authentication-and-roles: username, password, display_name; bearer opaco; customer/event_owner/administrator. Eventos y compras son propuestas futuras. El catálogo nunca presenta borradores; precios calculados en servidor; compra idempotente; no se confía en owner_id/customer_id/role del cliente. No se promete consistencia distribuida.

## Validación
OpenSpec estricto, parser HTML y revisión de navegación/labels, node --check para JS y prueba visual del prototipo si el navegador está disponible. No hay lógica productiva que justifique tests de negocio/Vitest nuevos en este issue. Registrar evidencia real y conservar revisión/CI/archivo pendientes.
