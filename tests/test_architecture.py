"""Guardrails for the inference-only runtime boundary."""

from pathlib import Path

RUNTIME_ROOT = Path("app")


def runtime_source() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in RUNTIME_ROOT.rglob("*.py"))


def test_runtime_has_no_database_client_or_outbound_http_dependencies() -> None:
    source = runtime_source().lower()
    assert "supabase" not in source
    assert "create_client" not in source
    assert "httpx" not in source
    assert "requests." not in source
    assert "urlopen" not in source


def test_runtime_has_no_mcp_or_a2ui_knowledge() -> None:
    source = runtime_source().lower()
    assert "mcp" not in source
    assert "a2ui" not in source
    assert "visualization_hint" not in source


def test_runtime_dependency_list_excludes_database_clients() -> None:
    project = Path("pyproject.toml").read_text(encoding="utf-8").lower()
    assert '"supabase' not in project
