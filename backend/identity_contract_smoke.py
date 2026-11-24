"""Integration smoke: real HTTP call from Ticketing container into Identity.

Uses a disposable, randomly named test account in the isolated Identity DB.
Never prints tokens, passwords or internal service credentials.
"""
import os
from secrets import token_urlsafe
from uuid import uuid4

import httpx

from app.ticketing_core.adapters.outbound.http_identity import HttpIdentityAdapter
from app.ticketing_core.application.identity import IdentityUnauthorized, authenticate_remote


def main() -> None:
    base_url = os.environ["IDENTITY_SERVICE_URL"].rstrip("/")
    internal_secret = os.environ["IDENTITY_INTERNAL_TOKEN"]
    username = "contract_" + uuid4().hex[:16]
    password = token_urlsafe(24)
    with httpx.Client(base_url=base_url, timeout=5, trust_env=False) as http:
        created = http.post("/api/v1/auth/register", json={
            "username": username, "display_name": "Contract Smoke",
            "password": password,
        })
        created.raise_for_status()
        logged_in = http.post("/api/v1/auth/login", json={
            "username": username, "password": password,
        })
        logged_in.raise_for_status()
        bearer = logged_in.json()["access_token"]
        adapter = HttpIdentityAdapter(base_url, internal_secret)
        principal = authenticate_remote(bearer, adapter, "identity-contract-smoke")
        assert principal.id.hex == created.json()["id"].replace("-", "")
        assert principal.role == "customer"
        assert principal.username == username
        assert http.post(
            "/api/v1/auth/logout", headers={"Authorization": f"Bearer {bearer}"}
        ).status_code == 204
        try:
            authenticate_remote(bearer, adapter, "identity-contract-smoke-revoked")
        except IdentityUnauthorized:
            pass
        else:
            raise AssertionError("Revoked token was accepted by Identity")
    print("PASS: Ticketing -> Identity HTTP contract, role, and logout revocation")


if __name__ == "__main__":
    main()
