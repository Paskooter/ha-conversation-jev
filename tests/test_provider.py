"""The real SDK must send OpenRouter System One requests, never chat completions."""

import asyncio
import json

import httpx2
import pytest
from typesafe_sdk import (
    TypeSafeAuthenticationError,
    TypeSafeRateLimitError,
)

from custom_components.jev_assist.jev_client import TypeSafeJevClient
from tests.fakes import LIVING_LAMP


def system_one_reply(request):
    """A synthetic response in OpenRouter's documented System One shape."""
    body = json.loads(request.content)
    labels = {
        "category": "command",
        "domain": "light",
        "action": "turn_off",
        "scope": "named_area",
        "target_area": "Living room",
    }
    answers = {}
    for key, question in body["questions"].items():
        if question["type"] == "choice":
            label = labels[key]
            answers[key] = {
                "type": "choice",
                "choice": label,
                "confidence": 0.95,
                "probabilities": {label: 0.95},
            }
        else:
            answers[key] = {"type": "noul", "noul": 0.05}
    return httpx2.Response(
        200,
        json={
            "id": "synthetic-response",
            "model": "typesafe/jev-1.13",
            "provider": "TypeSafe",
            "answers": answers,
            "usage": {"input_tokens": 10, "output_tokens": 2, "cost": 0.00001},
        },
    )


def sdk_transport(monkeypatch, handler):
    """Replace only HTTP transport, retaining real SDK serialization and parsing."""

    monkeypatch.setattr(
        "custom_components.jev_assist.jev_client._new_http_client",
        lambda: httpx2.AsyncClient(transport=httpx2.MockTransport(handler), trust_env=False),
    )


@pytest.mark.parametrize(
    "provider,url",
    [
        ("openrouter", "https://openrouter.ai/api/v1/systemone"),
        ("typesafe", "https://api.typesafe.ai/v1/systemone"),
    ],
)
async def test_sdk_endpoint_auth_state_and_extra_response_fields(monkeypatch, provider, url):
    requests = []

    def handler(request):
        requests.append(request)
        return system_one_reply(request)

    monkeypatch.setenv("TYPESAFE_BASE_URL", "https://untrusted.invalid")
    monkeypatch.setenv("TYPESAFE_API_KEY", "different-synthetic-key")
    sdk_transport(monkeypatch, handler)
    client = TypeSafeJevClient("synthetic-provider-key", provider=provider)
    classified = await client.classify("turn off the living room lights", [LIVING_LAMP], language="en")
    assert classified.category.choice == "command"
    assert classified.needs_llm.noul == 0.05
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == url
    assert request.headers["Authorization"] == "Bearer synthetic-provider-key"
    body = json.loads(request.content)
    assert body["model"] == "jev-latest"
    assert isinstance(body["state"], dict)
    assert body["state"]["exposed_entities"][0]["entity_id"] == LIVING_LAMP.entity_id
    assert set(body["questions"]) == {
        "category",
        "domain",
        "action",
        "scope",
        "target_area",
        "needs_llm",
        "is_compound",
    }


async def test_validation_uses_only_synthetic_state(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return system_one_reply(request)

    sdk_transport(monkeypatch, handler)
    await TypeSafeJevClient("synthetic", provider="openrouter").async_validate()
    body = json.loads(requests[0].content)
    assert body["state"] == {"connection_test": "synthetic"}
    assert "exposed_entities" not in body["state"]


async def test_context_is_bounded_to_visible_targets_without_robot_identifiers(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return system_one_reply(request)

    sdk_transport(monkeypatch, handler)
    await TypeSafeJevClient("synthetic", provider="openrouter").classify_with_context(
        "turn it off",
        [LIVING_LAMP],
        language="en",
        room="Living room",
        followup_entity_ids=[LIVING_LAMP.entity_id, "light.hidden_synthetic"],
    )
    body = json.loads(requests[0].content)
    assert body["state"]["device_context"] == {"area": "Living room", "target_entity_ids": [LIVING_LAMP.entity_id]}
    assert len(requests) == 1
    assert "device_id" not in json.dumps(body)
    assert "conversation_id" not in json.dumps(body)
    assert "hidden_synthetic" not in json.dumps(body)


@pytest.mark.parametrize(
    "status,exception",
    [(401, TypeSafeAuthenticationError), (429, TypeSafeRateLimitError)],
)
async def test_provider_rejection_is_not_retried(monkeypatch, status, exception):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx2.Response(status, json={"error": {"message": "synthetic rejection"}})

    sdk_transport(monkeypatch, handler)
    with pytest.raises(exception):
        await TypeSafeJevClient("synthetic", provider="openrouter").async_validate()
    assert len(requests) == 1


async def test_classifier_deadline_cancels_and_closes_transport(monkeypatch):
    closed = []
    started = []

    class SlowTransport(httpx2.AsyncBaseTransport):
        async def handle_async_request(self, request):
            started.append(request)
            await asyncio.sleep(10)

        async def aclose(self):
            closed.append(True)

    monkeypatch.setattr("custom_components.jev_assist.jev_client.TYPESAFE_TIMEOUT", 0.03)
    monkeypatch.setattr(
        "custom_components.jev_assist.jev_client._new_http_client",
        lambda: httpx2.AsyncClient(transport=SlowTransport(), trust_env=False),
    )
    with pytest.raises(TimeoutError):
        await TypeSafeJevClient("synthetic", provider="openrouter").classify("lights off", [], language="en")
    assert len(started) == 1
    assert closed == [True]
