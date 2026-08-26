import os
from pathlib import Path
import subprocess
import sys

import pytest

PROJECT_DIR = Path(__file__).parents[1]
TOKEN_ENV_NAME = "SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN"


def run_app_import(
    configured_token: str | None,
    working_directory: Path,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["AI_MODE"] = "mock"
    environment["PYTHONPATH"] = str(PROJECT_DIR)
    environment.pop(TOKEN_ENV_NAME, None)
    if configured_token is not None:
        environment[TOKEN_ENV_NAME] = configured_token
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.main import app; print(app.title)",
        ],
        cwd=working_directory,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


@pytest.mark.parametrize("configured_token", [None, ""])
def test_app_import_rejects_missing_or_blank_internal_service_token(
    configured_token: str | None,
    tmp_path: Path,
) -> None:
    result = run_app_import(configured_token, tmp_path)
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert TOKEN_ENV_NAME in output
    assert "must be configured with a non-blank value" in output


def test_app_import_accepts_explicit_internal_service_token(tmp_path: Path) -> None:
    token = "synthetic-subprocess-service-token"

    result = run_app_import(token, tmp_path)
    output = result.stdout + result.stderr

    assert result.returncode == 0
    assert result.stdout.strip() == "Support Copilot AI"
    assert token not in output
