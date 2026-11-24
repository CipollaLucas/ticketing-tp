"""Import boundary regression: domain/application cannot pull in frameworks."""
import ast
from pathlib import Path


def test_hexagonal_boundaries():
    root = Path(__file__).resolve().parents[1] / "events_service"
    for name in ("domain.py", "application.py", "drafts.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
        assert not any(
            module.startswith(("fastapi", "pydantic", "sqlalchemy", "alembic", "app."))
            for module in modules
        )
