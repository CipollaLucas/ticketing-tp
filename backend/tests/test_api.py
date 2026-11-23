from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_api_root():
    response = client.get("/api/v1")
    assert response.status_code == 200
    assert response.json()["stage"] == "bootstrap"
    assert response.headers["X-Request-ID"]


def test_health_ok():
    mock_engine = MagicMock()
    with patch("app.main.create_engine", return_value=mock_engine):
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
