# Plan incremental

- [x] Auditar arquitectura monolítica y dependencias de identidad/eventos/ticketing.
- [x] Escribir ADR-0005 y diseño objetivo sin atribuir despliegue inexistente.
- [x] Introducir reglas de dominio puras de compra y puertos preliminares de aplicación.
- [x] Adaptar digest/validación de replay del router legado para delegar al dominio, sin cambiar HTTP.
- [x] Agregar tests de dominio aislados.
- [ ] Validar OpenSpec y CI de la foundation.
- [ ] Extraer casos de uso completos y adaptadores SQLAlchemy con inyección real de puertos.
- [ ] Hacer Identity independiente (API+DB+migraciones) y probar permisos/revocación.
- [ ] Hacer Events independiente (API+DB+migraciones) y definir coordinación de estado.
- [ ] Hacer Ticketing independiente (API+DB+migraciones) y retestar concorrencia real.
- [ ] Montar gateway y docker-compose multi-servicio sin romper React.
- [ ] Ejecutar UAT completa de tres roles, fallos parciales y escenarios de sobreventa/idempotencia.
- [ ] Archivar change tras aceptación de arquitectura real, no antes.
