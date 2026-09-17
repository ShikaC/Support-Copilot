"""Static production-image contracts for the Task 15 container definitions."""

import re
from pathlib import Path
from typing import Final

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE_PATHS = (
    REPOSITORY_ROOT / "services/support-copilot-api/Dockerfile",
    REPOSITORY_ROOT / "services/support-copilot-ai/Dockerfile",
    REPOSITORY_ROOT / "apps/support-copilot-web/Dockerfile",
)
DIGEST_PIN = re.compile(r"^FROM\s+[^\s@]+:[^\s@]+@sha256:[a-f0-9]{64}", re.MULTILINE)
PYTHON_RUNTIME_BASE: Final = (
    "python:3.11.16-alpine3.24@sha256:"
    "cc19a3e1085aba7d26690cf0725d9a3e083cbea0feec34ba8133d40a8ac1d399"
)
NGINX_RUNTIME_BASE: Final = (
    "nginxinc/nginx-unprivileged:1.30.3-alpine-slim@sha256:"
    "3b24c4bfb2b9f60359b1475605ca1c8ed6e4963eb8369c6835be4d96bdb3ea81"
)


def read_repository_file(relative_path: str) -> str:
    """Return a required repository file as UTF-8 text."""
    return (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")


def test_image_bases_when_checked_then_are_digest_pinned() -> None:
    """Given production Dockerfiles, when parsed, then every base is immutable."""
    for dockerfile_path in DOCKERFILE_PATHS:
        dockerfile = dockerfile_path.read_text(encoding="utf-8")
        from_lines = [line for line in dockerfile.splitlines() if line.startswith("FROM ")]
        assert from_lines
        assert all(DIGEST_PIN.match(line) for line in from_lines)
        assert "latest" not in dockerfile.lower()


def test_api_image_when_built_then_uses_canonical_knowledge_and_non_root_runtime() -> None:
    """Given the API image, when built, then it carries the shared corpus safely."""
    dockerfile = read_repository_file("services/support-copilot-api/Dockerfile")

    assert dockerfile.count("FROM ") >= 2
    assert "services/support-copilot-ai/app/data/knowledge.json" in dockerfile
    assert "SUPPORT_COPILOT_KNOWLEDGE_CORPUS_PATH" in dockerfile
    assert re.search(r"^USER\s+(?!root\b)\S+", dockerfile, re.MULTILINE)
    assert "EXPOSE 8080" in dockerfile


def test_ai_image_when_built_then_installs_hash_locked_dependencies_and_serves_health() -> None:
    """Given the AI image, when built, then it preserves dependency and health contracts."""
    dockerfile = read_repository_file("services/support-copilot-ai/Dockerfile")

    assert "requirements.lock.txt" in dockerfile
    assert "--require-hashes" in dockerfile
    assert "uvicorn" in dockerfile
    assert "app.main:app" in dockerfile
    assert "EXPOSE 8000" in dockerfile
    assert re.search(r"^USER\s+(?!root\b)\S+", dockerfile, re.MULTILINE)
    assert ".env" not in dockerfile


def test_ai_image_when_checked_then_uses_current_python_base_in_both_stages() -> None:
    """Given the AI image, when parsed, then both stages share the exact Alpine base."""
    dockerfile = read_repository_file("services/support-copilot-ai/Dockerfile")
    from_images = [
        line.split()[1]
        for line in dockerfile.splitlines()
        if line.startswith("FROM python:")
    ]

    assert from_images == [PYTHON_RUNTIME_BASE, PYTHON_RUNTIME_BASE]


def test_ai_image_when_checked_then_hardens_only_the_runtime_before_application_copy() -> None:
    """Given the AI image, when hardened, then build tools stay out of runtime."""
    dockerfile = read_repository_file("services/support-copilot-ai/Dockerfile")
    _, build_stage, runtime_stage = dockerfile.split(f"FROM {PYTHON_RUNTIME_BASE}")

    assert "RUN apk add --no-cache setpriv=2.42.3-r1" in runtime_stage
    assert re.search(r"\bapk\s+(?:update|upgrade)\b", runtime_stage) is None
    assert "python -m pip uninstall --yes pip setuptools" in runtime_stage
    assert runtime_stage.index("RUN apk add") < runtime_stage.index("COPY --from=build")
    assert "python -m pip uninstall --yes pip setuptools" not in build_stage
    assert re.search(r"^USER\s+10001:10001$", runtime_stage, re.MULTILINE)


def test_ai_image_when_checked_then_declares_owned_artifact_volume() -> None:
    """Given the AI image policy, when parsed, then persistent state has one mount contract."""
    dockerfile = read_repository_file("services/support-copilot-ai/Dockerfile")
    _, _, runtime_stage = dockerfile.split(f"FROM {PYTHON_RUNTIME_BASE}")

    assert "/var/lib/support-copilot-ai" in dockerfile
    assert "EMBEDDING_ARTIFACT_ROOT=/var/lib/support-copilot-ai" in dockerfile
    assert "EMBEDDING_ARTIFACT_BUILD_POLICY=require-active" in dockerfile
    assert "addgroup -g 10001 appuser" in runtime_stage
    assert "adduser -D -H -s /sbin/nologin -u 10001 -G appuser appuser" in runtime_stage
    assert "mkdir -p /var/lib/support-copilot-ai" in runtime_stage
    assert "chown appuser:appuser /var/lib/support-copilot-ai" in runtime_stage
    assert "chmod 0750 /var/lib/support-copilot-ai" in runtime_stage
    assert re.search(r"^VOLUME\s+\[\"/var/lib/support-copilot-ai\"\]", dockerfile, re.MULTILINE)
    assert re.search(r"^USER\s+10001:10001$", dockerfile, re.MULTILINE)


def test_web_gateway_when_checked_then_serves_8080_health_spa_and_api_proxy() -> None:
    """Given the web gateway, when configured, then it exposes the browser contract."""
    dockerfile = read_repository_file("apps/support-copilot-web/Dockerfile")
    nginx_config = read_repository_file("apps/support-copilot-web/nginx.conf")

    assert dockerfile.count("FROM ") >= 2
    assert "npm ci" in dockerfile
    assert "nginxinc/nginx-unprivileged" in dockerfile
    assert "listen 8080" in nginx_config
    assert "location = /health" in nginx_config
    assert "try_files $uri $uri/ /index.html" in nginx_config
    assert "proxy_pass http://api:8080" in nginx_config


def test_web_gateway_when_checked_then_uses_current_nginx_runtime_base() -> None:
    """Given the web image, when parsed, then runtime uses the exact amd64 base."""
    dockerfile = read_repository_file("apps/support-copilot-web/Dockerfile")
    from_images = [
        line.split()[1]
        for line in dockerfile.splitlines()
        if line.startswith("FROM ")
    ]

    assert from_images[-1] == NGINX_RUNTIME_BASE


def test_web_gateway_when_checked_then_updates_only_runtime_packages_as_root() -> None:
    """Given the web image, when hardened, then package updates retain the unprivileged user."""
    dockerfile = read_repository_file("apps/support-copilot-web/Dockerfile")
    _, runtime_stage = dockerfile.split(f"FROM {NGINX_RUNTIME_BASE}")

    assert "USER root\nRUN apk upgrade --no-cache\nUSER 101\n\nCOPY" in runtime_stage
    assert runtime_stage.index("RUN apk upgrade --no-cache") < runtime_stage.index("COPY --from=build")
    assert runtime_stage.count("USER root") == 1
    assert runtime_stage.count("USER 101") == 1


def test_build_context_when_checked_then_excludes_secrets_and_generated_caches() -> None:
    """Given the repository context, when sent to Docker, then local-only data stays out."""
    dockerignore = read_repository_file(".dockerignore")

    for required_pattern in (".env", "**/node_modules", "**/.venv", "**/.gradle", ".git"):
        assert required_pattern in dockerignore
