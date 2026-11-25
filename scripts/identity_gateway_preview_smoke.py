"""UAT for H5 auth-only preview. Creates only a disposable customer in isolated DB."""
import json
import os
import urllib.error
import urllib.request
from uuid import uuid4

BASE = os.environ.get("H5_GATEWAY_URL", "http://127.0.0.1:8090").rstrip("/")
USERNAME = "h5_" + uuid4().hex[:12]
PASSWORD = "test-only-password-2026"


def call(method, path, body=None, token=None):
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        BASE + path, data=data, headers=headers, method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            content = response.read()
            return response.status, json.loads(content) if content else None
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode())


def main():
    status, health = call("GET", "/health")
    assert status == 200 and health["mode"] == "identity-preview-only"
    status, created = call("POST", "/api/v1/auth/register", {
        "username": USERNAME, "password": PASSWORD, "display_name": "H5 Preview",
    })
    assert status == 201, (status, created)
    assert created["role"] == "customer"
    status, logged = call("POST", "/api/v1/auth/login", {
        "username": USERNAME, "password": PASSWORD,
    })
    assert status == 200, (status, logged)
    token = logged["access_token"]
    status, profile = call("GET", "/api/v1/auth/me", token=token)
    assert status == 200 and profile["id"] == created["id"]
    status, _ = call("GET", "/api/v1/events", token=token)
    assert status == 503, "Never allow mixed-token fallback into Legacy"
    status, _ = call("POST", "/api/v1/auth/logout", token=token)
    assert status == 204
    status, _ = call("GET", "/api/v1/auth/me", token=token)
    assert status == 401
    print("PASS: gateway Identity registration/login/me/logout, revoked token; commercial 503")


if __name__ == "__main__":
    main()
