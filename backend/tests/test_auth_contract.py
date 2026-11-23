from fastapi.testclient import TestClient

from app.main import app


def test_protected_endpoint_rejects_missing_credentials():
    response = TestClient(app).get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
