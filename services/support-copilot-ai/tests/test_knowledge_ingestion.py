import json
import subprocess
import sys
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.knowledge_ingestion import KnowledgeIngestionError, build_knowledge_corpus
from app.knowledge_source import load_knowledge_chunks


def _write_text_pdf(path: Path, text: str) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): font_reference}
            )
        }
    )
    content = DecodedStreamObject()
    content.set_data(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(content)
    with path.open("wb") as stream:
        writer.write(stream)


def test_ingestion_error_allows_runtime_traceback_assignment(tmp_path: Path) -> None:
    # Given: a structured error that must cross Python context-manager boundaries.
    error = KnowledgeIngestionError(path=tmp_path, reason="source-empty")

    # When: the runtime attaches traceback state while propagating the error.
    error.__traceback__ = None

    # Then: the original structured error remains available to the caller.
    assert error.reason == "source-empty"


def test_cli_builds_reproducible_corpus_from_markdown(tmp_path: Path) -> None:
    # Given: an authorized Markdown runbook and explicit operational metadata.
    source_path = tmp_path / "identity-runbook.md"
    source_path.write_text(
        "# Identity support\n\n## SSO incidents\n\n"
        "For SSO-42, record the tenant identifier and identity provider status.\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "knowledge-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "release_id": "support-kb-test",
                "release_version": 1,
                "chunking": {"chunk_size": 120, "chunk_overlap": 20},
                "documents": [
                    {
                        "path": source_path.name,
                        "document_id": "identity-runbook",
                        "document_title": "Identity support runbook",
                        "source_uri": "https://support.example.test/identity",
                        "categories": ["ACCOUNT_ACCESS"],
                        "keywords": ["SSO-42", "tenant identifier"],
                        "allowed_scopes": ["ACCOUNT"],
                        "document_version": "2026.08",
                        "status": "PUBLISHED",
                        "updated_at": "2026-08-24",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "authorized-knowledge.json"
    provenance_path = tmp_path / "authorized-knowledge.provenance.json"
    command = (
        sys.executable,
        "-m",
        "scripts.build_knowledge_corpus",
        "--manifest",
        str(manifest_path),
        "--output",
        str(output_path),
    )

    # When: the same source set is indexed twice.
    first = subprocess.run(command, capture_output=True, check=False, text=True)
    first_corpus = output_path.read_bytes() if output_path.exists() else b""
    first_provenance = provenance_path.read_bytes() if provenance_path.exists() else b""
    second = subprocess.run(command, capture_output=True, check=False, text=True)

    # Then: both runs succeed and produce an identical, loadable index.
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert output_path.read_bytes() == first_corpus
    assert provenance_path.read_bytes() == first_provenance
    chunks = load_knowledge_chunks(output_path)
    assert len(chunks) == 1
    assert chunks[0].document_id == "identity-runbook"
    assert chunks[0].section == "SSO incidents"
    assert chunks[0].allowed_scopes == ("ACCOUNT",)
    assert "SSO-42" in chunks[0].content
    provenance_text = provenance_path.read_text(encoding="utf-8")
    provenance = json.loads(provenance_text)
    corpus = json.loads(output_path.read_text(encoding="utf-8"))
    assert provenance["release_id"] == "support-kb-test"
    assert provenance["release_version"] == 1
    assert provenance["corpus_checksum"] == corpus["corpus_checksum"]
    assert provenance["documents"][0]["allowed_scopes"] == ["ACCOUNT"]
    assert "identity-runbook.md" in provenance_text
    assert "SSO-42" not in provenance_text


def test_builder_extracts_text_from_pdf_pages(tmp_path: Path) -> None:
    # Given: an authorized PDF with a real text layer.
    source_path = tmp_path / "incident-runbook.pdf"
    _write_text_pdf(source_path, "PDF-84 requires the proxy diagnostics bundle.")
    manifest_path = tmp_path / "knowledge-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "release_id": "support-kb-test",
                "release_version": 1,
                "chunking": {"chunk_size": 120, "chunk_overlap": 20},
                "documents": [
                    {
                        "path": source_path.name,
                        "document_id": "incident-runbook",
                        "document_title": "Incident support runbook",
                        "source_uri": "https://support.example.test/incidents",
                        "categories": ["TECHNICAL"],
                        "keywords": ["PDF-84", "proxy diagnostics"],
                        "allowed_scopes": ["TECHNICAL"],
                        "document_version": "2026.08",
                        "status": "PUBLISHED",
                        "updated_at": "2026-08-24",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "authorized-knowledge.json"

    # When: the PDF source is indexed.
    build_knowledge_corpus(manifest_path, output_path)

    # Then: page text becomes traceable RAG evidence.
    chunks = load_knowledge_chunks(output_path)
    assert len(chunks) == 1
    assert chunks[0].section == "Page 1"
    assert "PDF-84" in chunks[0].content
