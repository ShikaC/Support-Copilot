import os


# API tests exercise the deterministic local workflow, regardless of developer .env values.
os.environ["AI_MODE"] = "mock"
os.environ["SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN"] = (
    "synthetic-test-internal-service-token"
)
