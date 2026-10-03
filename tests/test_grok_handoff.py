"""Grok handoff to conversation.spacexai_grok (mocked converse; no live HA)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from custom_components.jev_assist.const import (
    CONF_GROK_HANDOFF_AGENT_ID,
    GROK_HANDOFF_AGENT_ID,
    GROK_HANDOFF_UNAVAILABLE_SPEECH,
    ROUTE_FAILURE_SPEECH,
)
from custom_components.jev_assist.grok_handoff import (
    async_converse_kwargs,
    async_handoff_to_conversation_agent,
    async_try_handoff_to_conversation_agent,
    filter_supported_kwargs,
    is_self_handoff,
    resolve_grok_handoff_agent_id,
)


def test_conversation_entity_wires_async_converse() -> None:
    source = Path("custom_components/jev_assist/conversation.py").read_text(encoding="utf-8")
    assert "async_try_handoff_to_conversation_agent" in source
    assert "conversation.async_converse" in source
    assert "except Exception" in source
    assert "GROK_HANDOFF_UNAVAILABLE_SPEECH" in source
    assert "ROUTE_FAILURE_SPEECH" in source
    assert "Grok path (" not in source


def test_route_failure_speech_constant() -> None:
    assert ROUTE_FAILURE_SPEECH == "I can't help with that."


def test_default_handoff_agent_id() -> None:
    assert GROK_HANDOFF_AGENT_ID == "conversation.spacexai_grok"
    assert resolve_grok_handoff_agent_id() == GROK_HANDOFF_AGENT_ID
    assert resolve_grok_handoff_agent_id(SimpleNamespace()) == GROK_HANDOFF_AGENT_ID


def test_handoff_agent_id_options_override_data() -> None:
    entry = SimpleNamespace(
        options={CONF_GROK_HANDOFF_AGENT_ID: " conversation.custom_grok "},
        data={CONF_GROK_HANDOFF_AGENT_ID: "conversation.from_data"},
    )
    assert resolve_grok_handoff_agent_id(entry) == "conversation.custom_grok"


def test_handoff_agent_id_data_when_options_empty() -> None:
    entry = SimpleNamespace(
        options={CONF_GROK_HANDOFF_AGENT_ID: "  "},
        data={CONF_GROK_HANDOFF_AGENT_ID: "conversation.from_data"},
    )
    assert resolve_grok_handoff_agent_id(entry) == "conversation.from_data"


def test_handoff_agent_id_data_only() -> None:
    entry = SimpleNamespace(data={CONF_GROK_HANDOFF_AGENT_ID: "conversation.from_data"})
    assert resolve_grok_handoff_agent_id(entry) == "conversation.from_data"


def test_unavailable_speech_constant() -> None:
    assert GROK_HANDOFF_UNAVAILABLE_SPEECH == "Grok is not available."


@dataclass
class FakeInput:
    text: str = "tell me a joke"
    conversation_id: str | None = "conv-1"
    context: object = "ctx"
    language: str = "en"
    agent_id: str = "conversation.jev_assist"
    device_id: str | None = "device-1"
    satellite_id: str | None = "sat-1"
    extra_system_prompt: str | None = "be brief"


def test_converse_kwargs_forward_pipeline_fields() -> None:
    kwargs = async_converse_kwargs(FakeInput(), GROK_HANDOFF_AGENT_ID)
    assert kwargs == {
        "text": "tell me a joke",
        "conversation_id": "conv-1",
        "context": "ctx",
        "language": "en",
        "agent_id": GROK_HANDOFF_AGENT_ID,
        "device_id": "device-1",
        "satellite_id": "sat-1",
        "extra_system_prompt": "be brief",
    }


def test_converse_kwargs_omit_missing_optional_attrs() -> None:
    class Minimal:
        text = "hi"
        conversation_id = None
        context = None
        language = "de"
        agent_id = "conversation.jev_assist"

    kwargs = async_converse_kwargs(Minimal(), GROK_HANDOFF_AGENT_ID)
    assert "device_id" not in kwargs
    assert "satellite_id" not in kwargs
    assert "extra_system_prompt" not in kwargs
    assert kwargs["agent_id"] == GROK_HANDOFF_AGENT_ID
    assert kwargs["language"] == "de"


async def _old_converse(
    hass: Any,
    text: str,
    conversation_id: str | None,
    context: Any,
    language: str | None = None,
    agent_id: str | None = None,
    device_id: str | None = None,
) -> str:
    return "ok"


def test_filter_drops_kwargs_unknown_to_older_converse() -> None:
    kwargs = async_converse_kwargs(FakeInput(), GROK_HANDOFF_AGENT_ID)
    filtered = filter_supported_kwargs(_old_converse, kwargs)
    assert "satellite_id" not in filtered
    assert "extra_system_prompt" not in filtered
    assert filtered["agent_id"] == GROK_HANDOFF_AGENT_ID
    assert filtered["device_id"] == "device-1"


def test_filter_keeps_all_when_var_keyword() -> None:
    async def modern(hass: Any, **kwargs: Any) -> Any:
        return kwargs

    kwargs = async_converse_kwargs(FakeInput(), GROK_HANDOFF_AGENT_ID)
    assert filter_supported_kwargs(modern, kwargs) == kwargs


def test_is_self_handoff() -> None:
    assert is_self_handoff(FakeInput(), "conversation.jev_assist") is True
    assert is_self_handoff(FakeInput(), GROK_HANDOFF_AGENT_ID) is False
    assert is_self_handoff(SimpleNamespace(), GROK_HANDOFF_AGENT_ID) is False


@pytest.mark.asyncio
async def test_handoff_calls_async_converse_with_agent_id() -> None:
    handed = object()
    converse = AsyncMock(return_value=handed)
    hass = object()
    result = await async_handoff_to_conversation_agent(
        hass,
        FakeInput(),
        agent_id=GROK_HANDOFF_AGENT_ID,
        converse=converse,
    )
    assert result is handed
    converse.assert_awaited_once()
    args, kwargs = converse.await_args
    assert args == (hass,)
    assert kwargs["agent_id"] == GROK_HANDOFF_AGENT_ID
    assert kwargs["text"] == "tell me a joke"
    assert kwargs["conversation_id"] == "conv-1"
    assert kwargs["context"] == "ctx"
    assert kwargs["language"] == "en"
    assert kwargs["device_id"] == "device-1"
    assert kwargs["satellite_id"] == "sat-1"
    assert kwargs["extra_system_prompt"] == "be brief"


@pytest.mark.asyncio
async def test_handoff_filters_to_older_converse_signature() -> None:
    captured: dict[str, Any] = {}

    async def old_converse(
        hass: Any,
        text: str,
        conversation_id: str | None,
        context: Any,
        language: str | None = None,
        agent_id: str | None = None,
        device_id: str | None = None,
    ) -> str:
        captured.update(
            {
                "hass": hass,
                "text": text,
                "conversation_id": conversation_id,
                "context": context,
                "language": language,
                "agent_id": agent_id,
                "device_id": device_id,
            }
        )
        return "ok"

    hass = object()
    result = await async_handoff_to_conversation_agent(
        hass,
        FakeInput(),
        agent_id=GROK_HANDOFF_AGENT_ID,
        converse=old_converse,
    )
    assert result == "ok"
    assert captured["hass"] is hass
    assert captured["agent_id"] == GROK_HANDOFF_AGENT_ID
    assert captured["device_id"] == "device-1"


@pytest.mark.asyncio
async def test_handoff_refuses_self_agent() -> None:
    converse = AsyncMock()
    with pytest.raises(ValueError, match="this agent"):
        await async_handoff_to_conversation_agent(
            object(),
            FakeInput(),
            agent_id="conversation.jev_assist",
            converse=converse,
        )
    converse.assert_not_called()


@pytest.mark.asyncio
async def test_handoff_propagates_missing_agent() -> None:
    converse = AsyncMock(side_effect=ValueError("Agent conversation.spacexai_grok not found"))
    with pytest.raises(ValueError, match="not found"):
        await async_handoff_to_conversation_agent(
            object(),
            FakeInput(),
            agent_id=GROK_HANDOFF_AGENT_ID,
            converse=converse,
        )


@pytest.mark.asyncio
async def test_try_handoff_runtime_error_returns_speech_not_raise(
    caplog: pytest.LogCaptureFixture,
) -> None:
    converse = AsyncMock(side_effect=RuntimeError("agent lookup exploded"))
    with caplog.at_level("INFO"):
        result, speech = await async_try_handoff_to_conversation_agent(
            object(),
            FakeInput(),
            agent_id=GROK_HANDOFF_AGENT_ID,
            converse=converse,
            route_kind="grok",
            route_reason="no_named_or_area_target",
        )
    assert result is None
    assert speech == GROK_HANDOFF_UNAVAILABLE_SPEECH
    assert "kind=grok" in caplog.text
    assert "reason=no_named_or_area_target" in caplog.text


@pytest.mark.asyncio
async def test_try_handoff_value_error_returns_speech_not_raise() -> None:
    converse = AsyncMock(side_effect=ValueError("Agent conversation.spacexai_grok not found"))
    result, speech = await async_try_handoff_to_conversation_agent(
        object(),
        FakeInput(),
        agent_id=GROK_HANDOFF_AGENT_ID,
        converse=converse,
        route_kind="grok",
        route_reason="needs_llm",
    )
    assert result is None
    assert speech == GROK_HANDOFF_UNAVAILABLE_SPEECH


@pytest.mark.asyncio
async def test_try_handoff_success_returns_converse_result() -> None:
    handed = object()
    converse = AsyncMock(return_value=handed)
    result, speech = await async_try_handoff_to_conversation_agent(
        object(),
        FakeInput(),
        agent_id=GROK_HANDOFF_AGENT_ID,
        converse=converse,
        route_kind="grok",
        route_reason="needs_llm",
    )
    assert result is handed
    assert speech is None
