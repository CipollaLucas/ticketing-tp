"""Static contract regression for the opt-in H5 Gateway (no running services needed)."""
from pathlib import Path
import re

CONF = Path(__file__).resolve().parents[1] / "gateway" / "three-service-preview.conf"


def main() -> None:
    contents = CONF.read_text(encoding="utf-8")
    assert "http://backend:" not in contents and "http://legacy" not in contents
    assert "location ^~ /api/v1/internal/" in contents
    assert "location ^~ /api/v1/auth/" in contents
    assert "location ^~ /api/v1/owner/events" in contents
    assert "location = /api/v1/events" in contents
    assert "location ^~ /api/v1/events/" in contents
    assert "Idempotency-Key $http_idempotency_key" in contents
    assert "request_time=$request_time" in contents
    assert "proxy_set_header Authorization $http_authorization;" in contents
    assert re.search(r"location ~ \^/api/v1/events/\[\^/\]\+/orders/\?\$\s*\{\s*proxy_pass http://h4-ticketing:8003;", contents)
    assert contents.index("location ~ ^/api/v1/events/") < contents.index("location ^~ /api/v1/events/")
    print("PASS: H5 preview routing declaration and fail-closed defaults")


if __name__ == "__main__":
    main()
