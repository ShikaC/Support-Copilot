from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt


JAVA_CONTROLLERS = (
    "services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/"
    "ticket/TicketController.java",
    "services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/"
    "metrics/MetricsController.java",
    "services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/"
    "audit/AuditEventController.java",
    "services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/"
    "knowledge/KnowledgeController.java",
    "services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/"
    "knowledge/KnowledgeReleaseController.java",
    "services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/"
    "analysis/review/AnalysisReviewController.java",
)
FASTAPI_MAIN = "services/support-copilot-ai/app/main.py"
AI_CONFIG = "services/support-copilot-ai/app/config.py"
OPERATIONS_DOC = "docs/PILOT_OPERATIONS.md"
RELEASE_SURFACES = (
    "README.md",
    "docs/DEMO.md",
    OPERATIONS_DOC,
    "docs/PROJECT_BLUEPRINT.md",
    "docs/learning/V1_PROJECT_MAP.md",
)

JAVA_MAPPING = re.compile(
    r"@(Get|Post|Patch|Put|Delete)Mapping(?:\(\s*\"([^\"]*)\"\s*\))?"
)
REQUEST_MAPPING = re.compile(r'@RequestMapping\(\s*"([^"]+)"\s*\)')
FASTAPI_MAPPING = re.compile(
    r'@app\.(get|post|patch|put|delete)\(\s*"([^"]+)"', re.IGNORECASE
)
DOCUMENTED_API_ROW = re.compile(
    r"^\|\s*(GET|POST|PATCH|PUT|DELETE)\s*\|\s*`([^`]+)`\s*\|"
)

REQUIRED_BOUNDARIES = (
    "single-tenant",
    "synthetic/redacted data",
    "human approval",
    "non-production pilot",
)
FORBIDDEN_RELEASE_CLAIMS = (
    "production-ready",
    "生产就绪",
    "已在生产环境运行",
    "已完成多租户",
    "已通过真实 MySQL 验收",
    "已验证生产 SLO",
)
STALE_RELEASE_CLAIMS = (
    "当前 React 仍只支持匿名 demo 工作流",
    "React 登录/token adapter 尚未实现",
    "浏览器 JWT adapter 属于 Task 11",
    "尚未实现 JWT/OAuth2 和 RBAC",
    "OpenAI 实时模式尚未使用用户 API Key 完成外部调用验证",
)
REQUIRED_MODEL_SETTINGS = (
    "OPENAI_API_KEY",
    "OPENAI_EMBEDDING_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_EMBEDDING_BASE_URL",
    "OPENAI_CHAT_MODEL",
    "OPENAI_EMBEDDING_MODEL",
)


class DocumentationContractError(RuntimeError):
    pass


def tracked_markdown(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z", "--", "*.md"],
        check=True,
        capture_output=True,
    )
    return [repo_root / entry.decode() for entry in result.stdout.split(b"\0") if entry]


def markdown_targets(markdown: str) -> list[str]:
    targets: list[str] = []
    for token in MarkdownIt("commonmark").parse(markdown):
        children = token.children or []
        for child in children:
            if child.type == "link_open":
                href = child.attrGet("href")
                if href is not None:
                    targets.append(href)
            elif child.type == "image":
                src = child.attrGet("src")
                if src is not None:
                    targets.append(src)
    return targets


def validate_markdown_links(repo_root: Path, markdown_paths: list[Path]) -> list[str]:
    errors: list[str] = []
    for markdown_path in markdown_paths:
        relative_markdown = markdown_path.relative_to(repo_root)
        for target in markdown_targets(markdown_path.read_text(encoding="utf-8")):
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or (not parsed.path and parsed.fragment):
                continue
            decoded_path = unquote(parsed.path)
            if not decoded_path:
                continue
            if decoded_path.startswith("/"):
                errors.append(f"{relative_markdown}: repository link must be relative: {target}")
                continue
            resolved = (markdown_path.parent / decoded_path).resolve()
            try:
                resolved.relative_to(repo_root.resolve())
            except ValueError:
                errors.append(f"{relative_markdown}: link escapes repository: {target}")
                continue
            if not resolved.exists():
                errors.append(f"{relative_markdown}: missing local link target: {target}")
    return errors


def join_route(base: str, suffix: str) -> str:
    if not suffix:
        return base
    return f"{base.rstrip('/')}/{suffix.lstrip('/')}"


def java_routes(source: str) -> set[tuple[str, str]]:
    base_match = REQUEST_MAPPING.search(source)
    if base_match is None:
        raise DocumentationContractError("Java controller is missing @RequestMapping")
    base = base_match.group(1)
    return {
        (match.group(1).upper(), join_route(base, match.group(2) or ""))
        for match in JAVA_MAPPING.finditer(source)
    }


def fastapi_routes(source: str) -> set[tuple[str, str]]:
    return {
        (match.group(1).upper(), match.group(2))
        for match in FASTAPI_MAPPING.finditer(source)
    }


def source_api_routes(repo_root: Path) -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for controller in JAVA_CONTROLLERS:
        routes.update(java_routes((repo_root / controller).read_text(encoding="utf-8")))
    routes.update(fastapi_routes((repo_root / FASTAPI_MAIN).read_text(encoding="utf-8")))
    return routes


def documented_api_routes(operations_doc: str) -> set[tuple[str, str]]:
    return {
        (match.group(1), match.group(2))
        for line in operations_doc.splitlines()
        if (match := DOCUMENTED_API_ROW.match(line)) is not None
    }


def ai_modes(config_source: str) -> set[str]:
    tree = ast.parse(config_source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name) or node.target.id != "ai_mode":
            continue
        annotation = node.annotation
        if not isinstance(annotation, ast.Subscript):
            break
        if not isinstance(annotation.value, ast.Name) or annotation.value.id != "Literal":
            break
        slice_nodes = annotation.slice.elts if isinstance(annotation.slice, ast.Tuple) else [annotation.slice]
        values = {
            item.value
            for item in slice_nodes
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        }
        if values:
            return values
    raise DocumentationContractError("could not derive AI_MODE values from Settings.ai_mode")


def unsupported_release_claims(text: str) -> list[str]:
    claims = (*FORBIDDEN_RELEASE_CLAIMS, *STALE_RELEASE_CLAIMS)
    return [claim for claim in claims if claim in text]


def validate_release_contract(repo_root: Path) -> list[str]:
    errors: list[str] = []
    missing_surfaces = [path for path in RELEASE_SURFACES if not (repo_root / path).is_file()]
    errors.extend(f"missing required release document: {path}" for path in missing_surfaces)
    if missing_surfaces:
        return errors

    surfaces = {
        path: (repo_root / path).read_text(encoding="utf-8") for path in RELEASE_SURFACES
    }
    combined = "\n".join(surfaces.values())
    operations = surfaces[OPERATIONS_DOC]

    for boundary in REQUIRED_BOUNDARIES:
        if boundary not in operations:
            errors.append(f"{OPERATIONS_DOC}: missing capability boundary: {boundary}")
    for claim in unsupported_release_claims(combined):
        errors.append(f"release surfaces contain unsupported or stale claim: {claim}")

    actual_routes = source_api_routes(repo_root)
    documented_routes = documented_api_routes(operations)
    for method, route in sorted(actual_routes - documented_routes):
        errors.append(f"{OPERATIONS_DOC}: missing API route: {method} {route}")
    for method, route in sorted(documented_routes - actual_routes):
        errors.append(f"{OPERATIONS_DOC}: documents unknown API route: {method} {route}")

    profile_dir = repo_root / "services/support-copilot-api/src/main/resources"
    profiles = {
        path.stem.removeprefix("application-")
        for path in profile_dir.glob("application-*.properties")
    }
    expected_profile_statement = "Runtime profiles: `demo`, `test`, `local`, `pilot`."
    if profiles != {"demo", "test", "local", "pilot"}:
        errors.append(f"unexpected runtime profile set in code: {sorted(profiles)}")
    if expected_profile_statement not in operations:
        errors.append(f"{OPERATIONS_DOC}: missing exact runtime profile statement")

    config_source = (repo_root / AI_CONFIG).read_text(encoding="utf-8")
    modes = ai_modes(config_source)
    expected_mode_statement = "Configured AI_MODE values: `mock`, `live`, `auto`."
    if modes != {"mock", "live", "auto"}:
        errors.append(f"unexpected AI_MODE set in code: {sorted(modes)}")
    if expected_mode_statement not in operations:
        errors.append(f"{OPERATIONS_DOC}: missing exact AI_MODE statement")
    if "`fallback` is an analysis result mode, not an `AI_MODE` configuration value." not in operations:
        errors.append(f"{OPERATIONS_DOC}: missing fallback/configuration boundary")

    normalized_config = config_source.upper()
    for setting in REQUIRED_MODEL_SETTINGS:
        if setting not in normalized_config:
            errors.append(f"{AI_CONFIG}: missing expected model setting: {setting}")
        if setting not in operations:
            errors.append(f"{OPERATIONS_DOC}: missing model setting: {setting}")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Support Copilot release documentation")
    parser.add_argument("--repo-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    errors = validate_markdown_links(repo_root, tracked_markdown(repo_root))
    errors.extend(validate_release_contract(repo_root))
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        print(f"Documentation verification failed with {len(errors)} issue(s).", file=sys.stderr)
        return 1
    print("Documentation contracts passed: links, APIs, profiles, models, and boundaries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
