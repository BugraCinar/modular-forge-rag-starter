import ast
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from forge_rag.app import create_app
from forge_rag.chunking.character import CharacterChunker
from forge_rag.shared.errors import InvalidDocument
from forge_rag.shared.models import Section
from tests.conftest import auth


def test_disabled_modules_remove_routes(settings, account):
    settings.module_ingestion_enabled = False
    settings.module_api_docs_enabled = False
    settings.module_telemetry_enabled = False
    app = create_app(settings)
    assert app.state.rag.ingestion is None and app.state.rag.worker is None
    with TestClient(app) as client:
        assert client.post("/v1/documents", headers=auth(account), json={}).status_code == 404
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        modules = {
            module["id"]: module
            for module in client.get("/v1/modules", headers=auth(account)).json()
        }
        assert not modules["ingestion"]["enabled"] and not modules["api-docs"]["enabled"]


def test_optional_packages_are_not_loaded():
    code = """
from forge_rag.evaluation.runner import fixture
import sys
runtime, _ = fixture()
assert 'pypdf' not in sys.modules
assert 'pgvector' not in sys.modules
assert 'forge_rag.providers.openai' not in sys.modules
assert 'forge_rag.providers.ollama' not in sys.modules
assert 'forge_rag.reranking.lexical' not in sys.modules
runtime.close()
"""
    env = {**os.environ, "PYTHONPATH": str(Path("src").resolve())}
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_core_depends_on_ports_not_provider_classes():
    for package in ("retrieval", "ingestion", "security", "shared"):
        for path in (Path("src/forge_rag") / package).glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom):
                    assert not (node.module or "").startswith(
                        ("forge_rag.providers", "forge_rag.pdf", "forge_rag.reranking")
                    ), path


def test_chunks_preserve_unicode_page_offsets_and_bound_size():
    text = "Türkçe içerik ve kaynak. " * 50
    pieces = CharacterChunker(250, 30, 100).split([Section(text, 7)])
    assert len(pieces) > 1
    assert all(
        len(piece.text) <= 250 and piece.text == text[piece.start : piece.end] and piece.page == 7
        for piece in pieces
    )
    assert all(left.end > right.start for left, right in zip(pieces, pieces[1:], strict=False))
    assert pieces[-1].end == len(text)


def test_chunk_limit():
    import pytest

    with pytest.raises(InvalidDocument):
        CharacterChunker(200, 20, 1).split([Section("abc " * 300)])
