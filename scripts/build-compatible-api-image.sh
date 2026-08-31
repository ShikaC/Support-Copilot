#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly REPOSITORY_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
readonly PACKAGING_LABEL="io.support-copilot.packaging-dockerfile-sha256"
readonly OCI_REVISION_LABEL="org.opencontainers.image.revision"
readonly PLATFORM="linux/amd64"
readonly TEMP_PREFIX="support-copilot-compatible-api."
readonly TEMP_IMAGE_REPOSITORY="support-copilot-compatible-api-temp"
readonly LOCK_PARENT_INPUT="/tmp"
readonly LOCK_ROOT_PREFIX=".support-copilot-compatible-api-locks"
readonly IMAGE_LOCK_FD=9

temporary_dir=""
temporary_parent=""
temporary_name=""
temporary_parent_device=""
temporary_parent_inode=""
temporary_device=""
temporary_inode=""
temporary_uid=""
temporary_mode=""
temporary_image=""
temporary_image_cleanup_required=0
caller_tag_owned=0
validated_image_id=""
evidence_reserved=0
evidence_complete=0
evidence_parent=""
evidence_name=""
evidence_parent_device=""
evidence_parent_inode=""
evidence_device=""
evidence_inode=""
evidence_uid=""
evidence_mode=""
evidence_token=""
pending_sha256=""
pending_temp_sha256=""
manifest_sha256=""
manifest_temp_sha256=""
complete_sha256=""
complete_temp_sha256=""
preserve_recoverable_evidence=0
image_lock_acquired=0
image_lock_parent=""
image_lock_parent_device=""
image_lock_parent_inode=""
image_lock_root_name=""
image_lock_name=""
image_lock_root_device=""
image_lock_root_inode=""
image_lock_device=""
image_lock_inode=""
image_lock_uid=""
image_lock_mode=""
image_lock_owner=""
image_lock_path=""

fail() {
  printf 'error: %s\n' "$1" >&2
  exit 1
}

usage() {
  printf '%s\n' 'usage: build-compatible-api-image.sh --revision <compatible-ref> --image <image-ref> --evidence-dir <new-directory>' >&2
}

require_command() {
  local executable="$1"
  if [[ "$executable" == */* ]]; then
    [[ -x "$executable" ]] || fail "required executable is not executable: $executable"
  else
    command -v -- "$executable" >/dev/null 2>&1 || fail "required executable is unavailable: $executable"
  fi
}

sha256_file() {
  shasum -a 256 -- "$1" | awk '{print $1}'
}

docker_command() {
  if [[ "$DOCKER_USE_SUDO" == "1" ]]; then
    "$TIMEOUT_BIN" "$DOCKER_TIMEOUT_SECONDS" sudo -n -- "$DOCKER_BIN" "$@"
  else
    "$TIMEOUT_BIN" "$DOCKER_TIMEOUT_SECONDS" "$DOCKER_BIN" "$@"
  fi
}

path_identity() {
  "$PYTHON_BIN" - "$1" <<'PY'
import os
import stat
import sys

value = os.lstat(sys.argv[1])
kind = "directory" if stat.S_ISDIR(value.st_mode) and not stat.S_ISLNK(value.st_mode) else "other"
print(f"{value.st_dev}:{value.st_ino}:{value.st_uid}:{stat.S_IMODE(value.st_mode):o}:{kind}")
PY
}

acquire_image_lock() {
  local lock_result lock_status
  lock_result="$("$PYTHON_BIN" - "$image_lock_parent" "$image_lock_parent_device" \
    "$image_lock_parent_inode" "$image_lock_root_name" "$image_lock_name" "$image_lock_owner" <<'PY'
import os
import stat
import sys

parent, expected_parent_device, expected_parent_inode, root_name, lock_name, _owner = sys.argv[1:]
expected_parent = (int(expected_parent_device), int(expected_parent_inode))
directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
parent_fd = os.open(parent, directory_flags)
try:
    parent_stat = os.fstat(parent_fd)
    if (parent_stat.st_dev, parent_stat.st_ino) != expected_parent:
        raise SystemExit(3)
    try:
        os.mkdir(root_name, 0o700, dir_fd=parent_fd)
    except FileExistsError:
        pass
    root_fd = os.open(root_name, directory_flags, dir_fd=parent_fd)
    try:
        root_stat = os.fstat(root_fd)
        if (
            not stat.S_ISDIR(root_stat.st_mode)
            or root_stat.st_uid != os.getuid()
            or stat.S_IMODE(root_stat.st_mode) != 0o700
        ):
            raise SystemExit(3)
        lock_fd = os.open(
            lock_name,
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
            0o600,
            dir_fd=root_fd,
        )
        try:
            lock_stat = os.fstat(lock_fd)
            if (
                not stat.S_ISREG(lock_stat.st_mode)
                or lock_stat.st_uid != os.getuid()
                or stat.S_IMODE(lock_stat.st_mode) != 0o600
                or lock_stat.st_nlink != 1
            ):
                raise SystemExit(3)
            os.fsync(root_fd)
            print(
                f"{root_stat.st_dev}:{root_stat.st_ino}:"
                f"{lock_stat.st_dev}:{lock_stat.st_ino}:"
                f"{lock_stat.st_uid}:{stat.S_IMODE(lock_stat.st_mode):o}"
            )
        finally:
            os.close(lock_fd)
    finally:
        os.close(root_fd)
finally:
    os.close(parent_fd)
PY
  )" || fail 'cannot prepare caller image cooperative lock'
  IFS=':' read -r image_lock_root_device image_lock_root_inode image_lock_device \
    image_lock_inode image_lock_uid image_lock_mode <<<"$lock_result"
  image_lock_path="$image_lock_parent/$image_lock_root_name/$image_lock_name"
  if ! exec 9<>"$image_lock_path"; then
    fail 'cannot open caller image cooperative lock'
  fi
  set +e
  "$PYTHON_BIN" - "$IMAGE_LOCK_FD" "$image_lock_parent" "$image_lock_parent_device" \
    "$image_lock_parent_inode" "$image_lock_root_name" "$image_lock_name" "$image_lock_owner" \
    "$image_lock_root_device" "$image_lock_root_inode" "$image_lock_device" "$image_lock_inode" \
    "$image_lock_uid" "$image_lock_mode" <<'PY'
import fcntl
import os
import stat
import sys

(
    descriptor,
    parent,
    parent_device,
    parent_inode,
    root_name,
    lock_name,
    owner,
    root_device,
    root_inode,
    lock_device,
    lock_inode,
    lock_uid,
    lock_mode,
) = sys.argv[1:]
descriptor = int(descriptor)
expected_parent = (int(parent_device), int(parent_inode))
expected_root = (int(root_device), int(root_inode))
expected_lock = (int(lock_device), int(lock_inode), int(lock_uid), int(lock_mode, 8))
directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
parent_fd = os.open(parent, directory_flags)
try:
    parent_stat = os.fstat(parent_fd)
    if (parent_stat.st_dev, parent_stat.st_ino) != expected_parent:
        raise SystemExit(3)
    root_fd = os.open(root_name, directory_flags, dir_fd=parent_fd)
    try:
        root_stat = os.fstat(root_fd)
        if (root_stat.st_dev, root_stat.st_ino) != expected_root:
            raise SystemExit(3)
        path_fd = os.open(lock_name, os.O_RDWR | os.O_NOFOLLOW, dir_fd=root_fd)
        try:
            descriptor_stat = os.fstat(descriptor)
            path_stat = os.fstat(path_fd)
            identity = (
                descriptor_stat.st_dev,
                descriptor_stat.st_ino,
                descriptor_stat.st_uid,
                stat.S_IMODE(descriptor_stat.st_mode),
            )
            if (
                identity != expected_lock
                or (path_stat.st_dev, path_stat.st_ino) != expected_lock[:2]
                or not stat.S_ISREG(descriptor_stat.st_mode)
                or descriptor_stat.st_nlink != 1
            ):
                raise SystemExit(3)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise SystemExit(4)
            current = os.stat(lock_name, dir_fd=root_fd, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != expected_lock[:2] or not stat.S_ISREG(current.st_mode):
                raise SystemExit(3)
            os.ftruncate(descriptor, 0)
            os.lseek(descriptor, 0, os.SEEK_SET)
            payload = (owner + "\n").encode()
            while payload:
                payload = payload[os.write(descriptor, payload):]
            os.fsync(descriptor)
        finally:
            os.close(path_fd)
    finally:
        os.close(root_fd)
finally:
    os.close(parent_fd)
PY
  lock_status=$?
  set -e
  if (( lock_status == 4 )); then
    exec 9>&-
    fail 'caller image cooperative lock is already held'
  fi
  if (( lock_status != 0 )); then
    exec 9>&-
    fail 'cannot acquire caller image cooperative lock'
  fi
  image_lock_acquired=1
}

release_image_lock() {
  local release_status
  set +e
  "$PYTHON_BIN" - "$IMAGE_LOCK_FD" "$image_lock_parent" "$image_lock_parent_device" "$image_lock_parent_inode" \
    "$image_lock_root_name" "$image_lock_name" "$image_lock_owner" "$image_lock_root_device" \
    "$image_lock_root_inode" "$image_lock_device" "$image_lock_inode" "$image_lock_uid" \
    "$image_lock_mode" <<'PY'
import fcntl
import os
import stat
import sys

(
    descriptor,
    parent,
    parent_device,
    parent_inode,
    root_name,
    lock_name,
    owner,
    root_device,
    root_inode,
    lock_device,
    lock_inode,
    lock_uid,
    lock_mode,
) = sys.argv[1:]
descriptor = int(descriptor)
expected_parent = (int(parent_device), int(parent_inode))
expected_root = (int(root_device), int(root_inode))
expected_lock = (int(lock_device), int(lock_inode), int(lock_uid), int(lock_mode, 8))
directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
parent_fd = os.open(parent, directory_flags)
try:
    parent_stat = os.fstat(parent_fd)
    if (parent_stat.st_dev, parent_stat.st_ino) != expected_parent:
        raise SystemExit(3)
    root_fd = os.open(root_name, directory_flags, dir_fd=parent_fd)
    try:
        root_stat = os.fstat(root_fd)
        if (root_stat.st_dev, root_stat.st_ino) != expected_root:
            raise SystemExit(3)
        lock_fd = os.open(lock_name, os.O_RDWR | os.O_NOFOLLOW, dir_fd=root_fd)
        try:
            lock_stat = os.fstat(lock_fd)
            descriptor_stat = os.fstat(descriptor)
            identity = (
                descriptor_stat.st_dev,
                descriptor_stat.st_ino,
                descriptor_stat.st_uid,
                stat.S_IMODE(descriptor_stat.st_mode),
            )
            if (
                identity != expected_lock
                or (lock_stat.st_dev, lock_stat.st_ino) != expected_lock[:2]
                or not stat.S_ISREG(descriptor_stat.st_mode)
                or descriptor_stat.st_nlink != 1
            ):
                raise SystemExit(3)
            os.lseek(descriptor, 0, os.SEEK_SET)
            if os.read(descriptor, 4096) != (owner + "\n").encode():
                raise SystemExit(3)
            os.ftruncate(descriptor, 0)
            os.fsync(descriptor)
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)
    finally:
        os.close(root_fd)
finally:
    os.close(parent_fd)
PY
  release_status=$?
  exec 9>&-
  set -e
  image_lock_acquired=0
  return "$release_status"
}

cleanup_owned_tree() {
  "$PYTHON_BIN" - "$temporary_parent" "$temporary_name" "$TEMP_PREFIX" \
    "$temporary_parent_device" "$temporary_parent_inode" "$temporary_device" \
    "$temporary_inode" "$temporary_uid" "$temporary_mode" <<'PY'
import os
import stat
import sys

parent, name, prefix = sys.argv[1:4]
expected = tuple(int(value) for value in sys.argv[4:9]) + (int(sys.argv[9], 8),)
if not name.startswith(prefix) or "/" in name:
    raise SystemExit(3)
flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
try:
    parent_fd = os.open(parent, flags)
except OSError:
    raise SystemExit(3)
try:
    parent_stat = os.fstat(parent_fd)
    if (parent_stat.st_dev, parent_stat.st_ino) != expected[:2]:
        raise SystemExit(3)
    try:
        root_fd = os.open(name, flags, dir_fd=parent_fd)
    except FileNotFoundError:
        raise SystemExit(0)
    try:
        root_stat = os.fstat(root_fd)
        identity = (
            root_stat.st_dev,
            root_stat.st_ino,
            root_stat.st_uid,
            stat.S_IMODE(root_stat.st_mode),
        )
        if identity != expected[2:] or not stat.S_ISDIR(root_stat.st_mode):
            raise SystemExit(3)

        def remove_contents(directory_fd):
            for entry in os.scandir(directory_fd):
                entry_stat = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(entry_stat.st_mode) and not stat.S_ISLNK(entry_stat.st_mode):
                    child_fd = os.open(entry.name, flags, dir_fd=directory_fd)
                    try:
                        remove_contents(child_fd)
                    finally:
                        os.close(child_fd)
                    os.rmdir(entry.name, dir_fd=directory_fd)
                else:
                    os.unlink(entry.name, dir_fd=directory_fd)

        remove_contents(root_fd)
    finally:
        os.close(root_fd)
    current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if (current.st_dev, current.st_ino) != expected[2:4] or not stat.S_ISDIR(current.st_mode):
        raise SystemExit(3)
    os.rmdir(name, dir_fd=parent_fd)
finally:
    os.close(parent_fd)
PY
}

cleanup_evidence_reservation() {
  "$PYTHON_BIN" - "$evidence_parent" "$evidence_name" "$evidence_parent_device" \
    "$evidence_parent_inode" "$evidence_device" "$evidence_inode" "$evidence_uid" \
    "$evidence_mode" "$evidence_token" "$pending_sha256" "$pending_temp_sha256" \
    "$manifest_sha256" "$manifest_temp_sha256" "$complete_sha256" \
    "$complete_temp_sha256" <<'PY'
import hashlib
import os
import stat
import sys

parent, name = sys.argv[1:3]
expected = tuple(int(value) for value in sys.argv[3:8]) + (int(sys.argv[8], 8),)
(
    token,
    pending_digest,
    pending_temp_digest,
    manifest_digest,
    manifest_temp_digest,
    complete_digest,
    complete_temp_digest,
) = sys.argv[9:]
expected_files = {
    f".pending.{token}.tmp": pending_temp_digest,
    ".pending.json": pending_digest,
    f".manifest.{token}.tmp": manifest_temp_digest,
    "manifest.json": manifest_digest,
    f".COMPLETE.{token}.tmp": complete_temp_digest,
    "COMPLETE": complete_digest,
}
flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
try:
    parent_fd = os.open(parent, flags)
except OSError:
    print("cleanup refused: evidence parent is unavailable", file=sys.stderr)
    raise SystemExit(3)
try:
    parent_stat = os.fstat(parent_fd)
    if (parent_stat.st_dev, parent_stat.st_ino) != expected[:2]:
        print("cleanup refused: evidence parent identity changed", file=sys.stderr)
        raise SystemExit(3)
    try:
        evidence_fd = os.open(name, flags, dir_fd=parent_fd)
    except FileNotFoundError:
        raise SystemExit(0)
    except OSError:
        print("cleanup refused: evidence reservation path changed", file=sys.stderr)
        raise SystemExit(3)
    try:
        evidence_stat = os.fstat(evidence_fd)
        identity = (
            evidence_stat.st_dev,
            evidence_stat.st_ino,
            evidence_stat.st_uid,
            stat.S_IMODE(evidence_stat.st_mode),
        )
        if identity != expected[2:] or not stat.S_ISDIR(evidence_stat.st_mode):
            print("cleanup refused: evidence reservation identity changed", file=sys.stderr)
            raise SystemExit(3)
        refused = []
        for entry in os.scandir(evidence_fd):
            digest = expected_files.get(entry.name)
            if not digest:
                refused.append(entry.name)
                continue
            value = entry.stat(follow_symlinks=False)
            if (
                not stat.S_ISREG(value.st_mode)
                or stat.S_ISLNK(value.st_mode)
                or value.st_uid != os.getuid()
                or stat.S_IMODE(value.st_mode) != 0o600
                or value.st_nlink != 1
            ):
                refused.append(entry.name)
                continue
            descriptor = os.open(entry.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=evidence_fd)
            try:
                current_digest = hashlib.sha256()
                while chunk := os.read(descriptor, 1024 * 1024):
                    current_digest.update(chunk)
            finally:
                os.close(descriptor)
            if current_digest.hexdigest() != digest:
                refused.append(entry.name)
                continue
            os.unlink(entry.name, dir_fd=evidence_fd)
        os.fsync(evidence_fd)
        if refused or os.listdir(evidence_fd):
            print(
                "cleanup refused: evidence reservation contains unexpected or changed artifacts: "
                + ",".join(sorted(refused)),
                file=sys.stderr,
            )
            raise SystemExit(3)
    finally:
        os.close(evidence_fd)
    current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    current_identity = (
        current.st_dev,
        current.st_ino,
        current.st_uid,
        stat.S_IMODE(current.st_mode),
    )
    if current_identity != expected[2:] or not stat.S_ISDIR(current.st_mode):
        print("cleanup refused: evidence reservation changed before removal", file=sys.stderr)
        raise SystemExit(3)
    os.rmdir(name, dir_fd=parent_fd)
    os.fsync(parent_fd)
finally:
    os.close(parent_fd)
PY
}

inspect_existing_evidence() {
  "$PYTHON_BIN" - "$evidence_parent" "$evidence_name" "$evidence_parent_device" \
    "$evidence_parent_inode" "$resolved_revision" "$image" "$source_archive_sha256" \
    "$packaging_dockerfile_sha256" "$PLATFORM" "$TEMP_IMAGE_REPOSITORY" <<'PY'
import hashlib
import json
import os
import re
import stat
import sys

(
    parent,
    name,
    parent_device,
    parent_inode,
    revision,
    image_ref,
    archive_digest,
    packaging_digest,
    platform,
    temporary_repository,
) = sys.argv[1:]
expected_parent = (int(parent_device), int(parent_inode))
directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
token_pattern = re.compile(r"[A-Za-z0-9]{8}")
temporary_pattern = re.compile(r"\.(pending|manifest|COMPLETE)\.([A-Za-z0-9]{8})\.tmp")


def load_json(content):
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    return json.loads(content, object_pairs_hook=reject_duplicates)


def digest(content):
    return hashlib.sha256(content).hexdigest()


parent_fd = os.open(parent, directory_flags)
try:
    parent_stat = os.fstat(parent_fd)
    if (parent_stat.st_dev, parent_stat.st_ino) != expected_parent:
        raise SystemExit("evidence parent identity changed")
    try:
        evidence_fd = os.open(name, directory_flags, dir_fd=parent_fd)
    except FileNotFoundError:
        print("absent")
        raise SystemExit(0)
    except OSError as error:
        raise SystemExit(f"evidence directory is unsafe: {error}")
    try:
        evidence_stat = os.fstat(evidence_fd)
        evidence_identity = (
            evidence_stat.st_dev,
            evidence_stat.st_ino,
            evidence_stat.st_uid,
            stat.S_IMODE(evidence_stat.st_mode),
        )
        if (
            not stat.S_ISDIR(evidence_stat.st_mode)
            or evidence_stat.st_uid != os.getuid()
            or stat.S_IMODE(evidence_stat.st_mode) != 0o700
        ):
            raise SystemExit("evidence directory ownership or mode is unsafe")

        contents = {}
        temporary_tokens = set()
        temporary_kinds = {}
        for entry in os.scandir(evidence_fd):
            if entry.name in {".pending.json", "manifest.json", "COMPLETE"}:
                pass
            else:
                match = temporary_pattern.fullmatch(entry.name)
                if match is None:
                    raise SystemExit(f"unexpected evidence artifact: {entry.name}")
                temporary_kinds[match.group(1)] = entry.name
                temporary_tokens.add(match.group(2))
            value = entry.stat(follow_symlinks=False)
            if (
                not stat.S_ISREG(value.st_mode)
                or stat.S_ISLNK(value.st_mode)
                or value.st_uid != os.getuid()
                or stat.S_IMODE(value.st_mode) != 0o600
                or value.st_nlink != 1
                or value.st_size > 1024 * 1024
            ):
                raise SystemExit(f"unsafe evidence artifact: {entry.name}")
            descriptor = os.open(entry.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=evidence_fd)
            try:
                value_after_open = os.fstat(descriptor)
                if (value_after_open.st_dev, value_after_open.st_ino) != (value.st_dev, value.st_ino):
                    raise SystemExit(f"evidence artifact changed: {entry.name}")
                chunks = bytearray()
                while chunk := os.read(descriptor, 1024 * 1024):
                    chunks.extend(chunk)
            finally:
                os.close(descriptor)
            contents[entry.name] = bytes(chunks)

        if len(temporary_tokens) > 1 or len(temporary_kinds) != len(temporary_tokens) and len(temporary_kinds) > 1:
            raise SystemExit("evidence temporary artifacts are ambiguous")

        pending_content = contents.get(".pending.json")
        pending = None
        pending_token = None
        temporary_ref = None
        if pending_content is not None:
            try:
                pending = load_json(pending_content)
            except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
                raise SystemExit(f"invalid pending evidence: {error}")
            expected_keys = {
                "schema_version",
                "state",
                "revision",
                "image_ref",
                "source_archive_sha256",
                "packaging_dockerfile_sha256",
                "platform",
                "temporary_image_ref",
                "token",
            }
            if not isinstance(pending, dict) or set(pending) != expected_keys:
                raise SystemExit("pending evidence schema mismatch")
            pending_token = pending["token"]
            if not isinstance(pending_token, str) or token_pattern.fullmatch(pending_token) is None:
                raise SystemExit("pending evidence token is unsafe")
            temporary_ref = f"{temporary_repository}:{revision[:12]}-{pending_token}"
            expected_pending = {
                "schema_version": 1,
                "state": "pending",
                "revision": revision,
                "image_ref": image_ref,
                "source_archive_sha256": archive_digest,
                "packaging_dockerfile_sha256": packaging_digest,
                "platform": platform,
                "temporary_image_ref": temporary_ref,
                "token": pending_token,
            }
            if type(pending["schema_version"]) is not int or pending != expected_pending:
                raise SystemExit("pending evidence does not bind this request")
            canonical_pending = (json.dumps(expected_pending, separators=(",", ":")) + "\n").encode()
            if pending_content != canonical_pending:
                raise SystemExit("pending evidence is not canonical")
            if temporary_tokens and temporary_tokens != {pending_token}:
                raise SystemExit("pending evidence temporary token mismatch")

        manifest_content = contents.get("manifest.json")
        manifest = None
        image_id = None
        manifest_digest = "-"
        complete_content_expected = None
        if manifest_content is not None:
            try:
                manifest = load_json(manifest_content)
            except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
                raise SystemExit(f"invalid manifest evidence: {error}")
            expected_keys = {
                "schema_version",
                "revision",
                "image_ref",
                "image_id",
                "source_archive_sha256",
                "packaging_dockerfile_sha256",
                "platform",
                "command_exit",
                "hash_binding",
            }
            if not isinstance(manifest, dict) or set(manifest) != expected_keys:
                raise SystemExit("manifest evidence schema mismatch")
            image_id = manifest["image_id"]
            if not isinstance(image_id, str) or re.fullmatch(r"sha256:[a-f0-9]{64}", image_id) is None:
                raise SystemExit("manifest image ID is unsafe")
            expected_manifest = {
                "schema_version": 1,
                "revision": revision,
                "image_ref": image_ref,
                "image_id": image_id,
                "source_archive_sha256": archive_digest,
                "packaging_dockerfile_sha256": packaging_digest,
                "platform": platform,
                "command_exit": {"git_archive": 0, "docker_build": 0, "docker_inspect": 0},
                "hash_binding": {
                    "oci_revision_label": revision,
                    "packaging_label": packaging_digest,
                    "source_archive_sha256": archive_digest,
                },
            }
            if type(manifest["schema_version"]) is not int or manifest != expected_manifest:
                raise SystemExit("manifest evidence does not bind this request")
            canonical_manifest = (json.dumps(expected_manifest, separators=(",", ":")) + "\n").encode()
            if manifest_content != canonical_manifest:
                raise SystemExit("manifest evidence is not canonical")
            manifest_digest = digest(manifest_content)
            complete_content_expected = f"manifest_sha256={manifest_digest}\n".encode()

        if pending is None and manifest is None:
            raise SystemExit("evidence directory is not an owned recoverable transaction")
        if pending is None and any(kind != "COMPLETE" for kind in temporary_kinds):
            raise SystemExit("manifest-only recovery has unexpected temporary artifacts")

        if ".pending.json" in contents and "pending" in temporary_kinds:
            if not pending_content.startswith(contents[temporary_kinds["pending"]]):
                raise SystemExit("pending temporary artifact is unrelated")
        if "manifest" in temporary_kinds:
            temporary_content = contents[temporary_kinds["manifest"]]
            if manifest_content is not None and not manifest_content.startswith(temporary_content):
                raise SystemExit("manifest temporary artifact is unrelated")
            if manifest_content is None and temporary_content not in (b"",) and not temporary_content.startswith(b"{"):
                raise SystemExit("manifest temporary artifact is malformed")
        if "COMPLETE" in temporary_kinds:
            if complete_content_expected is None:
                raise SystemExit("COMPLETE temporary artifact has no bound manifest")
            if not complete_content_expected.startswith(contents[temporary_kinds["COMPLETE"]]):
                raise SystemExit("COMPLETE temporary artifact is unrelated")

        state = "pending"
        complete_digest = "-"
        complete_content = contents.get("COMPLETE")
        if complete_content is not None:
            if pending is not None or temporary_kinds or complete_content_expected is None:
                raise SystemExit("completed evidence contains pending artifacts")
            if complete_content != complete_content_expected:
                raise SystemExit("COMPLETE evidence hash binding mismatch")
            state = "complete"
            complete_digest = digest(complete_content)

        token = pending_token or (next(iter(temporary_tokens)) if temporary_tokens else "-")
        hashes = {
            "pending": digest(pending_content) if pending_content is not None else "-",
            "pending_tmp": digest(contents[temporary_kinds["pending"]]) if "pending" in temporary_kinds else "-",
            "manifest": manifest_digest,
            "manifest_tmp": digest(contents[temporary_kinds["manifest"]]) if "manifest" in temporary_kinds else "-",
            "complete": complete_digest if complete_digest != "-" else (
                digest(complete_content_expected) if complete_content_expected is not None else "-"
            ),
            "complete_tmp": digest(contents[temporary_kinds["COMPLETE"]]) if "COMPLETE" in temporary_kinds else "-",
        }
        fields = [
            state,
            str(evidence_identity[0]),
            str(evidence_identity[1]),
            str(evidence_identity[2]),
            f"{evidence_identity[3]:o}",
            token,
            hashes["pending"],
            hashes["pending_tmp"],
            hashes["manifest"],
            hashes["manifest_tmp"],
            hashes["complete"],
            hashes["complete_tmp"],
            image_id or "-",
            temporary_ref or "-",
        ]
        print("\t".join(fields))
    finally:
        os.close(evidence_fd)
finally:
    os.close(parent_fd)
PY
}

validate_image_inspection() {
  local output="$1"
  local expected_id="$2"
  local inspected_id inspected_os inspected_arch inspected_revision inspected_packaging extra
  [[ "$output" != *$'\n'* ]] || return 1
  IFS='|' read -r inspected_id inspected_os inspected_arch inspected_revision inspected_packaging extra <<<"$output"
  [[ -z "${extra:-}" && "$inspected_id" =~ ^sha256:[a-f0-9]{64}$ ]] || return 1
  [[ -z "$expected_id" || "$inspected_id" == "$expected_id" ]] || return 1
  [[ "$inspected_os" == "linux" && "$inspected_arch" == "amd64" ]] || return 1
  [[ "$inspected_revision" == "$resolved_revision" ]] || return 1
  [[ "$inspected_packaging" == "$packaging_dockerfile_sha256" ]] || return 1
  checked_image_id="$inspected_id"
}

cleanup_recovery_temporary_tag() {
  local recovery_temporary_ref="$1"
  local recovery_expected_id="$2"
  local lookup_output lookup_status inspection_output inspection_status
  [[ "$recovery_expected_id" =~ ^sha256:[a-f0-9]{64}$ ]] || return 1
  [[ "$recovery_temporary_ref" != "-" ]] || return 0
  set +e
  lookup_output="$(docker_command image ls --quiet --no-trunc "$recovery_temporary_ref")"
  lookup_status=$?
  set -e
  (( lookup_status == 0 )) || return 1
  [[ -n "$lookup_output" ]] || return 0
  set +e
  inspection_output="$(docker_command image inspect --format "$inspect_format" "$recovery_temporary_ref")"
  inspection_status=$?
  set -e
  (( inspection_status == 0 )) || return 1
  validate_image_inspection "$inspection_output" "$recovery_expected_id" || return 1
  docker_command image rm "$recovery_temporary_ref" >/dev/null
}

prepare_evidence_for_complete() {
  "$PYTHON_BIN" - "$evidence_parent" "$evidence_name" "$evidence_parent_device" \
    "$evidence_parent_inode" "$evidence_device" "$evidence_inode" "$evidence_uid" \
    "$evidence_mode" "$evidence_token" "$pending_sha256" "$pending_temp_sha256" \
    "$manifest_sha256" "$manifest_temp_sha256" "$complete_temp_sha256" <<'PY'
import hashlib
import os
import stat
import sys

parent, name = sys.argv[1:3]
expected = tuple(int(value) for value in sys.argv[3:8]) + (int(sys.argv[8], 8),)
(
    token,
    pending_digest,
    pending_temp_digest,
    manifest_digest,
    manifest_temp_digest,
    complete_temp_digest,
) = sys.argv[9:]
allowed = {
    ".pending.json": pending_digest,
    f".pending.{token}.tmp": pending_temp_digest,
    "manifest.json": manifest_digest,
    f".manifest.{token}.tmp": manifest_temp_digest,
    f".COMPLETE.{token}.tmp": complete_temp_digest,
}
directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
parent_fd = os.open(parent, directory_flags)
try:
    parent_stat = os.fstat(parent_fd)
    if (parent_stat.st_dev, parent_stat.st_ino) != expected[:2]:
        raise SystemExit(2)
    evidence_fd = os.open(name, directory_flags, dir_fd=parent_fd)
    try:
        evidence_stat = os.fstat(evidence_fd)
        identity = (
            evidence_stat.st_dev,
            evidence_stat.st_ino,
            evidence_stat.st_uid,
            stat.S_IMODE(evidence_stat.st_mode),
        )
        if identity != expected[2:] or not stat.S_ISDIR(evidence_stat.st_mode):
            raise SystemExit(2)
        entries = sorted(os.listdir(evidence_fd))
        if "manifest.json" not in entries:
            raise SystemExit(2)
        for entry in entries:
            expected_digest = allowed.get(entry)
            if expected_digest in (None, "", "-"):
                raise SystemExit(2)
            descriptor = os.open(entry, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=evidence_fd)
            try:
                value = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(value.st_mode)
                    or value.st_uid != os.getuid()
                    or stat.S_IMODE(value.st_mode) != 0o600
                    or value.st_nlink != 1
                ):
                    raise SystemExit(2)
                current_digest = hashlib.sha256()
                while chunk := os.read(descriptor, 1024 * 1024):
                    current_digest.update(chunk)
            finally:
                os.close(descriptor)
            if current_digest.hexdigest() != expected_digest:
                raise SystemExit(2)
        for entry in entries:
            if entry != "manifest.json":
                os.unlink(entry, dir_fd=evidence_fd)
        os.fsync(evidence_fd)
    finally:
        os.close(evidence_fd)
finally:
    os.close(parent_fd)
PY
}

publish_complete_evidence() {
  "$PYTHON_BIN" - "$evidence_parent" "$evidence_name" "$evidence_parent_device" \
    "$evidence_parent_inode" "$evidence_device" "$evidence_inode" "$evidence_token" \
    "$manifest_sha256" "$complete_sha256" <<'PY'
import hashlib
import os
import stat
import sys

parent, name = sys.argv[1:3]
expected = tuple(int(value) for value in sys.argv[3:7])
token, manifest_digest, complete_digest = sys.argv[7:]
temporary_name = f".COMPLETE.{token}.tmp"
content = f"manifest_sha256={manifest_digest}\n".encode()
if hashlib.sha256(content).hexdigest() != complete_digest:
    raise SystemExit(2)
directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
parent_fd = os.open(parent, directory_flags)
try:
    parent_stat = os.fstat(parent_fd)
    if (parent_stat.st_dev, parent_stat.st_ino) != expected[:2]:
        raise SystemExit(2)
    evidence_fd = os.open(name, directory_flags, dir_fd=parent_fd)
    try:
        evidence_stat = os.fstat(evidence_fd)
        if (
            (evidence_stat.st_dev, evidence_stat.st_ino) != expected[2:]
            or not stat.S_ISDIR(evidence_stat.st_mode)
            or evidence_stat.st_uid != os.getuid()
            or stat.S_IMODE(evidence_stat.st_mode) != 0o700
            or sorted(os.listdir(evidence_fd)) != ["manifest.json"]
        ):
            raise SystemExit(2)
        manifest_fd = os.open("manifest.json", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=evidence_fd)
        try:
            manifest_stat = os.fstat(manifest_fd)
            if (
                not stat.S_ISREG(manifest_stat.st_mode)
                or manifest_stat.st_uid != os.getuid()
                or stat.S_IMODE(manifest_stat.st_mode) != 0o600
                or manifest_stat.st_nlink != 1
            ):
                raise SystemExit(2)
            manifest_hash = hashlib.sha256()
            while chunk := os.read(manifest_fd, 1024 * 1024):
                manifest_hash.update(chunk)
            os.fsync(manifest_fd)
        finally:
            os.close(manifest_fd)
        if manifest_hash.hexdigest() != manifest_digest:
            raise SystemExit(2)
        complete_fd = os.open(
            temporary_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=evidence_fd,
        )
        try:
            view = memoryview(content)
            while view:
                written = os.write(complete_fd, view)
                view = view[written:]
            os.fsync(complete_fd)
        finally:
            os.close(complete_fd)
        os.rename(
            temporary_name,
            "COMPLETE",
            src_dir_fd=evidence_fd,
            dst_dir_fd=evidence_fd,
        )
        os.fsync(evidence_fd)
        os.fsync(parent_fd)
    finally:
        os.close(evidence_fd)
finally:
    os.close(parent_fd)
PY
}

fsync_completed_evidence() {
  "$PYTHON_BIN" - "$evidence_parent" "$evidence_name" "$evidence_parent_device" \
    "$evidence_parent_inode" "$evidence_device" "$evidence_inode" "$manifest_sha256" \
    "$complete_sha256" <<'PY'
import hashlib
import os
import stat
import sys

parent, name = sys.argv[1:3]
expected = tuple(int(value) for value in sys.argv[3:7])
manifest_digest, complete_digest = sys.argv[7:]
directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
parent_fd = os.open(parent, directory_flags)
try:
    parent_stat = os.fstat(parent_fd)
    if (parent_stat.st_dev, parent_stat.st_ino) != expected[:2]:
        raise SystemExit(2)
    evidence_fd = os.open(name, directory_flags, dir_fd=parent_fd)
    try:
        evidence_stat = os.fstat(evidence_fd)
        if (
            (evidence_stat.st_dev, evidence_stat.st_ino) != expected[2:]
            or evidence_stat.st_uid != os.getuid()
            or stat.S_IMODE(evidence_stat.st_mode) != 0o700
            or sorted(os.listdir(evidence_fd)) != ["COMPLETE", "manifest.json"]
        ):
            raise SystemExit(2)
        for artifact, expected_digest in (
            ("manifest.json", manifest_digest),
            ("COMPLETE", complete_digest),
        ):
            descriptor = os.open(artifact, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=evidence_fd)
            try:
                value = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(value.st_mode)
                    or value.st_uid != os.getuid()
                    or stat.S_IMODE(value.st_mode) != 0o600
                    or value.st_nlink != 1
                ):
                    raise SystemExit(2)
                current_digest = hashlib.sha256()
                while chunk := os.read(descriptor, 1024 * 1024):
                    current_digest.update(chunk)
                if current_digest.hexdigest() != expected_digest:
                    raise SystemExit(2)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        os.fsync(evidence_fd)
        os.fsync(parent_fd)
    finally:
        os.close(evidence_fd)
finally:
    os.close(parent_fd)
PY
}

cleanup_owned_caller_tag() {
  local current_output current_status current_id
  current_output="$(docker_command image inspect --format "$inspect_format" "$image")"
  current_status=$?
  if (( current_status != 0 )); then
    printf 'error: cleanup refused: caller image tag ownership cannot be verified\n' >&2
    return 1
  fi
  current_id="${current_output%%|*}"
  if [[ "$current_id" != "$validated_image_id" ]]; then
    printf 'error: cleanup refused: caller image tag no longer resolves to the owned image ID\n' >&2
    return 1
  fi
  if ! docker_command image rm "$image" >/dev/null; then
    printf 'error: cleanup failed to remove the owned caller image tag\n' >&2
    return 1
  fi
  caller_tag_owned=0
}

cleanup_temporary_image_tag() {
  local temporary_images temporary_lookup_status
  set +e
  temporary_images="$(docker_command image ls --quiet --no-trunc "$temporary_image")"
  temporary_lookup_status=$?
  set -e
  if (( temporary_lookup_status != 0 )); then
    printf 'error: cleanup failed to inspect the exact temporary image tag\n' >&2
    return 1
  fi
  if [[ -z "$temporary_images" ]]; then
    temporary_image_cleanup_required=0
    return 0
  fi
  if ! docker_command image rm "$temporary_image" >/dev/null; then
    printf 'error: cleanup failed to remove the exact temporary image tag\n' >&2
    return 1
  fi
  temporary_image_cleanup_required=0
}

cleanup() {
  local original_status=$?
  local cleanup_failed=0
  trap - EXIT
  set +e
  if (( caller_tag_owned )); then
    cleanup_owned_caller_tag || cleanup_failed=1
  fi
  if (( temporary_image_cleanup_required )) && [[ -n "$temporary_image" ]]; then
    cleanup_temporary_image_tag || cleanup_failed=1
  fi
  if (( evidence_reserved && ! evidence_complete && ! preserve_recoverable_evidence )); then
    cleanup_evidence_reservation || cleanup_failed=1
  fi
  if [[ -n "$temporary_dir" ]]; then
    if ! cleanup_owned_tree; then
      printf 'error: cleanup refused to remove a changed temporary build directory\n' >&2
      cleanup_failed=1
    fi
  fi
  if (( image_lock_acquired )); then
    if ! release_image_lock; then
      printf 'error: cleanup refused to release a changed caller image lock\n' >&2
      cleanup_failed=1
    fi
  fi
  if (( original_status == 0 && cleanup_failed != 0 )); then
    original_status=1
  fi
  exit "$original_status"
}
trap cleanup EXIT

revision=""
image=""
evidence_dir=""
while (( $# > 0 )); do
  case "$1" in
    --revision)
      (( $# >= 2 )) || { usage; fail 'missing value for --revision'; }
      [[ -z "$revision" ]] || fail 'duplicate --revision'
      revision="$2"
      shift 2
      ;;
    --image)
      (( $# >= 2 )) || { usage; fail 'missing value for --image'; }
      [[ -z "$image" ]] || fail 'duplicate --image'
      image="$2"
      shift 2
      ;;
    --evidence-dir)
      (( $# >= 2 )) || { usage; fail 'missing value for --evidence-dir'; }
      [[ -z "$evidence_dir" ]] || fail 'duplicate --evidence-dir'
      evidence_dir="$2"
      shift 2
      ;;
    *)
      usage
      fail "unknown argument: $1"
      ;;
  esac
done

[[ -n "$revision" && -n "$image" && -n "$evidence_dir" ]] || { usage; fail 'all arguments are required and must be non-empty'; }
[[ "$revision" =~ ^[A-Za-z0-9][A-Za-z0-9._/@-]*$ ]] || fail 'revision is unsafe'
[[ "$image" =~ ^[a-z0-9][a-z0-9._/:@-]*$ && "$image" != *".."* && "$image" != *"//"* && "$image" != */ && "$image" != *: ]] || fail 'image reference is unsafe'

if [[ "$evidence_dir" != /* ]]; then
  evidence_dir="$REPOSITORY_ROOT/$evidence_dir"
fi
case "/$evidence_dir/" in
  *'/../'* | *'/./'*) fail 'evidence directory is unsafe' ;;
esac
evidence_parent_input="${evidence_dir%/*}"
evidence_name="${evidence_dir##*/}"
[[ -n "$evidence_parent_input" && -n "$evidence_name" && "$evidence_name" != '.' && "$evidence_name" != '..' ]] || fail 'evidence directory is unsafe'
[[ -d "$evidence_parent_input" && ! -L "$evidence_parent_input" ]] || fail 'evidence directory parent must be an existing non-symlink directory'
evidence_parent="$(cd -- "$evidence_parent_input" && pwd -P)"
evidence_dir="$evidence_parent/$evidence_name"

GIT_BIN="${GIT_BIN:-git}"
DOCKER_BIN="${DOCKER_BIN:-docker}"
DOCKER_USE_SUDO="${DOCKER_USE_SUDO:-0}"
TIMEOUT_BIN="${TIMEOUT_BIN:-timeout}"
DOCKER_TIMEOUT_SECONDS="${DOCKER_TIMEOUT_SECONDS:-600}"
if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -x "$REPOSITORY_ROOT/services/support-copilot-ai/.venv/bin/python" ]]; then
    PYTHON_BIN="$REPOSITORY_ROOT/services/support-copilot-ai/.venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi
case "$DOCKER_USE_SUDO" in
  0 | 1) ;;
  *) fail 'DOCKER_USE_SUDO must be 0 or 1' ;;
esac
[[ "$DOCKER_TIMEOUT_SECONDS" =~ ^[1-9][0-9]*$ && "$DOCKER_TIMEOUT_SECONDS" -le 900 ]] || fail 'DOCKER_TIMEOUT_SECONDS must be a positive integer no greater than 900'
require_command "$GIT_BIN"
require_command "$DOCKER_BIN"
require_command "$TIMEOUT_BIN"
require_command "$PYTHON_BIN"
require_command shasum
require_command mktemp
if [[ "$DOCKER_USE_SUDO" == "1" ]]; then
  require_command sudo
fi
IFS=':' read -r evidence_parent_device evidence_parent_inode _ _ evidence_parent_kind <<<"$(path_identity "$evidence_parent")"
[[ "$evidence_parent_kind" == "directory" ]] || fail 'evidence directory parent became unsafe'

resolved_revision="$("$GIT_BIN" -C "$REPOSITORY_ROOT" rev-parse --verify --quiet --end-of-options "${revision}^{commit}")" || fail 'revision does not resolve to a commit'
current_head="$("$GIT_BIN" -C "$REPOSITORY_ROOT" rev-parse --verify HEAD^{commit})"
[[ "$resolved_revision" != "$current_head" ]] || fail 'revision must not resolve to current HEAD (no-op build)'
if ! "$GIT_BIN" -C "$REPOSITORY_ROOT" merge-base --is-ancestor "$resolved_revision" "$current_head"; then
  fail 'revision is not an ancestor of current HEAD'
fi
[[ "$("$GIT_BIN" -C "$REPOSITORY_ROOT" cat-file -t "$resolved_revision:services/support-copilot-api")" == "tree" ]] || fail 'revision API source must be a tree'
[[ "$("$GIT_BIN" -C "$REPOSITORY_ROOT" cat-file -t "$resolved_revision:services/support-copilot-ai/app/data/knowledge.json")" == "blob" ]] || fail 'revision knowledge.json must be a blob'

readonly DOCKERFILE="$REPOSITORY_ROOT/services/support-copilot-api/Dockerfile"
[[ -f "$DOCKERFILE" && ! -L "$DOCKERFILE" ]] || fail 'current API Dockerfile must be a regular non-symlink file'

tmp_parent_input="${TMPDIR:-/tmp}"
[[ -d "$tmp_parent_input" ]] || fail 'temporary directory parent does not exist'
temporary_parent="$(cd -- "$tmp_parent_input" && pwd -P)"
IFS=':' read -r temporary_parent_device temporary_parent_inode _ _ parent_kind <<<"$(path_identity "$temporary_parent")"
[[ "$parent_kind" == "directory" ]] || fail 'temporary directory parent is unsafe'
image_lock_parent="$(cd -- "$LOCK_PARENT_INPUT" && pwd -P)"
IFS=':' read -r image_lock_parent_device image_lock_parent_inode _ _ lock_parent_kind <<<"$(path_identity "$image_lock_parent")"
[[ "$lock_parent_kind" == "directory" ]] || fail 'fixed caller image lock parent is unsafe'
image_lock_root_name="$LOCK_ROOT_PREFIX.$(id -u)"
umask 077
temporary_dir="$(mktemp -d "$temporary_parent/${TEMP_PREFIX}XXXXXXXX")" || fail 'cannot create build temporary directory'
temporary_name="${temporary_dir##*/}"
IFS=':' read -r temporary_device temporary_inode temporary_uid temporary_mode temporary_kind <<<"$(path_identity "$temporary_dir")"
[[ "$temporary_kind" == "directory" && "$temporary_name" == "$TEMP_PREFIX"* && "$temporary_uid" == "$(id -u)" && "$temporary_mode" == "700" ]] || fail 'mktemp returned an unsafe temporary directory'

archive_path="$temporary_dir/source.tar"
context_dir="$temporary_dir/context"
dockerfile_snapshot="$temporary_dir/current-api.Dockerfile"

snapshot_identity="$("$PYTHON_BIN" - "$DOCKERFILE" "$dockerfile_snapshot" <<'PY'
import hashlib
import os
import stat
import sys

source, destination = sys.argv[1:]
source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
try:
    source_stat = os.fstat(source_fd)
    if not stat.S_ISREG(source_stat.st_mode):
        raise SystemExit(2)
    destination_fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    digest = hashlib.sha256()
    try:
        while chunk := os.read(source_fd, 1024 * 1024):
            digest.update(chunk)
            view = memoryview(chunk)
            while view:
                written = os.write(destination_fd, view)
                view = view[written:]
        os.fsync(destination_fd)
    finally:
        os.close(destination_fd)
    print(f"{source_stat.st_dev}:{source_stat.st_ino}:{source_stat.st_size}:{source_stat.st_mtime_ns}:{digest.hexdigest()}")
finally:
    os.close(source_fd)
PY
)" || fail 'cannot snapshot current API Dockerfile'
IFS=':' read -r dockerfile_device dockerfile_inode dockerfile_size dockerfile_mtime packaging_dockerfile_sha256 <<<"$snapshot_identity"

"$GIT_BIN" -C "$REPOSITORY_ROOT" archive --format=tar "$resolved_revision" -- services/support-copilot-api services/support-copilot-ai/app/data/knowledge.json >"$archive_path"
source_archive_sha256="$(sha256_file "$archive_path")"
mkdir -m 0700 -- "$context_dir"
if ! "$PYTHON_BIN" - "$archive_path" "$context_dir" <<'PY'
import os
import shutil
import stat
import sys
import tarfile
from pathlib import Path, PurePosixPath

archive_path, destination_text = sys.argv[1:]
destination = Path(destination_text)
roots = (
    "services/support-copilot-api",
    "services/support-copilot-ai/app/data/knowledge.json",
)
seen = set()
with tarfile.open(archive_path, mode="r:") as archive:
    members = archive.getmembers()
    for member in members:
        raw_name = member.name.rstrip("/")
        raw_parts = raw_name.split("/")
        path = PurePosixPath(raw_name)
        allowed = any(raw_name == root or raw_name.startswith(root + "/") for root in roots)
        ancestor = member.isdir() and any(root.startswith(raw_name + "/") for root in roots)
        if (
            not raw_name
            or member.name.startswith("/")
            or any(part in {"", ".", ".."} for part in raw_parts)
            or str(path) != raw_name
            or not (allowed or ancestor)
            or not (member.isdir() or member.isfile())
            or raw_name in seen
        ):
            raise SystemExit(f"unsafe archive member: {member.name}")
        seen.add(raw_name)
    for member in members:
        relative = Path(member.name.rstrip("/"))
        target = destination / relative
        if member.isdir():
            target.mkdir(mode=0o700, parents=True, exist_ok=True)
            continue
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        for parent in (destination, *target.parents):
            if parent == destination.parent:
                break
            value = os.lstat(parent)
            if not stat.S_ISDIR(value.st_mode) or stat.S_ISLNK(value.st_mode):
                raise SystemExit(f"unsafe extracted directory: {parent}")
            if parent == destination:
                break
        source = archive.extractfile(member)
        if source is None:
            raise SystemExit(f"unsafe archive file: {member.name}")
        with source, target.open("xb") as output:
            shutil.copyfileobj(source, output)
        target.chmod(0o700 if member.mode & 0o111 else 0o600)

    for raw_name in seen:
        target = destination / raw_name
        relative_parts = Path(raw_name).parts
        current = destination
        for part in relative_parts[:-1]:
            current /= part
            value = os.lstat(current)
            if not stat.S_ISDIR(value.st_mode) or stat.S_ISLNK(value.st_mode):
                raise SystemExit(f"unsafe extracted directory: {current}")
        value = os.lstat(target)
        if stat.S_ISLNK(value.st_mode) or not (stat.S_ISDIR(value.st_mode) or stat.S_ISREG(value.st_mode)):
            raise SystemExit(f"unsafe extracted path: {target}")

api = destination / "services/support-copilot-api"
knowledge = destination / "services/support-copilot-ai/app/data/knowledge.json"
if not api.is_dir() or api.is_symlink() or not knowledge.is_file() or knowledge.is_symlink():
    raise SystemExit("unsafe extracted source shape")
PY
then
  fail 'unsafe archive rejected before extraction'
fi

current_snapshot_identity="$("$PYTHON_BIN" - "$DOCKERFILE" <<'PY'
import hashlib
import os
import stat
import sys

descriptor = os.open(sys.argv[1], os.O_RDONLY | os.O_NOFOLLOW)
try:
    value = os.fstat(descriptor)
    if not stat.S_ISREG(value.st_mode):
        raise SystemExit(2)
    digest = hashlib.sha256()
    while chunk := os.read(descriptor, 1024 * 1024):
        digest.update(chunk)
    print(f"{value.st_dev}:{value.st_ino}:{value.st_size}:{value.st_mtime_ns}:{digest.hexdigest()}")
finally:
    os.close(descriptor)
PY
)" || fail 'current API Dockerfile became unsafe'
[[ "$current_snapshot_identity" == "$snapshot_identity" ]] || fail 'current API Dockerfile changed after snapshot'

if ! "$PYTHON_BIN" - "$dockerfile_snapshot" "$context_dir/services/support-copilot-api/Dockerfile" "$packaging_dockerfile_sha256" <<'PY'
import hashlib
import os
import shutil
import stat
import sys
from pathlib import Path

source, destination_text, expected_digest = sys.argv[1:]
destination = Path(destination_text)
for parent in destination.parents:
    if parent.name == "context":
        break
    value = os.lstat(parent)
    if not stat.S_ISDIR(value.st_mode) or stat.S_ISLNK(value.st_mode):
        raise SystemExit(2)
if destination.exists() or destination.is_symlink():
    value = os.lstat(destination)
    if not stat.S_ISREG(value.st_mode) or stat.S_ISLNK(value.st_mode):
        raise SystemExit(2)
    destination.unlink()
with open(source, "rb") as input_stream, destination.open("xb") as output:
    shutil.copyfileobj(input_stream, output)
destination.chmod(0o600)
if hashlib.sha256(destination.read_bytes()).hexdigest() != expected_digest:
    raise SystemExit(2)
PY
then
  fail 'cannot install the controlled Dockerfile snapshot'
fi

temporary_token="${temporary_name#"$TEMP_PREFIX"}"
evidence_token="$temporary_token"
temporary_image="$TEMP_IMAGE_REPOSITORY:${resolved_revision:0:12}-$temporary_token"
inspect_format='{{.Id}}|{{.Os}}|{{.Architecture}}|{{index .Config.Labels "org.opencontainers.image.revision"}}|{{index .Config.Labels "io.support-copilot.packaging-dockerfile-sha256"}}'
image_lock_digest="$(printf '%s' "$image" | shasum -a 256 | awk '{print $1}')"
image_lock_name="image-$image_lock_digest.lock"
image_lock_owner="$temporary_token:$resolved_revision:$$"
# The fixed per-UID host lock serializes cooperating publishers across build TMPDIRs.
# Docker has no conditional tag API, so direct Docker writers remain outside this contract.
acquire_image_lock

set +e
existing_evidence="$(inspect_existing_evidence)"
existing_evidence_status=$?
set -e
(( existing_evidence_status == 0 )) || fail 'recovery refused: evidence directory is stale, unsafe, changed, or unrelated'
IFS=$'\t' read -r evidence_state recovered_evidence_device recovered_evidence_inode \
  recovered_evidence_uid recovered_evidence_mode recovered_token recovered_pending_sha256 \
  recovered_pending_temp_sha256 recovered_manifest_sha256 recovered_manifest_temp_sha256 \
  recovered_complete_sha256 recovered_complete_temp_sha256 recovered_image_id \
  recovered_temporary_image <<<"$existing_evidence"

if [[ "$evidence_state" != "absent" ]]; then
  [[ "$evidence_state" == "pending" || "$evidence_state" == "complete" ]] || fail 'recovery refused: evidence state is invalid'
  [[ "$recovered_image_id" =~ ^sha256:[a-f0-9]{64}$ ]] || fail 'recovery refused: evidence has no exact durable image ID binding'
  evidence_device="$recovered_evidence_device"
  evidence_inode="$recovered_evidence_inode"
  evidence_uid="$recovered_evidence_uid"
  evidence_mode="$recovered_evidence_mode"
  if [[ "$recovered_token" == "-" ]]; then
    evidence_token="$temporary_token"
  else
    evidence_token="$recovered_token"
  fi
  pending_sha256="$recovered_pending_sha256"
  pending_temp_sha256="$recovered_pending_temp_sha256"
  manifest_sha256="$recovered_manifest_sha256"
  manifest_temp_sha256="$recovered_manifest_temp_sha256"
  complete_sha256="$recovered_complete_sha256"
  complete_temp_sha256="$recovered_complete_temp_sha256"
  evidence_reserved=1
  preserve_recoverable_evidence=1

  set +e
  caller_images="$(docker_command image ls --quiet --no-trunc "$image")"
  caller_lookup_status=$?
  set -e
  (( caller_lookup_status == 0 )) || fail 'recovery refused: cannot inspect caller image tag'

  if [[ -z "$caller_images" ]]; then
    [[ "$evidence_state" == "pending" ]] || fail 'recovery refused: completed evidence has no caller image tag'
    if ! cleanup_recovery_temporary_tag "$recovered_temporary_image" "$recovered_image_id"; then
      fail 'recovery refused: pending temporary image tag changed or cannot be removed'
    fi
    if ! cleanup_evidence_reservation; then
      fail 'recovery refused: pending evidence changed before removal'
    fi
    evidence_reserved=0
    preserve_recoverable_evidence=0
    evidence_device=""
    evidence_inode=""
    evidence_uid=""
    evidence_mode=""
    evidence_token="$temporary_token"
    pending_sha256=""
    pending_temp_sha256=""
    manifest_sha256=""
    manifest_temp_sha256=""
    complete_sha256=""
    complete_temp_sha256=""
  else
    [[ "$recovered_image_id" != "-" ]] || fail 'recovery refused: caller image tag has no bound manifest image ID'
    set +e
    recovered_caller_inspection="$(docker_command image inspect --format "$inspect_format" "$image")"
    recovered_caller_status=$?
    set -e
    (( recovered_caller_status == 0 )) || fail 'recovery refused: caller image tag cannot be inspected'
    validate_image_inspection "$recovered_caller_inspection" "$recovered_image_id" || \
      fail 'recovery refused: caller image tag is changed or unrelated'
    validated_image_id="$checked_image_id"

    if [[ "$evidence_state" == "complete" ]]; then
      fsync_completed_evidence || fail 'recovery refused: completed evidence changed before durability verification'
      if ! cleanup_owned_tree; then
        fail 'validated temporary build directory changed before cleanup'
      fi
      temporary_dir=""
      evidence_complete=1
      if ! release_image_lock; then
        fail 'caller image cooperative lock changed before release'
      fi
      preserve_recoverable_evidence=0
      exit 0
    fi

    if ! cleanup_recovery_temporary_tag "$recovered_temporary_image" "$recovered_image_id"; then
      fail 'recovery refused: pending temporary image tag changed or cannot be removed'
    fi
    prepare_evidence_for_complete || fail 'recovery refused: pending evidence changed before reconciliation'
    evidence_token="$temporary_token"
    pending_sha256="-"
    pending_temp_sha256="-"
    manifest_temp_sha256="-"
    complete_temp_sha256="$complete_sha256"
    if ! cleanup_owned_tree; then
      fail 'validated temporary build directory changed before cleanup'
    fi
    temporary_dir=""
    publish_complete_evidence || fail 'cannot durably reconcile COMPLETE evidence'
    evidence_complete=1
    if ! release_image_lock; then
      fail 'caller image cooperative lock changed before release'
    fi
    preserve_recoverable_evidence=0
    exit 0
  fi
fi

set +e
caller_images="$(docker_command image ls --quiet --no-trunc "$image")"
caller_lookup_status=$?
set -e
(( caller_lookup_status == 0 )) || fail 'cannot inspect caller image tag availability'
[[ -z "$caller_images" ]] || fail 'caller image tag already exists'

set +e
temporary_images="$(docker_command image ls --quiet --no-trunc "$temporary_image")"
temporary_lookup_status=$?
set -e
(( temporary_lookup_status == 0 )) || fail 'cannot inspect temporary image tag availability'
[[ -z "$temporary_images" ]] || fail 'generated temporary image tag already exists'

pending_source="$temporary_dir/pending-evidence.json"
pending_sha256="$("$PYTHON_BIN" - "$pending_source" "$resolved_revision" "$image" \
  "$source_archive_sha256" "$packaging_dockerfile_sha256" "$PLATFORM" "$temporary_image" \
  "$evidence_token" <<'PY'
import hashlib
import json
import os
import sys

destination, revision, image_ref, archive_digest, packaging_digest, platform, temporary_ref, token = sys.argv[1:]
pending = {
    "schema_version": 1,
    "state": "pending",
    "revision": revision,
    "image_ref": image_ref,
    "source_archive_sha256": archive_digest,
    "packaging_dockerfile_sha256": packaging_digest,
    "platform": platform,
    "temporary_image_ref": temporary_ref,
    "token": token,
}
content = (json.dumps(pending, separators=(",", ":")) + "\n").encode()
descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
try:
    view = memoryview(content)
    while view:
        written = os.write(descriptor, view)
        view = view[written:]
    os.fsync(descriptor)
finally:
    os.close(descriptor)
print(hashlib.sha256(content).hexdigest())
PY
)" || fail 'cannot create pending evidence payload'
pending_temp_sha256="$pending_sha256"

evidence_reservation="$("$PYTHON_BIN" - "$evidence_parent" "$evidence_name" \
  "$evidence_parent_device" "$evidence_parent_inode" "$evidence_token" "$pending_source" \
  "$pending_sha256" <<'PY'
import hashlib
import os
import stat
import sys

parent, name, parent_device, parent_inode, token, source, expected_digest = sys.argv[1:]
expected_parent = (int(parent_device), int(parent_inode))
temporary_name = f".pending.{token}.tmp"
flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
parent_fd = os.open(parent, flags)
try:
    parent_stat = os.fstat(parent_fd)
    if (parent_stat.st_dev, parent_stat.st_ino) != expected_parent:
        raise SystemExit(2)
    os.mkdir(name, 0o700, dir_fd=parent_fd)
    evidence_fd = os.open(name, flags, dir_fd=parent_fd)
    try:
        evidence_stat = os.fstat(evidence_fd)
        if (
            not stat.S_ISDIR(evidence_stat.st_mode)
            or evidence_stat.st_uid != os.getuid()
            or stat.S_IMODE(evidence_stat.st_mode) != 0o700
        ):
            raise SystemExit(2)
        source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            source_stat = os.fstat(source_fd)
            content = bytearray()
            current_digest = hashlib.sha256()
            while chunk := os.read(source_fd, 1024 * 1024):
                current_digest.update(chunk)
                content.extend(chunk)
        finally:
            os.close(source_fd)
        if not stat.S_ISREG(source_stat.st_mode) or current_digest.hexdigest() != expected_digest:
            raise SystemExit(2)
        pending_fd = os.open(
            temporary_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=evidence_fd,
        )
        try:
            view = memoryview(content)
            while view:
                written = os.write(pending_fd, view)
                view = view[written:]
            os.fsync(pending_fd)
        finally:
            os.close(pending_fd)
        os.rename(temporary_name, ".pending.json", src_dir_fd=evidence_fd, dst_dir_fd=evidence_fd)
        os.fsync(evidence_fd)
        os.fsync(parent_fd)
        print(
            f"{parent_stat.st_dev}:{parent_stat.st_ino}:"
            f"{evidence_stat.st_dev}:{evidence_stat.st_ino}:"
            f"{evidence_stat.st_uid}:{stat.S_IMODE(evidence_stat.st_mode):o}"
        )
    finally:
        os.close(evidence_fd)
finally:
    os.close(parent_fd)
PY
)" || fail 'cannot reserve fresh evidence directory'
IFS=':' read -r evidence_parent_device evidence_parent_inode evidence_device evidence_inode \
  evidence_uid evidence_mode <<<"$evidence_reservation"
evidence_reserved=1

temporary_image_cleanup_required=1
set +e
docker_command build \
  --pull=false \
  --platform "$PLATFORM" \
  --file "$context_dir/services/support-copilot-api/Dockerfile" \
  --label "$OCI_REVISION_LABEL=$resolved_revision" \
  --label "$PACKAGING_LABEL=$packaging_dockerfile_sha256" \
  --tag "$temporary_image" \
  "$context_dir"
build_status=$?
set -e
if (( build_status != 0 )); then
  printf 'error: docker build failed with exit status %s\n' "$build_status" >&2
  exit "$build_status"
fi

inspect_format='{{.Id}}|{{.Os}}|{{.Architecture}}|{{index .Config.Labels "org.opencontainers.image.revision"}}|{{index .Config.Labels "io.support-copilot.packaging-dockerfile-sha256"}}'
set +e
inspect_output="$(docker_command image inspect --format "$inspect_format" "$temporary_image")"
inspect_status=$?
set -e
if (( inspect_status != 0 )); then
  printf 'error: docker image inspect failed with exit status %s\n' "$inspect_status" >&2
  exit "$inspect_status"
fi
[[ "$inspect_output" != *$'\n'* ]] || fail 'docker image inspect returned malformed output'
IFS='|' read -r image_id operating_system architecture inspected_revision inspected_packaging extra_field <<<"$inspect_output"
[[ -z "${extra_field:-}" && "$image_id" =~ ^sha256:[a-f0-9]{64}$ ]] || fail 'docker image inspect did not return a sha256 image ID'
[[ "$operating_system" == "linux" ]] || fail 'built image operating system is not linux'
[[ "$architecture" == "amd64" ]] || fail 'built image architecture is not amd64'
[[ "$inspected_revision" == "$resolved_revision" ]] || fail 'built image OCI revision label does not match resolved revision'
[[ "$inspected_packaging" == "$packaging_dockerfile_sha256" ]] || fail 'built image packaging hash label does not match current Dockerfile snapshot'
validated_image_id="$image_id"

manifest_source="$temporary_dir/manifest.pending"
payload_hashes="$("$PYTHON_BIN" - "$manifest_source" "$resolved_revision" "$image" "$image_id" \
  "$source_archive_sha256" "$packaging_dockerfile_sha256" "$PLATFORM" <<'PY'
import hashlib
import json
import os
import sys

destination, revision, image_ref, image_id, archive_digest, packaging_digest, platform = sys.argv[1:]
manifest = {
    "schema_version": 1,
    "revision": revision,
    "image_ref": image_ref,
    "image_id": image_id,
    "source_archive_sha256": archive_digest,
    "packaging_dockerfile_sha256": packaging_digest,
    "platform": platform,
    "command_exit": {"git_archive": 0, "docker_build": 0, "docker_inspect": 0},
    "hash_binding": {
        "oci_revision_label": revision,
        "packaging_label": packaging_digest,
        "source_archive_sha256": archive_digest,
    },
}
manifest_bytes = (json.dumps(manifest, separators=(",", ":")) + "\n").encode()
complete_bytes = f"manifest_sha256={hashlib.sha256(manifest_bytes).hexdigest()}\n".encode()
descriptor = os.open(
    destination,
    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
    0o600,
)
try:
    view = memoryview(manifest_bytes)
    while view:
        written = os.write(descriptor, view)
        view = view[written:]
    os.fsync(descriptor)
finally:
    os.close(descriptor)
print(f"{hashlib.sha256(manifest_bytes).hexdigest()}:{hashlib.sha256(complete_bytes).hexdigest()}")
PY
)" || fail 'cannot create manifest payload'
IFS=':' read -r manifest_sha256 complete_sha256 <<<"$payload_hashes"
manifest_temp_sha256="$manifest_sha256"
complete_temp_sha256="$complete_sha256"

if ! "$PYTHON_BIN" - "$evidence_parent" "$evidence_name" "$evidence_parent_device" \
  "$evidence_parent_inode" "$evidence_device" "$evidence_inode" "$evidence_token" \
  "$manifest_source" "$manifest_sha256" <<'PY'
import hashlib
import os
import stat
import sys

parent, name = sys.argv[1:3]
expected = tuple(int(value) for value in sys.argv[3:7])
token, source, expected_digest = sys.argv[7:]
temporary_name = f".manifest.{token}.tmp"
directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
parent_fd = os.open(parent, directory_flags)
try:
    parent_stat = os.fstat(parent_fd)
    if (parent_stat.st_dev, parent_stat.st_ino) != expected[:2]:
        raise SystemExit(2)
    evidence_fd = os.open(name, directory_flags, dir_fd=parent_fd)
    try:
        evidence_stat = os.fstat(evidence_fd)
        if (
            (evidence_stat.st_dev, evidence_stat.st_ino) != expected[2:]
            or not stat.S_ISDIR(evidence_stat.st_mode)
            or evidence_stat.st_uid != os.getuid()
            or stat.S_IMODE(evidence_stat.st_mode) != 0o700
            or sorted(os.listdir(evidence_fd)) != [".pending.json"]
        ):
            raise SystemExit(2)
        pending_fd = os.open(".pending.json", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=evidence_fd)
        try:
            pending_stat = os.fstat(pending_fd)
            pending_digest = hashlib.sha256()
            while chunk := os.read(pending_fd, 1024 * 1024):
                pending_digest.update(chunk)
        finally:
            os.close(pending_fd)
        pending_source = os.path.join(os.path.dirname(source), "pending-evidence.json")
        pending_source_fd = os.open(pending_source, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            expected_pending_digest = hashlib.sha256()
            while chunk := os.read(pending_source_fd, 1024 * 1024):
                expected_pending_digest.update(chunk)
        finally:
            os.close(pending_source_fd)
        if (
            not stat.S_ISREG(pending_stat.st_mode)
            or pending_stat.st_uid != os.getuid()
            or stat.S_IMODE(pending_stat.st_mode) != 0o600
            or pending_stat.st_nlink != 1
            or pending_digest.digest() != expected_pending_digest.digest()
        ):
            raise SystemExit(2)
        source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            source_stat = os.fstat(source_fd)
            if not stat.S_ISREG(source_stat.st_mode):
                raise SystemExit(2)
            content = bytearray()
            digest = hashlib.sha256()
            while chunk := os.read(source_fd, 1024 * 1024):
                digest.update(chunk)
                content.extend(chunk)
        finally:
            os.close(source_fd)
        if digest.hexdigest() != expected_digest:
            raise SystemExit(2)
        destination_fd = os.open(
            temporary_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=evidence_fd,
        )
        try:
            view = memoryview(content)
            while view:
                written = os.write(destination_fd, view)
                view = view[written:]
            os.fsync(destination_fd)
        finally:
            os.close(destination_fd)
        os.rename(
            temporary_name,
            "manifest.json",
            src_dir_fd=evidence_fd,
            dst_dir_fd=evidence_fd,
        )
        os.fsync(evidence_fd)
    finally:
        os.close(evidence_fd)
finally:
    os.close(parent_fd)
PY
then
  fail 'cannot durably stage manifest evidence'
fi

set +e
caller_images="$(docker_command image ls --quiet --no-trunc "$image")"
caller_lookup_status=$?
set -e
(( caller_lookup_status == 0 )) || fail 'cannot recheck caller image tag availability'
[[ -z "$caller_images" ]] || fail 'caller image tag appeared during validation'

docker_command image tag "$image_id" "$image"
caller_tag_owned=1
caller_inspect_output="$(docker_command image inspect --format "$inspect_format" "$image")"
[[ "$caller_inspect_output" == "$inspect_output" ]] || fail 'published caller image tag does not resolve to the validated image'

docker_command image rm "$temporary_image" >/dev/null
temporary_image_cleanup_required=0

if ! cleanup_owned_tree; then
  fail 'validated temporary build directory changed before cleanup'
fi
temporary_dir=""

prepare_evidence_for_complete || fail 'pending evidence changed before COMPLETE publication'
publish_complete_evidence || fail 'cannot durably publish COMPLETE evidence'
if ! release_image_lock; then
  fail 'caller image cooperative lock changed before release'
fi
evidence_complete=1
caller_tag_owned=0
