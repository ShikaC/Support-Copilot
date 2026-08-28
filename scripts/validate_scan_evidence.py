from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypeAlias

JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
_DIR_FLAGS: Final = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
_READ_FLAGS: Final = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
_PROVENANCE_KEYS: Final = {
    "schema_version", "label", "lock_type", "scanner_exit_status", "outcome",
    "vulnerability_occurrences", "report_present", "report_accepted",
    "inventory_sha256", "report_sha256", "stderr_sha256", "stderr_size",
}


@dataclass(frozen=True, slots=True)
class EvidenceRejectedError(Exception):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"scan evidence rejected at {self.path}: {self.reason}"


@dataclass(frozen=True, slots=True)
class ValidatedProvenance:
    label: str
    lock_type: str
    scanner_exit_status: int
    outcome: str
    vulnerability_occurrences: int | None
    report_present: bool
    report_accepted: bool
    inventory_sha256: str
    report_sha256: str | None
    stderr_sha256: str
    stderr_size: int


def _open_directory(path: Path) -> int:
    if not path.is_absolute():
        raise EvidenceRejectedError(path, "evidence path is not absolute")
    current_fd = os.open("/", _DIR_FLAGS)
    try:
        for component in path.parts[1:]:
            next_fd = os.open(component, _DIR_FLAGS, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
    except OSError as error:
        os.close(current_fd)
        raise EvidenceRejectedError(path, f"cannot open evidence directory: {error}") from None
    return current_fd


def _decode(data: bytes, path: Path) -> JsonValue:
    try:
        value: JsonValue = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvidenceRejectedError(path, f"invalid JSON: {error}") from None
    return value


def _read_regular(directory_fd: int, name: str, path: Path) -> tuple[bytes, int]:
    try:
        file_fd = os.open(name, _READ_FLAGS, dir_fd=directory_fd)
    except OSError as error:
        raise EvidenceRejectedError(path, f"cannot open {name}: {error}") from None
    try:
        file_stat = os.fstat(file_fd)
        if not stat.S_ISREG(file_stat.st_mode):
            raise EvidenceRejectedError(path, f"{name} is not regular")
        chunks: list[bytes] = []
        while chunk := os.read(file_fd, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks), file_stat.st_mtime_ns
    finally:
        os.close(file_fd)


def _parse_provenance(value: JsonValue, path: Path) -> ValidatedProvenance:
    match value:  # noqa: MATCH_OK - untrusted JSON must have a rejecting default.
        case {
            "schema_version": 2, "label": str(label), "lock_type": str(lock_type),
            "scanner_exit_status": int(status), "outcome": str(outcome),
            "vulnerability_occurrences": occurrences, "report_present": bool(present),
            "report_accepted": bool(accepted), "inventory_sha256": str(inventory_sha),
            "report_sha256": report_sha, "stderr_sha256": str(stderr_sha),
            "stderr_size": int(stderr_size),
        } if set(value) == _PROVENANCE_KEYS:
            if not (occurrences is None or type(occurrences) is int):
                raise EvidenceRejectedError(path, "vulnerability count has an invalid type")
            if not (report_sha is None or type(report_sha) is str):
                raise EvidenceRejectedError(path, "report digest has an invalid type")
            if stderr_size < 0:
                raise EvidenceRejectedError(path, "stderr size is negative")
            return ValidatedProvenance(
                label, lock_type, status, outcome, occurrences, present, accepted,
                inventory_sha, report_sha, stderr_sha, stderr_size,
            )
        case _:
            raise EvidenceRejectedError(path, "provenance shape is invalid")


def validate_evidence(path: Path) -> ValidatedProvenance:
    directory_fd = _open_directory(path)
    try:
        complete_bytes, complete_time = _read_regular(directory_fd, "COMPLETE", path)
        provenance_bytes, provenance_time = _read_regular(directory_fd, "provenance.json", path)
        expected_complete = {
            "provenance_sha256": hashlib.sha256(provenance_bytes).hexdigest(),
            "schema_version": 1,
        }
        if _decode(complete_bytes, path) != expected_complete:
            raise EvidenceRejectedError(path, "COMPLETE marker is inconsistent")
        provenance = _parse_provenance(_decode(provenance_bytes, path), path)
        expected_names = {"COMPLETE", "inventory", "provenance.json", "stderr"}
        if provenance.report_present:
            expected_names.add("report")
        if set(os.listdir(directory_fd)) != expected_names:
            raise EvidenceRejectedError(path, "evidence entries are inconsistent")
        inventory, inventory_time = _read_regular(directory_fd, "inventory", path)
        stderr, stderr_time = _read_regular(directory_fd, "stderr", path)
        report_data = None
        published_times = [inventory_time, stderr_time, provenance_time]
        if provenance.report_present:
            report_data, report_time = _read_regular(directory_fd, "report", path)
            published_times.append(report_time)
        if complete_time < max(published_times):
            raise EvidenceRejectedError(path, "COMPLETE was not created last")
        if hashlib.sha256(inventory).hexdigest() != provenance.inventory_sha256:
            raise EvidenceRejectedError(path, "inventory digest mismatch")
        if hashlib.sha256(stderr).hexdigest() != provenance.stderr_sha256:
            raise EvidenceRejectedError(path, "stderr digest mismatch")
        if len(stderr) != provenance.stderr_size:
            raise EvidenceRejectedError(path, "stderr size mismatch")
        report_digest = None if report_data is None else hashlib.sha256(report_data).hexdigest()
        if report_digest != provenance.report_sha256:
            raise EvidenceRejectedError(path, "report digest mismatch")
        return provenance
    finally:
        os.close(directory_fd)
