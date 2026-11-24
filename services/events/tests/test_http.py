from fastapi.testclient import TestClient

from events_service.main import app, session_scope


def test_catalog_read_only_over_http():
    class EmptyDb:
        pass

    # The dependency must not access the configured database in this test.
    class EmptyRepo:
        def upcoming(self, now, limit, offset):
            return [], 0

    from events_service import main

    original = main.SqlAlchemyEventReader
    main.SqlAlchemyEventReader = lambda db: EmptyRepo()
    app.dependency_overrides[session_scope] = lambda: EmptyDb()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/events")
            assert response.status_code == 200
            assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}
            assert client.post("/api/v1/events", json={}).status_code == 405
            assert client.get("/api/v1/events?limit=0").status_code == 422
    finally:
        app.dependency_overrides.clear()
        main.SqlAlchemyEventReader = original
