"""Hexagonal core cannot import frameworks or other service ORM."""
import ast
from pathlib import Path


def test_domain_and_application_have_no_infrastructure_imports():
    root = Path(__file__).resolve().parents[1] / "ticketing_service"
    forbidden = ("fastapi", "sqlalchemy", "pydantic", "identity", "events_service")
    for filename in ("domain.py", "application.py"):
        tree = ast.parse((root / filename).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(forbidden), (filename, node.module)
            if isinstance(node, ast.Import):
                for name in node.names:
                    assert not name.name.startswith(forbidden), (filename, name.name)
