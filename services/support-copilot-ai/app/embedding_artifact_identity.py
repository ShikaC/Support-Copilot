from hashlib import sha256
import json
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from app.data_redaction import redact_sensitive_text
from app.knowledge_source import KnowledgeChunk


JsonIdentity = list[dict[str, str | int | list[str]]] | dict[str, str | int]


def canonical_bytes(value: JsonIdentity) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def file_checksum(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def chunk_checksum(chunk: KnowledgeChunk) -> str:
    payload = chunk.model_dump(mode="json")
    payload["content"] = redact_sensitive_text(chunk.content)
    return sha256(canonical_bytes(payload)).hexdigest()


def provider_identity(base_url: str | None) -> str:
    if base_url is None:
        return "openai-default"
    parsed = urlsplit(base_url)
    hostname = parsed.hostname or "invalid-host"
    port = f":{parsed.port}" if parsed.port is not None else ""
    return urlunsplit(
        (
            parsed.scheme.lower(),
            f"{hostname.lower()}{port}",
            parsed.path.rstrip("/"),
            "",
            "",
        )
    )


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
