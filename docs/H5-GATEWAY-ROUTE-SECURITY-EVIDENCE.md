# H5 — Explicit Gateway route and denial security probes

This increment augments the real three-service `h5_gateway_smoke.py` run under disposable `h5-gateway-ci`; it does **not** change NGINX routing, production flags or business logic.

The preexisting UAT already checked public route ownership (Identity/Events/Ticketing), forwarded bearer credentials, three roles, purchase idempotency, forbidden ticket access and absence of Legacy fallback. This increment adds explicit negative probes:

| Probe | Expected |
| --- | --- |
| Browser accesses private auth introspection | HTTP 404, `Cache-Control: no-store` |
| Browser accesses private sales availability/gate paths | HTTP 404, `Cache-Control: no-store` |
| Forged internal service credential presented to Gateway | Still HTTP 404 for all private paths |
| Unknown `/api/v1/route-not-extracted` | HTTP 503, `Cache-Control: no-store` |
| Unknown non-API path | HTTP 404 |
| Identity `/auth/me` with absent or invalid bearer | HTTP 401 from actual Identity routing |
| Response body | No reflected fake internal credential |

All probes execute through the actual NGINX Gateway to independently persisted services, with no Legacy container and no real secrets printed. A synthetic marker is used instead of a real internal service secret.

**Evidence limits:** This verifies selected explicit paths, not all possible URL normalization tricks, fuzzing, every HTTP error status, header injection variants, secret scanning of every response, or security of a production deployment. A broader penetration and full contract audit remains a separate concern. After green CI and review, this can justify the *bounded H5 UAT route/security* task but not an unqualified security certification.

No OpenSpec archive or production cutover is implied.
