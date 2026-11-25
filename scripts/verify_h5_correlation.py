"""CI-only check of one H5 publish request across Gateway, Identity, Events, Ticketing."""
import re
import subprocess
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Expected: project-name smoke-log-path")
    project, smoke_path = sys.argv[1:]
    if not re.fullmatch(r"h5-[a-z0-9-]+", project):
        raise SystemExit("Refusing non-disposable Compose project")
    smoke = Path(smoke_path).read_text(encoding="utf-8")
    traces = re.findall(r"H5_PUBLISH_TRACE_ID=([a-f0-9]{32})", smoke)
    if len(traces) != 1:
        raise SystemExit("Exactly one H5 publish correlation ID is required")
    trace = traces[0]
    overlays = [
        "-f", "docker-compose.h3-contract.yml",
        "-f", "docker-compose.h4-live.yml",
        "-f", "docker-compose.h5-gateway-preview.yml",
    ]
    for service in ("h5-gateway", "h3-identity", "h3-events", "h4-ticketing"):
        result = subprocess.run(
            ["docker", "compose", "-p", project, *overlays, "logs",
             "--no-color", "--no-log-prefix", service],
            check=True,
            capture_output=True,
            text=True,
        )
        records = [
            line for line in result.stdout.splitlines()
            if "request_id=" + trace in line
        ]
        if not records:
            raise SystemExit(f"Missing end-to-end correlation in {service}")
        expected = (
            r"request_time=\d+\.\d+"
            if service == "h5-gateway"
            else r"duration_ms=\d+\.\d+"
        )
        if not any(re.search(expected, record) for record in records):
            raise SystemExit(f"No duration for correlation in {service}")
        print(f"PASS: {service} emits correlated request and duration")
    print("PASS: H5 publication correlated across four process logs")


if __name__ == "__main__":
    main()
