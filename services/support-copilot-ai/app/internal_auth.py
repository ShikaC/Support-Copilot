import secrets
from dataclasses import dataclass
from typing import Annotated, Final

from fastapi import Header
from pydantic import SecretStr

from app.models import AnalyzeRequest

INTERNAL_SERVICE_TOKEN_HEADER: Final = "X-Internal-Service-Token"


@dataclass(frozen=True, slots=True)
class InternalServiceAuthenticationError(Exception):
    trace_id: str

    def __str__(self) -> str:
        return "A valid internal service credential is required."


class InternalServiceAuthenticator:
    def __init__(self, expected_token: SecretStr) -> None:
        self._expected_token = expected_token

    def require(
        self,
        request: AnalyzeRequest,
        presented_token: Annotated[
            str | None,
            Header(alias=INTERNAL_SERVICE_TOKEN_HEADER),
        ] = None,
    ) -> None:
        expected = self._expected_token.get_secret_value()
        presented = presented_token or ""
        matches = secrets.compare_digest(
            presented.encode("utf-8"),
            expected.encode("utf-8"),
        )
        if not matches:
            raise InternalServiceAuthenticationError(trace_id=request.trace_id)
