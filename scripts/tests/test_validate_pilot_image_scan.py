from __future__ import annotations
# noqa: SIZE_OK - The fixed Task 15 write set permits one validator test module.

import hashlib
import json
from pathlib import Path

import pytest

from scripts import validate_pilot_image_scan as validator


IMAGE_ID = "sha256:" + "1" * 64
REPO_DIGEST = "registry.test/pilot-api@" + IMAGE_ID


def _write_fixture(
    root: Path,
    *,
    image_ref: str = "pilot-api:test",
    report: str | None = None,
    image_id: str = IMAGE_ID,
    scanner_exit: int = 0,
) -> tuple[validator.ImageInput, ...]:
    root.mkdir()
    (root / "scanner-version.json").write_text(
        json.dumps(
            {
                "Version": "0.66.0",
                "VulnerabilityDB": {
                    "Version": 2,
                    "UpdatedAt": "2026-08-30T00:00:00Z",
                },
            }
        ),
        encoding="utf-8",
    )
    report_text = report
    if report_text is None:
        report_text = json.dumps(
            {
                "SchemaVersion": 2,
                "Metadata": {"ImageID": image_id, "RepoDigests": [REPO_DIGEST]},
                "Results": [],
            }
        )
    (root / "report-001.json").write_text(report_text, encoding="utf-8")
    (root / "scanner-001.stderr").write_text("", encoding="utf-8")
    return (
        validator.ImageInput(
            image_ref,
            IMAGE_ID,
            (REPO_DIGEST,),
            "report-001.json",
            scanner_exit,
        ),
    )


def _finalize(root: Path, images: tuple[validator.ImageInput, ...]) -> bool:
    return validator.finalize(
        root,
        validator.SCANNER_REF,
        "sha256:086971aaf400beebd94e8300fd8ea623774419597169156cec56eec5b00dfb1e",
        "scanner-version.json",
        images,
    )


def _blocking_report(
    vulnerabilities: list[dict[str, validator.JsonValue]],
    *,
    image_id: str = IMAGE_ID,
    repo_digest: str = REPO_DIGEST,
    target: str = "site-packages",
) -> str:
    return json.dumps(
        {
            "SchemaVersion": 2,
            "Metadata": {"ImageID": image_id, "RepoDigests": [repo_digest]},
            "Results": [{"Target": target, "Class": "lang-pkgs", "Type": "python-pkg", "Vulnerabilities": vulnerabilities}],
        }
    )


def test_validator_rejects_secret_shaped_image_reference(tmp_path: Path) -> None:
    # Given: an otherwise valid report whose user-supplied reference resembles a credential.
    output = tmp_path / "evidence"
    images = _write_fixture(output, image_ref="pilot-api:token=super-secret-value")

    # When: evidence is finalized for publication.
    with pytest.raises(validator.ScanRejectedError, match="secret"):
        _finalize(output, images)

    # Then: no human-readable artifact can persist the credential-shaped input.
    assert not (output / "summary.json").exists()


@pytest.mark.parametrize("report", ["", "{not-json"])
def test_validator_rejects_empty_or_invalid_report(
    tmp_path: Path, report: str
) -> None:
    # Given: Trivy returns an empty or malformed machine report.
    output = tmp_path / "evidence"
    images = _write_fixture(output, report=report)

    # When/Then: finalization rejects it and cannot claim completeness.
    with pytest.raises(validator.ScanRejectedError):
        _finalize(output, images)
    assert not (output / "COMPLETE").exists()


def test_validator_rejects_wrong_image_identity(tmp_path: Path) -> None:
    # Given: a valid-looking report names a different local image ID.
    output = tmp_path / "evidence"
    images = _write_fixture(output, image_id="sha256:" + "2" * 64)

    # When/Then: report-to-image binding fails closed.
    with pytest.raises(validator.ScanRejectedError, match="identity mismatch"):
        _finalize(output, images)
    assert not (output / "COMPLETE").exists()


def test_validator_accepts_clean_results_when_trivy_omits_vulnerabilities(
    tmp_path: Path,
) -> None:
    # Given: Trivy omits the empty vulnerability key for OS and library targets.
    output = tmp_path / "evidence"
    report = json.dumps(
        {
            "SchemaVersion": 2,
            "Metadata": {"ImageID": IMAGE_ID, "RepoDigests": [REPO_DIGEST]},
            "Results": [
                {"Class": "os-pkgs", "Type": "ubuntu", "Target": "redacted"},
                {"Class": "lang-pkgs", "Type": "jar", "Target": "redacted"},
            ],
        }
    )
    images = _write_fixture(output, report=report)

    # When: the valid clean report is finalized.
    blocked = _finalize(output, images)

    # Then: omitted empty arrays mean zero findings, not malformed evidence.
    assert blocked is False
    validator.verify(output)


def test_validator_rejects_symlink_report(tmp_path: Path) -> None:
    # Given: the expected report path is replaced by a symlink.
    output = tmp_path / "evidence"
    images = _write_fixture(output)
    report = output / "report-001.json"
    external = tmp_path / "external.json"
    external.write_bytes(report.read_bytes())
    report.unlink()
    report.symlink_to(external)

    # When/Then: finalization refuses non-regular evidence.
    with pytest.raises(validator.ScanRejectedError, match="not a regular file"):
        _finalize(output, images)
    assert not (output / "COMPLETE").exists()


def test_verifier_detects_report_tamper(tmp_path: Path) -> None:
    # Given: a complete clean set whose report bytes are later changed.
    output = tmp_path / "evidence"
    images = _write_fixture(output)
    _finalize(output, images)
    (output / "report-001.json").write_text("{}", encoding="utf-8")

    # When/Then: independent verification rejects the hash mismatch.
    with pytest.raises(validator.ScanRejectedError, match="digest mismatch"):
        validator.verify(output)


def test_verifier_rejects_incomplete_marker(tmp_path: Path) -> None:
    # Given: valid artifacts exist but the last-written marker is missing.
    output = tmp_path / "evidence"
    images = _write_fixture(output)
    _finalize(output, images)
    (output / "COMPLETE").unlink()

    # When/Then: verification cannot infer completion from other files.
    with pytest.raises(validator.ScanRejectedError, match="COMPLETE"):
        validator.verify(output)


def test_human_artifacts_exclude_secret_shapes_and_package_inventory(
    tmp_path: Path,
) -> None:
    # Given: raw Trivy details contain package inventory and credential/JWT shapes.
    output = tmp_path / "evidence"
    secret = "OPENAI_API_KEY=sk-test-never-publish"
    jwt = "eyJabcdefghijk.eyJabcdefghijk.abcdefghijklm"
    report = json.dumps(
        {
            "SchemaVersion": 2,
            "Metadata": {"ImageID": IMAGE_ID, "RepoDigests": [REPO_DIGEST]},
            "Results": [
                {
                    "Target": "site-packages",
                    "Class": "lang-pkgs",
                    "Type": "python-pkg",
                    "Vulnerabilities": [
                        {
                            "Severity": "CRITICAL",
                            "VulnerabilityID": "CVE-2026-99999",
                            "PkgName": secret,
                            "Description": jwt,
                        }
                    ]
                }
            ],
        }
    )
    images = _write_fixture(output, report=report, scanner_exit=1)

    # When: the blocked result is finalized.
    blocked = _finalize(output, images)

    # Then: safe counts/CVE remain while secret and inventory material stay raw-only.
    human = (output / "summary.json").read_text(encoding="utf-8") + (
        output / "manifest.json"
    ).read_text(encoding="utf-8")
    assert blocked is True
    assert "CVE-2026-99999" in human
    assert secret not in human
    assert jwt not in human
    assert secret in (output / "report-001.json").read_text(encoding="utf-8")


def test_findings_artifact_is_allowlisted_redacted_and_hash_bound(
    tmp_path: Path,
) -> None:
    # Given: Trivy reports one blocking finding, one LOW finding, and unsafe extras.
    output = tmp_path / "evidence"
    secret = "authorization=Bearer never-publish"
    report = json.dumps(
        {
            "SchemaVersion": 2,
            "Metadata": {"ImageID": IMAGE_ID, "RepoDigests": [REPO_DIGEST]},
            "Results": [
                {
                    "Target": "usr/lib/pilot-api.jar",
                    "Class": "lang-pkgs",
                    "Type": "jar",
                    "Packages": [{"Name": "unrelated-inventory"}],
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2026-11111",
                            "PkgName": "example-lib",
                            "InstalledVersion": "1.0.0",
                            "FixedVersion": "1.0.1",
                            "Severity": "HIGH",
                            "Status": "fixed",
                            "DataSource": {
                                "ID": "ghsa",
                                "Name": "GitHub Security Advisory",
                                "URL": "https://github.com/advisories",
                            },
                            "Description": secret,
                            "Title": "must-not-survive",
                            "PrimaryURL": "https://example.test/CVE-2026-11111",
                            "Layer": {"Digest": "sha256:" + "9" * 64},
                            "Unexpected": {"token": secret},
                        },
                        {
                            "VulnerabilityID": "CVE-2026-22222",
                            "PkgName": "low-lib",
                            "InstalledVersion": "2.0.0",
                            "Severity": "LOW",
                            "Description": secret,
                        },
                    ],
                }
            ],
        }
    )
    images = _write_fixture(output, report=report, scanner_exit=1)

    # When: blocked evidence is finalized.
    assert _finalize(output, images) is True

    # Then: only the required HIGH record survives, bound to image and target.
    findings_path = output / "findings.json"
    findings_bytes = findings_path.read_bytes()
    assert json.loads(findings_bytes) == {
        "schema_version": 1,
        "threshold": ["HIGH", "CRITICAL"],
        "findings": [
            {
                "ImageRef": "pilot-api:test",
                "ImageID": IMAGE_ID,
                "RepoDigests": [REPO_DIGEST],
                "Target": "usr/lib/pilot-api.jar",
                "Class": "lang-pkgs",
                "Type": "jar",
                "VulnerabilityID": "CVE-2026-11111",
                "PkgName": "example-lib",
                "InstalledVersion": "1.0.0",
                "FixedVersion": "1.0.1",
                "Severity": "HIGH",
                "Status": "fixed",
                "PrimaryDataSource": "ghsa",
            }
        ],
    }
    rendered = findings_bytes.decode()
    for forbidden in (
        secret,
        "unrelated-inventory",
        "CVE-2026-22222",
        "Description",
        "Title",
        "PrimaryURL",
        "Layer",
        "URL",
        "Unexpected",
    ):
        assert forbidden not in rendered

    digest = hashlib.sha256(findings_bytes).hexdigest()
    manifest = json.loads((output / "manifest.json").read_bytes())
    complete = json.loads((output / "COMPLETE").read_bytes())
    assert manifest["files"]["findings.json"] == digest
    assert manifest["findings"] == {
        "path": "findings.json",
        "sha256": digest,
        "count": 1,
    }
    assert complete["findings_sha256"] == digest
    validator.verify(output)


def test_verifier_rejects_rebound_secret_shaped_unexpected_finding_field(
    tmp_path: Path,
) -> None:
    # Given: a valid record is extended with a secret and every digest is rebound.
    output = tmp_path / "evidence"
    report = _blocking_report(
        [{"Severity": "HIGH", "VulnerabilityID": "CVE-2026-33333"}]
    )
    _finalize(output, _write_fixture(output, report=report, scanner_exit=1))
    findings_path = output / "findings.json"
    findings = json.loads(findings_path.read_bytes())
    findings["findings"][0]["Description"] = "token=never-publish"
    findings_bytes = (json.dumps(findings, sort_keys=True, separators=(",", ":")) + "\n").encode()
    findings_path.write_bytes(findings_bytes)
    findings_sha = hashlib.sha256(findings_bytes).hexdigest()
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["files"]["findings.json"] = findings_sha
    manifest["findings"]["sha256"] = findings_sha
    manifest_bytes = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    manifest_path.write_bytes(manifest_bytes)
    (output / "COMPLETE").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "findings_sha256": findings_sha,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )

    # When/Then: structural allowlisting rejects internally consistent tampering.
    with pytest.raises(validator.ScanRejectedError, match="finding"):
        validator.verify(output)


def test_findings_preserve_missing_package_and_fix_as_null(tmp_path: Path) -> None:
    # Given: Trivy emits a blocking advisory without package or version fields.
    output = tmp_path / "evidence"
    report = _blocking_report(
        [{"Severity": "CRITICAL", "VulnerabilityID": "GHSA-xxxx-yyyy-zzzz"}]
    )

    # When: the report is compacted.
    _finalize(output, _write_fixture(output, report=report, scanner_exit=1))

    # Then: absence is explicit and cannot be confused with dropped records.
    finding = json.loads((output / "findings.json").read_bytes())["findings"][0]
    assert finding["PkgName"] is None
    assert finding["InstalledVersion"] is None
    assert finding["FixedVersion"] is None
    assert finding["PrimaryDataSource"] is None
    assert "Status" not in finding
    validator.verify(output)


def test_findings_are_deterministic_across_trivy_ordering(tmp_path: Path) -> None:
    # Given: equivalent reports present the same findings in opposite order.
    vulnerabilities: list[dict[str, validator.JsonValue]] = [
        {"Severity": "HIGH", "VulnerabilityID": "CVE-2026-50002", "PkgName": "z-lib"},
        {"Severity": "CRITICAL", "VulnerabilityID": "CVE-2026-50001", "PkgName": "a-lib"},
    ]
    rendered: list[bytes] = []
    for name, ordered in (("forward", vulnerabilities), ("reverse", list(reversed(vulnerabilities)))):
        output = tmp_path / name
        report = _blocking_report(ordered)
        _finalize(output, _write_fixture(output, report=report, scanner_exit=1))
        rendered.append((output / "findings.json").read_bytes())

    # When/Then: canonical sorting produces byte-identical compact evidence.
    assert rendered[0] == rendered[1]


def test_findings_bind_each_record_to_its_image_identity(tmp_path: Path) -> None:
    # Given: two blocked image reports carry distinct IDs and repository digests.
    output = tmp_path / "evidence"
    first = _write_fixture(
        output,
        report=_blocking_report(
            [{"Severity": "HIGH", "VulnerabilityID": "CVE-2026-60001"}],
            target="api.jar",
        ),
        scanner_exit=1,
    )[0]
    second_id = "sha256:" + "2" * 64
    second_digest = "registry.test/pilot-ai@" + second_id
    (output / "report-002.json").write_text(
        _blocking_report(
            [{"Severity": "CRITICAL", "VulnerabilityID": "CVE-2026-60002"}],
            image_id=second_id,
            repo_digest=second_digest,
            target="ai.whl",
        ),
        encoding="utf-8",
    )
    (output / "scanner-002.stderr").write_text("", encoding="utf-8")
    second = validator.ImageInput(
        "pilot-ai:test", second_id, (second_digest,), "report-002.json", 1
    )

    # When: both reports are finalized into one gate result.
    assert _finalize(output, (first, second)) is True

    # Then: each finding repeats the exact bound identity of its source image.
    findings = json.loads((output / "findings.json").read_bytes())["findings"]
    by_identifier = {finding["VulnerabilityID"]: finding for finding in findings}
    assert (by_identifier["CVE-2026-60001"]["ImageRef"], by_identifier["CVE-2026-60001"]["ImageID"]) == ("pilot-api:test", IMAGE_ID)
    assert by_identifier["CVE-2026-60001"]["RepoDigests"] == [REPO_DIGEST]
    assert (by_identifier["CVE-2026-60002"]["ImageRef"], by_identifier["CVE-2026-60002"]["ImageID"]) == ("pilot-ai:test", second_id)
    assert by_identifier["CVE-2026-60002"]["RepoDigests"] == [second_digest]
    validator.verify(output)


@pytest.mark.parametrize("mutation", ["tamper", "missing"])
def test_verifier_rejects_tampered_or_missing_findings(
    tmp_path: Path, mutation: str
) -> None:
    # Given: a complete clean evidence set loses findings bytes or their integrity.
    output = tmp_path / "evidence"
    _finalize(output, _write_fixture(output))
    findings_path = output / "findings.json"
    if mutation == "tamper":
        findings_path.write_bytes(findings_path.read_bytes() + b" ")
    else:
        findings_path.unlink()

    # When/Then: direct and transitive digest checks both fail closed.
    with pytest.raises(validator.ScanRejectedError, match="findings"):
        validator.verify(output)
