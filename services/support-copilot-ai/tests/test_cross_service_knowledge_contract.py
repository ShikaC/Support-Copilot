from pathlib import Path

from app.knowledge_source import calculate_corpus_checksum, load_knowledge_corpus
from app.models import AnalyzeRequest, SupportScope


CONTRACT_FIXTURE_PATH = (
    Path(__file__).parents[2]
    / "support-copilot-api"
    / "src"
    / "test"
    / "resources"
    / "contracts"
    / "knowledge-access-request.json"
)
CORPUS_PATH = Path(__file__).parents[1] / "app" / "data" / "knowledge.json"


def test_java_request_fixture_matches_strict_loaded_python_release() -> None:
    request = AnalyzeRequest.model_validate_json(
        CONTRACT_FIXTURE_PATH.read_text(encoding="utf-8")
    )
    corpus = load_knowledge_corpus(CORPUS_PATH)

    assert request.knowledge_access.release_id == corpus.release_id
    assert request.knowledge_access.release_version == corpus.release_version
    assert request.knowledge_access.corpus_checksum == corpus.corpus_checksum
    assert corpus.corpus_checksum == calculate_corpus_checksum(corpus.chunks)
    assert request.knowledge_access.allowed_scopes == (SupportScope.BILLING,)
