import os


# API tests exercise the deterministic local workflow, regardless of developer .env values.
os.environ["AI_MODE"] = "mock"
