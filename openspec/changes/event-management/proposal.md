## Why
Event owners need to design and publish events, and clients need to browse published events. Identity is integrated, but event APIs and persistence are missing.

## What Changes
- Manage event drafts, publish/unpublish and owner-scoped editing.
- Public event catalog and event detail.
- Represent event venue and scheduling metadata.
- Define API contracts and event lifecycle, coordinating with authentication.

## Out of scope
Ticket inventory, purchases, queue management, recommendations and advanced relevance search (later changes).

## Issue #13 — propuesta de implementación
Base actualizada: main d9acfcc; rama feat/event-management. Reutilizar identidad y
guards integrados en PR #12. El diseño detalla contratos, migración reversible,
permisos y pruebas antes de implementar.

El usuario confirmó resolver únicamente #13 en este PR. Se implementa publicación
sin zonas para entregar catálogo sin introducir inventario fuera de alcance. Es
una decisión explícita de implementación para revisión del equipo: publicar no
habilita compra. Se actualizan API-ETAPA-I y DOMINIO. El Core sigue incompleto.
La organización de los otros changes y la consolidación por etapa quedan fuera
de este PR; no se altera ni archiva trabajo ajeno.
