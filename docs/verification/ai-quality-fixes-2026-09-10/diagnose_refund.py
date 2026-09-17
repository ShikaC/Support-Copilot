"""Bounded synthetic-only wire diagnosis, separate from baseline reports."""
import asyncio
import json
from pathlib import Path

import httpx

from app.config import Settings
from app.knowledge import KnowledgeRetriever
from app.models import AnalyzeRequest, BUNDLED_KNOWLEDGE_ACCESS, TicketInput
from app.workflow import AnalysisWorkflow


async def main() -> None:
    output = Path('../../docs/verification/ai-quality-fixes-2026-09-10/refund-wire-diagnostic.json')
    case = next(case for case in json.loads(Path('evaluation/data/live-quality-v2.json').read_text())['cases'] if case['id'] == 'quality-refund')
    observations = []
    for attempt in range(1, 4):
        settings = Settings(ai_mode='live')
        workflow = AnalysisWorkflow(settings, KnowledgeRetriever(settings))
        assert workflow._provider is not None
        observation = {'attempt': attempt}

        async def capture(response: httpx.Response) -> None:
            await response.aread()
            observation['http_status'] = response.status_code
            if response.status_code == 200:
                payload = response.json()
                message = payload.get('choices', [{}])[0].get('message', {})
                observation['synthetic_model_content'] = message.get('content')

        workflow._provider._client._client.event_hooks['response'].append(capture)
        request = AnalyzeRequest(trace_id=f'diagnostic-refund-{attempt}', knowledge_access=BUNDLED_KNOWLEDGE_ACCESS,
                                 ticket=TicketInput(id='diagnostic-refund', **case['ticket']))
        result = await workflow.run(request)
        observation['result_status'] = result.status
        observation['fallback_reason'] = result.fallback_reason
        observations.append(observation)
        await workflow._provider._client.close()
        output.write_text(json.dumps(observations, ensure_ascii=False, indent=2) + '\n')
        if result.fallback_reason == 'invalid_model_response':
            break
    print('Diagnostic attempts:',len(observations))


asyncio.run(main())
