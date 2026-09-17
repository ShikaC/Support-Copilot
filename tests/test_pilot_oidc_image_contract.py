"""Static contract for the test-only OIDC derived image."""

import json
import shlex
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE_PATH = REPOSITORY_ROOT / "infra" / "images" / "oidc" / "Dockerfile"
UPSTREAM_REFERENCE = (
    "ghcr.io/navikt/mock-oauth2-server:6.0.2@"
    "sha256:b538810afd589d42fbfb856c588c2065eaeed1dc528d6c532972048e67fc2aff"
)
RUNTIME_REFERENCE = (
    "cgr.dev/chainguard/jre@"
    "sha256:dbe71fe6d7de0b29342cd3dd693e713098088ddc3d2be904a721ffea905e1569"
)
EXPECTED_ENTRYPOINT = [
    "java",
    "--sun-misc-unsafe-memory-access=allow",
    "-cp",
    "@/app/jib-classpath-file",
    "no.nav.security.mock.oauth2.StandaloneMockOAuth2ServerKt",
]


def dockerfile_instructions() -> list[tuple[str, str]]:
    instructions: list[tuple[str, str]] = []
    for raw_line in DOCKERFILE_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        instruction, separator, value = line.partition(" ")
        assert separator, f"invalid Dockerfile instruction: {line}"
        instructions.append((instruction.upper(), value.strip()))
    return instructions


def test_oidc_image_when_parsed_uses_only_exact_pinned_stages() -> None:
    instructions = dockerfile_instructions()
    from_values = [value for instruction, value in instructions if instruction == "FROM"]
    assert from_values == [
        f"{UPSTREAM_REFERENCE} AS upstream",
        RUNTIME_REFERENCE,
    ]
    assert all("@sha256:" in value for value in from_values)


def test_oidc_image_when_parsed_copies_only_exact_upstream_app_bits() -> None:
    copy_values = [
        value
        for instruction, value in dockerfile_instructions()
        if instruction == "COPY"
    ]

    assert copy_values == ["--from=upstream --chown=65532:65532 /app /app"]
    forbidden_paths = {"/", "/etc", "/lib", "/lib64", "/usr"}
    copied_paths = set(shlex.split(copy_values[0])[-2:])
    assert copied_paths.isdisjoint(forbidden_paths)


def test_oidc_image_when_parsed_preserves_upstream_runtime_contract() -> None:
    instructions = dockerfile_instructions()
    values_by_instruction = {
        instruction: value
        for instruction, value in instructions
        if instruction in {"USER", "WORKDIR", "EXPOSE", "ENTRYPOINT"}
    }

    assert values_by_instruction == {
        "USER": "65532",
        "WORKDIR": "/app",
        "EXPOSE": "8080",
        "ENTRYPOINT": json.dumps(EXPECTED_ENTRYPOINT),
    }


def test_oidc_image_when_parsed_records_source_and_provenance() -> None:
    labels = [
        value
        for instruction, value in dockerfile_instructions()
        if instruction == "LABEL"
    ]

    assert 'org.opencontainers.image.source="https://github.com/navikt/mock-oauth2-server"' in labels
    assert f'org.opencontainers.image.base.name="{RUNTIME_REFERENCE}"' in labels
    assert 'org.opencontainers.image.revision="118597560f2a3cff0aad51e17d2511c8cb4221b9"' in labels
    assert 'io.support-copilot.test-only="true"' in labels
    assert f'io.support-copilot.oidc.upstream="{UPSTREAM_REFERENCE}"' in labels
    assert (
        'io.support-copilot.oidc.provenance='
        '"linux/amd64-app-manifest:sha256:8734e6a7c258ee928fb18ad64c2d55fe3f9488b735587d489661e89c0b9bf2c2"'
    ) in labels
