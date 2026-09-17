import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.markdown_contracts import validate_markdown_links
from scripts.source_contracts import (
    FASTAPI_MAIN,
    JAVA_CONTROLLER_ROOT,
    DocumentationContractError,
    documented_api_routes,
    documented_verification_commands,
    fastapi_routes,
    java_routes,
    settings_environment_names,
    source_api_routes,
)
from scripts.verify_docs import (
    AI_CONFIG,
    OPERATIONS_DOC,
    RELEASE_SURFACES,
    VERIFIER_SCRIPT,
    unsupported_release_claims,
    validate_release_contract,
)


def copy_release_fixture(destination: Path) -> None:
    source_root = Path(__file__).resolve().parents[2]
    paths = [
        *(source_root / path for path in RELEASE_SURFACES),
        source_root / AI_CONFIG,
        source_root / "services/support-copilot-ai/.env.example",
        source_root / FASTAPI_MAIN,
        source_root / VERIFIER_SCRIPT,
        *(source_root / JAVA_CONTROLLER_ROOT).rglob("*Controller.java"),
        *(source_root / "services/support-copilot-api/src/main/resources").glob(
            "application-*.properties"
        ),
    ]
    for source in paths:
        target = destination / source.relative_to(source_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def test_markdown_links_accept_existing_targets_and_reject_missing_targets(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    target = docs / "target.md"
    target.write_text("# Target\n", encoding="utf-8")
    source = docs / "source.md"
    source.write_text(
        "[valid](target.md#target)\n[external](https://example.com)\n[missing](missing.md)\n",
        encoding="utf-8",
    )

    assert validate_markdown_links(tmp_path, [source]) == [
        "docs/source.md: missing local link target: missing.md"
    ]


def test_markdown_links_reject_missing_markdown_anchors(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    target = docs / "target.md"
    target.write_text("# Existing heading\n", encoding="utf-8")
    source = docs / "source.md"
    source.write_text("[missing](target.md#missing-heading)\n", encoding="utf-8")

    assert validate_markdown_links(tmp_path, [source]) == [
        "docs/source.md: missing local anchor: target.md#missing-heading"
    ]


def test_markdown_links_allow_ignored_local_evidence(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text("evidence/**/*.json\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    source = docs / "source.md"
    source.write_text(
        "[local](../evidence/run/trials.json)\n[missing](../evidence/run/other.txt)\n",
        encoding="utf-8",
    )

    assert validate_markdown_links(tmp_path, [source]) == [
        "docs/source.md: missing local link target: ../evidence/run/other.txt"
    ]


def test_markdown_links_reject_missing_targets_outside_a_git_repository(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    source = docs / "source.md"
    source.write_text("[missing](artifacts.json)\n", encoding="utf-8")

    assert validate_markdown_links(tmp_path, [source]) == [
        "docs/source.md: missing local link target: artifacts.json"
    ]


def test_java_and_fastapi_route_extraction_preserves_method_and_path() -> None:
    java_source = '''
@RequestMapping(path = "/api/items")
class ItemController {
    @GetMapping
    void list() {}
    @PostMapping(path = "/{itemId}/publish")
    void publish() {}
}
'''
    python_source = '''
@app.get("/health")
def health(): ...
@app.post("/analyze", response_model=Response)
def analyze(): ...
'''

    assert java_routes(java_source) == {
        ("GET", "/api/items"),
        ("POST", "/api/items/{itemId}/publish"),
    }
    assert fastapi_routes(python_source) == {
        ("GET", "/health"),
        ("POST", "/analyze"),
    }


def test_java_route_extraction_fails_closed_for_nonliteral_paths() -> None:
    source = '''
@RequestMapping("/api/items")
class ItemController {
    @GetMapping(path = ITEM_PATH)
    void item() {}
}
'''

    with pytest.raises(DocumentationContractError, match="non-literal mapping path"):
        java_routes(source)


def test_source_routes_discovers_new_controllers(tmp_path: Path) -> None:
    controllers = (
        tmp_path
        / "services/support-copilot-api/src/main/java/com/example"
    )
    controllers.mkdir(parents=True)
    (controllers / "FirstController.java").write_text(
        '''
@RequestMapping("/api/first")
class FirstController {
    @GetMapping
    void list() {}
}
''',
        encoding="utf-8",
    )
    (controllers / "SecondController.java").write_text(
        '''
@RequestMapping(value = "/api/second")
class SecondController {
    @PostMapping(path = "/{id}")
    void update() {}
}
''',
        encoding="utf-8",
    )
    fastapi = tmp_path / "services/support-copilot-ai/app/main.py"
    fastapi.parent.mkdir(parents=True)
    fastapi.write_text('@app.get("/health")\ndef health(): ...\n', encoding="utf-8")

    assert source_api_routes(tmp_path) == {
        ("GET", "/api/first"),
        ("POST", "/api/second/{id}"),
        ("GET", "/health"),
    }


def test_documented_api_table_ignores_non_api_tables() -> None:
    markdown = '''
| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness |
| POST | `/analyze` | Analyze |

| Mode | Meaning |
| --- | --- |
| mock | local |
'''

    assert documented_api_routes(markdown) == {
        ("GET", "/health"),
        ("POST", "/analyze"),
    }


def test_unsupported_and_stale_release_claims_fail_closed() -> None:
    assert unsupported_release_claims(
        "系统已经 production-ready，且 React 登录/token adapter 尚未实现。"
    ) == ["production-ready", "React 登录/token adapter 尚未实现"]


def test_settings_environment_names_come_from_fields_not_comments() -> None:
    source = '''
# OPENAI_EMBEDDING_MODEL is only a comment.
class Settings:
    openai_api_key: str | None = None
    openai_chat_model: str | None = None
'''

    assert settings_environment_names(source) == {
        "OPENAI_API_KEY",
        "OPENAI_CHAT_MODEL",
    }


def test_release_contract_rejects_missing_chat_protocol_template_setting(
    tmp_path: Path,
) -> None:
    # Given: an otherwise current fixture whose config template lost the protocol.
    copy_release_fixture(tmp_path)
    template_path = tmp_path / "services/support-copilot-ai/.env.example"
    template_path.write_text(
        template_path.read_text(encoding="utf-8").replace(
            "OPENAI_CHAT_PROTOCOL=responses\n", ""
        ),
        encoding="utf-8",
    )

    # When: the release contract is checked.
    errors = validate_release_contract(tmp_path)

    # Then: template drift fails closed.
    assert (
        "services/support-copilot-ai/.env.example: missing model setting: "
        "OPENAI_CHAT_PROTOCOL"
    ) in errors


def test_verify_docs_unsets_chat_protocol() -> None:
    # Given: the clean-fixture verifier launcher.
    repo_root = Path(__file__).resolve().parents[2]

    # When: the environment-cleaning block is isolated.
    unset_block = (repo_root / VERIFIER_SCRIPT).read_text(encoding="utf-8").split(
        "unset AI_MODE", maxsplit=1
    )[1].split(
        'fixture_root="$(mktemp', maxsplit=1
    )[0]

    # Then: local protocol configuration cannot leak into verification.
    assert "OPENAI_CHAT_PROTOCOL" in unset_block


def test_documented_verification_commands_parse_only_contract_rows() -> None:
    markdown = '''
| Verification ID | Executed command |
| --- | --- |
| verify-python-tests | `cd services/support-copilot-ai && .venv/bin/pytest -q` |

```bash
echo "not part of the command contract"
```
'''

    assert documented_verification_commands(markdown) == {
        "verify-python-tests": "cd services/support-copilot-ai && .venv/bin/pytest -q"
    }


def test_release_contract_checks_frontend_and_roadmap_claims(tmp_path: Path) -> None:
    copy_release_fixture(tmp_path)
    assert validate_release_contract(tmp_path) == []

    roadmap = tmp_path / "docs/optimizations/ROADMAP.md"
    roadmap.write_text(
        roadmap.read_text(encoding="utf-8") + "\nproduction-ready\n",
        encoding="utf-8",
    )

    assert "release surfaces contain unsupported or stale claim: production-ready" in (
        validate_release_contract(tmp_path)
    )


def test_release_contract_rejects_missing_documented_command(tmp_path: Path) -> None:
    copy_release_fixture(tmp_path)
    operations = tmp_path / OPERATIONS_DOC
    row = "| verify-react-e2e | `cd apps/support-copilot-web && npm run test:e2e` |\n"
    operations.write_text(
        operations.read_text(encoding="utf-8").replace(row, ""), encoding="utf-8"
    )

    assert f"{OPERATIONS_DOC}: missing verification command: verify-react-e2e" in (
        validate_release_contract(tmp_path)
    )


def test_release_contract_rejects_unmapped_executed_command(tmp_path: Path) -> None:
    copy_release_fixture(tmp_path)
    verifier = tmp_path / VERIFIER_SCRIPT
    verifier.write_text(
        verifier.read_text(encoding="utf-8").replace(
            "run_documented_gate verify-react-e2e",
            "run_gate verify-react-e2e",
        ),
        encoding="utf-8",
    )

    assert f"{VERIFIER_SCRIPT}: verification command is not executed: verify-react-e2e" in (
        validate_release_contract(tmp_path)
    )
