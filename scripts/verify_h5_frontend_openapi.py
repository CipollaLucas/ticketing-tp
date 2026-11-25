"""H5 browser API contract ownership against live, disposable OpenAPI schemas.

Exact public methods used by frontend/src/coreApi.ts. Refuses non-H5 Compose
projects and never contacts Legacy or a production URL.
"""
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend" / "src" / "coreApi.ts"
GATEWAY = ROOT / "gateway" / "three-service-preview.conf"
FILES = [
    "-f", "docker-compose.h3-contract.yml",
    "-f", "docker-compose.h4-live.yml",
    "-f", "docker-compose.h5-gateway-preview.yml",
]

# Frontend method name, HTTP verb, actual FastAPI path, owner and source reference.
CONTRACTS = [
    ("register", "POST", "/api/v1/auth/register", "h3-identity", "'/auth/register'"),
    ("login", "POST", "/api/v1/auth/login", "h3-identity", "'/auth/login'"),
    ("me", "GET", "/api/v1/auth/me", "h3-identity", "'/auth/me'"),
    ("logout", "POST", "/api/v1/auth/logout", "h3-identity", "'/auth/logout'"),
    ("changeRole", "PATCH", "/api/v1/admin/users/{user_id}/role", "h3-identity", "/admin/users/"),
    ("ownerEvents", "GET", "/api/v1/owner/events", "h3-events", "'/owner/events'"),
    ("createEvent", "POST", "/api/v1/events", "h3-events", "'/events'"),
    ("createZone", "POST", "/api/v1/events/{event_id}/zones", "h4-ticketing", "/zones"),
    ("publishEvent", "POST", "/api/v1/events/{event_id}/publish", "h3-events", "/publish"),
    ("getInventory", "GET", "/api/v1/events/{event_id}/inventory", "h4-ticketing", "/inventory"),
    ("purchase", "POST", "/api/v1/orders", "h4-ticketing", "'/orders'"),
    ("myTickets", "GET", "/api/v1/me/tickets", "h4-ticketing", "'/me/tickets'"),
]


def schema(service: str) -> dict:
    result = subprocess.run(
        ["docker", "compose", "-p", "h5-gateway-ci", *FILES, "exec",
         "-T", service, "python", "-c",
         "import json,urllib.request; print(json.dumps(json.load("
         "urllib.request.urlopen('http://127.0.0.1:"
         + {"h3-identity": "8001", "h3-events": "8002", "h4-ticketing": "8003"}[service]
         + "/openapi.json',timeout=5))))"],
        cwd=ROOT, capture_output=True, text=True, timeout=20, check=True,
    )
    return json.loads(result.stdout)


def main() -> None:
    if os.environ.get("H5_PROJECT") != "h5-gateway-ci":
        raise SystemExit("REFUSED: only disposable H5 project")
    source = SOURCE.read_text(encoding="utf-8")
    gateway = GATEWAY.read_text(encoding="utf-8")
    openapi = {owner: schema(owner) for owner in ("h3-identity", "h3-events", "h4-ticketing")}
    for method_name, method, path, owner, needle in CONTRACTS:
        function = re.search(r"export async function " + re.escape(method_name) + r"\(", source)
        if not function:
            raise AssertionError("Missing React API function: " + method_name)
        next_function = source.find("export async function ", function.end())
        body = source[function.start():next_function if next_function >= 0 else len(source)]
        if needle not in body:
            raise AssertionError(f"React path changed: {method_name}")
        actual = openapi[owner].get("paths", {}).get(path, {})
        if method.lower() not in actual:
            raise AssertionError(f"OpenAPI method missing in {owner}: {method} {path}")
        for other, schema_doc in openapi.items():
            if other != owner and method.lower() in schema_doc.get("paths", {}).get(path, {}):
                raise AssertionError(f"Ambiguous owner: {method} {path} in {owner} and {other}")
        print(f"PASS: {method} {path} owned by {owner}")
    # Gateway routing priority remains a separate check in h5_gateway_contract_check.
    required = [
        "location ^~ /api/v1/internal/",
        "location = /api/v1/orders { proxy_pass http://h4-ticketing:8003; }",
        "location = /api/v1/me/tickets { proxy_pass http://h4-ticketing:8003; }",
        "location /api/v1/events/ { proxy_pass http://h3-events:8002; }",
        "location ~ ^/api/v1/events/[^/]+/inventory/?$",
        "location ~ ^/api/v1/events/[^/]+/zones/?$",
    ]
    if any(fragment not in gateway for fragment in required):
        raise AssertionError("Gateway ownership rule missing")
    if "proxy_pass http://backend:" in gateway or "proxy_pass http://legacy" in gateway:
        raise AssertionError("Legacy fallback must not exist")
    print(f"PASS: {len(CONTRACTS)} React operations match independently owned OpenAPI methods")
    print("LIMIT: this is method/path ownership, not full response/error-schema parity")


if __name__ == "__main__":
    main()
