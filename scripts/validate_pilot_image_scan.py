#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
# noqa: SIZE_OK - The fixed Task 15 write set permits one standalone validator module.
# How to run from the repository root:
#   Finalize: ./scripts/validate_pilot_image_scan.py finalize <output> <scanner-ref> <scanner-id> <version-json> (<image-ref> <image-id> <repo-digests-json> <report-name> <exit>)+
#   Verify: ./scripts/validate_pilot_image_scan.py verify <output>

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypeAlias, TypeGuard

JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
SEVERITIES: Final = ("HIGH", "CRITICAL")
SHA_PATTERN: Final = re.compile(r"^sha256:[0-9a-f]{64}$")
CVE_PATTERN: Final = re.compile(r"^CVE-[0-9]{4}-[0-9]+$")
SECRET_PATTERN: Final = re.compile(
    r"(?i)(?:api[_-]?key|authorization|bearer|jwt|password|secret|token)\s*[:=]|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"
)
URL_PATTERN: Final = re.compile(r"(?i)\b(?:https?|ftp)://")
FINDING_KEYS: Final = frozenset(
    {
        "ImageRef", "ImageID", "RepoDigests", "Target", "Class", "Type",
        "VulnerabilityID", "PkgName", "InstalledVersion", "FixedVersion",
        "Severity", "PrimaryDataSource",
    }
)
EXPECTED_SCANNER_VERSION: Final = "0.66.0"
SCANNER_REF: Final = "aquasec/trivy:0.66.0@sha256:086971aaf400beebd94e8300fd8ea623774419597169156cec56eec5b00dfb1e"


@dataclass(frozen=True, slots=True)
class ScanRejectedError(Exception):
    reason: str

    def __str__(self) -> str:
        return f"pilot image scan rejected: {self.reason}"


@dataclass(frozen=True, slots=True)
class ImageInput:
    image_ref: str
    image_id: str
    repo_digests: tuple[str, ...]
    report_name: str
    scanner_exit: int


@dataclass(frozen=True, slots=True)
class ParsedReport:
    high: int
    critical: int
    cves: tuple[str, ...]
    findings: tuple[dict[str, JsonValue], ...]


def _load_json(path: Path) -> JsonValue:
    _regular_file(path)
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ScanRejectedError(f"cannot read {path.name}: {error}") from None
    if not data:
        raise ScanRejectedError(f"{path.name} is empty")
    try:
        value: JsonValue = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ScanRejectedError(f"{path.name} is invalid JSON: {error}") from None
    return value


def _regular_file(path: Path) -> None:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise ScanRejectedError(f"cannot stat {path.name}: {error}") from None
    if not stat.S_ISREG(metadata.st_mode):
        raise ScanRejectedError(f"{path.name} is not a regular file")


def _digest(path: Path) -> str:
    _regular_file(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_repo_digests(raw: str) -> tuple[str, ...]:
    try:
        value: JsonValue = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ScanRejectedError(f"repo digests are invalid JSON: {error}") from None
    match value:  # noqa: MATCH_OK - open JSON boundary rejects unknown variants.
        case None:
            return ()
        case list(items):
            parsed: list[str] = []
            for item in items:
                match item:  # noqa: MATCH_OK - external JSON has a rejecting default.
                    case str(digest):
                        parsed.append(digest)
                    case _:
                        raise ScanRejectedError("repo digests must be a string array")
            return tuple(parsed)
        case _:
            raise ScanRejectedError("repo digests must be a string array")


def _parse_image_arguments(arguments: list[str]) -> tuple[ImageInput, ...]:
    if not arguments or len(arguments) % 5:
        raise ScanRejectedError("at least one complete image record is required")
    images: list[ImageInput] = []
    for offset in range(0, len(arguments), 5):
        image_ref, image_id, digests, report_name, scanner_exit = arguments[offset : offset + 5]
        try:
            parsed_exit = int(scanner_exit)
        except ValueError:
            raise ScanRejectedError("scanner exit must be an integer") from None
        if not image_ref or not SHA_PATTERN.fullmatch(image_id):
            raise ScanRejectedError("image reference or image id is invalid")
        if not re.fullmatch(r"report-[0-9]{3}\.json", report_name):
            raise ScanRejectedError("report name is invalid")
        images.append(ImageInput(image_ref, image_id, _parse_repo_digests(digests), report_name, parsed_exit))
    if len({image.image_ref for image in images}) != len(images):
        raise ScanRejectedError("image references must be unique")
    return tuple(images)


def _safe_optional_string(value: JsonValue, field: str, path: Path) -> JsonValue:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ScanRejectedError(f"{path.name} {field} is malformed")
    return "[REDACTED]" if SECRET_PATTERN.search(value) or URL_PATTERN.search(value) else value


def _are_strings(values: list[JsonValue]) -> TypeGuard[list[str]]:
    return all(isinstance(value, str) for value in values)


def _primary_data_source(vulnerability: dict[str, JsonValue], path: Path) -> JsonValue:
    source = vulnerability.get("DataSource")
    if source is None:
        return None
    if not isinstance(source, dict):
        raise ScanRejectedError(f"{path.name} DataSource is malformed")
    identifier = source.get("ID") or source.get("Name")
    return _safe_optional_string(identifier, "DataSource", path)


def _finding(
    image: ImageInput,
    target: str,
    result_class: str,
    result_type: str,
    vulnerability: dict[str, JsonValue],
    path: Path,
) -> dict[str, JsonValue]:
    record: dict[str, JsonValue] = {
        "ImageRef": image.image_ref,
        "ImageID": image.image_id,
        "RepoDigests": list(image.repo_digests),
        "Target": _safe_optional_string(target, "Target", path),
        "Class": result_class,
        "Type": result_type,
        "VulnerabilityID": _safe_optional_string(vulnerability["VulnerabilityID"], "VulnerabilityID", path),
        "PkgName": _safe_optional_string(vulnerability.get("PkgName"), "PkgName", path),
        "InstalledVersion": _safe_optional_string(vulnerability.get("InstalledVersion"), "InstalledVersion", path),
        "FixedVersion": _safe_optional_string(vulnerability.get("FixedVersion"), "FixedVersion", path),
        "Severity": vulnerability["Severity"],
        "PrimaryDataSource": _primary_data_source(vulnerability, path),
    }
    if vulnerability.get("Status") is not None:
        record["Status"] = _safe_optional_string(vulnerability["Status"], "Status", path)
    return record


def _parse_report(path: Path, image: ImageInput) -> ParsedReport:
    value = _load_json(path)
    match value:  # noqa: MATCH_OK - open Trivy boundary rejects unknown variants.
        case {"Metadata": {"ImageID": str(report_id), "RepoDigests": report_digests}, "Results": list(results)}:
            if report_id != image.image_id:
                raise ScanRejectedError(f"{path.name} image identity mismatch")
            match report_digests:  # noqa: MATCH_OK - external JSON has a rejecting default.
                case None:
                    parsed_report_digests: tuple[str, ...] = ()
                case list(items):
                    parsed_items: list[str] = []
                    for item in items:
                        match item:  # noqa: MATCH_OK - external JSON has a rejecting default.
                            case str(digest):
                                parsed_items.append(digest)
                            case _:
                                raise ScanRejectedError(f"{path.name} repo digests are malformed")
                    parsed_report_digests = tuple(parsed_items)
                case _:
                    raise ScanRejectedError(f"{path.name} repo digests are malformed")
            if image.repo_digests and not set(image.repo_digests).issubset(parsed_report_digests):
                raise ScanRejectedError(f"{path.name} repo digest identity mismatch")
        case _:
            raise ScanRejectedError(f"{path.name} report shape is invalid")
    counts = {severity: 0 for severity in SEVERITIES}
    cves: set[str] = set()
    findings: list[dict[str, JsonValue]] = []
    for result in results:
        match result:  # noqa: MATCH_OK - Trivy result variants are externally supplied.
            case {"Target": str(), "Class": str(result_class), "Type": str()} if result_class in ("os-pkgs", "lang-pkgs") and "Vulnerabilities" not in result:
                continue
            case {"Target": str(), "Class": str(result_class), "Type": str(), "Vulnerabilities": None | []} if result_class in ("os-pkgs", "lang-pkgs"):
                continue
            case {"Target": str(target), "Class": str(result_class), "Type": str(result_type), "Vulnerabilities": list(vulnerabilities)} if result_class in ("os-pkgs", "lang-pkgs"):
                for vulnerability in vulnerabilities:
                    match vulnerability:  # noqa: MATCH_OK - external report boundary.
                        case {"Severity": str(severity), "VulnerabilityID": str(identifier)} if isinstance(vulnerability, dict):
                            if severity in counts:
                                counts[severity] += 1
                                if CVE_PATTERN.fullmatch(identifier):
                                    cves.add(identifier)
                                findings.append(_finding(image, target, result_class, result_type, vulnerability, path))
                        case _:
                            raise ScanRejectedError(f"{path.name} vulnerability shape is invalid")
            case _:
                raise ScanRejectedError(f"{path.name} result shape is invalid")
    finding_count = sum(counts.values())
    if image.scanner_exit not in (0, 1) or (image.scanner_exit == 0) != (finding_count == 0):
        raise ScanRejectedError(f"{path.name} scanner exit contradicts findings")
    findings.sort(key=lambda finding: json.dumps(finding, sort_keys=True, separators=(",", ":")))
    return ParsedReport(counts["HIGH"], counts["CRITICAL"], tuple(sorted(cves)), tuple(findings))


def _scanner_metadata(path: Path, scanner_ref: str, scanner_id: str) -> dict[str, JsonValue]:
    if scanner_ref != SCANNER_REF or not SHA_PATTERN.fullmatch(scanner_id) or not scanner_ref.endswith(scanner_id):
        raise ScanRejectedError("scanner is not the approved immutable image")
    value = _load_json(path)
    match value:  # noqa: MATCH_OK - external scanner output boundary.
        case {"Version": str(version), **remainder}:
            if version != EXPECTED_SCANNER_VERSION:
                raise ScanRejectedError("scanner version does not match its pinned tag")
            database = remainder.get("VulnerabilityDB")
            redacted_db: JsonValue = None
            if isinstance(database, dict):
                redacted_db = {key: database[key] for key in ("Version", "UpdatedAt", "NextUpdate", "DownloadedAt") if key in database}
            return {"image_ref": scanner_ref, "image_id": scanner_id, "version": version, "vulnerability_db": redacted_db}
        case _:
            raise ScanRejectedError("scanner version output shape is invalid")


def _write_exclusive(path: Path, payload: JsonValue) -> None:
    data = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _manifest_identities(images: list[JsonValue]) -> dict[tuple[str, str, tuple[str, ...]], int]:
    identities: dict[tuple[str, str, tuple[str, ...]], int] = {}
    for image in images:
        match image:  # noqa: MATCH_OK - persisted evidence boundary.
            case {"image_ref": str(image_ref), "image_id": str(image_id), "repo_digests": list(repo_digests), "high": high, "critical": critical}:
                if (
                    not _are_strings(repo_digests)
                    or type(high) is not int
                    or type(critical) is not int
                    or high < 0
                    or critical < 0
                ):
                    raise ScanRejectedError("manifest image finding counts are malformed")
                identity = (image_ref, image_id, tuple(repo_digests))
                if identity in identities:
                    raise ScanRejectedError("manifest image identities are duplicated")
                identities[identity] = high + critical
            case _:
                raise ScanRejectedError("manifest image shape is invalid")
    return identities


def _validate_findings(records: list[JsonValue], images: list[JsonValue]) -> None:
    expected = _manifest_identities(images)
    actual = dict.fromkeys(expected, 0)
    rendered: list[str] = []
    for record in records:
        if not isinstance(record, dict) or set(record) not in (FINDING_KEYS, FINDING_KEYS | {"Status"}):
            raise ScanRejectedError("finding record fields are invalid")
        match record:  # noqa: MATCH_OK - persisted evidence boundary.
            case {
                "ImageRef": str(image_ref), "ImageID": str(image_id), "RepoDigests": list(repo_digests),
                "Target": str(target), "Class": str(result_class), "Type": str(result_type),
                "VulnerabilityID": str(identifier), "PkgName": package, "InstalledVersion": installed,
                "FixedVersion": fixed, "Severity": str(severity), "PrimaryDataSource": source,
            }:
                retained = (target, result_class, result_type, identifier, package, installed, fixed, source, record.get("Status"))
                if (
                    not SHA_PATTERN.fullmatch(image_id)
                    or not _are_strings(repo_digests)
                    or result_class not in ("os-pkgs", "lang-pkgs")
                    or severity not in SEVERITIES
                    or any(item is not None and not isinstance(item, str) for item in retained)
                    or any(isinstance(item, str) and (SECRET_PATTERN.search(item) or URL_PATTERN.search(item)) for item in (image_ref, *retained))
                ):
                    raise ScanRejectedError("finding record values are invalid")
                identity = (image_ref, image_id, tuple(repo_digests))
                if identity not in actual:
                    raise ScanRejectedError("finding image identity is not in manifest")
                actual[identity] += 1
                rendered.append(json.dumps(record, sort_keys=True, separators=(",", ":")))
            case _:
                raise ScanRejectedError("finding record shape is invalid")
    if actual != expected:
        raise ScanRejectedError("finding counts do not match manifest images")
    if rendered != sorted(rendered):
        raise ScanRejectedError("finding records are not deterministically ordered")


def finalize(output: Path, scanner_ref: str, scanner_id: str, version_name: str, images: tuple[ImageInput, ...]) -> bool:
    if output.is_symlink() or not output.is_dir():
        raise ScanRejectedError("output is not a real directory")
    if not images:
        raise ScanRejectedError("at least one image is required")
    version_path = output / version_name
    _regular_file(version_path)
    scanner = _scanner_metadata(version_path, scanner_ref, scanner_id)
    image_records: list[JsonValue] = []
    finding_records: list[JsonValue] = []
    files: dict[str, JsonValue] = {version_name: _digest(version_path)}
    blocked = False
    for image in images:
        if SECRET_PATTERN.search(image.image_ref):
            raise ScanRejectedError("image reference contains secret-shaped material")
        report_path = output / image.report_name
        parsed = _parse_report(report_path, image)
        blocked = blocked or parsed.high + parsed.critical > 0
        finding_records.extend(parsed.findings)
        report_sha = _digest(report_path)
        files[image.report_name] = report_sha
        stderr_name = f"scanner-{image.report_name[7:10]}.stderr"
        files[stderr_name] = _digest(output / stderr_name)
        image_records.append({"image_ref": image.image_ref, "image_id": image.image_id, "repo_digests": list(image.repo_digests), "report": image.report_name, "report_sha256": report_sha, "scanner_exit": image.scanner_exit, "high": parsed.high, "critical": parsed.critical, "cves": list(parsed.cves)})
    threshold: list[JsonValue] = list(SEVERITIES)
    finding_records.sort(key=lambda finding: json.dumps(finding, sort_keys=True, separators=(",", ":")))
    findings: dict[str, JsonValue] = {"schema_version": 1, "threshold": threshold, "findings": finding_records}
    _write_exclusive(output / "findings.json", findings)
    findings_sha = _digest(output / "findings.json")
    files["findings.json"] = findings_sha
    summary: dict[str, JsonValue] = {"schema_version": 1, "outcome": "blocked" if blocked else "clean", "threshold": threshold, "image_count": len(images), "images": image_records}
    _write_exclusive(output / "summary.json", summary)
    files["summary.json"] = _digest(output / "summary.json")
    policy: dict[str, JsonValue] = {"scanners": ["vuln"], "package_types": ["os", "library"], "severity_threshold": threshold, "ignore_unfixed": False}
    finding_binding: dict[str, JsonValue] = {"path": "findings.json", "sha256": findings_sha, "count": len(finding_records)}
    manifest: dict[str, JsonValue] = {"schema_version": 1, "scanner": scanner, "policy": policy, "images": image_records, "findings": finding_binding, "files": files}
    _write_exclusive(output / "manifest.json", manifest)
    _write_exclusive(output / "COMPLETE", {"schema_version": 1, "manifest_sha256": _digest(output / "manifest.json"), "findings_sha256": findings_sha})
    return blocked


def verify(output: Path) -> None:
    if output.is_symlink() or not output.is_dir():
        raise ScanRejectedError("output is not a real directory")
    complete = _load_json(output / "COMPLETE")
    manifest = _load_json(output / "manifest.json")
    match (complete, manifest):  # noqa: MATCH_OK - persisted evidence boundary.
        case (
            {"schema_version": 1, "manifest_sha256": str(expected), "findings_sha256": str(complete_findings)},
            {"schema_version": 1, "images": list(images), "findings": {"path": "findings.json", "sha256": str(manifest_findings), "count": finding_count}, "files": dict(files)},
        ):
            if expected != _digest(output / "manifest.json"):
                raise ScanRejectedError("manifest digest mismatch")
            findings_value = _load_json(output / "findings.json")
            match findings_value:  # noqa: MATCH_OK - persisted evidence boundary.
                case {"schema_version": 1, "threshold": ["HIGH", "CRITICAL"], "findings": list(persisted_findings)}:
                    if type(finding_count) is not int or finding_count != len(persisted_findings):
                        raise ScanRejectedError("findings count mismatch")
                    _validate_findings(persisted_findings, images)
                case _:
                    raise ScanRejectedError("findings shape is invalid")
            actual_findings = _digest(output / "findings.json")
            if complete_findings != manifest_findings or manifest_findings != actual_findings or files.get("findings.json") != actual_findings:
                raise ScanRejectedError("findings digest mismatch")
            for name, digest in files.items():
                if type(name) is not str or type(digest) is not str or digest != _digest(output / name):
                    raise ScanRejectedError(f"evidence digest mismatch for {name}")
            if set(os.listdir(output)) != set(files) | {"manifest.json", "COMPLETE"}:
                raise ScanRejectedError("evidence entries are incomplete or unexpected")
        case _:
            raise ScanRejectedError("manifest or COMPLETE shape is invalid")
    if (output / "COMPLETE").stat().st_mtime_ns < (output / "manifest.json").stat().st_mtime_ns:
        raise ScanRejectedError("COMPLETE was not written last")


def main() -> int:
    try:
        match sys.argv[1:]:  # noqa: MATCH_OK - argv is an open CLI boundary.
            case ["finalize", output, scanner_ref, scanner_id, version_name, *records]:
                finalize(Path(output), scanner_ref, scanner_id, version_name, _parse_image_arguments(records))
            case ["verify", output]:
                verify(Path(output))
            case _:
                raise ScanRejectedError("expected finalize or verify arguments")
    except (ScanRejectedError, OSError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
