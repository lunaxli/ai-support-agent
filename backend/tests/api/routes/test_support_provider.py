import json

import httpx
import pytest
from openai import OpenAI

from app.api.routes.support import KB
from app.support.providers import DeepSeekProvider
from app.support.workflow import SupportWorkflow


@pytest.mark.parametrize("invalid", [False, True])
def test_deepseek_json_and_evidence_with_mock_http(invalid):
    calls = []

    def fake_api(request):
        assert request.url.path == "/chat/completions"
        body = json.loads(request.content)
        assert body["model"] == "deepseek-flash"
        assert body["response_format"] == {"type": "json_object"}
        assert body["thinking"] == {"type": "disabled"}
        payload = json.loads(body["messages"][1]["content"])
        calls.append(payload)
        if "passages" in payload:
            content = json.dumps(
                {
                    "reply": "请在登录页选择忘记密码。",
                    "source_ids": [payload["passages"][0]["passage_id"]],
                }
            )
        elif invalid:
            content = " "
        else:
            content = json.dumps(
                {
                    "category": "account",
                    "priority": "normal",
                    "summary": "密码重置",
                    "risk_flags": [],
                }
            )
        return httpx.Response(
            200,
            json={
                "id": "test-completion",
                "created": 0,
                "model": "deepseek-flash",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": content,
                        },
                    }
                ],
            },
        )

    transport = httpx.MockTransport(fake_api)
    with OpenAI(
        api_key="test",
        base_url="https://provider.invalid",
        max_retries=0,
        http_client=httpx.Client(transport=transport),
    ) as client:
        result = SupportWorkflow(DeepSeekProvider(client, "deepseek-flash"), KB).run(
            "重置登录密码",
            "忘记登录密码，如何重置？",
        )
    if invalid:
        assert len(calls) == 1
        assert result.route == "human_review" and result.reason == "model_error"
    else:
        assert len(calls) == 2
        assert result.route == "draft_ready"
        assert result.sources[0].passage_id == "account.md#1"
