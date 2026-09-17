# Infrastructure

This directory contains the bounded infrastructure fixtures used by the enterprise-pilot work.

`compose.pilot.yml` defines the local five-service pilot topology: MySQL 8.4.11,
the test-only OIDC issuer, Python AI, Java API, and the Nginx web gateway. The
MySQL and OIDC services use project-local derived images. OIDC copies only
`/app` from the pinned NAV 6.0.2 image into the pinned `linux/amd64` Chainguard
JRE manifest. This is a local verification fixture, not a production deployment
definition.

## Canonical operations verification

Run the integrated verifier from the repository root with a fresh evidence path
and a unique project name:

```bash
./scripts/verify-pilot-operations.sh \
  --project task15-pilot-local \
  --evidence-dir .omo/evidence/task-15-pilot-local
```

The evidence directory must not already exist. The command requires Docker with
Compose v2 plus `curl`, `openssl`, Python 3, GNU `sha256sum`, and GNU `timeout`.
It creates a temporary mode-`0700` secret directory, writes mode-`0600` secret
files, generates a random run-ownership label, and removes only resources that
still carry both the exact Compose project label and that run label. All services
are pinned to `linux/amd64`; legacy Docker inspection must also prove that
platform. Both build and prebuilt modes bind the OIDC project reference,
platform-resolved image ID, and running container image ID. Prebuilt OIDC tags
are verified and preserved during cleanup. Bearer headers enter `curl` through
standard input rather than process arguments. Secret values are not evidence.

The derived OIDC source preserves the upstream user `65532`, `/app` workdir,
port `8080`, Java entrypoint, `JSON_CONFIG_PATH`, issuer/token/JWKS behavior, and
`/isalive` health contract. Its final runtime is OpenJDK 26 while the copied
application bytecode targets Java 17. Static source checks do not prove runtime
compatibility or a vulnerability result; both remain explicit Docker runtime
and image-scan gates.

`verify-mysql-persistence.sh` is a compatibility entry point that delegates all
arguments to the same integrated verifier. The verifier exercises authenticated
agent/reviewer/admin behavior, API/MySQL/stack restarts, embedding-artifact
identity, backup into a fresh evidence subdirectory, restore into a fresh
Compose project/volume, and identity-bound cleanup of its resources and image
references. Cleanup fails closed if a tag or resource no longer proves ownership.

For a genuine compatible-previous-API rehearsal, first build and retain
hash-bound evidence, then supply all three rollback arguments together:

```bash
./scripts/build-compatible-api-image.sh \
  --revision <compatible-git-revision> \
  --image <immutable-caller-image-tag> \
  --evidence-dir <fresh-builder-evidence-dir>

./scripts/verify-pilot-operations.sh \
  --project <unique-project> \
  --evidence-dir <fresh-operations-evidence-dir> \
  --previous-api-image <immutable-caller-image-tag> \
  --previous-api-revision <compatible-git-revision> \
  --previous-api-build-evidence <fresh-builder-evidence-dir>
```

Current Task 15 status (2026-08-31): MySQL 8.4.11 parity and the 11-case
current-image runtime acceptance pass. The integrated Compose run also passes
test-only OIDC boundaries plus API/MySQL/full-stack restart persistence and a
post-restart write. It does not yet pass the complete cross-version and
fresh-volume restore chain: an unrelated no-cache build loop exhausted the
shared host disk twice, so the two-attempt stop rule applies. Do not retry until
the Docker-root filesystem has at least 8 GiB available for 60 seconds with no
concurrent image build. The strict image release scan separately remains blocked
by 56 HIGH/CRITICAL findings; neither blocker may be waived by this runbook.

The remote partial Compose evidence predates the final platform, ownership and
credential-transport hardening above. Those controls pass local fake-Docker
fault-injection tests, including wrong-platform and image-tag-rebind cases, but
the current Compose/verifier source has not been rerun remotely because the same
two-attempt disk blocker still applies. Do not present the older partial run as a
current-source end-to-end pass.

Exit cleanup removes containers, networks and volumes only when both their
Compose project label and the run's random ownership label match. A same-project
resource with a different ownership value is reported and preserved. Image tags
are not deleted or overwritten by exit cleanup because Docker has no atomic
compare-and-untag operation: generated image references are retained as build
cache with their observed image IDs in `cleanup-receipt.log`, while caller-owned
prebuilt tags are verified against their original IDs. Apply image retention or
garbage collection as a separate controlled maintenance action.

The deployment step is only a same-schema sequencing and rollback rehearsal. It
captures the current images as known-good, rebuilds the same worktree, and
reapplies the captured images without a schema downgrade. It is not a distinct
cross-version rollback, does not prove down migrations, and does not by itself
satisfy Task 15's previous-compatible-version rollback acceptance criterion.

## Direct Compose and backup helpers

Direct Compose or helper use requires an existing mode-`0700` secret directory,
a retained random 32-character lowercase hexadecimal run-ownership value, and
four nonempty files with mode `0600`:

```text
mysql_app_password
mysql_root_password
internal_service_token
openai_api_key
```

Start the topology only when those files already exist:

```bash
export SUPPORT_COPILOT_PILOT_PROJECT="task15-pilot-local"
export PILOT_SECRET_DIR=/absolute/path/to/pilot-secrets
export SUPPORT_COPILOT_RUN_OWNERSHIP="$(openssl rand -hex 16)"
export SUPPORT_COPILOT_WEB_PORT=13080
export SUPPORT_COPILOT_MYSQL_IMAGE="${SUPPORT_COPILOT_PILOT_PROJECT}-mysql:latest"
export SUPPORT_COPILOT_OIDC_IMAGE="${SUPPORT_COPILOT_PILOT_PROJECT}-oidc:latest"
docker compose --project-name "$SUPPORT_COPILOT_PILOT_PROJECT" \
  --file infra/compose.pilot.yml up --build --detach --wait
```

Keep the same `SUPPORT_COPILOT_RUN_OWNERSHIP` value for helper calls that parse
this Compose project. The controlled local build tags are derived from
`SUPPORT_COPILOT_PILOT_PROJECT`; a tag itself is not immutable. The canonical
verifier captures and validates the exact image IDs for these controlled local
tags. Prebuilt inputs instead use immutable digest references. The canonical
verifier generates and exports the project images and run ownership
automatically.

`pilot-backup.sh` requires the running source project, that same secret
directory, three observed sentinel IDs, and a fresh evidence directory:

```bash
./scripts/pilot-backup.sh \
  --compose-file infra/compose.pilot.yml \
  --project "$SUPPORT_COPILOT_PILOT_PROJECT" \
  --secret-dir /absolute/path/to/pilot-secrets \
  --evidence-dir .omo/evidence/task-15-backup \
  --database support_copilot \
  --sentinel-ticket-id <ticket-id> \
  --sentinel-analysis-id <analysis-id> \
  --sentinel-audit-id <audit-id>
```

`pilot-restore.sh` requires that backup directory and a new project/evidence
pair, plus `SUPPORT_COPILOT_OIDC_IMAGE` for the test-only issuer image. The
MySQL image reference is taken from and checked against the backup manifest.
On failure it removes only resources carrying both that restore project
and the same run-ownership label. Same-project resources with another ownership
value remain untouched and make the cleanup receipt incomplete; on success its
caller owns the restored resources.

```bash
./scripts/pilot-restore.sh \
  --backup-dir .omo/evidence/task-15-backup \
  --compose-file infra/compose.pilot.yml \
  --project task15-pilot-restore \
  --secret-dir /absolute/path/to/pilot-secrets \
  --evidence-dir .omo/evidence/task-15-restore \
  --database support_copilot
```

## Explicit Docker acceptance

The standalone production-image runtime tests are opt-in. The evidence path
must be fresh and the run ID must be unique:

```bash
SUPPORT_COPILOT_CONTAINER_ACCEPTANCE=1 \
SUPPORT_COPILOT_CONTAINER_RUN_ID=task15-local-001 \
SUPPORT_COPILOT_CONTAINER_EVIDENCE_DIR=.omo/evidence/task-15-container-local-001 \
PYTHONPATH="$PWD" services/support-copilot-ai/.venv/bin/pytest -q \
  tests/test_pilot_container_images_runtime.py
```

Build the application images before scanning, then pass every current image to
the scanner with a fresh output directory. Include the actual project-local
infrastructure references selected by `SUPPORT_COPILOT_MYSQL_IMAGE` and
`SUPPORT_COPILOT_OIDC_IMAGE`:

```bash
PILOT_SECRET_DIR=/absolute/path/to/pilot-secrets \
SUPPORT_COPILOT_RUN_OWNERSHIP="$(openssl rand -hex 16)" \
SUPPORT_COPILOT_MYSQL_IMAGE=task15-scan-mysql:latest \
SUPPORT_COPILOT_OIDC_IMAGE=task15-scan-oidc:latest \
docker compose --project-name task15-scan \
  --file infra/compose.pilot.yml build

./scripts/scan-pilot-images.sh .omo/evidence/task-15-image-scan \
  task15-scan-api:latest task15-scan-ai:latest task15-scan-web:latest \
  task15-scan-mysql:latest task15-scan-oidc:latest
```

These commands describe the required runtime gates. A skipped opt-in test,
static contract test, or local fake-command test is not Compose success.
