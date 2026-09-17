"""Source-only behavior contracts for the derived MySQL image."""

import os
import re
import shlex
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest
import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = REPOSITORY_ROOT / "infra" / "compose.pilot.yml"
MYSQL_DOCKERFILE = REPOSITORY_ROOT / "infra" / "images" / "mysql" / "Dockerfile"
GOSU_WRAPPER = REPOSITORY_ROOT / "infra" / "images" / "mysql" / "gosu"
VERIFIER_PATH = REPOSITORY_ROOT / "scripts" / "verify-pilot-operations.sh"
MYSQL_IMAGE = "${SUPPORT_COPILOT_MYSQL_IMAGE:?SUPPORT_COPILOT_MYSQL_IMAGE is required}"
MYSQL_BASE = (
    "mysql:8.4.11-oraclelinux9@sha256:"
    "b3b90af2a6552ae30c266fdb7d5dd55f3afb72404bb78d37fe8a23eb857fd3fb"
)


@pytest.fixture
def fake_privilege_path(tmp_path: Path) -> Mapping[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tools = {
        "id": """#!/bin/sh
printf '%s %s\n' "$1" "$2" >> "$FAKE_ID_LOG"
case "$1:$2" in
  -u:mysql) printf '27\n' ;;
  -g:mysql) printf '28\n' ;;
  *) exit 91 ;;
esac
""",
        "setpriv": """#!/bin/sh
printf '%s\n' "$$" > "$FAKE_SETPRIV_PID"
printf '%s\n' "$@" > "$FAKE_SETPRIV_ARGV"
while [ "$#" -gt 0 ] && [ "$1" != -- ]; do shift; done
[ "$#" -gt 0 ] || exit 92
shift
exec "$@"
""",
        "command-probe": """#!/bin/sh
printf '%s\n' "$$" > "$FAKE_COMMAND_PID"
printf '%s\n' "$@" > "$FAKE_COMMAND_ARGV"
""",
    }
    for name, source in tools.items():
        path = bin_dir / name
        _ = path.write_text(source, encoding="utf-8")
        path.chmod(0o755)
    return {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "FAKE_ID_LOG": str(tmp_path / "id.log"),
        "FAKE_SETPRIV_ARGV": str(tmp_path / "setpriv.argv"),
        "FAKE_SETPRIV_PID": str(tmp_path / "setpriv.pid"),
        "FAKE_COMMAND_ARGV": str(tmp_path / "command.argv"),
        "FAKE_COMMAND_PID": str(tmp_path / "command.pid"),
    }


def test_mysql_service_when_parsed_has_local_only_image_lifecycle() -> None:
    with COMPOSE_PATH.open(encoding="utf-8") as compose_file:
        mysql = yaml.safe_load(compose_file)["services"]["mysql"]

    lifecycle = {
        key: mysql[key]
        for key in ("image", "pull_policy", "platform", "build")
    }
    assert lifecycle == {
        "image": MYSQL_IMAGE,
        "pull_policy": "never",
        "platform": "linux/amd64",
        "build": {
            "context": "..",
            "dockerfile": "infra/images/mysql/Dockerfile",
        },
    }


def test_mysql_lifecycle_when_verifier_parsed_has_build_and_no_build_modes() -> None:
    verifier = VERIFIER_PATH.read_text(encoding="utf-8")

    startup = re.search(
        r'if \[\[ "\$USE_PREBUILT_CURRENT_IMAGES" == true \]\]; then\n'
        r'\s*compose_for "\$PRIMARY_PROJECT" "\$WEB_PORT" up '
        r'(?P<prebuilt>--[^>\n]+?) >[^\n]+\n'
        r'else\n'
        r'\s*compose_for "\$PRIMARY_PROJECT" "\$WEB_PORT" up '
        r'(?P<source>--[^>\n]+?) >[^\n]+',
        verifier,
        re.MULTILINE,
    )

    assert startup is not None
    assert tuple(shlex.split(startup["prebuilt"])) == ("--no-build", "--detach", "--wait")
    assert tuple(shlex.split(startup["source"])) == ("--build", "--detach", "--wait")


def test_mysql_dockerfile_when_parsed_pins_base_and_package_versions() -> None:
    lines = MYSQL_DOCKERFILE.read_text(encoding="utf-8").splitlines()

    from_images = [line.removeprefix("FROM ") for line in lines if line.startswith("FROM ")]
    build_arguments = dict(
        line.removeprefix("ARG ").split("=", maxsplit=1)
        for line in lines
        if line.startswith("ARG ")
    )

    assert from_images == [MYSQL_BASE]
    assert build_arguments == {
        "CURL_VERSION": "7.76.1-40.el9_8.5",
        "SQLITE_LIBS_VERSION": "3.34.1-11.el9_8",
    }


@pytest.mark.parametrize("arguments", [(), ("mysql",)])
def test_gosu_wrapper_when_arguments_missing_fails_closed(
    tmp_path: Path,
    fake_privilege_path: Mapping[str, str],
    arguments: tuple[str, ...],
) -> None:
    result = subprocess.run(
        ["/bin/sh", str(GOSU_WRAPPER), *arguments],
        env=fake_privilege_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 64
    assert result.stderr == "gosu-compat:invalid-invocation\n"
    assert not (tmp_path / "id.log").exists()
    assert not (tmp_path / "setpriv.argv").exists()
    assert not (tmp_path / "command.argv").exists()


@pytest.mark.parametrize("target", ["root", "MYSQL", "mysql:27", "mysql "])
def test_gosu_wrapper_when_target_is_not_exact_mysql_fails_closed(
    tmp_path: Path,
    fake_privilege_path: Mapping[str, str],
    target: str,
) -> None:
    result = subprocess.run(
        ["/bin/sh", str(GOSU_WRAPPER), target, "command-probe"],
        env=fake_privilege_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 64
    assert result.stderr == "gosu-compat:invalid-invocation\n"
    assert not (tmp_path / "id.log").exists()
    assert not (tmp_path / "setpriv.argv").exists()
    assert not (tmp_path / "command.argv").exists()


def test_gosu_wrapper_when_target_is_mysql_execs_setpriv_with_original_argv(
    tmp_path: Path,
    fake_privilege_path: Mapping[str, str],
) -> None:
    process = subprocess.Popen(
        [
            "/bin/sh",
            str(GOSU_WRAPPER),
            "mysql",
            "command-probe",
            "arg with spaces",
            "--flag=value",
        ],
        env=fake_privilege_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = process.communicate(timeout=5)

    assert process.returncode == 0
    assert stdout == ""
    assert stderr == ""
    assert (tmp_path / "id.log").read_text(encoding="utf-8").splitlines() == [
        "-u mysql",
        "-g mysql",
    ]
    assert (tmp_path / "setpriv.argv").read_text(encoding="utf-8").splitlines() == [
        "--reuid=27",
        "--regid=28",
        "--init-groups",
        "--",
        "command-probe",
        "arg with spaces",
        "--flag=value",
    ]
    assert (tmp_path / "command.argv").read_text(encoding="utf-8").splitlines() == [
        "arg with spaces",
        "--flag=value",
    ]
    assert int((tmp_path / "setpriv.pid").read_text(encoding="utf-8")) == process.pid
    assert int((tmp_path / "command.pid").read_text(encoding="utf-8")) == process.pid
