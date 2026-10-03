"""Handoff Grok routes to the SpaceXAI conversation agent via HA async_converse."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Mapping
from typing import Any

from .const import (
    CONF_GROK_HANDOFF_AGENT_ID,
    GROK_HANDOFF_AGENT_ID,
    GROK_HANDOFF_UNAVAILABLE_SPEECH,
)

_LOGGER = logging.getLogger(__name__)

_CONVERSE_PASSTHROUGH_ATTRS = (
    "device_id",
    "satellite_id",
    "extra_system_prompt",
)


def resolve_grok_handoff_agent_id(entry: Any | None = None) -> str:
    """Return the conversation ``agent_id`` to hand off to.

    Default is :data:`GROK_HANDOFF_AGENT_ID`. Config-entry ``options`` win over
    ``data`` when ``grok_handoff_agent_id`` is set to a non-empty string.
    """
    for source in (
        getattr(entry, "options", None) if entry is not None else None,
        getattr(entry, "data", None) if entry is not None else None,
    ):
        if not isinstance(source, Mapping):
            continue
        raw = source.get(CONF_GROK_HANDOFF_AGENT_ID)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return GROK_HANDOFF_AGENT_ID


def is_self_handoff(user_input: Any, agent_id: str) -> bool:
    """True when the handoff target is the agent that is already processing."""
    source = getattr(user_input, "agent_id", None)
    return bool(agent_id) and source == agent_id


def async_converse_kwargs(user_input: Any, agent_id: str) -> dict[str, Any]:
    """Build ``conversation.async_converse`` kwargs from a ConversationInput."""
    kwargs: dict[str, Any] = {
        "text": user_input.text,
        "conversation_id": user_input.conversation_id,
        "context": user_input.context,
        "language": getattr(user_input, "language", None),
        "agent_id": agent_id,
    }
    for attr in _CONVERSE_PASSTHROUGH_ATTRS:
        if hasattr(user_input, attr):
            kwargs[attr] = getattr(user_input, attr)
    return kwargs


def filter_supported_kwargs(func: Any, kwargs: Mapping[str, Any]) -> dict[str, Any]:
    """Drop kwargs that ``func`` does not accept (older HA converse signatures)."""
    try:
        params = inspect.signature(func).parameters
    except TypeError, ValueError:
        return dict(kwargs)
    if any(param.kind is inspect.Parameter.VAR_KEYWORD for param in params.values()):
        return dict(kwargs)
    allowed = {
        name
        for name, param in params.items()
        if param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    return {key: value for key, value in kwargs.items() if key in allowed}


async def async_handoff_to_conversation_agent(
    hass: Any,
    user_input: Any,
    *,
    agent_id: str,
    converse: Any,
) -> Any:
    """Invoke HA ``conversation.async_converse`` for ``agent_id``.

    Raises:
        ValueError: handoff target is this agent, or ``converse`` reports a
            missing agent (HA raises ``ValueError: Agent … not found``).
    """
    if is_self_handoff(user_input, agent_id):
        raise ValueError(f"Grok handoff target is this agent: {agent_id}")
    kwargs = filter_supported_kwargs(converse, async_converse_kwargs(user_input, agent_id))
    _LOGGER.debug("Handing off to conversation agent %s", agent_id)
    return await converse(hass, **kwargs)


async def async_try_handoff_to_conversation_agent(
    hass: Any,
    user_input: Any,
    *,
    agent_id: str,
    converse: Any,
    route_kind: str = "grok",
    route_reason: str = "",
) -> tuple[Any | None, str | None]:
    """Handoff to Grok. Never raises into the Assist pipeline.

    Returns ``(converse_result, None)`` on success, or
    ``(None, GROK_HANDOFF_UNAVAILABLE_SPEECH)`` on any failure (missing agent,
    lookup errors, ``RuntimeError``, and other non-``ValueError`` exceptions).
    """
    try:
        result = await async_handoff_to_conversation_agent(
            hass,
            user_input,
            agent_id=agent_id,
            converse=converse,
        )
    except Exception as err:  # noqa: BLE001 — Assist must get speech, not a crash
        _LOGGER.info(
            "Grok handoff failed kind=%s reason=%s (%s)",
            route_kind,
            route_reason,
            type(err).__name__,
        )
        return None, GROK_HANDOFF_UNAVAILABLE_SPEECH
    return result, None
