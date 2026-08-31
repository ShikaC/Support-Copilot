"""Static contracts for the local pilot Compose topology."""

from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = REPOSITORY_ROOT / "infra" / "compose.pilot.yml"
OIDC_CONFIG_PATH = REPOSITORY_ROOT / "infra" / "oidc" / "config.json"
EXPECTED_SERVICES = {"mysql", "oidc", "ai", "api", "web"}
EXPECTED_ISSUER = "http://oidc:8080/default"
EXPECTED_AUDIENCE = "support-copilot-api"
EXPECTED_PLATFORM = "linux/amd64"
OWNERSHIP_LABEL = "io.support-copilot.run-ownership"
OWNERSHIP_VALUE = "${SUPPORT_COPILOT_RUN_OWNERSHIP:?SUPPORT_COPILOT_RUN_OWNERSHIP is required}"


def load_compose():
    """Parse the tracked pilot Compose contract."""
    with COMPOSE_PATH.open(encoding="utf-8") as compose_file:
        document = yaml.safe_load(compose_file)
    assert isinstance(document, dict)
    return document


def service_environment(service):
    """Return the mapping-form environment contract for one service."""
    environment = service.get("environment")
    assert isinstance(environment, dict)
    assert all(isinstance(key, str) and isinstance(value, str) for key, value in environment.items())
    return environment


def test_topology_when_parsed_has_all_pilot_services_and_network_boundaries() -> None:
    # Given: the local-pilot Compose file.
    compose = load_compose()

    # When: its service topology is inspected.
    services = compose["services"]

    # Then: browser-facing and backend-only traffic are explicitly separated.
    assert set(services) == EXPECTED_SERVICES
    assert set(compose["networks"]) == {"frontend", "backend"}
    assert services["web"]["networks"] == ["frontend"]
    assert services["api"]["networks"] == ["frontend", "backend"]
    for service_name in ("mysql", "oidc", "ai"):
        assert services[service_name]["networks"] == ["backend"]
    assert "ports" in services["web"]
    for service_name in ("mysql", "oidc", "ai", "api"):
        assert "ports" not in services[service_name]


def test_images_when_pilot_parsed_are_exact_and_digest_pinned() -> None:
    # Given: the Compose service definitions.
    services = load_compose()["services"]

    # When: infrastructure images are read.
    mysql_image = services["mysql"].get("image")
    oidc_image = services["oidc"].get("image")

    # Then: the remote-resolved MySQL 8 LTS and NAV issuer references are immutable.
    assert mysql_image == "mysql:8.4.11-oraclelinux9@sha256:b3b90af2a6552ae30c266fdb7d5dd55f3afb72404bb78d37fe8a23eb857fd3fb"
    assert oidc_image == "ghcr.io/navikt/mock-oauth2-server:6.0.2@sha256:b538810afd589d42fbfb856c588c2065eaeed1dc528d6c532972048e67fc2aff"


def test_resources_when_pilot_parsed_pin_platform_and_run_ownership() -> None:
    # Given: every resource created by one verifier run.
    compose = load_compose()

    # When/Then: architecture is explicit and cleanup ownership is independently labeled.
    for service in compose["services"].values():
        assert service["platform"] == EXPECTED_PLATFORM
        assert service["labels"][OWNERSHIP_LABEL] == OWNERSHIP_VALUE
    for resource in (*compose["networks"].values(), *compose["volumes"].values()):
        assert resource["labels"][OWNERSHIP_LABEL] == OWNERSHIP_VALUE


def test_secrets_when_pilot_parsed_require_files_without_plaintext_defaults() -> None:
    # Given: the parsed Compose document.
    compose = load_compose()

    # When: top-level and service-scoped secrets are inspected.
    secrets = compose["secrets"]
    services = compose["services"]

    # Then: every secret comes from an explicit host directory and passwords are never values.
    assert {"mysql_app_password", "mysql_root_password", "internal_service_token", "openai_api_key"} <= set(secrets)
    for secret in secrets.values():
        assert secret["file"].startswith("${PILOT_SECRET_DIR:?")
    mysql_environment = service_environment(services["mysql"])
    assert mysql_environment["MYSQL_PASSWORD_FILE"] == "/run/secrets/mysql_app_password"
    assert mysql_environment["MYSQL_ROOT_PASSWORD_FILE"] == "/run/secrets/mysql_root_password"
    for service in services.values():
        environment = service.get("environment", {})
        assert isinstance(environment, dict)
        assert all(
            "PASSWORD" not in key or key.endswith("_FILE")
            for key in environment
            if isinstance(key, str)
        )


def test_secret_bootstrap_when_pilot_parsed_reads_as_root_then_drops_privileges() -> None:
    # Given: services whose existing application settings require direct environment values.
    services = load_compose()["services"]

    # When: their secret bootstrap commands are inspected.
    # Then: host files can stay owner-readable while the application execs as its image user.
    for service_name in ("ai", "api"):
        service = services[service_name]
        assert service["user"] == "0:0"
        assert service["cap_drop"] == ["ALL"]
        assert service["cap_add"] == ["DAC_OVERRIDE", "SETGID", "SETUID"]
        assert "setpriv --reuid=10001 --regid=10001 --clear-groups \"$$@\"" in service["entrypoint"][2]
        assert "--bounding-set" not in service["entrypoint"][2]


def test_ai_artifacts_when_pilot_parsed_use_the_owned_writable_mount() -> None:
    # Given: the AI image's non-root, read-only filesystem contract.
    ai = load_compose()["services"]["ai"]

    # When: the artifact environment and named volume are inspected.
    # Then: both use the exact owned writable location from the image review.
    assert ai["read_only"] is True
    assert ai["environment"]["EMBEDDING_ARTIFACT_ROOT"] == "/var/lib/support-copilot-ai"
    assert ai["volumes"] == [{
        "type": "volume",
        "source": "embedding-artifacts",
        "target": "/var/lib/support-copilot-ai",
    }]


def test_dependencies_when_pilot_parsed_wait_for_healthy_upstreams() -> None:
    # Given: the pilot service definitions.
    services = load_compose()["services"]

    # When: health and startup gates are inspected.
    # Then: every service has a healthcheck and downstreams wait for healthy dependencies.
    for service in services.values():
        assert "healthcheck" in service
        assert service["restart"] == "unless-stopped"
        assert service["security_opt"] == ["no-new-privileges:true"]
        assert service["deploy"]["resources"]["limits"]["pids"] > 0
    assert services["mysql"]["cap_drop"] == ["NET_RAW"]
    for service_name in ("oidc", "ai", "api", "web"):
        assert services[service_name]["cap_drop"] == ["ALL"]
        assert services[service_name]["read_only"] is True
    assert "depends_on" not in services["ai"]
    assert services["api"]["depends_on"] == {
        "mysql": {"condition": "service_healthy"},
        "oidc": {"condition": "service_healthy"},
        "ai": {"condition": "service_healthy"},
    }
    assert services["web"]["depends_on"] == {
        "api": {"condition": "service_healthy"}
    }


def test_oidc_when_pilot_parsed_issues_role_scoped_tokens_for_the_real_resource_contract() -> None:
    # Given: the local test-only issuer configuration.
    with OIDC_CONFIG_PATH.open(encoding="utf-8") as oidc_file:
        oidc_config = yaml.safe_load(oidc_file)

    # When: its client-credential token callbacks are inspected.
    callbacks = oidc_config["tokenCallbacks"]
    mappings = callbacks[0]["requestMappings"]
    claims_by_client = {
        mapping["match"]: mapping["claims"]
        for mapping in mappings
    }

    # Then: each issued token matches SecurityConfig's issuer, audience, subject and roles.
    assert callbacks[0]["issuerId"] == "default"
    assert claims_by_client["support-copilot-agent"] == {
        "sub": "pilot-agent",
        "aud": [EXPECTED_AUDIENCE],
        "roles": ["SUPPORT_AGENT"],
        "support_scopes": ["ACCOUNT"],
        "scope": "support:agent",
    }
    assert claims_by_client["support-copilot-reviewer"] == {
        "sub": "pilot-reviewer",
        "aud": [EXPECTED_AUDIENCE],
        "roles": ["SUPPORT_REVIEWER"],
        "scope": "support:review",
    }
    assert claims_by_client["support-copilot-admin"] == {
        "sub": "pilot-admin",
        "aud": [EXPECTED_AUDIENCE],
        "roles": ["SUPPORT_ADMIN"],
        "scope": "support:admin",
    }
    api_environment = service_environment(load_compose()["services"]["api"])
    assert api_environment["SUPPORT_COPILOT_JWT_ISSUER_URI"] == EXPECTED_ISSUER
    assert api_environment["SUPPORT_COPILOT_JWT_AUDIENCE"] == EXPECTED_AUDIENCE
    assert "SUPPORT_COPILOT_JWT_JWK_SET_URI" not in api_environment
