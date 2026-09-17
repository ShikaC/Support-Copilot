from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt


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
        for child in token.children or []:
            if child.type == "link_open":
                target = child.attrGet("href")
            elif child.type == "image":
                target = child.attrGet("src")
            else:
                target = None
            if target is not None:
                targets.append(target)
    return targets


def github_heading_anchors(markdown: str) -> set[str]:
    anchors: set[str] = set()
    occurrences: dict[str, int] = {}
    tokens = MarkdownIt("commonmark").parse(markdown)
    for index, token in enumerate(tokens[:-1]):
        if token.type != "heading_open" or tokens[index + 1].type != "inline":
            continue
        heading = tokens[index + 1].content.lower().strip()
        base = re.sub(r"[^\w\- ]", "", heading, flags=re.UNICODE)
        base = re.sub(r"\s+", "-", base)
        duplicate = occurrences.get(base, 0)
        occurrences[base] = duplicate + 1
        anchors.add(base if duplicate == 0 else f"{base}-{duplicate}")
    for match in re.finditer(
        r'<a\s+(?:[^>]*?\s)?(?:id|name)=["\']([^"\']+)["\']', markdown
    ):
        anchors.add(match.group(1))
    return anchors


def ignored_local_evidence(repo_root: Path, relative_paths: list[str]) -> set[str]:
    """Return targets that .gitignore keeps out of the published tree.

    Evidence documents often link to local run artifacts (trials, corpus files,
    workspace snapshots) that stay on disk but are deliberately not published.
    Those links are allowed to be unresolvable in a tracked-only checkout, while
    links to published files must still resolve.
    """
    if not relative_paths:
        return set()
    result = subprocess.run(
        ["git", "-C", str(repo_root), "check-ignore", "--stdin"],
        input="\n".join(relative_paths),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        return set()
    return {line for line in result.stdout.splitlines() if line}


def validate_markdown_links(repo_root: Path, markdown_paths: list[Path]) -> list[str]:
    root = repo_root.resolve()
    entries: list[tuple[Path, str, Path, str]] = []
    for markdown_path in markdown_paths:
        relative_markdown = markdown_path.relative_to(repo_root)
        for target in markdown_targets(markdown_path.read_text(encoding="utf-8")):
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue
            decoded_path = unquote(parsed.path)
            resolved = (
                (markdown_path.parent / decoded_path).resolve()
                if decoded_path
                else markdown_path.resolve()
            )
            entries.append((relative_markdown, target, resolved, decoded_path))

    unresolved: list[str] = []
    for _, _, resolved, _ in entries:
        if resolved.exists() or not resolved.is_relative_to(root):
            continue
        unresolved.append(resolved.relative_to(root).as_posix())
    ignored = ignored_local_evidence(repo_root, unresolved)

    errors: list[str] = []
    anchor_cache: dict[Path, set[str]] = {}
    for relative_markdown, target, resolved, decoded_path in entries:
        if decoded_path.startswith("/"):
            errors.append(f"{relative_markdown}: repository link must be relative: {target}")
            continue
        try:
            resolved.relative_to(root)
        except ValueError:
            errors.append(f"{relative_markdown}: link escapes repository: {target}")
            continue
        if not resolved.exists():
            if resolved.relative_to(root).as_posix() in ignored:
                continue
            errors.append(f"{relative_markdown}: missing local link target: {target}")
            continue
        fragment_target = urlsplit(target).fragment
        if fragment_target and resolved.suffix.lower() == ".md":
            fragment = unquote(fragment_target)
            anchors = anchor_cache.setdefault(
                resolved,
                github_heading_anchors(resolved.read_text(encoding="utf-8")),
            )
            if fragment not in anchors:
                errors.append(f"{relative_markdown}: missing local anchor: {target}")
    return errors
