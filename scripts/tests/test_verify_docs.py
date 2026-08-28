from pathlib import Path

from scripts.verify_docs import (
    documented_api_routes,
    fastapi_routes,
    java_routes,
    unsupported_release_claims,
    validate_markdown_links,
)


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


def test_java_and_fastapi_route_extraction_preserves_method_and_path() -> None:
    java_source = '''
@RequestMapping("/api/items")
class ItemController {
    @GetMapping
    void list() {}
    @PostMapping("/{itemId}/publish")
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
