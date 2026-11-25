"""Correlation, timing and secret-minimizing HTTP audit regression."""
import logging
import re

from fastapi.testclient import TestClient

from events_service.main import app


def test_request_id_status_duration_and_no_query_leak(caplog):
    with caplog.at_level(logging.INFO, logger="events.http"):
        with TestClient(app) as client:
            response = client.get(
                "/path-not-exposed?password=never-log-me",
                headers={"X-Request-ID": "h5-correlation-123", "Authorization": "Bearer secret"},
            )
    assert response.status_code == 404
    assert response.headers["x-request-id"] == "h5-correlation-123"
    lines = [record.message for record in caplog.records if record.name == "events.http"]
    assert len(lines) == 1
    entry = lines[0]
    assert "request_id=h5-correlation-123" in entry
    assert "method=GET" in entry
    assert "path=/path-not-exposed" in entry
    assert "status=404" in entry
    assert re.search(r"duration_ms=\d+\.\d{2}", entry)
    assert "never-log-me" not in entry
    assert "secret" not in entry
    assert "password" not in entry


def test_untrusted_request_id_replaced(caplog):
    with caplog.at_level(logging.INFO, logger="events.http"):
        with TestClient(app) as client:
            response = client.get(
                "/path-not-exposed", headers={"X-Request-ID": "not a safe id"}
            )
    assert response.status_code == 404
    correlation = response.headers["x-request-id"]
    assert re.fullmatch(r"[a-f0-9]{32}", correlation)
    assert any(
        f"request_id={correlation}" in record.message
        for record in caplog.records if record.name == "events.http"
    )
