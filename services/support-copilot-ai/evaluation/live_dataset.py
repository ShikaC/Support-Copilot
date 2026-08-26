from hashlib import sha256
from pathlib import Path

from pydantic import ValidationError

from evaluation.live_models import LiveDataset


class LiveDatasetError(Exception):
    pass


def load_live_dataset(path: Path) -> LiveDataset:
    try:
        return LiveDataset.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise LiveDatasetError("invalid-live-evaluation-dataset") from exc


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()
