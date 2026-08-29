from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Final

from scripts.markdown_contracts import tracked_markdown, validate_markdown_links
from scripts.source_contracts import (
    ai_modes,
    documented_api_routes,
    documented_verification_commands,
    executed_verification_ids,
    settings_environment_names,
    source_api_routes,
)


AI_CONFIG = "services/support-copilot-ai/app/config.py"
AI_CONFIG_TEMPLATE = "services/support-copilot-ai/.env.example"
VERIFIER_SCRIPT = "scripts/verify-docs.sh"
OPERATIONS_DOC = "docs/PILOT_OPERATIONS.md"
RELEASE_SURFACES = (
    "README.md",
    "apps/support-copilot-web/README.md",
    "docs/DEMO.md",
    OPERATIONS_DOC,
    "docs/PROJECT_BLUEPRINT.md",
    "docs/learning/LIVE_RAG_COMPLETION_CRITERIA.md",
    "docs/learning/V1_PROJECT_MAP.md",
    "docs/optimizations/ROADMAP.md",
    "services/support-copilot-ai/evaluation/README.md",
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
    "OPENAI_CHAT_PROTOCOL",
    "OPENAI_EMBEDDING_MODEL",
)
REQUIRED_LIVE_EVIDENCE_BOUNDARIES: Final = (
    ("README.md", "responses-dataset-failures", ("`be9ac60`", "Responses 协议 4-case", "1 case live success、3 case `invalid_model_response` fallback", "b8560190583fc2888f2428353ffcb43caac6cbc3", "Responses 协议受限运行", "1 live success / 3 `invalid_model_response` fallback", "两次都是明确失败的历史 dataset evidence")),
    ("README.md", "human-review-incomplete", ("b8560190583fc2888f2428353ffcb43caac6cbc3", "机器门禁失败", "0/4 `NOT_REVIEWED`", "明确失败")),
    ("README.md", "fresh-chat-completions-evidence-required", ("Chat Completions relay", "1 次 chat 调用、0 次 Embedding", "7.437 秒", "不是完整 RAG", "仍需在干净提交上重新运行完整 Chat Completions live dataset", "完成真实人工标签")),
    ("docs/learning/LIVE_RAG_COMPLETION_CRITERIA.md", "historical-responses-e2e", ("59903a1e5fad74cf2b792263f735dafe36b8066c", "Responses 协议", "正式 Embedding", "均成功")),
    ("docs/learning/LIVE_RAG_COMPLETION_CRITERIA.md", "current-live-evidence-boundary", ("`be9ac60`", "Responses 数据集", "1 个 live success 和 3 个 `invalid_model_response` fallback", "`b856019`", "Responses 受限运行", "机器 gate 失败", "0/4", "明确失败的历史 dataset evidence", "Chat Completions relay", "无 Embedding", "不是 RAG", "完整 Chat Completions dataset", "人审仍待完成")),
    ("docs/learning/V1_PROJECT_MAP.md", "project-map-live-evidence-boundary", ("59903a1e5fad74cf2b792263f735dafe36b8066c", "Responses 路径的一次端到端成功", "`be9ac60`", "`b856019`", "Responses 数据集", "1 success + 3 fallback、0/4 人审失败记录", "Chat Completions relay", "没有 Embedding", "完整干净提交 dataset 与人工 groundedness 仍未完成")),
    ("docs/optimizations/ROADMAP.md", "roadmap-live-evidence-boundary", ("`be9ac60`", "`b856019`", "Responses 协议 dataset 失败", "1 live success + 3 `invalid_model_response` fallbacks", "0/4 human reviewed", "59903a1e5fad74cf2b792263f735dafe36b8066c", "Responses 单次端到端层级 3 证据", "Chat Completions relay", "无 Embedding", "不是 RAG、dataset、publishable", "完整干净提交 Chat Completions dataset 和人工 groundedness 仍阻塞")),
    ("services/support-copilot-ai/evaluation/README.md", "evaluation-live-evidence-boundary", ("59903a1e5fad74cf2b792263f735dafe36b8066c", "Responses 路径的一次端到端成功", "`be9ac60`", "`b856019`", "Responses 4-case dataset 失败", "1 success + 3 `invalid_model_response` fallbacks", "0/4", "Chat Completions relay", "无 Embedding", "不能算 RAG、dataset 或 publishable success", "仍需干净提交上的完整 dataset 与人工 groundedness")),
)
REQUIRED_DOCUMENTED_COMMANDS = {
    "verify-python-tests": "cd services/support-copilot-ai && .venv/bin/pytest -q",
    "verify-mock-evaluation": (
        "cd services/support-copilot-ai && "
        "AI_MODE=mock .venv/bin/python -m evaluation.run_mock_evaluation"
    ),
    "verify-java-tests": "cd services/support-copilot-api && ./gradlew test --no-daemon",
    "verify-react-lint": "cd apps/support-copilot-web && npm run lint",
    "verify-react-tests": "cd apps/support-copilot-web && npm test -- --run",
    "verify-react-build-budget": "cd apps/support-copilot-web && npm run build:budget",
    "verify-react-node-contracts": "cd apps/support-copilot-web && npm run test:node",
    "verify-react-e2e": "cd apps/support-copilot-web && npm run test:e2e",
    "verify-preflight": "./scripts/check-local-startup.sh --preflight",
    "verify-smoke": "./scripts/run-local-smoke.sh",
}


def unsupported_release_claims(text: str) -> list[str]:
    claims = (*FORBIDDEN_RELEASE_CLAIMS, *STALE_RELEASE_CLAIMS)
    return [claim for claim in claims if claim in text]


def contains_ordered_line_fragments(text: str, fragments: tuple[str, ...]) -> bool:
    pattern = r"^[^\n]*" + r"[^\n]*".join(re.escape(fragment) for fragment in fragments)
    return re.search(pattern + r"[^\n]*$", text, re.MULTILINE) is not None


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
    readme = surfaces["README.md"]

    for boundary in REQUIRED_BOUNDARIES:
        if boundary not in operations:
            errors.append(f"{OPERATIONS_DOC}: missing capability boundary: {boundary}")
    for claim in unsupported_release_claims(combined):
        errors.append(f"release surfaces contain unsupported or stale claim: {claim}")
    for path, boundary, fragments in REQUIRED_LIVE_EVIDENCE_BOUNDARIES:
        if not contains_ordered_line_fragments(surfaces[path], fragments):
            errors.append(
                f"{path}: missing canonical live evidence boundary: {boundary}"
            )

    actual_routes = source_api_routes(repo_root)
    documented_routes = documented_api_routes(operations)
    for method, route in sorted(actual_routes - documented_routes):
        errors.append(f"{OPERATIONS_DOC}: missing API route: {method} {route}")
    for method, route in sorted(documented_routes - actual_routes):
        errors.append(f"{OPERATIONS_DOC}: documents unknown API route: {method} {route}")

    documented_commands = documented_verification_commands(operations)
    for command_id, command in REQUIRED_DOCUMENTED_COMMANDS.items():
        if command_id not in documented_commands:
            errors.append(f"{OPERATIONS_DOC}: missing verification command: {command_id}")
        elif documented_commands[command_id] != command:
            errors.append(f"{OPERATIONS_DOC}: command drift: {command_id}")
    for command_id in sorted(documented_commands.keys() - REQUIRED_DOCUMENTED_COMMANDS.keys()):
        errors.append(f"{OPERATIONS_DOC}: unknown verification command: {command_id}")
    executed_commands = executed_verification_ids(
        (repo_root / VERIFIER_SCRIPT).read_text(encoding="utf-8")
    )
    for command_id in sorted(REQUIRED_DOCUMENTED_COMMANDS.keys() - executed_commands):
        errors.append(f"{VERIFIER_SCRIPT}: verification command is not executed: {command_id}")
    for command_id in sorted(executed_commands - REQUIRED_DOCUMENTED_COMMANDS.keys()):
        errors.append(f"{VERIFIER_SCRIPT}: executes unknown verification command: {command_id}")

    profile_dir = repo_root / "services/support-copilot-api/src/main/resources"
    profiles = {
        path.stem.removeprefix("application-")
        for path in profile_dir.glob("application-*.properties")
    }
    if profiles != {"demo", "test", "local", "pilot"}:
        errors.append(f"unexpected runtime profile set in code: {sorted(profiles)}")
    if "Runtime profiles: `demo`, `test`, `local`, `pilot`." not in operations:
        errors.append(f"{OPERATIONS_DOC}: missing exact runtime profile statement")

    config_source = (repo_root / AI_CONFIG).read_text(encoding="utf-8")
    modes = ai_modes(config_source)
    if modes != {"mock", "live", "auto"}:
        errors.append(f"unexpected AI_MODE set in code: {sorted(modes)}")
    if "Configured AI_MODE values: `mock`, `live`, `auto`." not in operations:
        errors.append(f"{OPERATIONS_DOC}: missing exact AI_MODE statement")
    fallback_statement = (
        "`fallback` is an analysis result mode, not an `AI_MODE` configuration value."
    )
    if fallback_statement not in operations:
        errors.append(f"{OPERATIONS_DOC}: missing fallback/configuration boundary")

    configured_environment_names = settings_environment_names(config_source)
    config_template = (repo_root / AI_CONFIG_TEMPLATE).read_text(encoding="utf-8")
    for setting in REQUIRED_MODEL_SETTINGS:
        if setting not in configured_environment_names:
            errors.append(f"{AI_CONFIG}: missing expected model setting: {setting}")
        if setting == "OPENAI_CHAT_PROTOCOL":
            if setting not in readme:
                errors.append(f"README.md: missing model setting: {setting}")
            if setting not in config_template:
                errors.append(f"{AI_CONFIG_TEMPLATE}: missing model setting: {setting}")
        elif setting not in operations:
            errors.append(f"{OPERATIONS_DOC}: missing model setting: {setting}")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Support Copilot release documentation")
    parser.add_argument("--repo-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    repo_root = parse_args().repo_root.resolve()
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
