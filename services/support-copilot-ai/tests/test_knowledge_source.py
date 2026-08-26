import json
from pathlib import Path

import pytest

from app.config import Settings
from app.knowledge import KnowledgeRetriever
from app.knowledge_source import KnowledgeSourceInvalidError


def test_duplicate_chunk_ids_are_rejected(tmp_path: Path) -> None:
    # Given: an external source with two records that claim the same stable ID.
    knowledge_path = tmp_path / "duplicate-knowledge.json"
    chunk = {
        "chunk_id": "duplicate-id",
        "document_id": "external-guide",
        "document_title": "External guide",
        "section": "Login",
        "content": "Escalate the login incident.",
        "source_uri": "https://support.example.test/login",
        "categories": ["ACCOUNT_ACCESS"],
        "keywords": ["login"],
        "document_version": "2026.08",
        "status": "PUBLISHED",
        "updated_at": "2026-08-24",
    }
    knowledge_path.write_text(json.dumps([chunk, chunk]), encoding="utf-8")

    # When / Then: the trust boundary rejects ambiguous evidence identifiers.
    with pytest.raises(
        KnowledgeSourceInvalidError,
        match="Knowledge source is invalid",
    ) as exc_info:
        KnowledgeRetriever(Settings(ai_mode="mock", knowledge_path=knowledge_path))
    assert exc_info.value.__cause__ is None
