"""Complementary source contract for the AI service container image."""

from pathlib import Path
from typing import Final

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
AI_DOCKERFILE: Final = REPOSITORY_ROOT / "services/support-copilot-ai/Dockerfile"
PYTHON_ALPINE_BASE: Final = (
    "python:3.11.16-alpine3.24@sha256:"
    "cc19a3e1085aba7d26690cf0725d9a3e083cbea0feec34ba8133d40a8ac1d399"
)
UV_IMAGE: Final = (
    "ghcr.io/astral-sh/uv:0.10.8@sha256:"
    "88234bc9e09c2b2f6d176a3daf411419eb0370d450a08129257410de9cfafd2a"
)


def test_ai_image_when_parsed_then_has_the_exact_pinned_build_sequence() -> None:
    dockerfile_lines = AI_DOCKERFILE.read_text(encoding="utf-8").splitlines()

    from_images = [line.removeprefix("FROM ") for line in dockerfile_lines if line.startswith("FROM ")]

    assert from_images == [f"{UV_IMAGE} AS uv", f"{PYTHON_ALPINE_BASE} AS build", PYTHON_ALPINE_BASE]


def test_ai_image_when_building_then_uv_syncs_the_hashed_lockfile() -> None:
    dockerfile = AI_DOCKERFILE.read_text(encoding="utf-8")

    assert "COPY --from=uv /uv /uvx /bin/" in dockerfile
    assert "uv venv --python python3 /opt/venv" in dockerfile
    assert "uv pip sync --python /opt/venv/bin/python --require-hashes requirements.lock.txt" in dockerfile
