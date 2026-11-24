"""Architecture contract: no dependency from the domain into frameworks/adapters."""
import ast
from pathlib import Path

DOMAIN_ROOT = Path(__file__).resolve().parents[1] / "app" / "ticketing_core" / "domain"
FORBIDDEN = ("fastapi", "pydantic", "sqlalchemy", "psycopg", "httpx", "requests",
             "app.database", "app.models", "app.auth", "app.events",
             "app.purchasing", "app.inventory", "app.ticketing_core.adapters")


def test_ticketing_domain_has_no_infrastructure_dependencies():
    assert DOMAIN_ROOT.is_dir()
    modules = sorted(DOMAIN_ROOT.rglob("*.py"))
    assert modules
    for source in modules:
        code = ast.parse(source.read_text(encoding="utf-8"))
        imported = []
        for node in ast.walk(code):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        for dependency in imported:
            assert not any(
                dependency == blocked or dependency.startswith(blocked + ".")
                for blocked in FORBIDDEN
            ), f"{source.name} violates domain boundary with {dependency}"
