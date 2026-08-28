#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
# Usage:
#   python -m scripts.publish_scan_evidence publish <root> <label> <lock-type> \
#     <inventory> <report-or-> <stderr> <status> <outcome> <occurrences-or-null> <accepted>
#   python -m scripts.publish_scan_evidence validate <evidence-directory>
# The release gate uses stdlib boundary parsing so a fresh CI runner needs no new package.

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, NewType, assert_never

from scripts.validate_scan_evidence import (
    EvidenceRejectedError,
    validate_evidence as _validate_evidence_files,
)

EvidenceLabel = NewType("EvidenceLabel", str)
LockType = NewType("LockType", str)
_NAMES: Final = ("inventory", "stderr", "report", "provenance.json", "COMPLETE")
_LABEL_PATTERN: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_DIR_FLAGS: Final = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
_READ_FLAGS: Final = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
_CREATE_FLAGS: Final = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)


class ScanOutcome(StrEnum):
    CLEAN = "clean"
    VULNERABILITY = "vulnerability"
    OPERATIONAL = "operational"
    INVALID_REPORT = "invalid-report"


@dataclass(frozen=True, slots=True)
class PublishRequest:
    evidence_root: Path
    label: EvidenceLabel
    lock_type: LockType
    inventory: Path
    report: Path | None
    scanner_stderr: Path
    scanner_exit_status: int
    outcome: ScanOutcome
    vulnerability_occurrences: int | None
    report_accepted: bool


@dataclass(frozen=True, slots=True)
class FileDigest:
    sha256: str
    size: int


@dataclass(frozen=True, slots=True)
class InvalidPublishRequestError(Exception):
    reason: str

    def __str__(self) -> str:
        return f"invalid scan evidence publish request: {self.reason}"


@dataclass(frozen=True, slots=True)
class DestinationExistsError(Exception):
    label: EvidenceLabel

    def __str__(self) -> str:
        return f"scan evidence path is not fresh for {self.label}"


def _open_directory_path(path: Path) -> int:
    if not path.is_absolute():
        raise InvalidPublishRequestError("evidence root must be absolute")
    current_fd = os.open("/", _DIR_FLAGS)
    try:
        for component in path.parts[1:]:
            next_fd = os.open(component, _DIR_FLAGS, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
    except OSError:
        os.close(current_fd)
        raise
    return current_fd


def _open_regular_source(path: Path) -> int:
    source_fd = os.open(path, _READ_FLAGS)
    if not stat.S_ISREG(os.fstat(source_fd).st_mode):
        os.close(source_fd)
        raise InvalidPublishRequestError(f"source is not a regular file: {path}")
    return source_fd


def _copy_source(destination_fd: int, name: str, source_fd: int) -> FileDigest:
    digest = hashlib.sha256()
    size = 0
    with os.fdopen(os.open(name, _CREATE_FLAGS, 0o600, dir_fd=destination_fd), "wb") as published:
        while chunk := os.read(source_fd, 1024 * 1024):
            published.write(chunk)
            digest.update(chunk)
            size += len(chunk)
        published.flush()
        os.fsync(published.fileno())
    return FileDigest(digest.hexdigest(), size)


def _write_file(destination_fd: int, name: str, data: bytes) -> None:
    with os.fdopen(os.open(name, _CREATE_FLAGS, 0o600, dir_fd=destination_fd), "wb") as published:
        published.write(data)
        published.flush()
        os.fsync(published.fileno())


def _is_consistent(request: PublishRequest) -> bool:
    present = request.report is not None
    match request.outcome:
        case ScanOutcome.CLEAN:
            return request.scanner_exit_status == 0 and request.vulnerability_occurrences == 0 and present and request.report_accepted
        case ScanOutcome.VULNERABILITY:
            count = request.vulnerability_occurrences
            return request.scanner_exit_status == 1 and count is not None and count > 0 and present and request.report_accepted
        case ScanOutcome.OPERATIONAL:
            return request.scanner_exit_status not in (0, 1) and request.vulnerability_occurrences is None and not request.report_accepted
        case ScanOutcome.INVALID_REPORT:
            return request.scanner_exit_status in (0, 1) and request.vulnerability_occurrences is None and not request.report_accepted
        case unreachable:
            assert_never(unreachable)


def _validate_request(request: PublishRequest) -> None:
    if not _LABEL_PATTERN.fullmatch(request.label):
        raise InvalidPublishRequestError("label has an unsafe format")
    if not request.lock_type:
        raise InvalidPublishRequestError("lock type is empty")
    if not _is_consistent(request):
        raise InvalidPublishRequestError("outcome fields are inconsistent")


def _provenance_bytes(request: PublishRequest, inventory: FileDigest, report: FileDigest | None, stderr: FileDigest) -> bytes:
    payload = {
        "schema_version": 2, "label": request.label, "lock_type": request.lock_type,
        "scanner_exit_status": request.scanner_exit_status, "outcome": request.outcome,
        "vulnerability_occurrences": request.vulnerability_occurrences,
        "report_present": request.report is not None, "report_accepted": request.report_accepted,
        "inventory_sha256": inventory.sha256, "report_sha256": None if report is None else report.sha256,
        "stderr_sha256": stderr.sha256, "stderr_size": stderr.size,
    }
    return (json.dumps(payload, sort_keys=True) + "\n").encode()


def _cleanup(root_fd: int, destination_fd: int, label: EvidenceLabel, identity: tuple[int, int]) -> None:
    for name in _NAMES:
        try:
            os.unlink(name, dir_fd=destination_fd)
        except FileNotFoundError:
            continue
    try:
        current = os.stat(label, dir_fd=root_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if stat.S_ISDIR(current.st_mode) and (current.st_dev, current.st_ino) == identity:
        os.rmdir(label, dir_fd=root_fd)


def publish(request: PublishRequest) -> Path:
    _validate_request(request)
    root_fd = _open_directory_path(request.evidence_root)
    destination_fd = -1
    succeeded = False
    try:
        try:
            os.mkdir(request.label, mode=0o700, dir_fd=root_fd)
        except FileExistsError:
            raise DestinationExistsError(request.label) from None
        destination_fd = os.open(request.label, _DIR_FLAGS, dir_fd=root_fd)
        claimed = os.fstat(destination_fd)
        identity = (claimed.st_dev, claimed.st_ino)
        source_fds: list[int] = []
        try:
            inventory_fd = _open_regular_source(request.inventory)
            source_fds.append(inventory_fd)
            stderr_fd = _open_regular_source(request.scanner_stderr)
            source_fds.append(stderr_fd)
            report_fd = None
            if request.report is not None:
                report_fd = _open_regular_source(request.report)
                source_fds.append(report_fd)
            inventory = _copy_source(destination_fd, "inventory", inventory_fd)
            stderr = _copy_source(destination_fd, "stderr", stderr_fd)
            report = None if report_fd is None else _copy_source(destination_fd, "report", report_fd)
            provenance = _provenance_bytes(request, inventory, report, stderr)
            _write_file(destination_fd, "provenance.json", provenance)
            complete = {"provenance_sha256": hashlib.sha256(provenance).hexdigest(), "schema_version": 1}
            _write_file(destination_fd, "COMPLETE", (json.dumps(complete, sort_keys=True) + "\n").encode())
            os.fsync(destination_fd)
            os.fsync(root_fd)
            succeeded = True
        finally:
            for source_fd in source_fds:
                os.close(source_fd)
            if not succeeded:
                _cleanup(root_fd, destination_fd, request.label, identity)
    finally:
        if destination_fd >= 0:
            os.close(destination_fd)
        os.close(root_fd)
    return request.evidence_root / request.label


def validate_evidence(path: Path) -> None:
    provenance = _validate_evidence_files(path)
    try:
        outcome = ScanOutcome(provenance.outcome)
    except ValueError:
        raise EvidenceRejectedError(path, "provenance outcome is unknown") from None
    request = PublishRequest(
        path.parent, EvidenceLabel(provenance.label), LockType(provenance.lock_type), path,
        path if provenance.report_present else None, path, provenance.scanner_exit_status,
        outcome, provenance.vulnerability_occurrences, provenance.report_accepted,
    )
    try:
        _validate_request(request)
    except InvalidPublishRequestError as error:
        raise EvidenceRejectedError(path, error.reason) from None


def _parse_publish(arguments: list[str]) -> PublishRequest:
    if len(arguments) != 10:
        raise InvalidPublishRequestError("publish expects 10 arguments")
    root, label, lock_type, inventory, report, stderr, status, outcome, occurrences, accepted = arguments
    try:
        parsed_status = int(status)
        parsed_outcome = ScanOutcome(outcome)
        parsed_occurrences = None if occurrences == "null" else int(occurrences)
    except ValueError as error:
        raise InvalidPublishRequestError(f"invalid scalar: {error}") from None
    if accepted not in ("true", "false"):
        raise InvalidPublishRequestError("accepted must be true or false")
    return PublishRequest(Path(root), EvidenceLabel(label), LockType(lock_type), Path(inventory), None if report == "-" else Path(report), Path(stderr), parsed_status, parsed_outcome, parsed_occurrences, accepted == "true")


def main() -> int:
    try:
        match sys.argv[1:]:  # noqa: MATCH_OK - argv is an untrusted open boundary.
            case ["publish", *arguments]:
                print(publish(_parse_publish(arguments)))
            case ["validate", evidence_path]:
                validate_evidence(Path(evidence_path))
                print(evidence_path)
            case _:
                raise InvalidPublishRequestError("expected publish or validate command")
    except (InvalidPublishRequestError, EvidenceRejectedError, DestinationExistsError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
