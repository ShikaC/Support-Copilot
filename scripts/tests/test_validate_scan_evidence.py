from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from scripts import publish_scan_evidence as publisher
from scripts.validate_scan_evidence import EvidenceRejectedError, validate_evidence


def publish_valid_evidence(root: Path) -> Path:
    inventory = root / "source-inventory"
    report = root / "source-report"
    stderr = root / "source-stderr"
    inventory.write_bytes(b"inventory\n")
    report.write_bytes(b"report\n")
    stderr.write_bytes(b"x")
    request = publisher.PublishRequest(
        evidence_root=root,
        label=publisher.EvidenceLabel("python-production"),
        lock_type=publisher.LockType("osv-scanner"),
        inventory=inventory,
        report=report,
        scanner_stderr=stderr,
        scanner_exit_status=1,
        outcome=publisher.ScanOutcome.VULNERABILITY,
        vulnerability_occurrences=1,
        report_accepted=True,
    )
    return publisher.publish(request)


def rewrite_provenance(destination: Path, field: str, value: bool | float | str) -> None:
    provenance_path = destination / "provenance.json"
    provenance = json.loads(provenance_path.read_bytes())
    provenance[field] = value
    provenance_bytes = (json.dumps(provenance, sort_keys=True) + "\n").encode()
    provenance_path.write_bytes(provenance_bytes)
    complete = {
        "provenance_sha256": hashlib.sha256(provenance_bytes).hexdigest(),
        "schema_version": 1,
    }
    (destination / "COMPLETE").write_text(json.dumps(complete, sort_keys=True) + "\n")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", True),
        ("schema_version", 2.0),
        ("scanner_exit_status", True),
        ("scanner_exit_status", 1.0),
        ("stderr_size", True),
        ("stderr_size", 1.0),
        ("vulnerability_occurrences", True),
        ("vulnerability_occurrences", 1.0),
    ],
)
def test_provenance_rejects_non_exact_integer_fields(
    tmp_path: Path, field: str, value: bool | float
) -> None:
    # Given valid public-API evidence with one integer field replaced by bool or float.
    destination = publish_valid_evidence(tmp_path)
    rewrite_provenance(destination, field, value)

    # When the strict validator reads the tampered provenance.
    # Then the completed evidence is rejected at the JSON type boundary.
    with pytest.raises(EvidenceRejectedError):
        validate_evidence(destination)


@pytest.mark.parametrize("value", [True, 1.0])
def test_complete_rejects_non_exact_schema_version(tmp_path: Path, value: bool | float) -> None:
    # Given valid evidence with a bool or float COMPLETE schema version.
    destination = publish_valid_evidence(tmp_path)
    complete_path = destination / "COMPLETE"
    complete = json.loads(complete_path.read_bytes())
    complete["schema_version"] = value
    complete_path.write_text(json.dumps(complete, sort_keys=True) + "\n")

    # When the strict validator reads the acceptance marker.
    # Then numeric equality cannot substitute for exact JSON integer type.
    with pytest.raises(EvidenceRejectedError):
        validate_evidence(destination)


def test_wrong_digest_is_rejected(tmp_path: Path) -> None:
    # Given completed evidence whose provenance names a wrong inventory digest.
    destination = publish_valid_evidence(tmp_path)
    rewrite_provenance(destination, "inventory_sha256", "0" * 64)

    # When validation recomputes payload digests, then it rejects the mismatch.
    with pytest.raises(EvidenceRejectedError, match="inventory digest mismatch"):
        validate_evidence(destination)


def test_unexpected_entry_is_rejected(tmp_path: Path) -> None:
    # Given completed evidence with an extra unprovenanced entry.
    destination = publish_valid_evidence(tmp_path)
    (destination / "unexpected").write_bytes(b"not accepted\n")

    # When validation compares the fixed evidence names, then it rejects the entry.
    with pytest.raises(EvidenceRejectedError, match="entries are inconsistent"):
        validate_evidence(destination)


def test_complete_older_than_every_payload_is_rejected(tmp_path: Path) -> None:
    # Given COMPLETE with an mtime strictly older than every published payload.
    destination = publish_valid_evidence(tmp_path)
    payload_time = 2_000_000_000_000_000_000
    for name in ("inventory", "report", "stderr", "provenance.json"):
        os.utime(destination / name, ns=(payload_time, payload_time))
    os.utime(destination / "COMPLETE", ns=(payload_time - 1_000_000, payload_time - 1_000_000))

    # When validation enforces last-state acceptance, then stale COMPLETE is rejected.
    with pytest.raises(EvidenceRejectedError, match="not created last"):
        validate_evidence(destination)
