import json

import httpx
import pytest

from app.errors import InvalidModelResponseError
from tests.test_openai_provider_protocols import (
    DRAFT_PAYLOAD,
    _chat_payload,
    _evidence,
    _request,
    _settings,
    _wire_provider,
)


@pytest.mark.anyio
@pytest.mark.parametrize("category", ["ACCOUNT", "BILLING_REFUND", "隐私与数据请求"])
async def test_unknown_provider_category_is_rejected_before_risk_decision(category: str) -> None:
    payload = dict(DRAFT_PAYLOAD, category=category)
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_chat_payload(content=json.dumps(payload)))
    provider, client = _wire_provider(_settings("chat_completions"), respond)
    async with client:
        with pytest.raises(InvalidModelResponseError):
            await provider.analyze(_request(), _evidence())
