"""Classify/route/service failures must speak, never raise into Assist."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from custom_components.jev_assist import conversation as conversation_mod  # noqa: E402
from custom_components.jev_assist.const import (
    DOMAIN,
    GROK_HANDOFF_UNAVAILABLE_SPEECH,
    ROUTE_FAILURE_SPEECH,
)
from custom_components.jev_assist.conversation import (  # noqa: E402
    JevAssistConversationEntity,
    _exposed_entities,
)
from custom_components.jev_assist.jev_router import RouteResult


class RaisingJevClient:
    def __init__(self, error: BaseException) -> None:
        self.error = error
        self.classify_calls = 0

    async def classify(self, utterance: str, exposed: Any, *, language: str) -> Any:
        self.classify_calls += 1
        raise self.error


def _entity(*, jev: Any, async_call: Any | None = None) -> JevAssistConversationEntity:
    hass = SimpleNamespace(
        data={DOMAIN: {"entry-1": SimpleNamespace(jev=jev)}},
        config=SimpleNamespace(language="de"),
        services=SimpleNamespace(async_call=async_call or AsyncMock()),
    )
    entry = SimpleNamespace(entry_id="entry-1", title="Jev Assist")
    return JevAssistConversationEntity(hass, entry)


def _input(text: str = "Licht aus") -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        language="de",
        conversation_id="conv-licht",
        context="ctx",
        agent_id="conversation.jev_assist",
    )


def _speech(result: Any) -> str | None:
    return result.response.speech.get("plain", {}).get("speech")


@pytest.mark.asyncio
async def test_classify_runtime_error_returns_speech_not_raise(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = RaisingJevClient(RuntimeError("typesafe exploded"))
    entity = _entity(jev=client)
    monkeypatch.setattr(
        "custom_components.jev_assist.conversation._exposed_entities",
        lambda hass: [],
    )
    user_input = _input()

    with caplog.at_level("ERROR"):
        result = await entity._async_route_and_act(user_input, chat_log=None)

    assert client.classify_calls == 1
    assert _speech(result) == ROUTE_FAILURE_SPEECH
    assert result.conversation_id == "conv-licht"
    assert "Jev route-and-act failed" in caplog.text
    assert "typesafe exploded" not in caplog.text


@pytest.mark.asyncio
async def test_async_process_classify_runtime_error_does_not_propagate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entity = _entity(jev=RaisingJevClient(RuntimeError("typesafe exploded")))
    monkeypatch.setattr(
        "custom_components.jev_assist.conversation._exposed_entities",
        lambda hass: [],
    )
    result = await entity.async_process(_input())
    assert _speech(result) == ROUTE_FAILURE_SPEECH


@pytest.mark.asyncio
async def test_grok_handoff_failure_still_uses_unavailable_speech(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_route(*args: Any, **kwargs: Any) -> RouteResult:
        return RouteResult(kind="grok", reason="no_named_or_area_target")

    entity = _entity(jev=SimpleNamespace())
    monkeypatch.setattr("custom_components.jev_assist.conversation.route", fake_route)
    monkeypatch.setattr(
        "custom_components.jev_assist.conversation._exposed_entities",
        lambda hass: [],
    )
    monkeypatch.setattr(
        "custom_components.jev_assist.conversation.async_try_handoff_to_conversation_agent",
        AsyncMock(side_effect=RuntimeError("agent lookup exploded")),
    )

    result = await entity._async_route_and_act(_input(), chat_log=None)
    assert _speech(result) == GROK_HANDOFF_UNAVAILABLE_SPEECH
    assert _speech(result) != ROUTE_FAILURE_SPEECH


class ComputedNameType:
    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:
        return self.value


def test_exposed_entities_coerces_computed_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = SimpleNamespace(
        entity_id="light.kitchen",
        name=ComputedNameType("Kitchen lamp"),
    )
    entry = SimpleNamespace(
        aliases=(ComputedNameType("Küche"),),
        area_id="kitchen",
        device_id=None,
    )
    hass = SimpleNamespace(
        states=SimpleNamespace(async_all=lambda: [state]),
    )
    monkeypatch.setattr(
        conversation_mod.er,
        "async_get",
        lambda _hass: SimpleNamespace(async_get=lambda _eid: entry),
        raising=False,
    )
    monkeypatch.setattr(
        conversation_mod.ar,
        "async_get",
        lambda _hass: SimpleNamespace(async_get_area=lambda _aid: SimpleNamespace(name=ComputedNameType("Kitchen"))),
        raising=False,
    )
    monkeypatch.setattr(
        "custom_components.jev_assist.conversation._should_expose",
        lambda _hass, _eid: True,
    )

    items = _exposed_entities(hass)
    assert len(items) == 1
    assert items[0].name == "Kitchen lamp"
    assert isinstance(items[0].name, str)
    assert items[0].area == "Kitchen"
    assert isinstance(items[0].area, str)
    assert items[0].aliases == ("Küche",)
    assert all(isinstance(alias, str) for alias in items[0].aliases)
