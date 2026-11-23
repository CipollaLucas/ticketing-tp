## ADDED Requirements
### Requirement: Configuración autorizada de inventario
El sistema SHALL permitir crear zonas únicamente al owner del evento o administrador,
en borrador futuro, con precio entero no negativo y moneda ISO soportada.
#### Scenario: Propietario configura zona general
- **WHEN** el owner crea una zona general con capacity 2, price_minor 1500 y ARS
- **THEN** persiste capacity=available=2 y responde 201
#### Scenario: Usuario sin propiedad
- **WHEN** otro owner intenta configurar la zona
- **THEN** responde 403 sin mutación
### Requirement: Modalidades y constraints
El sistema SHALL impedir cupos inválidos, asientos en zona general y duplicados.
#### Scenario: Numerada con etiquetas repetidas
- **WHEN** el payload repite una etiqueta en una zona numerada
- **THEN** responde 422 y no persiste zona ni asientos
#### Scenario: Creación concurrente
- **WHEN** dos requests PostgreSQL crean el mismo nombre de zona en un evento
- **THEN** una confirma y otra obtiene 409, sin filas parciales
### Requirement: Publicación y disponibilidad
El sistema SHALL conservar publicación independiente del inventario y exponer
inventario público solo para eventos publicados.
#### Scenario: Evento publicado sin zonas
- **WHEN** se consulta inventario de un evento publicado sin zonas
- **THEN** responde 200 con lista vacía sin prometer disponibilidad
#### Scenario: Consulta de borrador
- **WHEN** un visitante consulta inventario de un borrador
- **THEN** responde 404
