"""Structural guard: no frameworks inside Identity domain/application."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "identity"
FORBIDDEN = (
    "fastapi", "pydantic", "sqlalchemy", "psycopg", "httpx", "requests",
    "identity.adapters", "identity.database", "identity.settings",
    "app", "backend",
)


def test_domain_and_application_do_not_import_infrastructure():
    for layer in ("domain", "application"):
        files = sorted((ROOT / layer).rglob("*.py"))
        assert files
        for file in files:
            tree = ast.parse(file.read_text(encoding="utf-8"))
            modules = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules.append(node.module)
            for module in modules:
                assert not any(
                    module == name or module.startswith(name + ".")
                    for name in FORBIDDEN
                ), f"{file}: forbidden dependency {module}"


def test_service_has_no_legacy_backend_dependency():
    for source in (ROOT).rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not any(module == "app" or module.startswith("app.") for module in imports)
