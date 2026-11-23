# Prototipo navegable — issue #3

Abrir `index.html` directamente o servir desde la raíz: `python3 -m http.server 8765`; visitar http://localhost:8765/docs/mockups/.

No usa APIs, cookies, almacenamiento local, dependencias ni recursos remotos. El selector de rol solo simula vistas. No ingresar credenciales reales. Todo evento, precio, orden y ticket mostrado es ficticio.

## Recorrido de revisión
1. Catálogo → Ver evento → Ver compra de ejemplo → probar confirmación: comprobar que no afirma una compra exitosa.
2. Probar cantidad inválida: validación HTML; cambiar zona: explicación de numerado/general.
3. Catálogo: selector de estados con resultados/cargando/vacío/error.
4. Acceder: revisar campos y errores propuestos; no captura contraseñas.
5. Selector de rol: cliente → mis tickets; organizador → mis eventos; administrador → roles. Comprobar navegación diferenciada y acciones claramente simuladas.
6. Abrir `#admin` como visitante: aviso explícito de vista de ejemplo, nunca una autorización.
7. Revisar 320px y escritorio, tabulación, foco y avisos.

Los contratos de [API-ETAPA-I.md](../API-ETAPA-I.md) son la referencia para implementación posterior. Este issue no agrega componentes ni lógica al frontend React.
