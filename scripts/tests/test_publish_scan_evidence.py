from __future__ import annotations

import hashlib
import json
import os
import select
import signal
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import publish_scan_evidence as publisher


def make_request(
    root: Path,
    *,
    outcome: publisher.ScanOutcome = publisher.ScanOutcome.CLEAN,
    status: int = 0,
    occurrences: int | None = 0,
    report: bytes | None = b'{"results": []}\n',
    accepted: bool = True,
) -> publisher.PublishRequest:
    inventory = root / "source-inventory"
    stderr = root / "source-stderr"
    inventory.write_bytes(b"inventory\n")
    stderr.write_bytes(b"sanitized stderr\n")
    report_path = None
    if report is not None:
        report_path = root / "source-report"
        report_path.write_bytes(report)
    return publisher.PublishRequest(
        evidence_root=root,
        label=publisher.EvidenceLabel("python-production"),
        lock_type=publisher.LockType("osv-scanner"),
        inventory=inventory,
        report=report_path,
        scanner_stderr=stderr,
        scanner_exit_status=status,
        outcome=outcome,
        vulnerability_occurrences=occurrences,
        report_accepted=accepted,
    )


def test_sigkill_leaves_evidence_incomplete_and_rejected(tmp_path: Path) -> None:
    # Given a child publisher blocked immediately after destination fd capture.
    ready_read, ready_write = os.pipe()
    block_read, block_write = os.pipe()
    child = """
import os, sys
from pathlib import Path
from scripts import publish_scan_evidence as module

root = Path(sys.argv[1])
ready_fd, block_fd = int(sys.argv[2]), int(sys.argv[3])
request = module.PublishRequest(
    root, module.EvidenceLabel("python-production"), module.LockType("osv-scanner"),
    root / "source-inventory", root / "source-report", root / "source-stderr",
    0, module.ScanOutcome.CLEAN, 0, True,
)
def barrier_copy(destination_fd, name, source_fd):
    os.write(ready_fd, b"1")
    os.read(block_fd, 1)
    raise AssertionError("barrier unexpectedly released")
module._copy_source = barrier_copy
module.publish(request)
"""
    request = make_request(tmp_path)
    process = subprocess.Popen(
        [sys.executable, "-c", child, str(tmp_path), str(ready_write), str(block_read)],
        pass_fds=(ready_write, block_read),
    )
    os.close(ready_write)
    os.close(block_read)
    try:
        ready, _, _ = select.select([ready_read], [], [], 3.0)
        assert ready and os.read(ready_read, 1) == b"1"

        # When the parent kills the blocked publisher.
        process.send_signal(signal.SIGKILL)
        assert process.wait(timeout=3.0) == -signal.SIGKILL

        # Then the claimed directory has no acceptance marker and cannot be read.
        destination = request.evidence_root / request.label
        assert destination.is_dir()
        assert not (destination / "COMPLETE").exists()
        with pytest.raises(publisher.EvidenceRejectedError):
            publisher.validate_evidence(destination)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3.0)
        os.close(ready_read)
        os.close(block_write)


def test_replacement_survives_copy_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given a seam that renames the claimed inode and installs a replacement.
    request = make_request(tmp_path)
    destination = tmp_path / request.label
    owned = tmp_path / "owned-renamed"
    sentinel = b"replacement-must-survive\x00"

    def replace_then_fail(destination_fd: int, name: str, source_fd: int) -> publisher.FileDigest:
        os.rename(destination, owned)
        destination.mkdir()
        (destination / "sentinel").write_bytes(sentinel)
        raise OSError("injected replacement failure")

    monkeypatch.setattr(publisher, "_copy_source", replace_then_fail)

    # When publication fails after destination fd capture.
    with pytest.raises(OSError, match="injected replacement failure"):
        publisher.publish(request)

    # Then cleanup preserves the replacement and accepts neither directory.
    assert (destination / "sentinel").read_bytes() == sentinel
    assert not (destination / "COMPLETE").exists()
    assert owned.is_dir() and not (owned / "COMPLETE").exists()
    with pytest.raises(publisher.EvidenceRejectedError):
        publisher.validate_evidence(owned)


def test_owned_destination_is_removed_on_copy_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given an unexpected copy failure after an uncontested claim.
    request = make_request(tmp_path)

    def fail_copy(destination_fd: int, name: str, source_fd: int) -> publisher.FileDigest:
        raise OSError("injected copy failure")

    monkeypatch.setattr(publisher, "_copy_source", fail_copy)

    # When publication propagates the failure.
    with pytest.raises(OSError, match="injected copy failure"):
        publisher.publish(request)

    # Then inode-bound cleanup removes only the owned destination.
    assert not (tmp_path / request.label).exists()


@pytest.mark.parametrize(
    ("outcome", "status", "occurrences", "report", "accepted"),
    [
        (publisher.ScanOutcome.CLEAN, 0, 0, b"clean-report\n", True),
        (publisher.ScanOutcome.VULNERABILITY, 1, 2, b"vulnerable-report\n", True),
        (publisher.ScanOutcome.OPERATIONAL, 129, None, None, False),
        (publisher.ScanOutcome.INVALID_REPORT, 0, None, b"{\n", False),
    ],
)
def test_all_outcomes_publish_exact_complete_evidence(
    tmp_path: Path,
    outcome: publisher.ScanOutcome,
    status: int,
    occurrences: int | None,
    report: bytes | None,
    accepted: bool,
) -> None:
    # Given a consistent request for one scanner outcome.
    request = make_request(
        tmp_path,
        outcome=outcome,
        status=status,
        occurrences=occurrences,
        report=report,
        accepted=accepted,
    )

    # When evidence is published and read through the acceptance boundary.
    destination = publisher.publish(request)
    publisher.validate_evidence(destination)

    # Then bytes, outcome, provenance, and digests are exact.
    assert (destination / "inventory").read_bytes() == request.inventory.read_bytes()
    assert (destination / "stderr").read_bytes() == request.scanner_stderr.read_bytes()
    if report is None:
        assert not (destination / "report").exists()
    else:
        assert (destination / "report").read_bytes() == report
    provenance = json.loads((destination / "provenance.json").read_bytes())
    assert provenance["outcome"] == outcome
    assert provenance["scanner_exit_status"] == status
    assert provenance["vulnerability_occurrences"] == occurrences
    assert provenance["inventory_sha256"] == hashlib.sha256(request.inventory.read_bytes()).hexdigest()
    assert provenance["stderr_sha256"] == hashlib.sha256(request.scanner_stderr.read_bytes()).hexdigest()
    expected_report_digest = None if report is None else hashlib.sha256(report).hexdigest()
    assert provenance["report_sha256"] == expected_report_digest
    assert (destination / "COMPLETE").stat().st_mtime_ns >= (
        destination / "provenance.json"
    ).stat().st_mtime_ns


def test_existing_destination_is_never_replaced(tmp_path: Path) -> None:
    # Given an existing destination with caller-owned bytes.
    request = make_request(tmp_path)
    destination = tmp_path / request.label
    destination.mkdir()
    sentinel = destination / "sentinel"
    sentinel.write_bytes(b"preexisting\n")

    # When publication attempts its no-replace claim.
    with pytest.raises(publisher.DestinationExistsError):
        publisher.publish(request)

    # Then the preexisting destination is byte-identical and incomplete.
    assert sentinel.read_bytes() == b"preexisting\n"
    assert not (destination / "COMPLETE").exists()


@pytest.mark.parametrize(
    ("label", "remove_report"),
    [
        (publisher.EvidenceLabel("../escape"), False),
        (publisher.EvidenceLabel("python-production"), True),
    ],
)
def test_malformed_or_inconsistent_request_is_rejected(
    tmp_path: Path, label: publisher.EvidenceLabel, remove_report: bool
) -> None:
    # Given malformed boundary data or a clean outcome without a report.
    original = make_request(tmp_path)
    request = replace(original, label=label, report=None if remove_report else original.report)

    # When publication parses the request contract, then it rejects before claiming.
    with pytest.raises(publisher.InvalidPublishRequestError):
        publisher.publish(request)
    assert not (tmp_path / request.label).exists()
