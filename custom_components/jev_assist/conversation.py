"""Conversation entity: local state answers, single HA actions or agent handoff."""

from __future__ import annotations

import asyncio
import logging
import math
from time import monotonic
from typing import Literal

from homeassistant.components import conversation
from homeassistant.components.light import brightness_supported
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
)
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers import (
    entity_registry as er,
)
from homeassistant.helpers import (
    intent,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import color as color_util
from typesafe_sdk import TypeSafeAuthenticationError, TypeSafePermissionDeniedError

from .const import DOMAIN, GROK_HANDOFF_UNAVAILABLE_SPEECH, ROUTE_FAILURE_SPEECH
from .exposure import should_expose_compat, sort_lights_first
from .grok_handoff import (
    async_try_handoff_to_conversation_agent,
    resolve_grok_handoff_agent_id,
)
from .home_query import describe_state
from .jev_router import ExposedEntity, RouteResult, route

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the conversation entity."""
    async_add_entities([JevAssistConversationEntity(hass, entry)])


class JevAssistConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
):
    """Assist agent with bounded local actions, queries and brief target context."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._target_memory: dict[tuple[str, str, str | None], tuple[float, tuple[str, ...]]] = {}
        self.route_counts: dict[str, int] = {}
        self._attr_unique_id = f"{entry.entry_id}-conversation"
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Jev Assist",
            model="jev-latest",
        )

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    async def async_will_remove_from_hass(self) -> None:
        self._target_memory.clear()
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        return await self._async_route_and_act(user_input, chat_log=chat_log)

    async def async_process(self, user_input: conversation.ConversationInput) -> conversation.ConversationResult:
        """Older HA path without ChatLog wrapping."""
        return await self._async_route_and_act(user_input, chat_log=None)

    async def _async_route_and_act(
        self,
        user_input: conversation.ConversationInput,
        *,
        chat_log: conversation.ChatLog | None,
    ) -> conversation.ConversationResult:
        try:
            return await self._async_route_and_act_inner(user_input, chat_log=chat_log)
        except TypeSafeAuthenticationError, TypeSafePermissionDeniedError:
            if key := _context_key(self.hass, user_input):
                self._target_memory.pop(key, None)
            self.entry.async_start_reauth(self.hass)
            speech = "Jev needs a new API key. Check its settings in Home Assistant."
            result = _speech_result(user_input, speech, error=intent.IntentResponseErrorCode.NO_INTENT_MATCH)
            _attach_assistant(chat_log, user_input, speech)
            return result
        except Exception as err:  # noqa: BLE001 — never raise into Assist
            if key := _context_key(self.hass, user_input):
                self._target_memory.pop(key, None)
            # Provider errors can echo an utterance/key. Log the type only.
            _LOGGER.error("Jev route-and-act failed (%s)", type(err).__name__)
            speech = ROUTE_FAILURE_SPEECH
            result = _speech_result(user_input, speech, error=intent.IntentResponseErrorCode.NO_INTENT_MATCH)
            _attach_assistant(chat_log, user_input, speech)
            return result

    async def _async_route_and_act_inner(
        self,
        user_input: conversation.ConversationInput,
        *,
        chat_log: conversation.ChatLog | None,
    ) -> conversation.ConversationResult:
        runtime = self.hass.data[DOMAIN][self.entry.entry_id]
        now = monotonic()
        self._target_memory = {key: value for key, value in self._target_memory.items() if value[0] > now}
        context_key = _context_key(self.hass, user_input)
        prior_targets = self._target_memory.get(context_key, (0, ()))[1] if context_key else ()
        room = _device_area(self.hass, getattr(user_input, "device_id", None))
        try:
            exposed = _exposed_entities(self.hass)
        except Exception:  # noqa: BLE001 — registry/expose must not crash Assist
            _LOGGER.error("Jev exposed-entity collection failed", exc_info=True)
            exposed = []
        routed: RouteResult = await route(
            user_input.text,
            exposed,
            language=user_input.language or self.hass.config.language,
            client=runtime.jev,
            room=room,
            followup_entity_ids=prior_targets,
        )
        self.route_counts[routed.kind] = self.route_counts.get(routed.kind, 0) + 1
        if hasattr(runtime, "route_counts"):
            runtime.route_counts = dict(self.route_counts)
        if routed.kind == "fast_service":
            _LOGGER.debug("Jev route kind=%s reason=%s", routed.kind, routed.reason)
        else:
            _LOGGER.info("Jev route kind=%s reason=%s", routed.kind, routed.reason)

        if routed.kind == "grok":
            if context_key:
                self._target_memory.pop(context_key, None)
            # Target agent owns ChatLog content on success; attach only on local fallback.
            try:
                handed, speech = await self._async_handoff_to_grok(
                    user_input,
                    route_kind=routed.kind,
                    route_reason=routed.reason,
                )
            except Exception as err:  # noqa: BLE001 — never raise into Assist
                _LOGGER.info(
                    "Grok handoff failed kind=%s reason=%s (%s)",
                    routed.kind,
                    routed.reason,
                    type(err).__name__,
                )
                handed, speech = None, GROK_HANDOFF_UNAVAILABLE_SPEECH
            if handed is not None:
                return handed
            speech = speech or GROK_HANDOFF_UNAVAILABLE_SPEECH
            result = _speech_result(
                user_input,
                speech,
                error=intent.IntentResponseErrorCode.FAILED_TO_HANDLE,
            )
            _attach_assistant(chat_log, user_input, speech)
            return result

        if routed.kind == "fast_service" and routed.domain and routed.service:
            result = await self._async_fast_service(user_input, routed)
            speech = result.response.speech.get("plain", {}).get("speech", "")
        elif routed.kind == "fast_query":
            result = self._async_fast_query(user_input, routed)
            speech = result.response.speech.get("plain", {}).get("speech", "")
        else:
            speech = ROUTE_FAILURE_SPEECH
            result = _speech_result(
                user_input,
                speech,
                error=intent.IntentResponseErrorCode.NO_VALID_TARGETS,
            )

        if context_key:
            targets = tuple(target.id for target in result.response.success_results if target.id)
            if (
                targets
                and result.response.error_code is None
                and not result.response.failed_results
                and routed.domain not in {"scene", "script"}
            ):
                if len(self._target_memory) >= 128:
                    self._target_memory.pop(next(iter(self._target_memory)))
                self._target_memory[context_key] = (monotonic() + 30, targets)
            else:
                self._target_memory.pop(context_key, None)

        _attach_assistant(chat_log, user_input, speech)
        return result

    def _async_fast_query(self, user_input, routed):
        """Answer from current exposed states with no service or agent call."""
        target_ids = routed.target_entity_ids
        if not target_ids or any(not _should_expose(self.hass, entity_id) for entity_id in target_ids):
            return _speech_result(
                user_input,
                "I couldn't resolve an exposed device for that question.",
                error=intent.IntentResponseErrorCode.NO_VALID_TARGETS,
            )
        success, failed, parts = [], [], []
        for entity_id in target_ids:
            state = self.hass.states.get(entity_id)
            name = str(state.name) if state else entity_id
            if state is None or state.state == STATE_UNAVAILABLE:
                parts.append(f"{name} is unavailable.")
                failed.append(entity_id)
            elif (
                state.state == STATE_UNKNOWN
                or (
                    description := describe_state(
                        state, routed.query_property, temperature_unit=str(self.hass.config.units.temperature_unit)
                    )
                )
                is None
            ):
                parts.append(f"I don't know the current {routed.query_property.replace('_', ' ')} of {name}.")
                failed.append(entity_id)
            else:
                parts.append(f"{name} {description}.")
                success.append(entity_id)
        result = _speech_result(user_input, " ".join(parts))
        result.response.response_type = intent.IntentResponseType.QUERY_ANSWER
        result.response.async_set_results(
            [_target(self.hass, entity_id) for entity_id in success],
            [_target(self.hass, entity_id) for entity_id in failed],
        )
        return result

    async def _async_fast_service(self, user_input, routed):
        """Recheck exposure, execute once, and confirm light state honestly."""
        data = dict(routed.service_data or {})
        target_ids = data.get("entity_id", [])
        if isinstance(target_ids, str):
            target_ids = [target_ids]
        if not target_ids or any(not _should_expose(self.hass, entity_id) for entity_id in target_ids):
            return _speech_result(
                user_input,
                "That device is not exposed to Assist.",
                error=intent.IntentResponseErrorCode.NO_VALID_TARGETS,
            )
        available = []
        unavailable = []
        unsupported = []
        expected = {}
        for entity_id in target_ids:
            state = self.hass.states.get(entity_id)
            if (
                state is None
                or state.state == STATE_UNAVAILABLE
                or state.state == STATE_UNKNOWN
                and routed.domain != "scene"
            ):
                unavailable.append(entity_id)
                continue
            if "rgb_color" in data and not set(state.attributes.get("supported_color_modes") or ()) & {
                "hs",
                "xy",
                "rgb",
                "rgbw",
                "rgbww",
            }:
                unsupported.append(entity_id)
                continue
            if "brightness_pct" in data and not brightness_supported(state.attributes.get("supported_color_modes")):
                unsupported.append(entity_id)
                continue
            available.append(entity_id)
            if routed.domain == "light":
                if routed.service == "toggle":
                    expected[entity_id] = "off" if state.state == "on" else "on"
                elif routed.service in ("turn_on", "turn_off"):
                    expected[entity_id] = (
                        "off" if routed.service == "turn_off" or data.get("brightness_pct") == 0 else "on"
                    )
        if not available:
            return _speech_result(
                user_input,
                (
                    "The device does not support brightness."
                    if "brightness_pct" in data
                    else "The device does not support color."
                )
                if unsupported and not unavailable
                else "The device is unavailable.",
                error=intent.IntentResponseErrorCode.NO_VALID_TARGETS,
            )
        data["entity_id"] = available
        try:
            await self.hass.services.async_call(
                routed.domain,
                routed.service,
                data,
                blocking=True,
                context=user_input.context,
            )
            async with asyncio.timeout(2):
                while any(
                    (state := self.hass.states.get(entity_id)) is None
                    or state.state != value
                    or (
                        "brightness_pct" in data
                        and value != "off"
                        and not _brightness_confirmed(state, data["brightness_pct"])
                    )
                    or ("rgb_color" in data and not _color_confirmed(state, data["rgb_color"]))
                    for entity_id, value in expected.items()
                ):
                    await asyncio.sleep(0.05)
        except Exception as err:
            _LOGGER.warning("Jev service outcome unconfirmed (%s)", type(err).__name__)
            return _speech_result(
                user_input,
                "I couldn't confirm the result.",
                error=intent.IntentResponseErrorCode.FAILED_TO_HANDLE,
            )
        result = _speech_result(
            user_input,
            f"Started {self.hass.states.get(available[0]).name}."
            if routed.domain in {"scene", "script"}
            else "Done, but some devices were unavailable or unsupported."
            if unavailable or unsupported
            else "OK",
        )
        result.response.async_set_results(
            [_target(self.hass, entity_id) for entity_id in available],
            [_target(self.hass, entity_id) for entity_id in unavailable + unsupported],
        )
        return result

    async def _async_handoff_to_grok(
        self,
        user_input: conversation.ConversationInput,
        *,
        route_kind: str,
        route_reason: str,
    ) -> tuple[conversation.ConversationResult | None, str | None]:
        agent_id = resolve_grok_handoff_agent_id(self.entry)
        return await async_try_handoff_to_conversation_agent(
            self.hass,
            user_input,
            agent_id=agent_id,
            converse=conversation.async_converse,
            route_kind=route_kind,
            route_reason=route_reason,
        )


def _speech_result(
    user_input: conversation.ConversationInput, speech: str, *, error=None
) -> conversation.ConversationResult:
    intent_response = intent.IntentResponse(language=user_input.language)
    if error is not None:
        intent_response.async_set_error(error, speech)
    else:
        intent_response.async_set_speech(speech)
    return conversation.ConversationResult(
        response=intent_response,
        conversation_id=user_input.conversation_id or getattr(user_input.context, "id", None),
    )


def _context_key(hass, user_input) -> tuple[str, str, str | None] | None:
    device_id = getattr(user_input, "device_id", None)
    conversation_id = user_input.conversation_id or getattr(user_input.context, "id", None)
    if not device_id or not conversation_id:
        return None
    if dr.async_get(hass).async_get(device_id) is None:
        return None
    return device_id, conversation_id, getattr(user_input.context, "user_id", None)


def _device_area(hass, device_id: str | None) -> str | None:
    if not device_id:
        return None
    device = dr.async_get(hass).async_get(device_id)
    area_id = _effective_device_area_id(hass, device) if device else None
    area = ar.async_get(hass).async_get_area(area_id) if area_id else None
    return str(area.name) if area else None


def _effective_device_area_id(hass, device):
    resolve = getattr(dr, "async_get_effective_area_id", None)
    return resolve(hass, device) if resolve else device.area_id


def _bounded_channel(value, maximum) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0 <= value <= maximum
        and math.isfinite(value)
    )


def _brightness_confirmed(state, percentage) -> bool:
    actual = state.attributes.get("brightness")
    return _bounded_channel(actual, 255) and abs(actual - round(255 * percentage / 100)) <= 2


def _color_confirmed(state, rgb) -> bool:
    actual = state.attributes.get("hs_color")
    if not isinstance(actual, (tuple, list)) or len(actual) != 2:
        actual_rgb = state.attributes.get("rgb_color")
        if (
            not isinstance(actual_rgb, (tuple, list))
            or len(actual_rgb) != 3
            or any(not _bounded_channel(value, 255) for value in actual_rgb)
        ):
            return False
        actual = color_util.color_RGB_to_hs(*actual_rgb)
    if not _bounded_channel(actual[0], 360) or not _bounded_channel(actual[1], 100):
        return False
    requested_hue, requested_saturation = color_util.color_RGB_to_hs(*rgb)
    hue_delta = abs((actual[0] - requested_hue + 180) % 360 - 180)
    return abs(actual[1] - requested_saturation) <= 3 and (requested_saturation < 1 or hue_delta <= 3)


def _target(hass, entity_id):
    state = hass.states.get(entity_id)
    return intent.IntentResponseTarget(
        name=str(state.name) if state else entity_id,
        type=intent.IntentResponseTargetType.ENTITY,
        id=entity_id,
    )


def _attach_assistant(
    chat_log: conversation.ChatLog | None,
    user_input: conversation.ConversationInput,
    speech: str,
) -> None:
    if chat_log is None or not speech:
        return
    try:
        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(
                agent_id=user_input.agent_id,
                content=speech,
            )
        )
    except Exception:  # noqa: BLE001 — older ChatLog shapes
        _LOGGER.debug("Chat log attach skipped", exc_info=True)


def _exposed_entities(hass: HomeAssistant) -> list[ExposedEntity]:
    """Collect Assist-exposed entities (lights first; cap applied in the client)."""
    ent_reg = er.async_get(hass)
    area_reg = ar.async_get(hass)
    should_expose = _should_expose
    items: list[ExposedEntity] = []
    for state in hass.states.async_all():
        entity_id = state.entity_id
        domain = entity_id.split(".", 1)[0]
        if not should_expose(hass, entity_id):
            continue
        entry = ent_reg.async_get(entity_id)
        area_name: str | None = None
        aliases: tuple[str, ...] = ()
        if entry is not None:
            aliases = tuple(str(alias) for alias in er.async_get_entity_aliases(hass, entry))
            area_id = entry.area_id
            if not area_id and entry.device_id:
                device = dr.async_get(hass).async_get(entry.device_id)
                area_id = _effective_device_area_id(hass, device) if device else None
            if area_id:
                area = area_reg.async_get_area(area_id)
                if area is not None and area.name is not None:
                    area_name = str(area.name)
        items.append(
            ExposedEntity(
                entity_id=str(entity_id),
                domain=str(domain),
                # HA 2025+ `state.name` may be ComputedNameType, not a plain str.
                name=str(state.name),
                area=area_name,
                aliases=aliases,
                device_class=getattr(state, "attributes", {}).get("device_class"),
            )
        )
    return sort_lights_first(items)


def _should_expose(hass: HomeAssistant, entity_id: str) -> bool:
    try:
        from homeassistant.components.homeassistant.exposed_entities import (
            async_should_expose,
        )
    except ImportError:
        return False

    return should_expose_compat(lambda: async_should_expose(hass, conversation.DOMAIN, entity_id))
