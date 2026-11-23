## Alcance y arquitectura
Usar React 19 + CSS propio; no añadir dependencias de routing, iconos, imágenes externas ni estado global. Navegación por un estado `Page` y hash simple, selector `Role` simulado. Los eventos, precios, zonas y tickets son ejemplos en memoria.

## Límites explícitos
- Nunca pedir credenciales reales ni almacenarlas.
- No ejecutar `POST /orders`, no usar bearer tokens, no afirmar que hay pago, reserva o tickets válidos.
- El catálogo real se integrará en un change posterior cuando el Issue #13 pueda publicar eventos con inventario.
- Los panels de organizador y admin son muestras visuales, no controles de acceso.
- Conservar en `docs/mockups/` el aporte HTML del Issue #3.

## Diseño
Estilo editorial claro, tipografía fuerte, formas gráficas CSS y tarjetas, responsive en móvil y desktop. Inputs etiquetados, estados explícitos y navegación con botones. Revisión visual manual solicitada antes de merge final.
