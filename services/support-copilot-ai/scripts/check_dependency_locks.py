"""检查 Python 范围文件和锁文件是否保持同步。"""

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final


PROJECT_DIR: Final = Path(__file__).parents[1]


@dataclass(frozen=True, slots=True)
class LockSpec:
    """一组由范围文件生成的锁文件。"""

    source: Path
    lock: Path


LOCK_SPECS: Final = (
    LockSpec(
        source=PROJECT_DIR / "requirements.txt",
        lock=PROJECT_DIR / "requirements.lock.txt",
    ),
    LockSpec(
        source=PROJECT_DIR / "requirements-dev.txt",
        lock=PROJECT_DIR / "requirements-dev.lock.txt",
    ),
)


def _without_generation_header(content: str) -> tuple[str, ...]:
    """移除包含输出路径的顶部生成命令，保留依赖来源注释。"""
    lines = content.splitlines()
    first_requirement = next(
        (
            index
            for index, line in enumerate(lines)
            if line.strip() and not line.lstrip().startswith("#")
        ),
        len(lines),
    )
    return tuple(line.rstrip() for line in lines[first_requirement:])


def lock_contents_match(committed: str, generated: str) -> bool:
    """比较仓库锁文件和重新生成的锁文件。"""
    return _without_generation_header(committed) == _without_generation_header(
        generated
    )


def _regenerate_lock(spec: LockSpec, output: Path) -> None:
    """在临时位置按当前范围文件重新生成锁文件。"""
    shutil.copyfile(spec.lock, output)
    subprocess.run(
        (
            sys.executable,
            "-m",
            "uv",
            "pip",
            "compile",
            "-q",
            "--universal",
            "--python-version",
            "3.11",
            "--generate-hashes",
            "--output-file",
            str(output),
            spec.source.name,
        ),
        cwd=PROJECT_DIR,
        check=True,
    )


def find_stale_locks() -> tuple[Path, ...]:
    """返回与当前范围文件不一致的锁文件。"""
    stale: list[Path] = []
    with TemporaryDirectory(prefix="support-copilot-lock-check-") as directory:
        temporary_dir = Path(directory)
        for spec in LOCK_SPECS:
            generated = temporary_dir / spec.lock.name
            _regenerate_lock(spec, generated)
            if not lock_contents_match(
                spec.lock.read_text(encoding="utf-8"),
                generated.read_text(encoding="utf-8"),
            ):
                stale.append(spec.lock)
    return tuple(stale)


def main() -> int:
    """检查全部锁文件，并用退出码表示结果。"""
    stale_locks = find_stale_locks()
    if not stale_locks:
        print("Python dependency locks are up to date.")
        return 0

    print("Python dependency locks are stale:", file=sys.stderr)
    for lock in stale_locks:
        print(f"- {lock.relative_to(PROJECT_DIR)}", file=sys.stderr)
    print("Regenerate the lock files with the commands in README.md.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
